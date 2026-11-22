import random
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import requests

from collector.config import DISCOVERY_QUERY_LIMIT, MIN_SUBSCRIBERS
from collector.database import select, update, upsert
from collector.youtube_api import get_channels, search_videos

MAX_CONSECUTIVE_429 = 3


class YouTubeRateLimitError(RuntimeError):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def sanitize_error(error):
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status == 429 or isinstance(error, YouTubeRateLimitError):
        return "YouTube Data API 429 Too Many Requests; 6시간 후 재시도"
    if status:
        return f"YouTube Data API HTTP {status}; 요청 실패"
    text = str(error or "")
    text = re.sub(r"([?&](?:key|api_key|apikey)=)[^&\s]+", r"\1REDACTED", text, flags=re.I)
    text = re.sub(r"AIza[0-9A-Za-z_-]+", "REDACTED", text)
    if "googleapis.com/youtube" in text.lower():
        return "YouTube Data API 요청 실패; 6시간 후 재시도"
    return text[:500]


def due_queries():
    rows = select(
        "discovery_queries",
        "query_id,query_text,category,priority,last_run_at,next_run_at,run_count,channels_found,active_channels_found,consecutive_empty_runs,error_count,last_error",
        {"enabled": "eq.true", "next_run_at": f"lte.{utcnow().isoformat()}"},
        limit=max(1, DISCOVERY_QUERY_LIMIT),
        order="priority.desc,next_run_at.asc,last_run_at.asc.nullsfirst",
    )
    return rows[:DISCOVERY_QUERY_LIMIT]


def search_with_retry(query):
    waits = (5, 10, 20)
    for attempt in range(4):
        try:
            return search_videos(query, max_results=50)
        except requests.HTTPError as error:
            status = getattr(error.response, "status_code", None)
            if status != 429:
                raise
            if attempt == 3:
                raise YouTubeRateLimitError("YouTube 429 retry exhausted") from error
            wait = waits[attempt] + random.uniform(0.2, 1.0)
            print(f"YouTube 429 retry | query={query} | attempt={attempt + 1}/3 | wait={wait:.1f}s")
            time.sleep(wait)


def record_success(row, found, active):
    empty = 0 if found else int(row.get("consecutive_empty_runs") or 0) + 1
    delay = timedelta(days=1 if active else 3 if found else 7)
    if empty >= 5:
        delay = timedelta(days=30)
    now = utcnow()
    update(
        "discovery_queries",
        {
            "last_run_at": now.isoformat(),
            "next_run_at": (now + delay).isoformat(),
            "run_count": int(row.get("run_count") or 0) + 1,
            "channels_found": int(row.get("channels_found") or 0) + found,
            "active_channels_found": int(row.get("active_channels_found") or 0) + active,
            "consecutive_empty_runs": empty,
            "last_error": None,
            "updated_at": now.isoformat(),
        },
        {"query_id": f"eq.{row['query_id']}"},
    )


def record_error(row, error):
    now = utcnow()
    update(
        "discovery_queries",
        {
            "last_run_at": now.isoformat(),
            "next_run_at": (now + timedelta(hours=6)).isoformat(),
            "run_count": int(row.get("run_count") or 0) + 1,
            "error_count": int(row.get("error_count") or 0) + 1,
            "last_error": sanitize_error(error),
            "updated_at": now.isoformat(),
        },
        {"query_id": f"eq.{row['query_id']}"},
    )


def collect(rows):
    names = {}
    votes = defaultdict(Counter)
    per_query = {}
    errors = {}
    deferred = []
    consecutive_429 = 0

    for index, row in enumerate(rows, 1):
        query = row["query_text"]
        category = row.get("category") or "기타"
        try:
            if index > 1:
                time.sleep(1.2 + random.uniform(0.1, 0.6))
            items = search_with_retry(query)
            consecutive_429 = 0
            found = set()
            for item in items:
                snippet = item.get("snippet", {})
                channel_id = str(snippet.get("channelId", "")).strip()
                if not channel_id:
                    continue
                found.add(channel_id)
                names[channel_id] = str(snippet.get("channelTitle") or channel_id).strip()
                votes[channel_id][category] += 1
            per_query[row["query_id"]] = found
            print(f"[{index}/{len(rows)}] {category} | {query} | channels={len(found)}")
        except YouTubeRateLimitError as error:
            per_query[row["query_id"]] = set()
            errors[row["query_id"]] = error
            consecutive_429 += 1
            print(f"[{index}/{len(rows)}] {category} | {query} | ERROR: {sanitize_error(error)}")
            if consecutive_429 >= MAX_CONSECUTIVE_429:
                deferred = [item["query_id"] for item in rows[index:]]
                print(f"YouTube search stopped early | remaining_queries={len(deferred)} | retry_after=6h")
                break
        except Exception as error:
            per_query[row["query_id"]] = set()
            errors[row["query_id"]] = error
            consecutive_429 = 0
            print(f"[{index}/{len(rows)}] {category} | {query} | ERROR: {sanitize_error(error)}")
    return names, votes, per_query, errors, deferred


def channel_records(items, names, votes):
    records = []
    statuses = {}
    for item in items:
        channel_id = str(item.get("id", "")).strip()
        if not channel_id:
            continue
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        details = item.get("contentDetails", {})
        hidden = bool(stats.get("hiddenSubscriberCount", False))
        subscribers = int(stats.get("subscriberCount", 0) or 0)
        status = "hidden_subscribers" if hidden else "active" if subscribers >= MIN_SUBSCRIBERS else "below_threshold"
        if subscribers >= 1_000_000:
            priority = 5
        elif subscribers >= 300_000:
            priority = 4
        elif subscribers >= 100_000:
            priority = 3
        else:
            priority = 1
        channel_votes = votes.get(channel_id, Counter())
        category = channel_votes.most_common(1)[0][0] if channel_votes else "기타"
        records.append({
            "channel_id": channel_id,
            "channel_name": str(snippet.get("title") or names.get(channel_id) or channel_id).strip(),
            "subscriber_count": subscribers,
            "subscriber_hidden": hidden,
            "country": snippet.get("country"),
            "description": str(snippet.get("description", ""))[:5000],
            "primary_category": category,
            "category_scores": dict(channel_votes),
            "uploads_playlist_id": details.get("relatedPlaylists", {}).get("uploads"),
            "status": status,
            "scan_priority": priority,
            "last_scanned_at": utcnow().isoformat(),
        })
        statuses[channel_id] = status
    return records, statuses


def main():
    rows = due_queries()
    if not rows:
        print("No discovery queries are due.")
        return
    print(f"Due discovery queries selected: {len(rows)}")
    names, votes, per_query, errors, deferred = collect(rows)
    items = get_channels(list(names)) if names else []
    records, statuses = channel_records(items, names, votes)
    if records:
        upsert("channels", records, "channel_id")

    for row in rows:
        query_id = row["query_id"]
        if query_id in deferred:
            record_error(row, YouTubeRateLimitError("연속 429로 조기 중단"))
        elif query_id in errors:
            record_error(row, errors[query_id])
        else:
            found = per_query.get(query_id, set())
            active = sum(1 for channel_id in found if statuses.get(channel_id) == "active")
            record_success(row, len(found), active)

    active_total = sum(1 for record in records if record["status"] == "active")
    print(
        "Secure channel discovery completed | "
        f"queries={len(rows)} | unique_channels={len(records)} | "
        f"active_channels={active_total} | query_errors={len(errors)} | deferred_queries={len(deferred)}"
    )


if __name__ == "__main__":
    main()

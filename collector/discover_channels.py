from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import random
import time

import requests

from collector.config import DISCOVERY_QUERY_LIMIT, MIN_SUBSCRIBERS
from collector.database import select, update, upsert
from collector.youtube_api import get_channels, search_videos

KST = timezone(timedelta(hours=9))


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def select_due_queries(limit):
    rows = select(
        "discovery_queries",
        (
            "query_id,query_text,category,priority,last_run_at,next_run_at,"
            "run_count,channels_found,active_channels_found,"
            "consecutive_empty_runs,error_count,last_error"
        ),
        {
            "enabled": "eq.true",
            "next_run_at": f"lte.{now_iso()}",
        },
        limit=max(1, limit),
        order="priority.desc,next_run_at.asc,last_run_at.asc.nullsfirst",
    )

    # 최초 실행 직후에는 모든 행의 next_run_at가 비슷하다.
    # REST order 호환성 차이를 피하기 위해 코드에서도 한 번 정렬한다.
    rows.sort(
        key=lambda row: (
            -int(row.get("priority", 1) or 1),
            row.get("next_run_at") or "",
            row.get("last_run_at") or "",
        )
    )
    return rows[:limit]


def record_query_success(query_row, found_count, active_count):
    empty_runs = 0 if found_count > 0 else int(query_row.get("consecutive_empty_runs", 0) or 0) + 1

    if active_count > 0:
        delay = timedelta(days=1)
    elif found_count > 0:
        delay = timedelta(days=3)
    else:
        delay = timedelta(days=7)

    # 연속 빈 결과 5회 이상은 삭제하지 않고 30일 뒤로 미룬다.
    if empty_runs >= 5:
        delay = timedelta(days=30)

    current = datetime.now(timezone.utc)
    update(
        "discovery_queries",
        {
            "last_run_at": current.isoformat(),
            "next_run_at": (current + delay).isoformat(),
            "run_count": int(query_row.get("run_count", 0) or 0) + 1,
            "channels_found": int(query_row.get("channels_found", 0) or 0) + found_count,
            "active_channels_found": int(query_row.get("active_channels_found", 0) or 0) + active_count,
            "consecutive_empty_runs": empty_runs,
            "last_error": None,
            "updated_at": current.isoformat(),
        },
        {"query_id": f"eq.{query_row['query_id']}"},
    )


def record_query_error(query_row, error):
    current = datetime.now(timezone.utc)
    update(
        "discovery_queries",
        {
            "last_run_at": current.isoformat(),
            "next_run_at": (current + timedelta(hours=6)).isoformat(),
            "run_count": int(query_row.get("run_count", 0) or 0) + 1,
            "error_count": int(query_row.get("error_count", 0) or 0) + 1,
            "last_error": str(error)[:1000],
            "updated_at": current.isoformat(),
        },
        {"query_id": f"eq.{query_row['query_id']}"},
    )


def search_videos_with_retry(query_text, max_results=25):
    """YouTube 검색의 순간적인 429를 지수 백오프로 재시도한다."""
    waits = (5, 10, 20)
    last_error = None

    for attempt in range(len(waits) + 1):
        try:
            return search_videos(query_text, max_results=max_results)
        except requests.HTTPError as error:
            last_error = error
            status = getattr(error.response, "status_code", None)
            if status != 429 or attempt >= len(waits):
                raise
            wait_seconds = waits[attempt] + random.uniform(0.2, 1.2)
            print(
                f"YouTube 429 retry | query={query_text} | "
                f"attempt={attempt + 1}/{len(waits)} | wait={wait_seconds:.1f}s"
            )
            time.sleep(wait_seconds)
        except Exception as error:
            last_error = error
            raise

    raise last_error


def collect_candidates(query_rows):
    channel_names = {}
    category_votes = defaultdict(Counter)
    query_channel_ids = {}
    errors = {}

    for index, row in enumerate(query_rows, start=1):
        query_text = row["query_text"]
        category = row.get("category") or "기타"
        try:
            # 검색 요청 사이의 간격으로 순간적인 QPS 제한을 줄인다.
            if index > 1:
                time.sleep(1.2 + random.uniform(0.1, 0.6))
            items = search_videos_with_retry(query_text, max_results=25)
            found = set()
            for item in items:
                snippet = item.get("snippet", {})
                channel_id = str(snippet.get("channelId", "")).strip()
                channel_name = str(snippet.get("channelTitle", "")).strip()
                if not channel_id:
                    continue
                found.add(channel_id)
                if channel_name:
                    channel_names[channel_id] = channel_name
                category_votes[channel_id][category] += 1

            query_channel_ids[row["query_id"]] = found
            print(
                f"[{index}/{len(query_rows)}] {category} | {query_text} | "
                f"channels={len(found)}"
            )
        except Exception as error:
            query_channel_ids[row["query_id"]] = set()
            errors[row["query_id"]] = error
            print(
                f"[{index}/{len(query_rows)}] {category} | {query_text} | ERROR: {error}"
            )

    return channel_names, category_votes, query_channel_ids, errors


def build_channel_records(channel_items, channel_names, category_votes):
    records = []
    status_by_channel = {}
    scanned_at = now_iso()

    for item in channel_items:
        channel_id = str(item.get("id", "")).strip()
        if not channel_id:
            continue

        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        content_details = item.get("contentDetails", {})
        hidden = bool(statistics.get("hiddenSubscriberCount", False))

        try:
            subscribers = int(statistics.get("subscriberCount", 0) or 0)
        except (TypeError, ValueError):
            subscribers = 0

        if hidden:
            status = "hidden_subscribers"
        elif subscribers >= MIN_SUBSCRIBERS:
            status = "active"
        else:
            status = "below_threshold"

        votes = category_votes.get(channel_id, Counter())
        primary_category = votes.most_common(1)[0][0] if votes else "기타"
        uploads = content_details.get("relatedPlaylists", {}).get("uploads")

        records.append(
            {
                "channel_id": channel_id,
                "channel_name": str(
                    snippet.get("title") or channel_names.get(channel_id) or channel_id
                ).strip(),
                "subscriber_count": subscribers,
                "subscriber_hidden": hidden,
                "country": snippet.get("country"),
                "description": str(snippet.get("description", "") or "")[:5000],
                "primary_category": primary_category,
                "category_scores": dict(votes),
                "uploads_playlist_id": uploads,
                "status": status,
                "last_scanned_at": scanned_at,
            }
        )
        status_by_channel[channel_id] = status

    return records, status_by_channel


def main():
    query_rows = select_due_queries(DISCOVERY_QUERY_LIMIT)
    if not query_rows:
        print("No discovery queries are due. Nothing to run.")
        return

    print(f"Due discovery queries selected: {len(query_rows)}")
    for row in query_rows:
        print(f"- priority={row.get('priority', 1)} [{row.get('category')}] {row['query_text']}")

    channel_names, category_votes, query_channel_ids, errors = collect_candidates(query_rows)
    channel_ids = list(channel_names.keys())
    channel_items = get_channels(channel_ids) if channel_ids else []
    records, status_by_channel = build_channel_records(
        channel_items, channel_names, category_votes
    )

    if records:
        upsert("channels", records, "channel_id")

    for row in query_rows:
        query_id = row["query_id"]
        if query_id in errors:
            record_query_error(row, errors[query_id])
            continue

        found_ids = query_channel_ids.get(query_id, set())
        active_count = sum(
            1 for channel_id in found_ids if status_by_channel.get(channel_id) == "active"
        )
        record_query_success(row, len(found_ids), active_count)

    active_total = sum(1 for record in records if record["status"] == "active")
    print(
        "DB-scheduled channel discovery completed | "
        f"queries={len(query_rows)} | unique_channels={len(records)} | "
        f"active_1m_plus={active_total} | query_errors={len(errors)}"
    )


if __name__ == "__main__":
    main()

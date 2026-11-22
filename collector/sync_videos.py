from datetime import datetime, timedelta, timezone

from collector.config import VIDEOS_PER_CHANNEL
from collector.database import select, update, upsert
from collector.youtube_api import get_playlist_videos, get_videos

MAX_CHANNELS_PER_RUN = 150


def now_utc():
    return datetime.now(timezone.utc)


def chunks(values, size=100):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def get_due_channels():
    """다음 확인 시간이 지났거나 미스캔된 활성 채널을 우선순위 순으로 선택한다."""
    rows = select(
        "channels",
        (
            "channel_id,channel_name,uploads_playlist_id,scan_priority,"
            "next_video_scan_at,last_video_published_at,total_scanned_videos,"
            "product_candidate_videos,extracted_product_count"
        ),
        {
            "status": "eq.active",
            "uploads_playlist_id": "not.is.null",
            "or": f"(next_video_scan_at.is.null,next_video_scan_at.lte.{now_utc().isoformat()})",
        },
        limit=MAX_CHANNELS_PER_RUN,
        order="scan_priority.desc,next_video_scan_at.asc.nullsfirst",
    )
    return rows[:MAX_CHANNELS_PER_RUN]


def get_existing_videos(video_ids):
    """기존 영상 상태를 가져와 analyzed 등의 값을 보존한다."""
    result = {}
    clean_ids = list(dict.fromkeys(video_id for video_id in video_ids if video_id))
    for group in chunks(clean_ids, 100):
        rows = select(
            "videos",
            "video_id,analysis_status,product_score,published_at",
            {"video_id": f"in.({','.join(group)})"},
            limit=len(group),
        )
        for row in rows:
            result[row["video_id"]] = row
    return result


def next_scan_delay(priority):
    """상품 영상 비율이 높은 채널을 더 자주 확인한다."""
    return {
        5: timedelta(days=1),
        4: timedelta(days=3),
        3: timedelta(days=3),
        2: timedelta(days=7),
        1: timedelta(days=30),
    }.get(int(priority or 1), timedelta(days=30))


def build_video_row(item, fallback_channel_id, is_new):
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})
    row = {
        "video_id": item["id"],
        "channel_id": snippet.get("channelId") or fallback_channel_id,
        "title": snippet.get("title", "제목 없음"),
        "description": str(snippet.get("description", "") or "")[:10000],
        "published_at": snippet.get("publishedAt"),
        "view_count": int(statistics.get("viewCount", 0) or 0),
        "like_count": int(statistics.get("likeCount", 0) or 0),
        "youtube_category_id": snippet.get("categoryId"),
    }
    if is_new:
        row.update({
            "product_score": 0,
            "analysis_status": "pending",
            "analysis_error": None,
        })
    return row


def refresh_channel_metrics(channel_id):
    """현재 DB를 기준으로 채널별 상품 영상 비율과 우선순위를 다시 계산한다."""
    videos = select(
        "videos",
        "video_id,product_score,analysis_status,published_at",
        {"channel_id": f"eq.{channel_id}"},
        limit=5000,
    )
    recommendations = select(
        "recommendations",
        "recommendation_id",
        {"channel_id": f"eq.{channel_id}"},
        limit=5000,
    )

    total = len(videos)
    candidates = sum(
        1
        for video in videos
        if int(video.get("product_score") or 0) >= 5
        or video.get("analysis_status") in {
            "queued", "analyzed", "no_product", "rejected_generic"
        }
    )
    extracted = len(recommendations)
    latest_published = max(
        (video.get("published_at") for video in videos if video.get("published_at")),
        default=None,
    )
    ratio = (candidates / total) if total else 0

    if total == 0:
        priority = 3
    elif ratio >= 0.30:
        priority = 5
    elif ratio >= 0.10:
        priority = 4
    elif ratio >= 0.03:
        priority = 2
    else:
        priority = 1

    return {
        "total_scanned_videos": total,
        "product_candidate_videos": candidates,
        "extracted_product_count": extracted,
        "product_video_ratio": round(ratio, 4),
        "scan_priority": priority,
        "last_video_published_at": latest_published,
    }


def sync_channel(channel):
    channel_id = channel["channel_id"]
    playlist_id = channel.get("uploads_playlist_id")
    priority_before = int(channel.get("scan_priority") or 1)

    playlist_items = get_playlist_videos(playlist_id, VIDEOS_PER_CHANNEL)
    video_ids = [
        item.get("contentDetails", {}).get("videoId")
        for item in playlist_items
        if item.get("contentDetails", {}).get("videoId")
    ]
    video_ids = list(dict.fromkeys(video_ids))

    if not video_ids:
        next_at = now_utc() + next_scan_delay(priority_before)
        update(
            "channels",
            {"next_video_scan_at": next_at.isoformat()},
            {"channel_id": f"eq.{channel_id}"},
        )
        return {"found": 0, "new": 0, "updated": 0, "priority": priority_before}

    existing = get_existing_videos(video_ids)
    details = get_videos(video_ids)
    new_rows = []
    existing_rows = []

    for item in details:
        video_id = item.get("id")
        if not video_id:
            continue
        is_new = video_id not in existing
        row = build_video_row(item, channel_id, is_new)
        if is_new:
            new_rows.append(row)
        else:
            # 분석 상태 필드를 넣지 않아 기존 analyzed/no_product 등을 보존한다.
            existing_rows.append(row)

    if new_rows:
        upsert("videos", new_rows, "video_id")
    if existing_rows:
        upsert("videos", existing_rows, "video_id")

    metrics = refresh_channel_metrics(channel_id)
    next_at = now_utc() + next_scan_delay(metrics["scan_priority"])
    update(
        "channels",
        {**metrics, "next_video_scan_at": next_at.isoformat()},
        {"channel_id": f"eq.{channel_id}"},
    )

    return {
        "found": len(details),
        "new": len(new_rows),
        "updated": len(existing_rows),
        "priority": metrics["scan_priority"],
    }


def main():
    channels = get_due_channels()
    if not channels:
        print("No active channels are due for video scanning.")
        return

    total_found = total_new = total_updated = errors = 0
    print(f"Due active channels selected: {len(channels)}")

    for index, channel in enumerate(channels, start=1):
        name = channel.get("channel_name") or channel["channel_id"]
        try:
            result = sync_channel(channel)
            total_found += result["found"]
            total_new += result["new"]
            total_updated += result["updated"]
            print(
                f"[{index}/{len(channels)}] {name} | found={result['found']} | "
                f"new={result['new']} | updated={result['updated']} | "
                f"next_priority={result['priority']}"
            )
        except Exception as error:
            errors += 1
            # 일시 오류는 6시간 뒤 재시도한다.
            update(
                "channels",
                {"next_video_scan_at": (now_utc() + timedelta(hours=6)).isoformat()},
                {"channel_id": f"eq.{channel['channel_id']}"},
            )
            print(f"[{index}/{len(channels)}] {name} | ERROR: {error}")

    print(
        "Priority video sync completed | "
        f"channels={len(channels)} | found={total_found} | new={total_new} | "
        f"updated={total_updated} | errors={errors}"
    )


if __name__ == "__main__":
    main()

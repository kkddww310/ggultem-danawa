from collector.config import VIDEOS_PER_CHANNEL
from collector.database import select, upsert
from collector.youtube_api import (
    get_playlist_videos,
    get_videos,
)


def chunk_list(values, size=100):
    """
    Supabase in 필터가 너무 길어지지 않도록
    ID 목록을 일정 크기로 나눈다.
    """
    for start in range(0, len(values), size):
        yield values[start:start + size]


def get_existing_video_ids(video_ids):
    """
    Supabase videos 테이블에 이미 존재하는
    video_id만 조회한다.

    기존 영상의 analysis_status를 다시 pending으로
    바꾸지 않기 위한 확인 단계다.
    """
    existing_ids = set()

    clean_ids = list(
        dict.fromkeys(
            video_id
            for video_id in video_ids
            if video_id
        )
    )

    for chunk in chunk_list(clean_ids, 100):
        if not chunk:
            continue

        rows = select(
            "videos",
            "video_id",
            {
                "video_id": (
                    f"in.({','.join(chunk)})"
                )
            },
            limit=len(chunk),
        )

        for row in rows:
            video_id = row.get("video_id")

            if video_id:
                existing_ids.add(video_id)

    return existing_ids


def build_video_row(
    item,
    fallback_channel_id,
    is_new,
):
    """
    YouTube API의 영상 데이터를 Supabase 저장 형식으로 바꾼다.

    신규 영상에만 analysis_status=pending을 넣는다.
    기존 영상에는 analysis_status를 아예 넣지 않아서
    analyzed, no_product, ai_error 등의 기존 상태를 보존한다.
    """
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})

    video_id = item.get("id", "")
    channel_id = (
        snippet.get("channelId")
        or fallback_channel_id
    )

    row = {
        "video_id": video_id,
        "channel_id": channel_id,
        "title": snippet.get(
            "title",
            "제목 없음",
        ),
        "description": (
            snippet.get("description", "")
            or ""
        )[:10000],
        "published_at": snippet.get(
            "publishedAt"
        ),
        "view_count": int(
            statistics.get("viewCount", 0)
            or 0
        ),
        "like_count": int(
            statistics.get("likeCount", 0)
            or 0
        ),
        "youtube_category_id": snippet.get(
            "categoryId"
        ),
    }

    # 새 영상만 AI 분석 대기 상태로 등록
    if is_new:
        row["product_score"] = 0
        row["analysis_status"] = "pending"
        row["analysis_error"] = None

    return row


def sync_channel_videos(channel):
    """
    활성 채널 한 개의 최근 영상을 가져와 저장한다.

    반환값:
    {
        "channel_id": "...",
        "found": 20,
        "new": 3,
        "updated": 17
    }
    """
    channel_id = channel.get(
        "channel_id",
        "",
    )

    uploads_playlist_id = channel.get(
        "uploads_playlist_id",
        "",
    )

    if not channel_id:
        return {
            "channel_id": "",
            "found": 0,
            "new": 0,
            "updated": 0,
            "error": "channel_id 없음",
        }

    if not uploads_playlist_id:
        return {
            "channel_id": channel_id,
            "found": 0,
            "new": 0,
            "updated": 0,
            "error": "uploads_playlist_id 없음",
        }

    playlist_items = get_playlist_videos(
        uploads_playlist_id,
        VIDEOS_PER_CHANNEL,
    )

    video_ids = []

    for playlist_item in playlist_items:
        video_id = (
            playlist_item
            .get("contentDetails", {})
            .get("videoId")
        )

        if video_id:
            video_ids.append(video_id)

    video_ids = list(
        dict.fromkeys(video_ids)
    )

    if not video_ids:
        return {
            "channel_id": channel_id,
            "found": 0,
            "new": 0,
            "updated": 0,
            "error": "",
        }

    existing_ids = get_existing_video_ids(
        video_ids
    )

    details = get_videos(video_ids)

    new_rows = []
    existing_rows = []

    for item in details:
        video_id = item.get("id", "")

        if not video_id:
            continue

        is_new = (
            video_id not in existing_ids
        )

        row = build_video_row(
            item=item,
            fallback_channel_id=channel_id,
            is_new=is_new,
        )

        if is_new:
            new_rows.append(row)
        else:
            existing_rows.append(row)

    # 신규 영상:
    # pending 상태를 포함해 최초 저장
    if new_rows:
        upsert(
            "videos",
            new_rows,
            "video_id",
        )

    # 기존 영상:
    # 제목·설명·조회수 등만 갱신
    # analysis_status와 product_score는 row에 없으므로 유지
    if existing_rows:
        upsert(
            "videos",
            existing_rows,
            "video_id",
        )

    return {
        "channel_id": channel_id,
        "found": len(details),
        "new": len(new_rows),
        "updated": len(existing_rows),
        "error": "",
    }


def main():
    """
    구독자 조건을 통과해 status=active인 채널의
    최근 영상을 동기화한다.

    핵심 정책:
    - 새 video_id만 pending으로 등록
    - 기존 영상의 분석 상태는 보존
    - 조회수, 제목, 설명 등 메타데이터는 갱신
    """
    channels = select(
        "channels",
        (
            "channel_id,"
            "channel_name,"
            "uploads_playlist_id"
        ),
        {
            "status": "eq.active",
            "uploads_playlist_id": (
                "not.is.null"
            ),
        },
        limit=5000,
        order="subscriber_count.desc",
    )

    total_channels = len(channels)
    total_found = 0
    total_new = 0
    total_updated = 0
    total_errors = 0

    print(
        f"Active channels to scan: "
        f"{total_channels}"
    )

    for index, channel in enumerate(
        channels,
        start=1,
    ):
        channel_id = channel.get(
            "channel_id",
            "",
        )

        channel_name = channel.get(
            "channel_name",
            channel_id,
        )

        try:
            result = sync_channel_videos(
                channel
            )

            total_found += result["found"]
            total_new += result["new"]
            total_updated += result["updated"]

            print(
                f"[{index}/{total_channels}] "
                f"{channel_name} | "
                f"found={result['found']} | "
                f"new={result['new']} | "
                f"updated={result['updated']}"
            )

        except Exception as error:
            total_errors += 1

            print(
                f"[{index}/{total_channels}] "
                f"{channel_name} | "
                f"ERROR: {error}"
            )

    print(
        "Video sync completed | "
        f"channels={total_channels} | "
        f"found={total_found} | "
        f"new={total_new} | "
        f"updated={total_updated} | "
        f"errors={total_errors}"
    )


if __name__ == "__main__":
    main()

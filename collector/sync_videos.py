from collector.config import VIDEOS_PER_CHANNEL
from collector.database import select, upsert
from collector.youtube_api import get_playlist_videos, get_videos


def main():
    channels = select(
        "channels", "channel_id,uploads_playlist_id",
        {"status": "eq.active", "uploads_playlist_id": "not.is.null"}, limit=1000,
    )
    synced = 0
    for channel in channels:
        playlist_items = get_playlist_videos(channel["uploads_playlist_id"], VIDEOS_PER_CHANNEL)
        video_ids = [x.get("contentDetails", {}).get("videoId") for x in playlist_items]
        details = get_videos(video_ids)
        rows = []
        for item in details:
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            rows.append({
                "video_id": item["id"],
                "channel_id": snippet.get("channelId") or channel["channel_id"],
                "title": snippet.get("title", ""),
                "description": snippet.get("description", "")[:10000],
                "published_at": snippet.get("publishedAt"),
                "view_count": int(stats.get("viewCount", 0) or 0),
                "like_count": int(stats.get("likeCount", 0) or 0),
                "youtube_category_id": snippet.get("categoryId"),
                "analysis_status": "pending",
            })
        upsert("videos", rows, "video_id")
        synced += len(rows)
    print(f"Synced {synced} recent videos from {len(channels)} active channels")


if __name__ == "__main__":
    main()

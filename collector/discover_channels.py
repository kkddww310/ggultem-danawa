from datetime import datetime, timezone
from collector.config import DISCOVERY_QUERIES, DISCOVERY_QUERY_LIMIT, MIN_SUBSCRIBERS
from collector.database import upsert
from collector.youtube_api import search_videos, get_channels


def main():
    channel_ids = set()
    for query in DISCOVERY_QUERIES[:DISCOVERY_QUERY_LIMIT]:
        for item in search_videos(query, 25):
            channel_id = item.get("snippet", {}).get("channelId")
            if channel_id:
                channel_ids.add(channel_id)

    records = []
    for item in get_channels(channel_ids):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        hidden = bool(stats.get("hiddenSubscriberCount", False))
        subscribers = int(stats.get("subscriberCount", 0) or 0)
        uploads = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        status = "active" if not hidden and subscribers >= MIN_SUBSCRIBERS else (
            "hidden_subscribers" if hidden else "below_threshold"
        )
        records.append({
            "channel_id": item["id"],
            "channel_name": snippet.get("title", ""),
            "subscriber_count": subscribers,
            "subscriber_hidden": hidden,
            "country": snippet.get("country"),
            "description": snippet.get("description", "")[:5000],
            "uploads_playlist_id": uploads,
            "status": status,
            "last_scanned_at": datetime.now(timezone.utc).isoformat(),
        })

    upsert("channels", records, "channel_id")
    active = sum(1 for row in records if row["status"] == "active")
    print(f"Discovered {len(records)} channels; active 1M+ channels: {active}")


if __name__ == "__main__":
    main()

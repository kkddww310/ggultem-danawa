import requests
from collector.config import YOUTUBE_API_KEY

BASE = "https://www.googleapis.com/youtube/v3"


def _get(path, params):
    params = dict(params)
    params["key"] = YOUTUBE_API_KEY
    response = requests.get(f"{BASE}/{path}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def search_videos(query, max_results=25):
    return _get("search", {
        "part": "snippet", "q": query, "type": "video",
        "maxResults": min(max_results, 50), "relevanceLanguage": "ko",
        "regionCode": "KR", "safeSearch": "moderate",
    }).get("items", [])


def get_channels(channel_ids):
    output = []
    ids = list(dict.fromkeys(x for x in channel_ids if x))
    for start in range(0, len(ids), 50):
        data = _get("channels", {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(ids[start:start + 50]), "maxResults": 50,
        })
        output.extend(data.get("items", []))
    return output


def get_playlist_videos(playlist_id, max_results=20):
    return _get("playlistItems", {
        "part": "snippet,contentDetails", "playlistId": playlist_id,
        "maxResults": min(max_results, 50),
    }).get("items", [])


def get_videos(video_ids):
    output = []
    ids = list(dict.fromkeys(x for x in video_ids if x))
    for start in range(0, len(ids), 50):
        data = _get("videos", {
            "part": "snippet,statistics", "id": ",".join(ids[start:start + 50]),
            "maxResults": 50,
        })
        output.extend(data.get("items", []))
    return output

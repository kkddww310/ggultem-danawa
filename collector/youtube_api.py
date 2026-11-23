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


def get_creator_comments(video_id, channel_id, max_results=20):
    """영상의 댓글 중 채널 주인이 작성한 댓글(고정 댓글 등)만 추출한다."""
    if not video_id or not channel_id:
        return []
    try:
        data = _get("commentThreads", {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(max_results, 50),
            "order": "relevance",
            "textFormat": "plainText",
        })
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code in {403, 404}:
            return []
        raise

    comments = []
    for item in data.get("items", []):
        top = (item.get("snippet") or {}).get("topLevelComment") or {}
        snippet = top.get("snippet") or {}
        author_id = (snippet.get("authorChannelId") or {}).get("value")
        text = str(snippet.get("textDisplay") or "").strip()
        if author_id == channel_id and text:
            comments.append(text)
    return comments

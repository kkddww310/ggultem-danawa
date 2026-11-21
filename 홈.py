import streamlit as st
import json
import os
import re
import html
import time
import hashlib
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs, quote

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None

# =========================================================
# 기본 설정
# =========================================================
APP_NAME = "꿀템 다나와"
DB_FILE = "items.json"
HISTORY_FILE = "visited_history.json"
VIDEO_CACHE_FILE = "video_cache.json"
DEFAULT_OPENROUTER_KEY = ""
KST = timezone(timedelta(hours=9))
FILE_LOCK = threading.RLock()

OPENROUTER_MODELS = (
    "openrouter/free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
)

DEFAULT_YOUTUBER_LIST = [
    "ITSub잇섭", "테크몽 Techmong", "주연 ZUYONI", "뻘짓연구소", "가전주부",
    "오늘의 주우재", "짱구대디", "이사배 RISABAE", "레오제이 LeoJ Makeup",
    "디렉터 파이", "원지의하루", "귀곰", "자취남", "승우아빠", "지냐",
]

AUTO_DISCOVERY_QUERIES = [
    "유튜버 내돈내산 추천템",
    "삶의 질 수직상승 꿀템 추천",
    "올리브영 추천템 내돈내산",
    "쿠팡 추천템 자취 필수템",
    "데스크테리어 가성비 IT 추천템",
    "여행 필수템 캐리어 꿀템 추천",
]

INITIAL_SEED_DB = [
    {
        "id": "seed-anker-maggo-qi2",
        "name": "앤커 맥고 Qi2 3in1 맥세이프 충전기",
        "normalized_name": "앤커맥고qi23in1맥세이프충전기",
        "keyword": "충전기",
        "youtuber": "ITSub잇섭",
        "reason": "아이폰·애플워치·에어팟을 15W 고속으로 한 번에 정리하는 접이식 충전 스테이션",
        "timestamp": "03:15",
        "start_sec": 195,
        "video_id": "",
        "youtube_url": "https://www.youtube.com/results?search_query=잇섭+앤커+맥고+충전기",
        "is_shorts": False,
        "evidence": "기본 샘플 데이터",
        "confidence": 1.0,
        "created_at": "",
    },
    {
        "id": "seed-logitech-mx-master-3s",
        "name": "로지텍 MX Master 3S 무선 마우스",
        "normalized_name": "로지텍mxmaster3s무선마우스",
        "keyword": "마우스",
        "youtuber": "테크몽 Techmong",
        "reason": "저소음 클릭과 초고속 무한 휠로 장시간 편집·업무 피로도를 줄여주는 마우스",
        "timestamp": "05:40",
        "start_sec": 340,
        "video_id": "",
        "youtube_url": "https://www.youtube.com/results?search_query=테크몽+MX+Master+3S",
        "is_shorts": False,
        "evidence": "기본 샘플 데이터",
        "confidence": 1.0,
        "created_at": "",
    },
    {
        "id": "seed-jungsaemmool-cushion",
        "name": "정샘물 에센셜 스킨 누더 쿠션",
        "normalized_name": "정샘물에센셜스킨누더쿠션",
        "keyword": "쿠션",
        "youtuber": "이사배 RISABAE",
        "reason": "피부 본연의 윤기를 살리면서 자연스럽고 화사하게 밀착되는 베이스 쿠션",
        "timestamp": "03:40",
        "start_sec": 220,
        "video_id": "",
        "youtube_url": "https://www.youtube.com/results?search_query=이사배+정샘물+스킨+누더+쿠션",
        "is_shorts": False,
        "evidence": "기본 샘플 데이터",
        "confidence": 1.0,
        "created_at": "",
    },
]

NON_PRODUCT_KEYWORDS = (
    "인트로", "오프닝", "마무리", "아웃트로", "총평", "결론", "구독", "이벤트",
    "당첨", "발표", "공지", "커뮤니티", "종료", "마감", "쿠키", "예고", "목차",
    "할인코드", "쿠폰", "최종가", "할인가", "혜택가", "정상가", "체감가",
    "진행기간", "한국시간", "항공권", "숙박", "예약", "배송", "소요",
    "챌린지", "장바구니", "신규회원", "원딜", "광군제", "블프", "세일",
    "free download", "watch more", "ncs", "stream", "download",
)

st.set_page_config(page_title=APP_NAME, page_icon="🛍️", layout="centered")

# =========================================================
# 공통 유틸
# =========================================================
def now_iso():
    return datetime.now(KST).isoformat(timespec="seconds")


def safe_text(value):
    return html.escape(str(value or ""), quote=True)


def stable_id(*parts):
    raw = "|".join(str(p or "").strip().lower() for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def atomic_write_json(path, data):
    tmp = f"{path}.tmp"
    with FILE_LOCK:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with FILE_LOCK, open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def normalize_product_name(name):
    text = (name or "").lower().strip()
    replacements = {
        "logitech": "로지텍", "samsung": "삼성", "anker": "앤커",
        "apple": "애플", "ugreen": "유그린",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def is_non_product(text):
    t = (text or "").strip()
    t_low = t.lower()
    if not t or len(t) < 2 or len(t) > 80:
        return True
    if t[0] in ("=", "👉", "※", "→", "▶", "|", "-", "•", "🎉", "🔥", "✈️", "⚠️"):
        return True
    if "?" in t or "!" in t:
        return True
    if re.search(r"(?:합니다|입니다|됩니다|있습니다|없습니다|하세요|주세요|바랍니다|해요|예요|이에요|에요|가요|네요|같아요)$", t):
        return True
    if t.endswith((" 제품", " 상품", " 아이템", " 추천", " 후기", " 리뷰", " 소개", " 챌린지", " 원딜", " 딜")):
        return True
    return any(word in t_low for word in NON_PRODUCT_KEYWORDS)


def extract_video_id(url):
    if not url:
        return None
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in ("youtu.be", "www.youtu.be"):
        return parsed.path.lstrip("/").split("/")[0] or None
    if host in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith(("/shorts/", "/embed/")):
            parts = parsed.path.split("/")
            return parts[2] if len(parts) > 2 else None
    return None


def seconds_to_timestamp(sec):
    sec = max(0, int(sec or 0))
    mm, ss = divmod(sec, 60)
    hh, mm = divmod(mm, 60)
    return f"{hh:02d}:{mm:02d}:{ss:02d}" if hh else f"{mm:02d}:{ss:02d}"


def parse_timestamp_to_seconds(value):
    if isinstance(value, (int, float)):
        return max(0, int(value))
    parts = str(value or "").strip().split(":")
    try:
        nums = [int(x) for x in parts]
        if len(nums) == 2:
            return nums[0] * 60 + nums[1]
        if len(nums) == 3:
            return nums[0] * 3600 + nums[1] * 60 + nums[2]
    except Exception:
        pass
    return 0

# =========================================================
# DB / 이력 / 캐시
# =========================================================
def migrate_item(item):
    x = dict(item or {})
    x["name"] = str(x.get("name", "")).strip()
    x["keyword"] = str(x.get("keyword", "")).strip()
    x["youtuber"] = str(x.get("youtuber", "")).strip() or "알 수 없는 채널"
    x["reason"] = str(x.get("reason", "")).strip()
    x["youtube_url"] = str(x.get("youtube_url", "")).strip()
    x["video_id"] = x.get("video_id") or extract_video_id(x["youtube_url"]) or ""
    x["is_shorts"] = bool(x.get("is_shorts") or "/shorts/" in x["youtube_url"] or x.get("timestamp") == "Shorts")
    x["start_sec"] = parse_timestamp_to_seconds(x.get("start_sec", x.get("timestamp", 0)))
    x["timestamp"] = "Shorts" if x["is_shorts"] else seconds_to_timestamp(x["start_sec"])
    x["normalized_name"] = normalize_product_name(x["name"])
    x["confidence"] = float(x.get("confidence", 1.0 if str(x.get("id", "")).startswith("seed-") else 0.8))
    x["evidence"] = str(x.get("evidence", "")).strip()
    x["pros"] = [str(v).strip() for v in x.get("pros", []) if str(v).strip()][:3]
    x["cons"] = [str(v).strip() for v in x.get("cons", []) if str(v).strip()][:3]
    x["purchase_type"] = str(x.get("purchase_type", "확인되지 않음")).strip() or "확인되지 않음"
    x["use_case"] = str(x.get("use_case", "")).strip()
    x["created_at"] = str(x.get("created_at", "")) or now_iso()
    x["id"] = str(x.get("id", "")) or stable_id(x["normalized_name"], x["youtuber"], x["video_id"])
    return x


def save_items(items):
    atomic_write_json(DB_FILE, [migrate_item(x) for x in items])


def load_items():
    raw = load_json(DB_FILE, [])
    cleaned = []
    for item in raw:
        x = migrate_item(item)
        if x["name"] and not is_non_product(x["name"]):
            cleaned.append(x)
    if not cleaned:
        cleaned = [migrate_item(x) for x in INITIAL_SEED_DB]
    if cleaned != raw:
        save_items(cleaned)
    return cleaned


def add_unique_items(new_items):
    db = load_items()
    existing_keys = {(x["normalized_name"], x.get("youtuber", "").lower()) for x in db}
    added = []
    for raw in new_items:
        item = migrate_item(raw)
        key = (item["normalized_name"], item["youtuber"].lower())
        if not item["normalized_name"] or is_non_product(item["name"]):
            continue
        if key in existing_keys:
            continue
        db.append(item)
        existing_keys.add(key)
        added.append(item)
    if added:
        save_items(db)
    return added


def load_history():
    data = load_json(HISTORY_FILE, {"videos": {}, "queries": {}})
    data.setdefault("videos", {})
    data.setdefault("queries", {})
    return data


def save_history(history):
    atomic_write_json(HISTORY_FILE, history)


def history_should_skip(video_id):
    rec = load_history()["videos"].get(video_id)
    if not rec:
        return False
    try:
        checked = datetime.fromisoformat(rec.get("last_checked", ""))
    except Exception:
        return False
    age = datetime.now(KST) - checked.astimezone(KST)
    status = rec.get("status", "")
    cooldowns = {
        "success": timedelta(days=30),
        "no_product": timedelta(days=21),
        "no_text": timedelta(days=7),
        "network_error": timedelta(hours=1),
        "ai_error": timedelta(hours=6),
    }
    return age < cooldowns.get(status, timedelta(hours=1))


def update_video_history(video_id, status, item_count=0, reason=""):
    with FILE_LOCK:
        history = load_history()
        old = history["videos"].get(video_id, {})
        history["videos"][video_id] = {
            "status": status,
            "attempts": int(old.get("attempts", 0)) + 1,
            "last_checked": now_iso(),
            "item_count": int(item_count),
            "reason": str(reason)[:300],
        }
        save_history(history)


def update_query_history(query, found_count, error=""):
    with FILE_LOCK:
        history = load_history()
        history["queries"][query] = {
            "last_checked": now_iso(),
            "found_count": int(found_count),
            "error": str(error)[:300],
        }
        save_history(history)


def load_video_cache():
    return load_json(VIDEO_CACHE_FILE, {})


def get_cached_bundle(video_id, max_age_days=14):
    rec = load_video_cache().get(video_id)
    if not rec:
        return None
    try:
        cached_at = datetime.fromisoformat(rec.get("cached_at", ""))
        if datetime.now(KST) - cached_at.astimezone(KST) > timedelta(days=max_age_days):
            return None
    except Exception:
        return None
    return rec.get("bundle")


def put_cached_bundle(video_id, bundle):
    with FILE_LOCK:
        cache = load_video_cache()
        cache[video_id] = {"cached_at": now_iso(), "bundle": bundle}
        if len(cache) > 1000:
            cache = dict(list(cache.items())[-800:])
        atomic_write_json(VIDEO_CACHE_FILE, cache)

# =========================================================
# 키 / HTTP
# =========================================================
def get_openrouter_key():
    try:
        key = str(st.secrets.get("OPENROUTER_API_KEY", "")).strip()
        if key:
            return key
    except Exception:
        pass
    return str(st.session_state.get("openrouter_key", DEFAULT_OPENROUTER_KEY)).strip()


def request_json(url, payload, headers, timeout=10, retries=2):
    body = json.dumps(payload).encode("utf-8")
    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8", errors="ignore"))
        except urllib.error.HTTPError as e:
            last_error = RuntimeError(f"HTTP {e.code}: {e.reason}")
            if e.code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:
            last_error = e
        if attempt < retries:
            time.sleep(0.8 * (2 ** attempt))
    raise last_error or RuntimeError("HTTP 요청 실패")

# =========================================================
# YouTube InnerTube
# =========================================================
def innertube_post(endpoint, payload_extra, client="WEB"):
    if client == "IOS":
        client_data = {
            "clientName": "IOS", "clientVersion": "19.45.4",
            "deviceMake": "Apple", "deviceModel": "iPhone16,2", "hl": "ko", "gl": "KR",
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "com.google.ios.youtube/19.45.4 (iPhone16,2; U; CPU iOS 18_1 like Mac OS X)",
            "X-YouTube-Client-Name": "5",
            "X-YouTube-Client-Version": "19.45.4",
        }
    else:
        client_data = {"clientName": "WEB", "clientVersion": "2.20241126.01.00", "hl": "ko", "gl": "KR"}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36",
            "X-YouTube-Client-Name": "1",
            "X-YouTube-Client-Version": "2.20241126.01.00",
            "Origin": "https://www.youtube.com",
            "Referer": "https://www.youtube.com/",
        }
    payload = {"context": {"client": client_data}}
    payload.update(payload_extra)
    return request_json(
        f"https://www.youtube.com/youtubei/v1/{endpoint}?prettyPrint=false",
        payload, headers, timeout=9, retries=1,
    )


def normalize_channel_name(value):
    return re.sub(r"[\s()\[\]_-]+", "", (value or "").lower())


def is_channel_match(query, channel_name):
    q = normalize_channel_name(query)
    c = normalize_channel_name(channel_name)
    if not q or not c or c == "유튜버":
        return False
    core = re.sub(r"(추천템|꿀템|필수템|가성비템|리뷰|내돈내산|하울|영상|쇼츠|숏츠)", "", q).strip()
    return (len(core) >= 2 and (core in c or c in core)) or q in c or c in q


def extract_videos_from_data(data, default_youtuber="유튜버", default_channel_id="", force_shorts=False):
    found, seen = [], set()

    def add(video_id, title, youtuber, channel_id, is_shorts):
        if isinstance(video_id, str) and len(video_id) == 11 and video_id not in seen:
            seen.add(video_id)
            found.append({
                "video_id": video_id,
                "title": title or "제목 없음",
                "youtuber": youtuber or default_youtuber,
                "channel_id": channel_id or default_channel_id,
                "is_shorts": bool(is_shorts),
            })

    def walk(node):
        if isinstance(node, dict):
            vr = node.get("videoRenderer")
            if vr:
                title_runs = vr.get("title", {}).get("runs", [])
                owner_runs = vr.get("ownerText", {}).get("runs", []) or vr.get("longBylineText", {}).get("runs", [])
                owner = owner_runs[0] if owner_runs else {}
                channel_id = owner.get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId", "")
                nav_url = vr.get("navigationEndpoint", {}).get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", "")
                add(
                    vr.get("videoId", ""),
                    title_runs[0].get("text", "제목 없음") if title_runs else "제목 없음",
                    owner.get("text", default_youtuber), channel_id,
                    force_shorts or "/shorts/" in nav_url,
                )
            rr = node.get("reelItemRenderer")
            if rr:
                video_id = rr.get("videoId") or rr.get("navigationEndpoint", {}).get("reelWatchEndpoint", {}).get("videoId", "")
                headline = rr.get("headline", {})
                title = headline.get("simpleText") or (headline.get("runs", [{}])[0].get("text") if headline.get("runs") else "Shorts 영상")
                add(video_id, title, default_youtuber, default_channel_id, True)
            sl = node.get("shortsLockupViewModel")
            if sl:
                video_id = sl.get("onTap", {}).get("innertubeCommand", {}).get("reelWatchEndpoint", {}).get("videoId", "")
                if not video_id:
                    matched = re.search(r"([A-Za-z0-9_-]{11})$", sl.get("entityId", ""))
                    video_id = matched.group(1) if matched else ""
                title = sl.get("overlayMetadata", {}).get("primaryText", {}).get("content", "Shorts 영상")
                add(video_id, title, default_youtuber, default_channel_id, True)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return found


def search_youtube_videos(query, limit=4, only_official=True):
    search_query = f"{query} 추천템" if only_official else query
    raw = extract_videos_from_data(innertube_post("search", {"query": search_query}))
    if not only_official:
        long_videos = [x for x in raw if not x["is_shorts"]]
        shorts = [x for x in raw if x["is_shorts"]]
        return (long_videos + shorts)[:limit]

    matched = [x for x in raw if is_channel_match(query, x["youtuber"])]
    if len(matched) < limit:
        extra = extract_videos_from_data(innertube_post("search", {"query": query}))
        seen = {x["video_id"] for x in matched}
        for item in extra:
            if item["video_id"] not in seen and is_channel_match(query, item["youtuber"]):
                matched.append(item)
                seen.add(item["video_id"])
                if len(matched) >= limit:
                    break
    return matched[:limit]


def parse_caption_xml(base_url):
    try:
        req = urllib.request.Request(base_url, headers={
            "User-Agent": "com.google.ios.youtube/19.45.4 (iPhone16,2; U; CPU iOS 18_1 like Mac OS X)"
        })
        with urllib.request.urlopen(req, timeout=7) as response:
            xml_text = response.read().decode("utf-8", errors="ignore")
        lines = []
        for matched in re.finditer(r'<text[^>]*start="([\d.]+)"[^>]*>(.*?)</text>', xml_text, re.DOTALL):
            sec = int(float(matched.group(1)))
            text = html.unescape(re.sub(r"<[^>]+>", "", matched.group(2))).replace("\n", " ").strip()
            if text:
                lines.append(f"[{seconds_to_timestamp(sec)}] {text}")
        return "\n".join(lines)
    except Exception:
        return ""


def fetch_transcript_text(video_id, caption_tracks=None):
    tracks = caption_tracks or []
    preferred = next((t for t in tracks if t.get("languageCode") == "ko"), None) or (tracks[0] if tracks else None)
    if preferred and preferred.get("baseUrl"):
        text = parse_caption_xml(preferred["baseUrl"])
        if text:
            return text
    if YouTubeTranscriptApi is None:
        return ""
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["ko", "en"])
        return "\n".join(
            f"[{seconds_to_timestamp(int(segment.start))}] {segment.text}"
            for segment in fetched
        )
    except Exception:
        return ""


def sample_transcript(text, max_chars=3600):
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    segment = max_chars // 3
    middle_start = max(0, len(text) // 2 - segment // 2)
    return "\n... [중간 생략] ...\n".join([
        text[:segment], text[middle_start:middle_start + segment], text[-segment:]
    ])


def fetch_video_bundle(video_id, youtuber_hint="유튜버", title_hint="", is_shorts=False):
    cached = get_cached_bundle(video_id)
    if cached:
        return cached

    title, description, youtuber, channel_id = title_hint, "", youtuber_hint, ""
    caption_tracks = []
    # YouTube는 특정 InnerTube 클라이언트를 일괄 차단하거나 400을 반환할 수 있다.
    # WEB -> IOS 순서로 시도하고, player가 실패해도 검색에서 얻은 제목으로 분석을 계속한다.
    data = {}
    player_errors = []
    for player_client in ("WEB", "IOS"):
        try:
            candidate = innertube_post("player", {"videoId": video_id}, client=player_client)
            if candidate.get("videoDetails"):
                data = candidate
                break
            playability = candidate.get("playabilityStatus", {})
            player_errors.append(f"{player_client}: {playability.get('status', 'NO_DETAILS')} {playability.get('reason', '')}")
        except Exception as error:
            player_errors.append(f"{player_client}: {error}")

    details = data.get("videoDetails", {})
    if details:
        title = details.get("title") or title
        description = details.get("shortDescription", "") or description
        youtuber = details.get("author") or youtuber
        channel_id = details.get("channelId", "")
    caption_tracks = data.get("captions", {}).get("playerCaptionsTracklistRenderer", {}).get("captionTracks", [])
    transcript = fetch_transcript_text(video_id, caption_tracks)

    # player 메타데이터가 막혀도 검색 결과 제목이 있으면 title_only로 보존한다.
    # 이렇게 해야 영상 18개가 모두 HTTP 400으로 폐기되는 현상을 피할 수 있다.
    if not data and not title.strip():
        raise RuntimeError("YouTube player 조회 실패: " + " | ".join(player_errors))

    evidence_level = "title_only"
    if len(transcript.strip()) > 50:
        evidence_level = "transcript"
    elif len(description.strip()) > 50:
        evidence_level = "description"

    bundle = {
        "video_id": video_id,
        "youtuber": youtuber,
        "channel_id": channel_id,
        "title": title,
        "desc": description[:1800],
        "transcript": sample_transcript(transcript, 3600),
        "is_shorts": bool(is_shorts),
        "evidence_level": evidence_level,
    }
    put_cached_bundle(video_id, bundle)
    return bundle

# =========================================================
# OpenRouter 분석
# =========================================================
def extract_json_object(text):
    cleaned = re.sub(r"```(?:json)?", "", str(text or ""), flags=re.IGNORECASE).replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    decoder = json.JSONDecoder()
    for idx, char in enumerate(cleaned):
        if char not in "[{":
            continue
        try:
            result, _ = decoder.raw_decode(cleaned[idx:])
            return result
        except Exception:
            continue
    raise ValueError("AI 응답에서 JSON을 찾지 못했습니다.")


def analyze_batch_with_openrouter(bundles):
    api_key = get_openrouter_key()
    if not api_key or not api_key.isascii():
        raise RuntimeError("OpenRouter API 키가 없습니다. 설정 탭에서 이번 세션용 키를 입력하거나 Streamlit secrets에 등록하세요.")

    bundle_map = {b["video_id"]: b for b in bundles}
    blocks = []
    for bundle in bundles:
        blocks.append(
            f"=== VIDEO_ID: {bundle['video_id']} | YOUTUBER: {bundle['youtuber']} | EVIDENCE_LEVEL: {bundle['evidence_level']} ===\n"
            f"[제목] {bundle['title']}\n"
            f"[설명란]\n{bundle['desc']}\n"
            f"[자막 샘플]\n{bundle['transcript']}"
        )

    prompt = f"""너는 한국 유튜브의 제품 추천을 검증하는 쇼핑 큐레이터다.
아래 영상별 제목, 설명란, 자막 샘플에 명시적으로 등장하는 실제 구매 가능한 제품만 추출하라.
브랜드나 모델명이 근거에 없으면 절대 추측하거나 보완하지 마라.

반드시 아래 JSON 객체 하나만 반환한다.
{{"items":[{{"video_id":"영상ID","youtuber":"채널명","name":"브랜드 + 정확한 제품명","keyword":"일반 품목명","reason":"영상에서 언급된 추천 이유 한 줄","start_sec":0,"evidence":"입력에서 확인되는 짧은 근거 문구","confidence":0.0,"pros":["장점"],"cons":["단점"],"purchase_type":"직접 구매|제품 제공|유료 광고|확인되지 않음","use_case":"추천 사용 상황"}}]}}

검증 규칙:
1. 이벤트, 챌린지, 프로모션, 배송, 할인, 쿠폰, 숙박, 항공권, 음악 다운로드 문구는 제외한다.
2. confidence는 0~1이다. 브랜드와 모델명이 자막/설명란에서 직접 확인되면 0.85 이상, 일부만 확인되면 0.6 이하로 준다.
3. EVIDENCE_LEVEL이 title_only이면 제목에 브랜드와 제품명이 직접 적힌 경우만 추출하고 confidence 0.90 이상을 부여한다.
4. evidence에는 입력에 실제 존재하는 80자 이하 근거만 쓴다.
5. start_sec는 자막 타임스탬프가 확인될 때만 초 단위로 쓰고, 확인되지 않으면 0이다.
6. 같은 영상의 같은 제품은 한 번만 반환한다.
7. pros와 cons는 영상에 명시된 내용만 각각 최대 3개까지 쓴다. 근거가 없으면 빈 배열로 둔다.
8. purchase_type은 직접 구매, 제품 제공, 유료 광고, 확인되지 않음 중 하나만 쓴다. 명시적 근거가 없으면 확인되지 않음이다.
9. use_case는 영상 근거에 맞는 짧은 사용 상황이며, 추측하지 않는다.
10. 제품이 없으면 {{"items":[]}}만 반환한다.

{chr(10).join(blocks)}"""

    last_error = None
    content = None
    for model in OPENROUTER_MODELS:
        try:
            response = request_json(
                "https://openrouter.ai/api/v1/chat/completions",
                {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.05,
                },
                {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://ggultem-danawa.streamlit.app",
                    "X-Title": "Ggultem Danawa",
                },
                timeout=38,
                retries=1,
            )
            if response.get("error"):
                raise RuntimeError(response["error"].get("message", str(response["error"])))
            content = response["choices"][0]["message"]["content"]
            break
        except Exception as error:
            last_error = error

    if content is None:
        raise RuntimeError(f"OpenRouter 호출 실패: {last_error}")

    parsed = extract_json_object(content)
    raw_items = parsed.get("items", []) if isinstance(parsed, dict) else parsed
    if not isinstance(raw_items, list):
        return []

    results, seen = [], set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        video_id = str(raw.get("video_id", "")).strip()
        bundle = bundle_map.get(video_id)
        if not bundle:
            continue
        name = str(raw.get("name", "")).strip()
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0))))
        threshold = 0.90 if bundle["evidence_level"] == "title_only" else 0.72
        if not name or confidence < threshold or is_non_product(name):
            continue
        normalized = normalize_product_name(name)
        dedupe_key = (video_id, normalized)
        if not normalized or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        start_sec = max(0, int(raw.get("start_sec", 0) or 0))
        is_shorts = bundle["is_shorts"]
        url = f"https://www.youtube.com/shorts/{video_id}" if is_shorts else f"https://youtu.be/{video_id}?t={start_sec}"
        results.append({
            "id": stable_id(normalized, bundle["youtuber"], video_id),
            "name": name,
            "normalized_name": normalized,
            "keyword": str(raw.get("keyword", "")).strip(),
            "youtuber": bundle["youtuber"],
            "reason": str(raw.get("reason", "")).strip(),
            "timestamp": "Shorts" if is_shorts else seconds_to_timestamp(start_sec),
            "start_sec": start_sec,
            "video_id": video_id,
            "youtube_url": url,
            "is_shorts": is_shorts,
            "evidence": str(raw.get("evidence", "")).strip()[:160],
            "confidence": confidence,
            "pros": [str(v).strip() for v in raw.get("pros", []) if str(v).strip()][:3],
            "cons": [str(v).strip() for v in raw.get("cons", []) if str(v).strip()][:3],
            "purchase_type": str(raw.get("purchase_type", "확인되지 않음")).strip(),
            "use_case": str(raw.get("use_case", "")).strip()[:80],
            "created_at": now_iso(),
        })
    return results

# =========================================================
# 수집 오케스트레이션
# =========================================================
def collect_parallel_batch(queries, per_query_limit=3, only_official=True, status_box=None, progress_bar=None):
    stats = {
        "queries": len(queries), "search_success": 0, "search_errors": 0,
        "found": 0, "skipped_history": 0, "bundle_success": 0,
        "no_text": 0, "ai_chunks": 0, "extracted": 0, "added": 0,
    }
    errors = []
    targets, seen_video_ids = [], set()

    def status(message, kind="info"):
        if status_box is not None:
            render_banner(status_box, message, kind)

    status(f"1/3 검색어 {len(queries)}개에서 새 추천 영상을 찾고 있어요.")
    if progress_bar is not None:
        progress_bar.progress(10)

    def search_task(query):
        try:
            videos = search_youtube_videos(query, limit=per_query_limit, only_official=only_official)
            update_query_history(query, len(videos))
            return query, videos, ""
        except Exception as error:
            update_query_history(query, 0, str(error))
            return query, [], str(error)

    workers = min(4, max(1, len(queries)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(search_task, query) for query in queries]
        for future in as_completed(futures):
            query, videos, error = future.result()
            if error:
                stats["search_errors"] += 1
                errors.append(f"{query}: {error}")
            else:
                stats["search_success"] += 1
            for video in videos:
                video_id = video["video_id"]
                if video_id in seen_video_ids:
                    continue
                if history_should_skip(video_id):
                    stats["skipped_history"] += 1
                    continue
                seen_video_ids.add(video_id)
                targets.append(video)

    stats["found"] = len(targets)
    if not targets:
        if progress_bar is not None:
            progress_bar.progress(100)
        message = "재분석 대기시간이 지나지 않은 영상뿐이거나 새로운 영상이 없어요."
        return [], stats, errors, message

    status(f"2/3 새 영상 {len(targets)}개의 제목·설명·자막을 가져오고 있어요.")
    if progress_bar is not None:
        progress_bar.progress(38)

    bundles = []
    with ThreadPoolExecutor(max_workers=min(6, len(targets))) as executor:
        future_map = {
            executor.submit(fetch_video_bundle, v["video_id"], v["youtuber"], v["title"], v.get("is_shorts", False)): v
            for v in targets
        }
        for future in as_completed(future_map):
            video = future_map[future]
            video_id = video["video_id"]
            try:
                bundle = future.result()
                title_len = len(bundle.get("title", "").strip())
                desc_len = len(bundle.get("desc", "").strip())
                transcript_len = len(bundle.get("transcript", "").strip())
                if transcript_len > 20 or desc_len > 20 or title_len > 12:
                    bundles.append(bundle)
                    stats["bundle_success"] += 1
                else:
                    stats["no_text"] += 1
                    update_video_history(video_id, "no_text", reason="제목·설명·자막이 부족함")
            except Exception as error:
                errors.append(f"{video_id}: {error}")
                update_video_history(video_id, "network_error", reason=str(error))

    if not bundles:
        if progress_bar is not None:
            progress_bar.progress(100)
        return [], stats, errors, "분석할 수 있는 제목·설명·자막을 확보하지 못했어요."

    status(f"3/3 분석 가능한 영상 {len(bundles)}개에서 실제 상품을 검증하고 있어요.")
    if progress_bar is not None:
        progress_bar.progress(62)

    # 글자 수와 영상 수를 함께 제한해 무료 모델 입력 초과를 줄인다.
    chunks, current, chars = [], [], 0
    for bundle in bundles:
        bundle_chars = len(bundle["title"]) + len(bundle["desc"]) + len(bundle["transcript"])
        if current and (len(current) >= 3 or chars + bundle_chars > 11000):
            chunks.append(current)
            current, chars = [], 0
        current.append(bundle)
        chars += bundle_chars
    if current:
        chunks.append(current)

    all_extracted = []
    for index, chunk in enumerate(chunks, 1):
        stats["ai_chunks"] += 1
        status(f"3/3 AI 검증 중 {index}/{len(chunks)} 묶음 · 영상 {len(bundles)}개")
        if progress_bar is not None:
            progress_bar.progress(62 + int(index / len(chunks) * 35))
        try:
            extracted = analyze_batch_with_openrouter(chunk)
            all_extracted.extend(extracted)
            counts = {}
            for item in extracted:
                counts[item["video_id"]] = counts.get(item["video_id"], 0) + 1
            for bundle in chunk:
                count = counts.get(bundle["video_id"], 0)
                update_video_history(bundle["video_id"], "success" if count else "no_product", item_count=count)
        except Exception as error:
            errors.append(str(error))
            for bundle in chunk:
                update_video_history(bundle["video_id"], "ai_error", reason=str(error))

    stats["extracted"] = len(all_extracted)
    added = add_unique_items(all_extracted)
    stats["added"] = len(added)
    if progress_bar is not None:
        progress_bar.progress(100)
    return added, stats, errors, ""

def product_group_key(item):
    """동일 상품으로 볼 수 있는 항목을 보수적으로 묶는다."""
    normalized = item.get("normalized_name") or normalize_product_name(item.get("name", ""))
    # 품목 일반어만 남은 데이터가 과도하게 합쳐지지 않도록 6자 미만은 고유 ID 사용
    if len(normalized) < 6:
        return item.get("id") or stable_id(item.get("name"), item.get("youtuber"))
    return normalized


def group_products(items):
    groups = {}
    for item in items:
        key = product_group_key(item)
        groups.setdefault(key, []).append(item)
    result = []
    for key, recommendations in groups.items():
        recommendations.sort(key=lambda x: (x.get("confidence", 0), x.get("created_at", "")), reverse=True)
        representative = recommendations[0]
        youtubers = sorted({x.get("youtuber", "") for x in recommendations if x.get("youtuber")})
        videos = {x.get("video_id") or x.get("youtube_url") for x in recommendations if x.get("video_id") or x.get("youtube_url")}
        result.append({
            "key": key,
            "representative": representative,
            "recommendations": recommendations,
            "youtubers": youtubers,
            "youtuber_count": len(youtubers),
            "video_count": len(videos),
            "max_confidence": max(float(x.get("confidence", 0)) for x in recommendations),
        })
    result.sort(key=lambda g: (g["youtuber_count"], g["video_count"], g["max_confidence"]), reverse=True)
    return result


def purchase_badge(value):
    return {
        "직접 구매": "💳 직접 구매",
        "제품 제공": "🎁 제품 제공",
        "유료 광고": "📢 유료 광고",
        "확인되지 않음": "❓ 구매 형태 미확인",
    }.get(value, "❓ 구매 형태 미확인")

# =========================================================
# UI
# =========================================================
def render_banner(target, text, kind="info"):
    palettes = {
        "info": ("#E8F3FF", "#1B64DA", "#C9E0FF"),
        "success": ("#E8F8F0", "#0B7A4B", "#BCEAD5"),
        "warning": ("#FFF6E5", "#9A5B00", "#FFE0A3"),
        "error": ("#FFEFEF", "#C92A2A", "#FFC9C9"),
    }
    bg, fg, border = palettes.get(kind, palettes["info"])
    box = (
        f'<div style="background:{bg};color:{fg};border:1px solid {border};border-radius:14px;'
        f'padding:13px 15px;margin-top:10px;font-size:13.5px;font-weight:700;line-height:1.45;">'
        f'{safe_text(text)}</div>'
    )
    (target if target is not None else st).markdown(box, unsafe_allow_html=True)


def pick_icon_style(name, keyword):
    text = f"{name} {keyword}".lower()
    groups = [
        (("헤드폰", "이어폰", "airpods", "스피커", "오디오", "마이크", "헤드셋"), "🎧", "#EEF4FF"),
        (("배터리", "충전", "케이블", "어댑터", "멀티탭"), "🔋", "#E8F8F0"),
        (("키보드", "마우스", "노트북", "모니터", "태블릿", "맥북", "거치대", "ssd", "rtx"), "💻", "#F3EEFF"),
        (("카메라", "액션캠", "고프로", "삼각대", "조명", "오즈모", "미러리스"), "📷", "#FFF4E5"),
        (("쿠션", "블러셔", "틴트", "컨실러", "클렌징", "미스트", "토너", "크림", "세럼", "립"), "💄", "#FFEFF4"),
        (("가습", "청소기", "매트", "담요", "히터", "제습", "토스터", "쓰레기통", "선풍기", "프라이팬"), "🏠", "#EBF8FF"),
        (("지갑", "케이스", "백팩", "가방", "캐리어", "여행", "스니커즈", "운동화", "선글라스", "모자"), "🎒", "#F0F4FF"),
    ]
    for keywords, icon, color in groups:
        if any(word in text for word in keywords):
            return icon, color
    return "🛍️", "#F2F4F6"


def inject_css():
    st.markdown("""
<style>
:root { color-scheme: light !important; }
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main {
  background:#F2F4F6 !important; color:#191F28 !important;
  font-family:-apple-system,BlinkMacSystemFont,"Pretendard","Noto Sans KR",sans-serif !important;
}
[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer { visibility:hidden; background:transparent !important; }
.block-container { max-width:500px !important; padding:1.2rem 1rem 4rem !important; }
.hero-card { background:#fff; border-radius:24px; padding:22px; box-shadow:0 2px 16px rgba(0,0,0,.04); margin-bottom:16px; }
.app-topbar { display:flex; justify-content:space-between; align-items:center; padding:2px 4px 12px; }
.app-title { font-size:20px; font-weight:800; color:#191F28; }
.hero-label { font-size:13px; font-weight:600; color:#8B95A1; margin-bottom:4px; }
.hero-big { font-size:32px; font-weight:800; color:#191F28; line-height:1.2; margin-bottom:10px; }
.hero-dots { display:flex; gap:14px; font-size:13px; font-weight:600; color:#4E5968; margin-bottom:14px; }
.hero-bar-box { background:#F4F6F8; border-radius:14px; padding:12px 14px; }
.hero-bar-top { display:flex; justify-content:space-between; font-size:12px; font-weight:600; color:#4E5968; margin-bottom:7px; }
.hero-bar-track { height:7px; background:#E5E8EB; border-radius:99px; overflow:hidden; margin-bottom:6px; }
.hero-bar-fill { height:100%; background:#3182F6; border-radius:99px; }
.hero-bar-sub { font-size:11.5px; color:#8B95A1; }
.item-meta { font-size:12px; font-weight:600; color:#8B95A1; padding-top:4px; }
.item-row { display:flex; align-items:center; gap:13px; margin:6px 0 14px; }
.item-icon { width:46px; height:46px; min-width:46px; border-radius:15px; display:flex; align-items:center; justify-content:center; font-size:22px; }
.item-info { flex:1; min-width:0; }
.item-name { font-size:15.5px; font-weight:700; color:#191F28; line-height:1.35; margin-bottom:3px; word-break:keep-all; }
.item-reason { font-size:12.5px; color:#6B7684; line-height:1.45; }
.shorts-badge { display:inline-block; background:#FFEFEF; color:#E11D48; font-size:10.5px; font-weight:700; padding:1px 6px; border-radius:6px; margin-left:5px; }
div[data-testid="stVerticalBlockBorderWrapper"] { background:#fff !important; border:none !important; border-radius:22px !important; box-shadow:0 2px 14px rgba(0,0,0,.04) !important; padding:18px 20px !important; margin-bottom:12px !important; }
/* Streamlit/BaseWeb 입력 위젯을 강제로 라이트 테마로 고정 */
[data-testid="stTextInput"], [data-testid="stTextArea"], [data-testid="stSelectbox"] { color:#191F28 !important; }
[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stTextInput"] div[data-baseweb="base-input"],
[data-testid="stTextArea"] div[data-baseweb="textarea"],
[data-testid="stTextArea"] div[data-baseweb="base-input"],
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[role="combobox"] {
  background-color:#FFFFFF !important;
  color:#191F28 !important;
  border-color:#D1D6DB !important;
  box-shadow:none !important;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] input,
[data-testid="stSelectbox"] span,
[data-testid="stSelectbox"] div[role="combobox"],
[data-testid="stSelectbox"] div[role="combobox"] * {
  background-color:#FFFFFF !important;
  color:#191F28 !important;
  -webkit-text-fill-color:#191F28 !important;
  caret-color:#191F28 !important;
  opacity:1 !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
  color:#8B95A1 !important;
  -webkit-text-fill-color:#8B95A1 !important;
  opacity:1 !important;
}
[data-testid="stSelectbox"] svg { fill:#4E5968 !important; color:#4E5968 !important; }
ul[data-baseweb="menu"], ul[data-baseweb="menu"] li,
div[data-baseweb="popover"], div[data-baseweb="popover"] * {
  background-color:#FFFFFF !important;
  color:#191F28 !important;
  -webkit-text-fill-color:#191F28 !important;
}
/* 브라우저 자동완성도 흰색으로 유지 */
input:-webkit-autofill, input:-webkit-autofill:hover, input:-webkit-autofill:focus {
  -webkit-box-shadow:0 0 0 1000px #FFFFFF inset !important;
  -webkit-text-fill-color:#191F28 !important;
}
/* 라벨, 체크박스, 슬라이더 숫자 가독성 */
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p,
[data-testid="stCheckbox"] label, [data-testid="stCheckbox"] span,
[data-testid="stSlider"] p, [data-testid="stSlider"] span,
[data-testid="stMarkdownContainer"] p { color:#191F28 !important; }
[data-testid="stSlider"] [data-testid="stThumbValue"],
[data-testid="stSlider"] div[data-testid="stSliderThumbValue"] {
  color:#C94F5D !important; -webkit-text-fill-color:#C94F5D !important; font-weight:700 !important;
}
.stButton > button, .stDownloadButton > button, .stLinkButton > a { border-radius:13px !important; font-weight:700 !important; min-height:40px !important; }
button[kind="primary"], a[kind="primary"] { background:#3182F6 !important; color:#fff !important; border:none !important; }
button[kind="secondary"] { background:#E5E8EB !important; color:#4E5968 !important; border:none !important; }
.stLinkButton > a { width:100% !important; display:flex !important; align-items:center !important; justify-content:center !important; font-size:12px !important; white-space:nowrap !important; }

/* ===== 최종 라이트 테마 오버라이드: 반드시 style 맨 마지막에 유지 ===== */
:root, html, body, [data-testid="stAppViewContainer"] {
  color-scheme: light !important;
}

/* 일반 글자와 버튼 글자 */
.stButton button, .stButton button *,
.stDownloadButton button, .stDownloadButton button * {
  color:#191F28 !important;
  -webkit-text-fill-color:#191F28 !important;
}
button[kind="primary"], button[data-testid="stBaseButton-primary"] {
  background:#4C82EE !important;
  border:1px solid #4C82EE !important;
  color:#FFFFFF !important;
}
button[kind="primary"] *, button[data-testid="stBaseButton-primary"] * {
  color:#FFFFFF !important;
  -webkit-text-fill-color:#FFFFFF !important;
}
button[kind="secondary"], button[data-testid="stBaseButton-secondary"],
.stDownloadButton button {
  background:#E9EDF2 !important;
  border:1px solid #E9EDF2 !important;
  color:#191F28 !important;
}

/* 링크 버튼: 쿠팡, 영상보기까지 검은색 제거 */
.stLinkButton > a,
a[data-testid="stBaseLinkButton-secondary"],
a[kind="secondary"] {
  background:#E8F3FF !important;
  border:1px solid #D4E6FF !important;
  color:#2F6FD6 !important;
}
.stLinkButton > a *,
a[data-testid="stBaseLinkButton-secondary"] *,
a[kind="secondary"] * {
  color:#2F6FD6 !important;
  -webkit-text-fill-color:#2F6FD6 !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-primary"],
.stLinkButton > a[kind="primary"] {
  background:#4C82EE !important;
  border-color:#4C82EE !important;
  color:#FFFFFF !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-primary"] *,
.stLinkButton > a[kind="primary"] * {
  color:#FFFFFF !important;
  -webkit-text-fill-color:#FFFFFF !important;
}

/* 검색창 */
[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stTextInput"] div[data-baseweb="base-input"],
[data-testid="stTextInput"] input {
  background:#FFFFFF !important;
  color:#191F28 !important;
  -webkit-text-fill-color:#191F28 !important;
  caret-color:#191F28 !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"] {
  border:1px solid #AEB6BF !important;
  border-radius:11px !important;
}
[data-testid="stTextInput"] input::placeholder {
  color:#8B95A1 !important;
  -webkit-text-fill-color:#8B95A1 !important;
  opacity:1 !important;
}
/* 검색 아이콘이 들어 있는 입력창 내부 장식 */
[data-testid="stTextInput"] div[data-baseweb="input"] > div,
[data-testid="stTextInput"] div[data-baseweb="input"] svg {
  background:#FFFFFF !important;
  color:#4E5968 !important;
  fill:#4E5968 !important;
}

/* 셀렉트박스 전체와 오른쪽 화살표 칸 */
[data-testid="stSelectbox"] div[data-baseweb="select"],
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[role="combobox"],
[data-testid="stSelectbox"] div[role="combobox"] > div,
[data-testid="stSelectbox"] div[role="combobox"] > div:last-child {
  background:#FFFFFF !important;
  color:#191F28 !important;
  -webkit-text-fill-color:#191F28 !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  border:1px solid #AEB6BF !important;
  border-radius:11px !important;
  overflow:hidden !important;
}
[data-testid="stSelectbox"] svg,
[data-testid="stSelectbox"] div[role="combobox"] svg {
  color:#4E5968 !important;
  fill:#4E5968 !important;
}

/* 비밀번호 눈 아이콘 오른쪽 칸 */
[data-testid="stTextInput"] button,
[data-testid="stTextInput"] button * {
  background:#FFFFFF !important;
  color:#4E5968 !important;
  fill:#4E5968 !important;
  -webkit-text-fill-color:#4E5968 !important;
}

/* textarea */
[data-testid="stTextArea"] div[data-baseweb="textarea"],
[data-testid="stTextArea"] div[data-baseweb="base-input"],
[data-testid="stTextArea"] textarea {
  background:#FFFFFF !important;
  color:#191F28 !important;
  -webkit-text-fill-color:#191F28 !important;
  caret-color:#191F28 !important;
}
[data-testid="stTextArea"] div[data-baseweb="textarea"] {
  border:1px solid #AEB6BF !important;
  border-radius:11px !important;
}

/* Expander와 드롭다운 */
[data-testid="stExpander"],
[data-testid="stExpander"] details,
[data-testid="stExpander"] summary {
  background:#FFFFFF !important;
  color:#191F28 !important;
}
[data-testid="stExpander"] summary *,
[data-testid="stExpander"] details * {
  color:#191F28 !important;
  -webkit-text-fill-color:#191F28 !important;
}
ul[data-baseweb="menu"], ul[data-baseweb="menu"] li,
div[data-baseweb="popover"], div[data-baseweb="popover"] * {
  background:#FFFFFF !important;
  color:#191F28 !important;
  -webkit-text-fill-color:#191F28 !important;
}

/* hover 상태에서도 검은색으로 돌아가지 않게 */
.stLinkButton > a:hover, .stButton button:hover,
.stDownloadButton button:hover {
  filter:brightness(.98) !important;
  color:inherit !important;
}


/* ===== 2026-11 최종 UI 정리: 검은 외곽선/분할선 제거 ===== */

/* 카드: 검은 1px 테두리 대신 토스형 옅은 경계와 그림자 */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background:#FFFFFF !important;
  border:1px solid #E7EBF0 !important;
  outline:none !important;
  border-radius:20px !important;
  box-shadow:0 3px 14px rgba(25,31,40,.055) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div {
  border:none !important;
  outline:none !important;
  box-shadow:none !important;
}

/* 검색창: 외곽선은 부모 하나에만 두고 내부 선을 모두 제거 */
[data-testid="stTextInput"] div[data-baseweb="input"] {
  background:#FFFFFF !important;
  border:1px solid #DDE2E8 !important;
  outline:none !important;
  border-radius:14px !important;
  box-shadow:0 1px 3px rgba(25,31,40,.035) !important;
  overflow:hidden !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"] > div,
[data-testid="stTextInput"] div[data-baseweb="base-input"],
[data-testid="stTextInput"] input,
[data-testid="stTextInput"] button {
  background:#FFFFFF !important;
  border:none !important;
  outline:none !important;
  box-shadow:none !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
  border-color:#8EB8FF !important;
  box-shadow:0 0 0 3px rgba(49,130,246,.12) !important;
}

/* 비밀번호 눈 아이콘: 별도 검은 상자처럼 보이지 않게 */
[data-testid="stTextInput"] button {
  min-width:42px !important;
  border-left:none !important;
  border-radius:0 14px 14px 0 !important;
  color:#6B7684 !important;
}
[data-testid="stTextInput"] button:hover {
  background:#F6F8FA !important;
}

/* 셀렉트박스: 오른쪽 검은 화살표 칸과 분할선 제거 */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[role="combobox"] {
  background:#FFFFFF !important;
  border:none !important;
  outline:none !important;
  box-shadow:none !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] {
  background:#FFFFFF !important;
  border:1px solid #DDE2E8 !important;
  outline:none !important;
  border-radius:14px !important;
  box-shadow:0 1px 3px rgba(25,31,40,.035) !important;
  overflow:hidden !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
  border-color:#8EB8FF !important;
  box-shadow:0 0 0 3px rgba(49,130,246,.12) !important;
}
[data-testid="stSelectbox"] div[role="combobox"] > div,
[data-testid="stSelectbox"] div[role="combobox"] > div:last-child {
  background:#FFFFFF !important;
  border:none !important;
  outline:none !important;
  box-shadow:none !important;
}

/* textarea: 검은 상단선/옆선 제거, 하나의 부드러운 테두리만 유지 */
[data-testid="stTextArea"] div[data-baseweb="textarea"] {
  background:#FFFFFF !important;
  border:1px solid #DDE2E8 !important;
  outline:none !important;
  border-radius:14px !important;
  box-shadow:0 1px 3px rgba(25,31,40,.035) !important;
  overflow:hidden !important;
}
[data-testid="stTextArea"] div[data-baseweb="textarea"] > div,
[data-testid="stTextArea"] div[data-baseweb="base-input"],
[data-testid="stTextArea"] textarea {
  background:#FFFFFF !important;
  border:none !important;
  outline:none !important;
  box-shadow:none !important;
}
[data-testid="stTextArea"] div[data-baseweb="textarea"]:focus-within {
  border-color:#8EB8FF !important;
  box-shadow:0 0 0 3px rgba(49,130,246,.12) !important;
}

/* 버튼: 검은 테두리 제거 및 일관된 높이 */
.stButton > button,
.stDownloadButton > button,
.stLinkButton > a {
  border:1px solid transparent !important;
  outline:none !important;
  box-shadow:none !important;
  border-radius:14px !important;
  min-height:46px !important;
}
button[kind="primary"],
button[data-testid="stBaseButton-primary"],
.stLinkButton > a[kind="primary"],
.stLinkButton > a[data-testid="stBaseLinkButton-primary"] {
  background:#4C82EE !important;
  border-color:#4C82EE !important;
}
button[kind="secondary"],
button[data-testid="stBaseButton-secondary"],
.stDownloadButton > button {
  background:#F2F4F6 !important;
  border-color:#F2F4F6 !important;
}
.stLinkButton > a[kind="secondary"],
.stLinkButton > a[data-testid="stBaseLinkButton-secondary"] {
  background:#E8F3FF !important;
  border-color:#E8F3FF !important;
}

/* 토글 주변의 불필요한 테두리 제거 */
[data-testid="stToggle"], [data-testid="stCheckbox"] {
  background:transparent !important;
  border:none !important;
  outline:none !important;
  box-shadow:none !important;
}

/* expander도 검은 외곽선 대신 연한 경계 */
[data-testid="stExpander"] details {
  border:1px solid #E7EBF0 !important;
  border-radius:14px !important;
  box-shadow:none !important;
  overflow:hidden !important;
}
[data-testid="stExpander"] summary {
  border:none !important;
  outline:none !important;
  box-shadow:none !important;
}

</style>
""", unsafe_allow_html=True)


def render_product_group(group):
    item = group["representative"]
    icon, bg = pick_icon_style(item["name"], item.get("keyword", ""))
    strong = group["youtuber_count"] >= 2
    badge = "🔥 교차 추천" if strong else "✅ 영상 근거 확인"
    with st.container(border=True):
        top_left, top_right = st.columns([7, 1])
        top_left.markdown(
            f'<div class="item-meta">{badge} · 유튜버 {group["youtuber_count"]}명 · 영상 {group["video_count"]}개</div>',
            unsafe_allow_html=True,
        )
        if top_right.button("✕", key=f'delete_group_{group["key"]}', help="이 상품의 추천 기록 전체 삭제"):
            st.session_state["pending_delete_group"] = group["key"]
        if st.session_state.get("pending_delete_group") == group["key"]:
            c1, c2 = st.columns(2)
            if c1.button("전체 삭제", key=f'confirm_group_{group["key"]}', type="primary", use_container_width=True):
                delete_ids = {x["id"] for x in group["recommendations"]}
                save_items([x for x in load_items() if x["id"] not in delete_ids])
                st.session_state.pop("pending_delete_group", None)
                st.rerun()
            if c2.button("취소", key=f'cancel_group_{group["key"]}', use_container_width=True):
                st.session_state.pop("pending_delete_group", None)
                st.rerun()

        st.markdown(
            f'<div class="item-row"><div class="item-icon" style="background:{bg}">{icon}</div>'
            f'<div class="item-info"><div class="item-name">{safe_text(item["name"])}</div>'
            f'<div class="item-reason">{safe_text(item.get("reason", ""))}</div></div></div>',
            unsafe_allow_html=True,
        )
        st.caption("추천: " + " · ".join(group["youtubers"][:5]) + (" 외" if len(group["youtubers"]) > 5 else ""))
        chips = [purchase_badge(x.get("purchase_type", "확인되지 않음")) for x in group["recommendations"]]
        st.caption(" · ".join(dict.fromkeys(chips)))

        query = quote(item["name"])
        b1, b2 = st.columns(2)
        b1.link_button("네이버 가격 비교", f"https://search.shopping.naver.com/search/all?query={query}&sort=price_asc", type="primary", use_container_width=True)
        b2.link_button("쿠팡 가격 확인", f"https://www.coupang.com/np/search?q={query}&sorter=salePriceAsc", use_container_width=True)

        with st.expander(f"추천 근거·영상 {len(group['recommendations'])}건 보기"):
            pros = list(dict.fromkeys(v for x in group["recommendations"] for v in x.get("pros", [])))[:4]
            cons = list(dict.fromkeys(v for x in group["recommendations"] for v in x.get("cons", [])))[:4]
            if pros:
                st.markdown("**좋았던 점**")
                for value in pros:
                    st.write(f"• {value}")
            if cons:
                st.markdown("**아쉬운 점**")
                for value in cons:
                    st.write(f"• {value}")
            if not pros and not cons:
                st.caption("기존 데이터에는 장단점 정보가 없습니다. 새로 수집되는 상품부터 표시됩니다.")
            for index, rec in enumerate(group["recommendations"], 1):
                evidence_label = "근거 확실" if rec.get("confidence", 0) >= 0.85 else "확인 필요"
                st.markdown(f"**{index}. {safe_text(rec['youtuber'])}** · {evidence_label} · {rec.get('confidence', 0):.0%}")
                if rec.get("evidence"):
                    st.caption(rec["evidence"])
                st.link_button(
                    f"{rec.get('timestamp', '00:00')}부터 영상 보기",
                    rec["youtube_url"],
                    key=f'video_{group["key"]}_{rec["id"]}',
                    use_container_width=True,
                )


def render_collection_result(status_box, added, stats, errors, empty_message=""):
    if empty_message and not added:
        render_banner(status_box, empty_message, "info")
    elif errors and not added:
        render_banner(status_box, f"완료했지만 신규 상품이 없어요. 오류 {len(errors)}건이 기록됐습니다.", "warning")
    else:
        render_banner(
            status_box,
            f"완료! 검색 영상 {stats['found']}개, 분석 가능 {stats['bundle_success']}개, "
            f"AI 추출 {stats['extracted']}개, 신규 저장 {stats['added']}개예요.",
            "success",
        )
    if added:
        for item in added:
            st.write(f"• **{item['name']}** ({item['youtuber']} · `{item['timestamp']}` · {item['confidence']:.0%})")
    if errors:
        with st.expander(f"오류 상세 {len(errors)}건"):
            for error in errors[:20]:
                st.caption(error)


inject_css()
if "nav" not in st.session_state:
    st.session_state.nav = "꿀템 홈"

db = load_items()
youtuber_count = len({x["youtuber"] for x in db if x.get("youtuber")})
fill_pct = min(100, int(len(db) / 200 * 100)) if db else 0

st.markdown(
    '<div class="app-topbar"><div class="app-title">‹ &nbsp; 꿀템 다나와</div>'
    '<div style="font-size:13px;font-weight:600;color:#8B95A1">유튜버 추천템 큐레이션</div></div>',
    unsafe_allow_html=True,
)
st.markdown(f"""
<div class="hero-card">
  <div class="hero-label">모아둔 유튜버 검증 꿀템</div>
  <div class="hero-big">{len(db):,}개</div>
  <div class="hero-dots"><div><span style="color:#3182F6">●</span> 유튜버 <b>{youtuber_count}명</b></div><div><span style="color:#00C471">●</span> 최저가 비교 <b style="color:#3182F6">실시간 링크</b></div></div>
  <div class="hero-bar-box"><div class="hero-bar-top"><span>목표 DB 200개</span><span style="color:#3182F6">{fill_pct}%</span></div>
  <div class="hero-bar-track"><div class="hero-bar-fill" style="width:{fill_pct}%"></div></div>
  <div class="hero-bar-sub">상품명으로 네이버쇼핑·쿠팡 낮은 가격순 검색 결과를 열어요.</div></div>
</div>
""", unsafe_allow_html=True)

nav_cols = st.columns(3)
for column, label in zip(nav_cols, ("꿀템 홈", "자동 수집", "설정")):
    if column.button(label, key=f"nav_{label}", type="primary" if st.session_state.nav == label else "secondary", use_container_width=True):
        st.session_state.nav = label
        st.rerun()

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

if st.session_state.nav == "꿀템 홈":
    youtubers = ["전체 유튜버"] + sorted({x["youtuber"] for x in db if x.get("youtuber")})
    c1, c2 = st.columns([1.55, 1.1])
    keyword = c1.text_input("검색", placeholder="🔍 물건 검색", label_visibility="collapsed")
    selected = c2.selectbox("유튜버", youtubers, label_visibility="collapsed")
    filtered = [x for x in db if selected == "전체 유튜버" or x["youtuber"] == selected]
    if keyword:
        needle = keyword.lower()
        filtered = [x for x in filtered if needle in f"{x['name']} {x['keyword']} {x['reason']} {x['youtuber']}".lower()]
    groups = group_products(filtered)
    only_cross = st.toggle("🔥 여러 유튜버가 추천한 검증템만 보기", value=False)
    if only_cross:
        groups = [g for g in groups if g["youtuber_count"] >= 2]
    st.caption(f"상품 {len(groups)}개 · 추천 기록 {len(filtered)}건")
    for group in groups:
        render_product_group(group)
    if not groups:
        with st.container(border=True):
            st.markdown('<div class="item-name">조건에 맞는 추천템이 아직 없어요.</div>', unsafe_allow_html=True)

elif st.session_state.nav == "자동 수집":
    if not get_openrouter_key():
        render_banner(None, "설정 탭에서 OpenRouter 키를 이번 세션에 입력하거나 Streamlit secrets에 등록해 주세요.", "warning")

    with st.container(border=True):
        st.markdown('<div class="item-name">🔥 유튜브 전체 추천템 자동 발굴</div><div class="item-reason">주제별 검색어로 일반 영상과 Shorts를 찾아 제품 근거가 충분한 항목만 저장해요.</div>', unsafe_allow_html=True)
        if st.button("🚀 자동 발굴 실행", type="primary", use_container_width=True):
            status_box, bar = st.empty(), st.progress(0)
            if not get_openrouter_key():
                render_banner(status_box, "OpenRouter API 키가 없습니다.", "error")
            else:
                added, stats, errors, empty_message = collect_parallel_batch(AUTO_DISCOVERY_QUERIES, 3, False, status_box, bar)
                render_collection_result(status_box, added, stats, errors, empty_message)

    with st.container(border=True):
        st.markdown('<div class="item-name">🌐 대표 유튜버 고속 일괄 수집</div><div class="item-reason">공식 채널명과 일치하는 검색 결과만 우선 분석해요.</div>', unsafe_allow_html=True)
        list_text = st.text_area("수집할 유튜버", value="\n".join(DEFAULT_YOUTUBER_LIST), height=150, label_visibility="collapsed")
        per_limit = st.slider("유튜버당 검색 영상 수", 2, 5, 2)
        if st.button("✨ 리스트 전체 수집", type="primary", use_container_width=True):
            status_box, bar = st.empty(), st.progress(0)
            targets = [x.strip() for x in list_text.splitlines() if x.strip()]
            if not get_openrouter_key():
                render_banner(status_box, "OpenRouter API 키가 없습니다.", "error")
            elif not targets:
                render_banner(status_box, "수집할 유튜버를 한 명 이상 입력해 주세요.", "warning")
            else:
                added, stats, errors, empty_message = collect_parallel_batch(targets, per_limit, True, status_box, bar)
                render_collection_result(status_box, added, stats, errors, empty_message)

    with st.container(border=True):
        st.markdown('<div class="item-name">🔍 특정 유튜버·키워드 수집</div>', unsafe_allow_html=True)
        query = st.text_input("키워드", placeholder="예: 지냐, 곽튜브, 데스크테리어")
        official = st.checkbox("공식 채널만 수집", value=True)
        limit = st.slider("검색 영상 수", 2, 8, 4)
        if st.button("선택 항목 수집", type="primary", use_container_width=True):
            status_box, bar = st.empty(), st.progress(0)
            if not query.strip():
                render_banner(status_box, "검색할 유튜버나 키워드를 입력해 주세요.", "warning")
            elif not get_openrouter_key():
                render_banner(status_box, "OpenRouter API 키가 없습니다.", "error")
            else:
                added, stats, errors, empty_message = collect_parallel_batch([query.strip()], limit, official, status_box, bar)
                render_collection_result(status_box, added, stats, errors, empty_message)

elif st.session_state.nav == "설정":
    with st.container(border=True):
        st.markdown('<div class="item-name">⚡ OpenRouter API 키</div><div class="item-reason">보안을 위해 입력 키는 서버 파일에 저장하지 않고 현재 Streamlit 세션에서만 사용해요. 운영용 키는 .streamlit/secrets.toml에 넣으세요.</div>', unsafe_allow_html=True)
        new_key = st.text_input("OpenRouter API 키", type="password", placeholder="sk-or-v1-...", label_visibility="collapsed")
        if st.button("이번 세션에 키 적용", type="primary", use_container_width=True):
            key = new_key.strip()
            if not key.startswith("sk-or-") or not key.isascii():
                render_banner(None, "sk-or-로 시작하는 올바른 ASCII 키를 입력해 주세요.", "error")
            else:
                st.session_state.openrouter_key = key
                render_banner(None, f"이번 세션에 키가 적용됐어요. 끝 4자리: {key[-4:]}", "success")

    with st.container(border=True):
        st.markdown(f'<div class="item-name">🗂️ DB 백업 및 관리</div><div class="item-reason">현재 {len(db)}개 저장. Community Cloud 재시작 시 로컬 파일 변경분이 사라질 수 있으니 주기적으로 다운로드하세요.</div>', unsafe_allow_html=True)
        st.download_button("📥 items.json 다운로드", json.dumps(db, ensure_ascii=False, indent=2), "items.json", "application/json", use_container_width=True)
        history = load_history()
        st.download_button("📥 visited_history.json 다운로드", json.dumps(history, ensure_ascii=False, indent=2), "visited_history.json", "application/json", use_container_width=True)
        if st.button("수집 이력 초기화", use_container_width=True):
            save_history({"videos": {}, "queries": {}})
            render_banner(None, "수집 이력을 초기화했어요.", "success")
        if st.button("기본 샘플 DB로 초기화", use_container_width=True):
            save_items(INITIAL_SEED_DB)
            st.rerun()

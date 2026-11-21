import streamlit as st
import json, os, re, urllib.request
from urllib.parse import urlparse, parse_qs, quote
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types

DEFAULT_API_KEY = ""
DB_FILE = "items.json"
KEY_FILE = "api_key.txt"

st.set_page_config(page_title="꿀템 다나와", page_icon="🛍️", layout="centered")

def get_api_key():
    try:
        if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"].strip():
            return st.secrets["GEMINI_API_KEY"].strip()
    except Exception:
        pass
    if os.path.exists(KEY_FILE):
        saved = open(KEY_FILE, "r", encoding="utf-8").read().strip()
        if saved:
            return saved
    return DEFAULT_API_KEY

if "nav" not in st.session_state:
    st.session_state.nav = "꿀템 홈"
if "collect_mode" not in st.session_state:
    st.session_state.collect_mode = "ai" if get_api_key() else "local"

# === 토스 스타일 라이트 앱 UI ===
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

:root {
    color-scheme: light !important;
    --background-color: #F2F4F6 !important;
    --secondary-background-color: #FFFFFF !important;
    --text-color: #191F28 !important;
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main {
    background-color: #F2F4F6 !important;
    color: #191F28 !important;
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
}

[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {
    background: transparent !important;
    visibility: hidden;
}

.block-container {
    max-width: 480px !important;
    padding-top: 1.2rem !important;
    padding-bottom: 4rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label {
    color: #191F28 !important;
}

.hero-card {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 22px 22px 20px 22px;
    box-shadow: 0 2px 16px rgba(0, 0, 0, 0.04);
    margin-bottom: 16px;
}

div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    background-color: #FFFFFF !important;
    border: none !important;
    outline: none !important;
    border-radius: 22px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
    box-shadow: 0 2px 14px rgba(0, 0, 0, 0.04) !important;
    padding: 18px 20px !important;
    margin-bottom: 12px !important;
}

div[data-testid="stTextInputRootElement"],
div[data-testid="stTextInputRootElement"] > div,
div[data-baseweb="input"],
div[data-baseweb="base-input"],
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    border: 1.5px solid #E5E8EB !important;
    border-radius: 14px !important;
    color: #191F28 !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02) !important;
}
div[data-testid="stTextInputRootElement"]:focus-within {
    border-color: #3182F6 !important;
}
div[data-testid="stTextInputRootElement"] input,
div[data-baseweb="input"] input,
div[data-testid="stSelectbox"] span,
div[data-testid="stSelectbox"] div {
    background-color: transparent !important;
    color: #191F28 !important;
    -webkit-text-fill-color: #191F28 !important;
    font-size: 14px !important;
    font-weight: 500 !important;
}
div[data-testid="stTextInputRootElement"] input::placeholder {
    color: #8B95A1 !important;
    -webkit-text-fill-color: #8B95A1 !important;
}
div[data-testid="stSelectbox"] svg {
    fill: #4E5968 !important;
}
ul[data-baseweb="menu"],
ul[data-baseweb="menu"] li {
    background-color: #FFFFFF !important;
    color: #191F28 !important;
}

.stButton > button {
    border-radius: 13px !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    border: none !important;
    min-height: 40px !important;
    transition: all 0.15s ease !important;
}

button[data-testid="stBaseButton-primary"],
button[data-testid="baseButton-primary"],
button[kind="primary"] {
    background-color: #FFFFFF !important;
    color: #191F28 !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06) !important;
}
button[data-testid="stBaseButton-primary"] p,
button[kind="primary"] p {
    color: #191F28 !important;
}

button[data-testid="stBaseButton-secondary"],
button[data-testid="baseButton-secondary"],
button[kind="secondary"] {
    background-color: #E5E8EB !important;
    color: #6B7684 !important;
    box-shadow: none !important;
}
button[data-testid="stBaseButton-secondary"] p,
button[kind="secondary"] p {
    color: #6B7684 !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-primary"],
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] {
    background-color: #3182F6 !important;
    color: #FFFFFF !important;
    box-shadow: 0 3px 10px rgba(49, 130, 246, 0.25) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-primary"] p,
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] p {
    color: #FFFFFF !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-primary"]:hover {
    background-color: #1B64DA !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-secondary"],
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="secondary"] {
    background-color: #F2F4F6 !important;
    color: #6B7684 !important;
    min-height: 32px !important;
    padding: 4px 10px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-secondary"] p {
    color: #6B7684 !important;
}

.stLinkButton > a {
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 12.5px !important;
    text-decoration: none !important;
    border: none !important;
    width: 100% !important;
    min-height: 38px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 8px !important;
    white-space: nowrap !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-primary"],
.stLinkButton > a[kind="primary"] {
    background-color: #3182F6 !important;
    color: #FFFFFF !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-primary"] p,
.stLinkButton > a[kind="primary"] p {
    color: #FFFFFF !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-secondary"],
.stLinkButton > a[kind="secondary"] {
    background-color: #E8F3FF !important;
    color: #3182F6 !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-secondary"] p,
.stLinkButton > a[kind="secondary"] p {
    color: #3182F6 !important;
}

div[data-testid="stSlider"] div[role="slider"] {
    background-color: #3182F6 !important;
    border: 2px solid #FFFFFF !important;
    box-shadow: 0 2px 6px rgba(49, 130, 246, 0.4) !important;
}
div[data-testid="stSliderThumbValue"] {
    color: #3182F6 !important;
    font-weight: 700 !important;
}
div[data-testid="stSliderTickBarMin"],
div[data-testid="stSliderTickBarMax"] {
    color: #8B95A1 !important;
}

.app-topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 2px 4px 12px 4px;
}
.app-title {
    font-size: 20px;
    font-weight: 800;
    color: #191F28;
    letter-spacing: -0.4px;
}
.hero-label {
    font-size: 13px;
    font-weight: 600;
    color: #8B95A1;
    margin-bottom: 4px;
}
.hero-big {
    font-size: 32px;
    font-weight: 800;
    color: #191F28;
    letter-spacing: -0.8px;
    line-height: 1.2;
    margin-bottom: 10px;
}
.hero-dots {
    display: flex;
    gap: 14px;
    font-size: 13px;
    font-weight: 600;
    color: #4E5968;
    margin-bottom: 14px;
}
.dot-blue { color: #3182F6; margin-right: 4px; }
.dot-green { color: #00C471; margin-right: 4px; }
.hero-bar-box {
    background-color: #F4F6F8;
    border-radius: 14px;
    padding: 12px 14px;
}
.hero-bar-top {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    font-weight: 600;
    color: #4E5968;
    margin-bottom: 7px;
}
.hero-bar-track {
    width: 100%;
    height: 7px;
    background-color: #E5E8EB;
    border-radius: 99px;
    overflow: hidden;
    margin-bottom: 6px;
}
.hero-bar-fill {
    height: 100%;
    background-color: #3182F6;
    border-radius: 99px;
}
.hero-bar-sub {
    font-size: 11.5px;
    color: #8B95A1;
}
.field-label {
    font-size: 13px;
    font-weight: 700;
    color: #4E5968;
    margin: 12px 0 6px 2px;
}
.item-meta {
    font-size: 12px;
    font-weight: 600;
    color: #8B95A1;
    padding-top: 4px;
}
.item-row {
    display: flex;
    align-items: center;
    gap: 13px;
    margin: 6px 0 14px 0;
}
.item-icon {
    width: 46px;
    height: 46px;
    min-width: 46px;
    border-radius: 15px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
}
.item-info {
    flex: 1;
    min-width: 0;
}
.item-name {
    font-size: 15.5px;
    font-weight: 700;
    color: #191F28;
    line-height: 1.35;
    margin-bottom: 3px;
    word-break: keep-all;
}
.item-reason {
    font-size: 12.5px;
    color: #6B7684;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# === 비상품(문장/구매주의/배송안내/음원문구/공지) 차단 ===
NON_PRODUCT_KEYWORDS = (
    "인트로", "오프닝", "마무리", "아웃트로", "총평", "결론", "구독", "이벤트",
    "당첨", "발표", "공지", "커뮤니티", "종료", "마감", "쿠키", "예고", "목차",
    "근황", "소감", "질문", "후기", "원칙", "고능", "PD", "피디", "출연",
    "브이로그", "일상", "추천", "꿀템", "필수템", "가성비템", "모아옴", "모음",
    "총정리", "하이라이트", "문의", "비즈니스", "협찬", "광고", "인스타", "유튜브",
    "채널", "타임라인", "챕터", "링크", "바로가기", "프로필", "멤버십",
    "할인코드", "쿠폰", "최종가", "할인가", "혜택가", "정상가", "체감가",
    "해외직구", "직구", "로컬", "카테고리", "적용", "카드", "결제", "무료배송",
    "진행기간", "한국시간", "항공권", "숙박", "예약", "고르는", "방법", "비교",
    "배송", "소요", "선택해서", "구매하세요", "포함되어", "미포함", "옵션",
    "free download", "watch more", "ncs", "stream", "download"
)

def is_non_product(text, youtuber=""):
    t = (text or "").strip()
    t_low = t.lower()
    if not t or len(t) < 2 or len(t) > 42:
        return True
    # 1) 기호 시작, 의문문/감탄문 차단
    if t[0] in ("=", "👉", "※", "→", "▶", "|", "-", "•") or "?" in t or "!" in t:
        return True
    # 2) 문장 종결어미/부정·안내 서술어/관형형 구조 차단
    if re.search(r"(?:합니다|입니다|됩니다|있습니다|없습니다|않습니다|하세요|주세요|구매하세요|바랍니다|해요|예요|이에요|에요|가요|네요|같아요|되네|안해|소요|가능|불가|제외|ㄷㄷ|ㅋㅋ|ㅎㅎ|ㅠㅠ)$", t):
        return True
    if re.search(r"(?:같은|하는|되는|있는|없는|빠지는|넘어질|살펴볼|알아볼|고르는|포함되어)\s", t):
        return True
    if t.endswith((" 제품", " 상품", " 아이템", " 추천", " 후기", " 리뷰", " 소개")):
        return True
    if re.match(r"^(?:그래서|왜|어떻게|가장|제일|진짜|정말|드디어|이제|오늘|이번|옵션을)\s", t):
        return True
    # 3) 날짜/시간/가격/배송기간 단독 표기 차단
    if re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일|\d{1,2}\s*일\s*\([월화수목금토일]\)|\d{1,2}\s*시\s*\d{0,2}|\d+\s*[-~]\s*\d+\s*일", t):
        return True
    if re.fullmatch(r"(?:약\s*)?(?:USD|KRW|US\$|\$|₩)?\s*[\d,\.]+\s*(?:원|달러|불|USD|KRW|%)?", t, re.IGNORECASE):
        return True
    if re.match(r"^(?:약\s*)?[\$\₩]\s*\d", t):
        return True
    # 4) 괄호 단독/불완전 문구 차단
    if re.fullmatch(r"[\(\[\{〈《「『].*[\)\]\}\〉》」』]", t):
        return True
    if t.count("(") != t.count(")") or t.count("[") != t.count("]"):
        return True
    if len(re.findall(r"[가-힣A-Za-z0-9]", t)) < 2:
        return True
    if any(w in t_low for w in NON_PRODUCT_KEYWORDS):
        return True
    return False

def pick_icon_style(name, keyword):
    text = f"{name} {keyword}".lower()
    if any(k in text for k in ("헤드폰", "이어폰", "airpods", "스피커", "오디오", "마이크")):
        return "🎧", "#EEF4FF"
    if any(k in text for k in ("배터리", "충전", "케이블", "어댑터", "멀티탭")):
        return "🔋", "#E8F8F0"
    if any(k in text for k in ("키보드", "마우스", "노트북", "모니터", "태블릿", "맥북", "거치대", "책상", "데스크")):
        return "💻", "#F3EEFF"
    if any(k in text for k in ("카메라", "액션캠", "고프로", "삼각대", "조명")):
        return "📷", "#FFF4E5"
    if any(k in text for k in ("크림", "선크림", "클렌징", "멀티밤", "가습", "청소기", "매트", "담요", "난로", "양말", "히터")):
        return "🏠", "#FFEFF4"
    if any(k in text for k in ("지갑", "케이스", "백팩", "가방", "트렁크", "여행")):
        return "🎒", "#EBF8FF"
    return "🛍️", "#F2F4F6"

def load_items():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_items(items):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def add_unique_items(new_items):
    db = load_items()
    seen = {(i.get("name", "").strip().lower(), i.get("youtuber", "").strip().lower()) for i in db}
    added = []
    for item in new_items:
        key = (item.get("name", "").strip().lower(), item.get("youtuber", "").strip().lower())
        if key[0] and key not in seen:
            db.append(item)
            seen.add(key)
            added.append(item)
    save_items(db)
    return added

def extract_video_id(url):
    if not url:
        return None
    p = urlparse(url)
    if p.hostname in ("youtu.be", "www.youtu.be"):
        return p.path.lstrip("/").split("/")[0]
    if p.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if p.path == "/watch":
            return parse_qs(p.query).get("v", [None])[0]
        if p.path.startswith(("/shorts/", "/embed/")):
            parts = p.path.split("/")
            return parts[2] if len(parts) > 2 else None
    return None

def search_youtube_videos(query, limit=5):
    url = f"https://www.youtube.com/results?search_query={quote(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"})
    html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore")
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html) or re.search(r"ytInitialData\s*=\s*(\{.*?\});", html)
    if not m:
        return []
    data = json.loads(m.group(1))
    results, seen = [], set()

    def walk(node):
        if len(results) >= limit:
            return
        if isinstance(node, dict):
            if "videoRenderer" in node:
                vr = node["videoRenderer"]
                vid = vr.get("videoId", "")
                if isinstance(vid, str) and len(vid) == 11 and vid not in seen:
                    seen.add(vid)
                    t_runs = vr.get("title", {}).get("runs", [])
                    o_runs = vr.get("ownerText", {}).get("runs", []) or vr.get("longBylineText", {}).get("runs", [])
                    results.append({
                        "video_id": vid,
                        "title": t_runs[0].get("text", "제목 없음") if t_runs else "제목 없음",
                        "youtuber": o_runs[0].get("text", "유튜버") if o_runs else "유튜버",
                    })
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return results

def _find_desc_in_json(node):
    if isinstance(node, dict):
        if "attributedDescriptionBodyText" in node:
            c = node["attributedDescriptionBodyText"].get("content", "")
            if c:
                return c
        if "descriptionBodyText" in node:
            runs = node["descriptionBodyText"].get("runs", [])
            if runs:
                return "".join(r.get("text", "") for r in runs)
        for v in node.values():
            found = _find_desc_in_json(v)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_desc_in_json(item)
            if found:
                return found
    return ""

def fetch_transcript_text(video_id):
    try:
        ytt = YouTubeTranscriptApi()
        if hasattr(ytt, "fetch"):
            fetched = ytt.fetch(video_id, languages=["ko", "en"])
            return "\n".join([f"[{int(s.start)//60:02d}:{int(s.start)%60:02d}] {s.text}" for s in fetched])
    except Exception:
        pass
    try:
        raw = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
        return "\n".join([f"[{int(s['start'])//60:02d}:{int(s['start'])%60:02d}] {s['text']}" for s in raw])
    except Exception:
        return ""

def fetch_video_bundle(video_id, youtuber_hint="유튜버", title_hint="", need_transcript=True):
    title, desc, youtuber = title_hint, "", youtuber_hint

    try:
        payload = json.dumps({
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20261101.00.00",
                    "hl": "ko",
                    "gl": "KR"
                }
            },
            "videoId": video_id
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://www.youtube.com/youtubei/v1/next",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-YouTube-Client-Name": "1",
                "X-YouTube-Client-Version": "2.20261101.00.00",
            }
        )
        next_data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore"))
        desc = _find_desc_in_json(next_data)
    except Exception:
        pass

    if not desc:
        try:
            payload = json.dumps({
                "context": {
                    "client": {
                        "clientName": "IOS",
                        "clientVersion": "19.45.4",
                        "deviceMake": "Apple",
                        "deviceModel": "iPhone16,2",
                        "hl": "ko",
                        "gl": "KR"
                    }
                },
                "videoId": video_id
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://www.youtube.com/youtubei/v1/player",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "com.google.ios.youtube/19.45.4 (iPhone16,2; U; CPU iOS 18_1 like Mac OS X)",
                    "X-YouTube-Client-Name": "5",
                    "X-YouTube-Client-Version": "19.45.4",
                }
            )
            res_data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore"))
            details = res_data.get("videoDetails", {})
            if details:
                title = details.get("title", title)
                desc = details.get("shortDescription", "")
                youtuber = details.get("author", youtuber)
        except Exception:
            pass

    transcript = fetch_transcript_text(video_id) if (need_transcript or len(desc) < 150) else ""

    return {"video_id": video_id, "youtuber": youtuber, "title": title, "desc": desc, "transcript": transcript[:4500]}

# === [화이트리스트 방식] 쇼핑몰 링크가 붙은 줄 중 실제 제품명만 추출 ===
def extract_products_from_links(bundles):
    extracted = []
    for b in bundles:
        vid = b["video_id"]
        yt = b["youtuber"]
        title = b["title"]
        raw_lines = [ln.strip() for ln in b["desc"].splitlines() if ln.strip()]

        ts_list = []
        for ln in raw_lines:
            m_ts = re.match(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s+(.+)$", ln)
            if m_ts:
                hh = int(m_ts.group(1) or 0)
                mm, ss = int(m_ts.group(2)), int(m_ts.group(3))
                sec_val = hh * 3600 + mm * 60 + ss
                if sec_val > 0:
                    ts_list.append((sec_val, m_ts.group(4).strip()))

        for idx, raw_ln in enumerate(raw_lines):
            if "@" in raw_ln or raw_ln.startswith("#"):
                continue

            if "http" not in raw_ln:
                continue

            raw_low = raw_ln.lower()
            if any(bad in raw_low for bad in (
                "instagram.com", "youtube.com/@", "youtu.be", "t.me", "kakao",
                "ncs", "stream", "download", "이벤트", "공지", "당첨"
            )):
                continue

            ln = re.sub(r"https?://\S+", "", raw_ln).strip()
            ln = re.sub(r"[\(\[\{]\s*[\)\]\}]", "", ln).strip()

            if not ln and idx > 0:
                prev_ln = raw_lines[idx - 1]
                if "http" not in prev_ln and not re.match(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s+", prev_ln):
                    ln = prev_ln

            if not ln or len(ln) < 2:
                continue

            candidate = ln
            category = ""
            m_colon = re.match(r"^([^:：]{1,30})\s*[:：]\s*(.*)$", ln)
            if m_colon:
                left = m_colon.group(1).strip()
                right = m_colon.group(2).strip()
                if not right:
                    candidate = left
                else:
                    category = left
                    candidate = right

            candidate = re.sub(r"^[\-\•\*\▶\▸\✔\✓\d\.\)\]]+\s*", "", candidate).strip()
            candidate = re.split(r"\s*(?:👉|▶|→|\|)\s*", candidate)[0].strip()

            if is_non_product(candidate, yt):
                continue

            sec = 0
            for t_sec, t_label in ts_list:
                if any(tok and len(tok) >= 2 and tok in t_label for tok in candidate.split()[:2]):
                    sec = t_sec
                    break

            mm, ss = divmod(sec, 60)
            cat_label = category if (category and not category.isdigit()) else "추천"
            extracted.append({
                "name": candidate,
                "keyword": cat_label if cat_label != "추천" else candidate.split()[0],
                "youtuber": yt,
                "reason": f"'{title}'에서 {yt}가 구매 링크와 함께 소개한 제품",
                "timestamp": f"{mm:02d}:{ss:02d}",
                "youtube_url": f"https://youtu.be/{vid}?t={sec}",
            })

    return extracted

# === [AI 정밀 분석] 자막 + 설명란을 모두 읽어 실제 브랜드·제품명만 추출 ===
def analyze_batch_with_gemini(bundles):
    api_key = get_api_key()
    if not api_key or not api_key.isascii():
        raise RuntimeError("API 키가 설정되지 않았습니다. [설정] 탭에서 Gemini API 키를 먼저 저장해 주세요.")

    blocks = []
    for b in bundles:
        blocks.append(
            f"=== VIDEO_ID: {b['video_id']} | YOUTUBER: {b['youtuber']} ===\n"
            f"[영상 제목] {b['title']}\n"
            f"[설명란]\n{b['desc'][:2000]}\n"
            f"[영상 자막(대본)]\n{b['transcript']}"
        )

    prompt = f"""너는 유튜브 쇼핑 큐레이터야. 아래 영상의 [설명란]과 [영상 자막]을 모두 읽고, 실제로 네이버 쇼핑이나 쿠팡에서 검색해 구매할 수 있는 **'진짜 제품명(브랜드명 + 정확한 상품명)'**만 골라서 JSON 배열로 답해줘.

절대 규칙:
1. 유튜버가 목차에 적어둔 어그로 문구나 배송·옵션·구매주의 문구("그래서 얼마에요", "옵션을 ... 구매하세요", "배송 10-14일 소요", "어댑터는 포함되어있지 않습니다", "Free Download/Stream")는 절대 쓰지 마! 반드시 해당 타임스탬프 전후의 [영상 자막]을 읽어서 실제 소개된 **브랜드와 정확한 제품명**만 적어줘.
2. 자막에도 브랜드·모델명이 안 나와서 쇼핑몰 검색이 불가능하면 그 항목은 과감히 버려.
3. 이벤트, 행사 기간, 할인 금액, 음원/채널명은 절대 포함하지 마.
4. 키 이름: "video_id", "youtuber", "name"(쇼핑몰 검색용 정확한 브랜드+제품명), "keyword"(품목명), "reason"(추천 이유 한 줄 요약), "start_sec"(등장 시작 초 정수, 모르면 0)

{chr(10).join(blocks)}"""

    client = genai.Client(api_key=api_key, http_options={"timeout": 25000})
    last_err = None
    res = None
    for model_name in ("gemini-2.5-flash", "gemini-2.0-flash"):
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            break
        except Exception as e:
            last_err = e

    if res is None:
        raise RuntimeError(f"Gemini API 호출 실패: {last_err}")

    cleaned = re.sub(r"^```json|```$", "", res.text.strip()).strip()
    out = []
    for item in json.loads(cleaned):
        vid = item.get("video_id") or bundles[0]["video_id"]
        sec = int(item.get("start_sec", 0))
        mm, ss = divmod(sec, 60)
        name = item.get("name", "").strip()
        yt = item.get("youtuber", bundles[0]["youtuber"]).strip()
        if name and not is_non_product(name, yt):
            out.append({
                "name": name,
                "keyword": item.get("keyword", "").strip(),
                "youtuber": yt,
                "reason": item.get("reason", "").strip(),
                "timestamp": f"{mm:02d}:{ss:02d}",
                "youtube_url": f"https://youtu.be/{vid}?t={sec}",
            })
    return out

def render_toss_card(item, idx):
    icon, bg_color = pick_icon_style(item.get("name", ""), item.get("keyword", ""))
    with st.container(border=True):
        top_l, top_r = st.columns([6.5, 1])
        with top_l:
            st.markdown(f"<div class='item-meta'>{item['youtuber']} · {item['timestamp']} 등장</div>", unsafe_allow_html=True)
        with top_r:
            if st.button("✕", key=f"del_{idx}_{item['name']}", help="목록에서 삭제"):
                db = [x for x in load_items() if not (x.get("name") == item.get("name") and x.get("youtuber") == item.get("youtuber"))]
                save_items(db)
                st.rerun()

        st.markdown(f"""
        <div class="item-row">
            <div class="item-icon" style="background-color: {bg_color};">{icon}</div>
            <div class="item-info">
                <div class="item-name">{item['name']}</div>
                <div class="item-reason">{item['reason']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        q = quote(item["name"])
        b1, b2, b3 = st.columns(3)
        b1.link_button("네이버 최저가", f"https://search.shopping.naver.com/search/all?query={q}&sort=price_asc", type="primary", use_container_width=True)
        b2.link_button("쿠팡 최저가", f"https://www.coupang.com/np/search?q={q}&sorter=salePriceAsc", use_container_width=True)
        b3.link_button("▶️ 영상보기", item["youtube_url"], use_container_width=True)

# === 상단 앱 헤더 ===
db = load_items()
yt_count = len({i.get("youtuber", "") for i in db if i.get("youtuber")})

st.markdown("""
<div class="app-topbar">
    <div class="app-title">‹ &nbsp; 꿀템 다나와</div>
    <div style="font-size:13px; font-weight:600; color:#8B95A1;">유튜버 추천템</div>
</div>
""", unsafe_allow_html=True)

# === 상단 요약 대시보드 카드 ===
fill_pct = min(100, int((len(db) / 100) * 100)) if db else 0
st.markdown(f"""
<div class="hero-card">
    <div class="hero-label">모아둔 유튜버 추천 꿀템</div>
    <div class="hero-big">{len(db):,}개</div>
    <div class="hero-dots">
        <div><span class="dot-blue">●</span>유튜버 <b>{yt_count}명</b></div>
        <div><span class="dot-green">●</span>최저가 비교 <b style="color:#3182F6;">실시간 연동</b></div>
    </div>
    <div class="hero-bar-box">
        <div class="hero-bar-top">
            <span>목표 DB 100개</span>
            <span style="color:#3182F6;">{fill_pct}%</span>
        </div>
        <div class="hero-bar-track">
            <div class="hero-bar-fill" style="width: {fill_pct}%;"></div>
        </div>
        <div class="hero-bar-sub">버튼을 누르면 네이버·쿠팡 낮은가격순으로 바로 연결돼요</div>
    </div>
</div>
""", unsafe_allow_html=True)

# === 상단 3개 탭 버튼 ===
t1, t2, t3 = st.columns(3)
for col, label in zip([t1, t2, t3], ["꿀템 홈", "자동 수집", "설정"]):
    is_active = (st.session_state.nav == label)
    if col.button(label, key=f"nav_{label}", type="primary" if is_active else "secondary", use_container_width=True):
        st.session_state.nav = label
        st.rerun()

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

if st.session_state.nav == "꿀템 홈":
    yts = ["전체 유튜버"] + sorted(list({i.get("youtuber", "") for i in db if i.get("youtuber")}))
    c_search, c_filter = st.columns([1.65, 1])
    kw = c_search.text_input("검색", placeholder="🔍 찾는 물건 입력 (예: 보조배터리)", label_visibility="collapsed")
    sel_yt = c_filter.selectbox("유튜버", yts, label_visibility="collapsed")

    filtered = [i for i in db if sel_yt == "전체 유튜버" or i.get("youtuber") == sel_yt]
    if kw:
        filtered = [i for i in filtered if kw.lower() in (i.get("name", "") + i.get("keyword", "") + i.get("reason", "")).lower()]

    if filtered:
        st.markdown(f"<div style='font-size:13px; font-weight:700; color:#4E5968; margin: 12px 4px 8px 4px;'>추천템 목록 ({len(filtered)}건)</div>", unsafe_allow_html=True)
        for idx, item in enumerate(reversed(filtered)):
            render_toss_card(item, idx)
    elif kw:
        with st.container(border=True):
            st.markdown(f"<div class='item-name'>'{kw}' 추천템이 아직 없어요</div><div class='item-reason' style='margin:6px 0 12px 0;'>네이버 쇼핑에서 바로 최저가를 확인해 보세요.</div>", unsafe_allow_html=True)
            st.link_button(f"네이버 쇼핑에서 '{kw}' 최저가 보기", f"https://search.shopping.naver.com/search/all?query={quote(kw)}&sort=price_asc", type="primary", use_container_width=True)
    else:
        with st.container(border=True):
            st.markdown("<div class='item-name'>아직 저장된 추천템이 없어요</div><div class='item-reason'>위쪽 '자동 수집' 탭에서 유튜버 키워드를 입력해 꿀템을 모아보세요.</div>", unsafe_allow_html=True)

elif st.session_state.nav == "자동 수집":
    with st.container(border=True):
        st.markdown("<div class='item-name' style='margin-bottom:12px;'>🤖 유튜브 추천템 자동 수집</div>", unsafe_allow_html=True)

        m1, m2 = st.columns(2)
        if m1.button("🤖 AI 정밀 분석 (자막+설명란)", key="mode_ai", type="primary" if st.session_state.collect_mode == "ai" else "secondary", use_container_width=True):
            st.session_state.collect_mode = "ai"
            st.rerun()
        if m2.button("🔗 구매링크 전용 추출", key="mode_local", type="primary" if st.session_state.collect_mode == "local" else "secondary", use_container_width=True):
            st.session_state.collect_mode = "local"
            st.rerun()

        if st.session_state.collect_mode == "ai" and not get_api_key():
            st.caption("💡 영상 속 대화(자막)에서 정확한 브랜드·제품명을 뽑으려면 [설정] 탭에 Gemini API 키를 넣어주세요.")

        st.markdown("<div class='field-label'>유튜브 검색 키워드</div>", unsafe_allow_html=True)
        q_in = st.text_input("키워드", placeholder="예: 잇섭 추천템, 가전주부 추천템, 내돈내산", label_visibility="collapsed")

        st.markdown("<div class='field-label'>분석할 최신 영상 수</div>", unsafe_allow_html=True)
        lim = st.slider("영상 수", 1, 8, 5, label_visibility="collapsed")

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
        if st.button("🚀 자동 수집 시작하기", type="primary", use_container_width=True) and q_in:
            status = st.empty()
            try:
                use_ai = (st.session_state.collect_mode == "ai")
                status.info("1/2 유튜브 영상 목록과 자막·설명란을 불러오고 있어요...")
                videos = search_youtube_videos(q_in, limit=int(lim))
                analyzed = {extract_video_id(i.get("youtube_url", "")) for i in load_items()}
                targets = [v for v in videos if v["video_id"] not in analyzed]
                if not targets:
                    status.empty()
                    st.info("이미 모두 수집한 영상들이에요.")
                else:
                    bundles = [fetch_video_bundle(v["video_id"], v["youtuber"], v["title"], need_transcript=use_ai) for v in targets]
                    if use_ai:
                        status.info("2/2 AI가 영상 자막과 설명란을 대조해 실제 제품명만 추려내고 있어요...")
                        try:
                            items = analyze_batch_with_gemini(bundles)
                        except Exception as ai_err:
                            status.empty()
                            st.warning(f"AI 분석 실패({ai_err}) → 구매링크 전용 추출로 전환했어요.")
                            items = extract_products_from_links(bundles)
                    else:
                        status.info("2/2 설명란에서 구매 링크가 걸린 제품만 추려내고 있어요...")
                        items = extract_products_from_links(bundles)

                    added = add_unique_items(items)
                    status.empty()
                    st.success(f"완료! 총 {len(added)}개의 진짜 제품이 추가되었어요.")
                    for a in added:
                        st.write(f"• **{a['name']}** ({a['youtuber']} · `{a['timestamp']}`)")
            except Exception as e:
                status.empty()
                st.error(f"수집 중 오류가 발생했어요: {e}")

elif st.session_state.nav == "설정":
    with st.container(border=True):
        st.markdown("<div class='item-name' style='margin-bottom:6px;'>🔑 Gemini API 키 설정</div><div class='item-reason' style='margin-bottom:12px;'>영상 자막까지 읽어 정확한 브랜드·제품명을 뽑을 때 사용해요.</div>", unsafe_allow_html=True)
        new_key = st.text_input("API 키", type="password", placeholder="AIzaSy...", label_visibility="collapsed")
        if st.button("API 키 저장", type="primary", use_container_width=True) and new_key.strip():
            open(KEY_FILE, "w", encoding="utf-8").write(new_key.strip())
            st.session_state.collect_mode = "ai"
            st.success("새 API 키가 저장되었어요!")

    with st.container(border=True):
        st.markdown(f"<div class='item-name' style='margin-bottom:6px;'>🗂️ 데이터 관리</div><div class='item-reason' style='margin-bottom:12px;'>현재 저장된 추천템은 총 <b>{len(db)}개</b>입니다.</div>", unsafe_allow_html=True)
        if db and st.button("🧹 공지·문장·날짜 오류 항목 자동 정리", type="primary", use_container_width=True):
            cleaned_db = [x for x in db if not is_non_product(x.get("name", ""), x.get("youtuber", ""))]
            removed = len(db) - len(cleaned_db)
            save_items(cleaned_db)
            st.success(f"제품이 아닌 항목 {removed}개를 깔끔하게 지웠어요!")
            st.rerun()
        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
        if db and st.button("모든 데이터 초기화", use_container_width=True):
            save_items([])
            st.rerun()
# === 여기까지 복사되면 끝 ===

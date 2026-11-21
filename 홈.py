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

# === 토스 스타일 모바일 앱 UI 커스텀 CSS (라이트 모드 고정) ===
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

:root {
    color-scheme: light !important;
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #F2F4F6 !important;
    color: #191F28 !important;
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
}

[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {
    background: transparent !important;
    visibility: hidden;
}

.block-container {
    max-width: 500px !important;
    padding-top: 1.2rem !important;
    padding-bottom: 4rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* 흰색 둥근 카드 스타일 */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF !important;
    border-radius: 22px !important;
    border: none !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04) !important;
    padding: 18px 20px !important;
    margin-bottom: 12px !important;
}

/* 알약형 세그먼트 탭 (전체 | 지출 | 수입 스타일) */
div[role="radiogroup"] {
    background-color: #E5E8EB !important;
    padding: 4px !important;
    border-radius: 14px !important;
    display: flex !important;
    justify-content: space-between !important;
    gap: 4px !important;
    width: 100% !important;
}
div[role="radiogroup"] > label {
    flex: 1 !important;
    background: transparent !important;
    border-radius: 11px !important;
    padding: 8px 6px !important;
    margin: 0 !important;
    justify-content: center !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}
div[role="radiogroup"] > label:has(input:checked) {
    background-color: #FFFFFF !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06) !important;
}
div[role="radiogroup"] > label > div:first-child {
    display: none !important;
}
div[role="radiogroup"] > label p {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #4E5968 !important;
    margin: 0 !important;
    text-align: center !important;
}
div[role="radiogroup"] > label:has(input:checked) p {
    color: #191F28 !important;
    font-weight: 700 !important;
}

/* 검색창 & 입력 필드 */
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    border-radius: 14px !important;
    border: 1px solid #E5E8EB !important;
    color: #191F28 !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02) !important;
}
input, textarea {
    color: #191F28 !important;
    font-size: 14px !important;
}

/* 기본 버튼 (토스 블루 & 소프트 틴트) */
.stButton > button {
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    border: none !important;
    padding: 0.45rem 0.9rem !important;
    transition: all 0.15s ease !important;
}
.stButton > button[kind="primary"] {
    background-color: #3182F6 !important;
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #1B64DA !important;
}
.stButton > button[kind="secondary"] {
    background-color: #F2F4F6 !important;
    color: #4E5968 !important;
}

/* 링크 버튼 (네이버/쿠팡/유튜브) */
.stLinkButton > a {
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    text-decoration: none !important;
    border: none !important;
    width: 100% !important;
    justify-content: center !important;
    padding: 0.45rem 0.6rem !important;
}
.stLinkButton > a[kind="primary"] {
    background-color: #3182F6 !important;
    color: #FFFFFF !important;
}
.stLinkButton > a[kind="secondary"] {
    background-color: #E8F3FF !important;
    color: #3182F6 !important;
}

/* 커스텀 앱 컴포넌트 클래스 */
.app-topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 4px 14px 4px;
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
    font-size: 30px;
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

.item-meta {
    font-size: 12px;
    font-weight: 600;
    color: #8B95A1;
    margin-bottom: 10px;
}
.item-row {
    display: flex;
    align-items: center;
    gap: 13px;
    margin-bottom: 12px;
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

NOISE_WORDS = (
    "인트로", "오프닝", "시작", "마무리", "아웃트로", "총평", "결론",
    "구독", "이벤트", "쿠키", "예고", "목차", "근황", "달라졌어요",
    "소감", "질문", "후기", "원칙", "고능", "PD", "피디", "출연",
    "등장", "브이로그", "일상", "주부", "추천", "꿀템", "문의", "비즈니스",
    "협찬", "광고", "인스타", "유튜브", "채널", "타임라인", "챕터"
)

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
    if any(k in text for k in ("크림", "선크림", "클렌징", "멀티밤", "가습", "청소기", "매트", "담요", "난로", "양말")):
        return "🏠", "#FFEFF4"
    if any(k in text for k in ("지갑", "케이스", "백팩", "가방", "트렁크", "여행")):
        return "🎒", "#EBF8FF"
    return "🛍️", "#F2F4F6"

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

def fetch_video_bundle(video_id, youtuber_hint="유튜버", title_hint=""):
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

    if not desc:
        try:
            req = urllib.request.Request(
                f"https://www.youtube.com/watch?v={video_id}",
                headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"}
            )
            html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore")
            m = re.search(r"var ytInitialPlayerResponse = (\{.*?\});</script>", html)
            if m:
                details = json.loads(m.group(1)).get("videoDetails", {})
                title = details.get("title", title)
                desc = details.get("shortDescription", "")
                youtuber = details.get("author", youtuber)
        except Exception:
            pass

    transcript = ""
    if len(desc) < 150:
        try:
            ytt = YouTubeTranscriptApi()
            if hasattr(ytt, "fetch"):
                fetched = ytt.fetch(video_id, languages=["ko", "en"])
                transcript = "\n".join([f"[{int(s.start)}초] {s.text}" for s in fetched])
        except Exception:
            pass

    return {"video_id": video_id, "youtuber": youtuber, "title": title, "desc": desc, "transcript": transcript[:1200]}

def extract_products_locally(bundles):
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
                label = re.sub(r"^[\-\•\*\d\.\)\]]+\s*", "", m_ts.group(4)).strip()
                ts_list.append((hh * 3600 + mm * 60 + ss, label))

        for raw_ln in raw_lines:
            if "@" in raw_ln or raw_ln.startswith("#"):
                continue

            has_url = "http" in raw_ln
            ln = re.sub(r"https?://\S+", "", raw_ln).strip()
            ln = re.sub(r"[\(\[\{]\s*[\)\]\}]", "", ln).strip()
            if not ln or len(ln) < 2:
                continue

            candidate = None
            category = ""
            sec = 0

            m_colon = re.match(r"^([^:：]{1,35})\s*[:：]\s*(.*)$", ln)
            if m_colon:
                left = m_colon.group(1).strip()
                right = m_colon.group(2).strip()
                if has_url and not right:
                    candidate = left
                elif right:
                    category = left
                    candidate = right
            else:
                m_line_ts = re.match(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s+(.+)$", ln)
                if m_line_ts:
                    hh = int(m_line_ts.group(1) or 0)
                    mm, ss = int(m_line_ts.group(2)), int(m_line_ts.group(3))
                    sec = hh * 3600 + mm * 60 + ss
                    body = m_line_ts.group(4).strip()
                    if " - " in body:
                        parts = body.split(" - ", 1)
                        category = parts[0].strip()
                        candidate = parts[1].strip()
                    else:
                        candidate = body
                else:
                    m_list = re.match(r"^(?:[\-\•\*\▶\▸\✔\✓]|\d{1,2}[\.\)\]])\s*(.+)$", ln)
                    if m_list:
                        candidate = m_list.group(1).strip()

            if not candidate:
                continue

            candidate = re.sub(r"^[\-\•\*\▶\▸\d\.\)\]]+\s*", "", candidate).strip()
            candidate = re.split(r"\s*(?:👉|▶|→|\|)\s*", candidate)[0].strip()
            if len(candidate) < 2 or len(candidate) > 70:
                continue
            if any(w in candidate for w in NOISE_WORDS) and not re.search(r"[A-Za-z0-9]{2,}", candidate):
                continue

            if sec == 0 and ts_list:
                for t_sec, t_label in ts_list:
                    if any(tok and tok in t_label for tok in candidate.split()[:2]):
                        sec = t_sec
                        break

            split_names = [s.strip() for s in re.split(r"\s*(?:&|/)\s*", candidate) if len(s.strip()) >= 2]
            for pname in split_names:
                mm, ss = divmod(sec, 60)
                reason = f"'{title}'에서 {yt}가 소개한 {category or '추천'} 제품"
                extracted.append({
                    "name": pname,
                    "keyword": category or pname.split()[0],
                    "youtuber": yt,
                    "reason": reason,
                    "timestamp": f"{mm:02d}:{ss:02d}",
                    "youtube_url": f"https://youtu.be/{vid}?t={sec}",
                })

    return extracted

def analyze_batch_with_gemini(bundles):
    api_key = get_api_key()
    if not api_key or not api_key.isascii():
        raise RuntimeError("API 키가 설정되지 않았습니다.")

    blocks = []
    for b in bundles:
        blocks.append(f"=== VIDEO_ID: {b['video_id']} | YOUTUBER: {b['youtuber']} ===\n[제목] {b['title']}\n[설명란]\n{b['desc'][:1500]}\n[자막]\n{b['transcript']}")

    prompt = f"""아래 유튜브 영상들에서 실제로 쇼핑몰에서 구매할 수 있는 '구체적인 제품(브랜드+제품명)'만 골라 JSON 배열로만 답해줘.
규칙:
1. PD/출연진 이름, 코너명, 인트로/아웃트로, 추상적 주제는 절대 넣지 마.
2. 실제 구매 가능한 상품이 없으면 [] 만 반환해.
3. 키 이름: "video_id", "youtuber", "name"(쇼핑몰 검색용 정확한 제품명), "keyword"(핵심 품목명), "reason"(추천 이유 한 줄), "start_sec"(등장 시작 초 정수, 모르면 0)

{chr(10).join(blocks)}"""

    client = genai.Client(api_key=api_key, http_options={"timeout": 20000})
    res = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    cleaned = re.sub(r"^```json|```$", "", res.text.strip()).strip()
    out = []
    for item in json.loads(cleaned):
        vid = item.get("video_id") or bundles[0]["video_id"]
        sec = int(item.get("start_sec", 0))
        mm, ss = divmod(sec, 60)
        name = item.get("name", "").strip()
        if name:
            out.append({
                "name": name,
                "keyword": item.get("keyword", "").strip(),
                "youtuber": item.get("youtuber", bundles[0]["youtuber"]).strip(),
                "reason": item.get("reason", "").strip(),
                "timestamp": f"{mm:02d}:{ss:02d}",
                "youtube_url": f"https://youtu.be/{vid}?t={sec}",
            })
    return out

def render_toss_card(item, idx):
    icon, bg_color = pick_icon_style(item.get("name", ""), item.get("keyword", ""))
    with st.container(border=True):
        top_l, top_r = st.columns([5, 1])
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
        b1, b2, b3 = st.columns([1.25, 1.15, 1])
        b1.link_button("네이버 최저가", f"https://search.shopping.naver.com/search/all?query={q}&sort=price_asc", type="primary")
        b2.link_button("쿠팡 최저가", f"https://www.coupang.com/np/search?q={q}&sorter=salePriceAsc")
        b3.link_button("▶️ 영상보기", item["youtube_url"])

# === 상단 앱 헤더 ===
db = load_items()
yt_count = len({i.get("youtuber", "") for i in db if i.get("youtuber")})

st.markdown("""
<div class="app-topbar">
    <div class="app-title">‹ &nbsp; 꿀템 다나와</div>
    <div style="font-size:13px; font-weight:600; color:#8B95A1;">유튜버 추천템</div>
</div>
""", unsafe_allow_html=True)

# === 상단 요약 대시보드 카드 (가계부 앱 상단 카드 스타일) ===
fill_pct = min(100, int((len(db) / 100) * 100)) if db else 0
with st.container(border=True):
    st.markdown(f"""
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
        <div class="hero-bar-sub">제품명을 누르면 네이버·쿠팡 낮은가격순으로 바로 연결돼요</div>
    </div>
    """, unsafe_allow_html=True)

# === 알약형 네비게이션 탭 ===
nav = st.radio("메뉴", ["꿀템 홈", "자동 수집", "설정"], horizontal=True, label_visibility="collapsed")

if nav == "꿀템 홈":
    yts = ["전체 유튜버"] + sorted(list({i.get("youtuber", "") for i in db if i.get("youtuber")}))
    c_search, c_filter = st.columns([1.6, 1])
    kw = c_search.text_input("검색", placeholder="🔍 찾는 물건 입력 (예: 보조배터리)", label_visibility="collapsed")
    sel_yt = c_filter.selectbox("유튜버", yts, label_visibility="collapsed")

    filtered = [i for i in db if sel_yt == "전체 유튜버" or i.get("youtuber") == sel_yt]
    if kw:
        filtered = [i for i in filtered if kw.lower() in (i.get("name", "") + i.get("keyword", "") + i.get("reason", "")).lower()]

    if filtered:
        st.markdown(f"<div style='font-size:13px; font-weight:700; color:#4E5968; margin: 10px 4px;'>추천템 목록 ({len(filtered)}건)</div>", unsafe_allow_html=True)
        for idx, item in enumerate(reversed(filtered)):
            render_toss_card(item, idx)
    elif kw:
        with st.container(border=True):
            st.markdown(f"<div class='item-name'>'{kw}' 추천템이 아직 없어요</div><div class='item-reason' style='margin:6px 0 12px 0;'>네이버 쇼핑에서 바로 최저가를 확인해 보세요.</div>", unsafe_allow_html=True)
            st.link_button(f"네이버 쇼핑에서 '{kw}' 최저가 보기", f"https://search.shopping.naver.com/search/all?query={quote(kw)}&sort=price_asc", type="primary")
    else:
        with st.container(border=True):
            st.markdown("<div class='item-name'>아직 저장된 추천템이 없어요</div><div class='item-reason'>위쪽 '자동 수집' 탭에서 유튜버 키워드를 입력해 꿀템을 모아보세요.</div>", unsafe_allow_html=True)

elif nav == "자동 수집":
    with st.container(border=True):
        st.markdown("<div class='item-name' style='margin-bottom:8px;'>🤖 유튜브 추천템 자동 수집</div>", unsafe_allow_html=True)
        mode = st.radio(
            "수집 방식",
            ["⚡ 무제한 로컬 추출", "🤖 Gemini AI 분석"],
            horizontal=True,
            label_visibility="collapsed"
        )
        q_in = st.text_input("키워드", placeholder="유튜브 검색어 입력 (예: 잇섭 추천템, 내돈내산)", label_visibility="collapsed")
        lim = st.slider("분석할 최신 영상 수", 1, 8, 5)

        if st.button("🚀 자동 수집 시작하기", type="primary", use_container_width=True) and q_in:
            status = st.empty()
            try:
                status.info("1/2 유튜브 영상 목록과 설명란을 불러오고 있어요...")
                videos = search_youtube_videos(q_in, limit=int(lim))
                analyzed = {extract_video_id(i.get("youtube_url", "")) for i in load_items()}
                targets = [v for v in videos if v["video_id"] not in analyzed]
                if not targets:
                    status.empty()
                    st.info("이미 모두 수집한 영상들이에요.")
                else:
                    bundles = [fetch_video_bundle(v["video_id"], v["youtuber"], v["title"]) for v in targets]
                    if "무제한" in mode:
                        status.info("2/2 설명란에서 실제 구매 제품만 추려내고 있어요...")
                        items = extract_products_locally(bundles)
                    else:
                        status.info("2/2 Gemini AI가 영상을 정밀 분석하고 있어요...")
                        try:
                            items = analyze_batch_with_gemini(bundles)
                        except Exception:
                            status.info("2/2 AI 한도 초과 → 무제한 로컬 추출로 전환 중...")
                            items = extract_products_locally(bundles)

                    added = add_unique_items(items)
                    status.empty()
                    st.success(f"완료! 총 {len(added)}개의 제품이 추가되었어요.")
                    if not added:
                        st.caption(f"확인한 영상 {len(bundles)}개 중 설명란 수집: {sum(1 for b in bundles if b['desc'])}개")
                    for a in added:
                        st.write(f"• **{a['name']}** ({a['youtuber']})")
            except Exception as e:
                status.empty()
                st.error(f"수집 중 오류가 발생했어요: {e}")

elif nav == "설정":
    with st.container(border=True):
        st.markdown("<div class='item-name' style='margin-bottom:6px;'>🔑 Gemini API 키 설정</div><div class='item-reason' style='margin-bottom:12px;'>AI 정밀 분석 기능을 쓸 때만 필요해요.</div>", unsafe_allow_html=True)
        new_key = st.text_input("API 키", type="password", placeholder="AIzaSy...", label_visibility="collapsed")
        if st.button("API 키 저장", type="primary", use_container_width=True) and new_key.strip():
            open(KEY_FILE, "w", encoding="utf-8").write(new_key.strip())
            st.success("새 API 키가 저장되었어요!")

    with st.container(border=True):
        st.markdown(f"<div class='item-name' style='margin-bottom:6px;'>🗂️ 데이터 관리</div><div class='item-reason' style='margin-bottom:12px;'>현재 저장된 추천템은 총 <b>{len(db)}개</b>입니다.</div>", unsafe_allow_html=True)
        if db and st.button("모든 데이터 초기화", use_container_width=True):
            save_items([])
            st.rerun()
# === 여기까지 복사되면 끝 ===

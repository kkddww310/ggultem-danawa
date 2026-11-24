import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import quote

import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="에디션 픽 EDITION PICK · 검증된 리뷰 큐레이션", page_icon="✦", layout="wide")


def secret(name):
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


SUPABASE_URL = secret("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = secret("SUPABASE_SERVICE_ROLE_KEY")
CATEGORIES = ["IT·전자", "뷰티", "패션", "생활·살림", "주방", "여행", "자동차", "운동·건강", "육아", "반려동물", "기타"]
IMAGE_SOURCES = ["", "brand_official", "affiliate", "manual", "youtube_thumbnail"]
IMAGE_SOURCE_LABELS = {
    "": "출처 미선택",
    "brand_official": "브랜드 공식",
    "affiliate": "제휴사 제공",
    "manual": "직접 확인",
    "youtube_thumbnail": "유튜브 썸네일",
}
CATEGORY_VISUALS = {
    "IT·전자": ("🖥️", "#EAF3FF", "#3182F6"),
    "뷰티": ("🧴", "#FFF1E8", "#E67527"),
    "패션": ("👕", "#F4EEFF", "#7652C7"),
    "생활·살림": ("🏠", "#EEF8F3", "#218B61"),
    "주방": ("🍳", "#FFF6DF", "#BD7500"),
    "여행": ("🧳", "#EAF8FA", "#167C8C"),
    "자동차": ("🚗", "#EEF1F5", "#4E5968"),
    "운동·건강": ("🏃", "#FFF0F0", "#C92A2A"),
    "육아": ("🧸", "#FFF4E8", "#D06A19"),
    "반려동물": ("🐾", "#F4F7EA", "#6E832B"),
    "기타": ("🛍️", "#F1F4F8", "#5D6B7A"),
}
INVALID_POINT_PATTERNS = (
    "원문에", "명시됨", "후기는 없음", "후기 없음", "언급 없음",
    "정보가 없음", "확인되지 않", "알 수 없", "단점 없음", "장점 없음",
)
SEARCH_SYNONYMS = {
    "태블릿": ["pad", "탭", "아이패드", "갤럭시탭", "tablet"],
    "노트북": ["laptop", "맥북", "macbook", "그램", "갤럭시북"],
    "이어폰": ["버즈", "에어팟", "earbuds", "earphone"],
    "헤드폰": ["헤드셋", "headphone", "headset"],
    "청소기": ["다이슨", "dyson", "로봇청소기", "물걸레"],
    "키보드": ["keyboard"],
    "마우스": ["mouse"],
    "보조배터리": ["파워뱅크", "powerbank", "맥세이프"],
    "패딩": ["다운", "푸퍼", "파카", "점퍼", "down", "puffer", "parka"],
    "가방": ["백", "숄더백", "토트백", "크로스백", "핸드백", "에코백", "백팩", "bag"],
    "신발": ["스니커즈", "운동화", "로퍼", "부츠", "구두", "슬리퍼", "샌들", "shoes", "sneakers"],
}
EXTRA_MALLS = ("musinsa", "zigzag", "ably")
MALL_META = {
    "naver": {"label": "네이버쇼핑", "css": "shop-btn-naver"},
    "coupang": {"label": "쿠팡 검색", "css": "shop-btn-coupang"},
    "musinsa": {"label": "무신사", "css": "shop-btn-musinsa"},
    "zigzag": {"label": "지그재그", "css": "shop-btn-zigzag"},
    "ably": {"label": "에이블리", "css": "shop-btn-ably"},
}


def headers(prefer=None):
    result = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
    if SUPABASE_KEY.startswith("eyJ"):
        result["Authorization"] = f"Bearer {SUPABASE_KEY}"
    if prefer:
        result["Prefer"] = prefer
    return result


def api_get(table, fields="*", params=None):
    query = {"select": fields}
    query.update(params or {})
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers(), params=query, timeout=30)
    if not response.ok:
        raise RuntimeError(f"{table} 조회 실패: HTTP {response.status_code} · {response.text[:250]}")
    return response.json()


def api_post(table, values):
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers("return=minimal"),
        json=values,
        timeout=10,
    )
    if not response.ok:
        raise RuntimeError(f"{table} 저장 실패: HTTP {response.status_code}")


def api_get_all(table, fields="*", params=None, max_rows=10000):
    rows = []
    offset = 0
    step = 1000
    while offset < max_rows:
        query = dict(params or {})
        query["limit"] = str(step)
        query["offset"] = str(offset)
        batch = api_get(table, fields, query)
        rows.extend(batch)
        if len(batch) < step:
            break
        offset += step
    return rows


def fetch_by_ids(table, fields, id_col, ids):
    clean_ids = list(dict.fromkeys(str(i).strip() for i in ids if i))
    rows = []
    for start in range(0, len(clean_ids), 50):
        chunk = clean_ids[start:start + 50]
        rows.extend(api_get(table, fields, {id_col: f"in.({','.join(chunk)})", "limit": "1000"}))
    return rows


def api_patch(table, values, params):
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers("return=representation"),
        params=params,
        json=values,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"{table} 수정 실패: HTTP {response.status_code} · {response.text[:250]}")
    return response.json() if response.text else []


def safe(value):
    return html.escape(str(value or ""), quote=True)


def norm_key(value):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").lower())


def clean_evidence_text(value):
    text = re.sub(r"https?://\S+", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip(" ·,-/")
    return text


def count_by(rows, key):
    return Counter(str(row.get(key) or "unknown") for row in rows)


def is_meaningful_point(text):
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if len(cleaned) < 2:
        return False
    return not any(pattern in cleaned for pattern in INVALID_POINT_PATTERNS)


def score_product_search(product, query):
    """영상 제목 오염을 막고 상품 자체 정보(상품명·브랜드·키워드·리뷰 요약) 기준으로 일치 점수를 계산한다."""
    tokens = [t.strip().lower() for t in str(query or "").split() if t.strip()]
    if not tokens:
        return 1

    primary_text = " ".join([
        str(product.get("canonical_name") or ""),
        str(product.get("brand") or ""),
        str(product.get("model") or ""),
        str(product.get("search_keyword") or ""),
    ]).lower()

    meta_text = " ".join([
        str(product.get("category") or ""),
        " ".join(
            str((r.get("channel") or {}).get("channel_name") or "")
            for r in (product.get("recommendations") or [])
        ),
    ]).lower()

    review_parts = []
    for r in (product.get("recommendations") or []):
        reason = str(r.get("reason") or "").strip()
        if is_meaningful_point(reason):
            review_parts.append(reason)
        for p in (r.get("pros") or []):
            if is_meaningful_point(p):
                review_parts.append(str(p))
        for c in (r.get("cons") or []):
            if is_meaningful_point(c):
                review_parts.append(str(c))
    review_text = " ".join(review_parts).lower()

    total_score = 0
    for token in tokens:
        synonyms = SEARCH_SYNONYMS.get(token, [])
        if token in primary_text:
            total_score += 10
        elif any(syn in primary_text for syn in synonyms):
            total_score += 6
        elif token in meta_text:
            total_score += 4
        elif token in review_text or any(syn in review_text for syn in synonyms):
            total_score += 2
        else:
            return 0
    return total_score


def parse_extra_partner_links(product):
    """affiliate_note에 저장된 추가 쇼핑몰(무신사·지그재그·에이블리) 파트너 링크를 읽어온다."""
    raw = str(product.get("affiliate_note") or "").strip()
    links = {mall: "" for mall in EXTRA_MALLS}
    memo = ""
    if not raw:
        return links, memo
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                for mall in EXTRA_MALLS:
                    url = str(data.get(mall) or "").strip()
                    if url.startswith(("https://", "http://")):
                        links[mall] = url
                memo = str(data.get("memo") or "").strip()
                return links, memo
        except Exception:
            pass
    memo = raw
    return links, memo


def serialize_extra_partner_links(links, memo=""):
    clean_links = {
        mall: str(links.get(mall) or "").strip()
        for mall in EXTRA_MALLS
        if str(links.get(mall) or "").strip().startswith(("https://", "http://"))
    }
    clean_memo = str(memo or "").strip()
    if not clean_links:
        return clean_memo or None
    payload = dict(clean_links)
    if clean_memo:
        payload["memo"] = clean_memo
    return json.dumps(payload, ensure_ascii=False)


def detect_product_malls(product):
    """가독성을 위해 한 줄 최대 3버튼(네이버 + 쿠팡 + 대표 특화몰 1곳)을 자동 결정한다."""
    extra_links, _ = parse_extra_partner_links(product)
    has_coupang_partner = bool(
        product.get("affiliate_verified")
        and str(product.get("coupang_url") or "").startswith("https://link.coupang.com/")
    )

    buttons = [
        {"mall": "naver", "label": "네이버쇼핑", "css": "shop-btn-naver", "is_partner": False},
        {
            "mall": "coupang",
            "label": "쿠팡 최저가" if has_coupang_partner else "쿠팡 검색",
            "css": "shop-btn-coupang",
            "is_partner": has_coupang_partner,
        },
    ]

    category = str(product.get("category") or "").strip()
    rec_corpus = " ".join(
        [
            str(product.get("canonical_name") or ""),
            str(product.get("brand") or ""),
            str(product.get("search_keyword") or ""),
            " ".join(
                f"{(r.get('video') or {}).get('title', '')} {r.get('reason', '')} {r.get('evidence', '')}"
                for r in (product.get("recommendations") or [])
            ),
        ]
    ).lower()

    registered_malls = [mall for mall in EXTRA_MALLS if extra_links.get(mall)]
    if registered_malls:
        selected_extra = registered_malls
    else:
        picked = None
        if any(k in rec_corpus for k in ("무신사", "musinsa")):
            picked = "musinsa"
        elif any(k in rec_corpus for k in ("지그재그", "zigzag")):
            picked = "zigzag"
        elif any(k in rec_corpus for k in ("에이블리", "ably")):
            picked = "ably"
        elif category == "패션":
            womens_keywords = ("가방", "숄더백", "토트백", "원피스", "블라우스", "스커트", "가디건", "니트", "부츠", "귀걸이", "목걸이", "여성")
            picked = "zigzag" if any(k in rec_corpus for k in womens_keywords) else "musinsa"
        elif category == "뷰티":
            mens_keywords = ("남성", "옴므", "맨즈", "쉐이빙")
            picked = "musinsa" if any(k in rec_corpus for k in mens_keywords) else "zigzag"
        selected_extra = [picked] if picked else []

    for mall_key in selected_extra:
        has_partner = bool(extra_links.get(mall_key))
        base_label = MALL_META[mall_key]["label"]
        buttons.append(
            {
                "mall": mall_key,
                "label": f"{base_label} 최저가" if has_partner else base_label,
                "css": MALL_META[mall_key]["css"],
                "is_partner": has_partner,
            }
        )

    return buttons


def get_page_numbers(current_page, total_pages):
    """현재 페이지 기준으로 바로 이동할 페이지 번호 목록(최대 5개)을 만든다."""
    if total_pages <= 5:
        return list(range(1, total_pages + 1))
    if current_page <= 3:
        return [1, 2, 3, 4, total_pages]
    if current_page >= total_pages - 2:
        return [1, total_pages - 3, total_pages - 2, total_pages - 1, total_pages]
    return [1, current_page - 1, current_page, current_page + 1, total_pages]


def log_event(event_type, product_id=None, product_name=None, search_query=None):
    """클릭 및 검색 이벤트를 Supabase click_logs 테이블에 조용히 기록한다."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        payload = {
            "event_type": event_type,
            "product_id": product_id or None,
            "product_name": (str(product_name).strip()[:200] if product_name else None),
            "search_query": (str(search_query).strip()[:120] if search_query else None),
        }
        api_post("click_logs", [payload])
    except Exception:
        pass


def handle_click_redirect():
    """외부 쇼핑몰 링크(?go=coupang|naver|musinsa|zigzag|ably&pid=...) 클릭 시 로그를 남기고 즉시 이동시킨다."""
    go_type = str(st.query_params.get("go", "")).strip()
    go_pid = str(st.query_params.get("pid", "")).strip()
    if go_type not in {"coupang", "naver", "musinsa", "zigzag", "ably"} or not go_pid:
        return

    rows = []
    try:
        rows = api_get(
            "products",
            "product_id,canonical_name,search_keyword,coupang_url,affiliate_verified,affiliate_note",
            {"product_id": f"eq.{go_pid}", "limit": "1"},
        )
    except Exception:
        rows = []

    product = rows[0] if rows else {}
    product_name = str(product.get("canonical_name") or product.get("search_keyword") or "").strip()
    query_name = quote(product_name)
    extra_links, _ = parse_extra_partner_links(product)

    if go_type == "coupang":
        affiliate = bool(
            product.get("affiliate_verified")
            and str(product.get("coupang_url") or "").startswith("https://link.coupang.com/")
        )
        target_url = product["coupang_url"] if affiliate else f"https://www.coupang.com/np/search?q={query_name}"
    elif go_type == "naver":
        target_url = f"https://search.shopping.naver.com/search/all?query={query_name}"
    elif go_type == "musinsa":
        target_url = extra_links.get("musinsa") or f"https://www.musinsa.com/search/goods?keyword={query_name}"
    elif go_type == "zigzag":
        target_url = extra_links.get("zigzag") or f"https://zigzag.kr/search?keyword={query_name}"
    else:
        target_url = extra_links.get("ably") or f"https://m.a-bly.com/search?keyword={query_name}"

    log_event(f"{go_type}_click", product_id=go_pid if product else None, product_name=product_name or None)
    safe_url = html.escape(target_url, quote=True)
    js_url = json.dumps(target_url)
    st.markdown(
        f'<meta http-equiv="refresh" content="0;url={safe_url}">'
        f'<script>window.location.replace({js_url});</script>'
        f'<div style="padding:32px 16px;text-align:center;font-size:14px;color:#4E5968">'
        f'쇼핑몰 페이지로 이동 중입니다... <a href="{safe_url}">바로 이동하기</a></div>',
        unsafe_allow_html=True,
    )
    st.stop()


handle_click_redirect()


@st.cache_data(ttl=300, show_spinner=False)
def load_public_data():
    products = api_get_all(
        "products",
        "product_id,canonical_name,brand,model,category,search_keyword,coupang_url,affiliate_verified,affiliate_note,image_url,image_source,image_verified,image_checked_at,image_note,created_at",
        {"review_status": "eq.approved", "is_visible": "eq.true", "order": "created_at.desc"},
        max_rows=3000,
    )
    recs = api_get_all(
        "recommendations",
        "recommendation_id,product_id,video_id,channel_id,reason,pros,cons,evidence,confidence,purchase_type,created_at",
        {"order": "created_at.desc"},
        max_rows=10000,
    )
    video_ids = [r.get("video_id") for r in recs if r.get("video_id")]
    channel_ids = [r.get("channel_id") for r in recs if r.get("channel_id")]
    videos = fetch_by_ids("videos", "video_id,title,view_count,published_at", "video_id", video_ids)
    channels = fetch_by_ids("channels", "channel_id,channel_name,subscriber_count", "channel_id", channel_ids)
    video_map = {row["video_id"]: row for row in videos}
    channel_map = {row["channel_id"]: row for row in channels}
    grouped = {}
    for rec in recs:
        item = dict(rec)
        item["video"] = video_map.get(rec.get("video_id"), {})
        item["channel"] = channel_map.get(rec.get("channel_id"), {})
        grouped.setdefault(rec.get("product_id"), []).append(item)
    for product in products:
        product["recommendations"] = grouped.get(product["product_id"], [])
    products.sort(
        key=lambda p: (len({r.get("channel_id") for r in p["recommendations"]}), len(p["recommendations"])),
        reverse=True,
    )
    return products


@st.cache_data(ttl=60, show_spinner=False)
def load_admin_data():
    products = api_get_all(
        "products",
        "product_id,canonical_name,brand,model,category,search_keyword,identity_score,review_status,is_visible,review_note,coupang_url,coupang_product_name,affiliate_verified,affiliate_note,image_url,image_source,image_verified,image_checked_at,image_note,created_at",
        {"order": "created_at.desc"},
        max_rows=5000,
    )
    videos = api_get_all(
        "videos",
        "video_id,channel_id,title,analysis_status,analysis_error,product_score,created_at,published_at",
        {"order": "created_at.desc"},
        max_rows=10000,
    )
    channels = api_get_all(
        "channels",
        "channel_id,channel_name,status,scan_priority,total_scanned_videos,product_candidate_videos,extracted_product_count,last_scanned_at,next_video_scan_at",
        max_rows=10000,
    )
    queries = api_get_all(
        "discovery_queries",
        "query_id,query_text,category,enabled,run_count,channels_found,active_channels_found,error_count,last_error,last_run_at,next_run_at",
        max_rows=2000,
    )
    recs = api_get_all(
        "recommendations",
        "recommendation_id,product_id,video_id,channel_id,confidence,created_at",
        max_rows=10000,
    )
    try:
        click_logs = api_get_all(
            "click_logs",
            "log_id,event_type,product_id,product_name,search_query,created_at",
            {"order": "created_at.desc"},
            max_rows=10000,
        )
        click_logs_ready = True
    except Exception:
        click_logs = []
        click_logs_ready = False

    return products, videos, channels, queries, recs, click_logs, click_logs_ready


st.markdown("""
<style>
:root{
  --brand:#3182F6;
  --brand-dark:#1B64DA;
  --soft:#EAF3FF;
  --ink:#191F28;
  --sub:#4E5968;
  --muted:#8B95A1;
  --line:#E5E8EB;
  --canvas:#F4F6F9;
}
html,body,.stApp{background:var(--canvas);color:var(--ink);overflow-x:hidden!important}
.block-container{max-width:1180px;padding:1.1rem 1rem 4rem;box-sizing:border-box}

/* 스트림릿 기본 상단 헤더·선·스크롤 그림자·푸터 완전 제거 */
#MainMenu,
footer,
header,
header[data-testid="stHeader"],
[data-testid="stHeader"],
[data-testid="stAppHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
.viewerBadge_container__r5tak,
.styles_viewerBadge__CvC9N{
  display:none!important;
  visibility:hidden!important;
  height:0!important;
  max-height:0!important;
  min-height:0!important;
  border:0!important;
  box-shadow:none!important;
  background:transparent!important;
}
[data-testid="stElementContainer"]:has(iframe[height="0"]),
[data-testid="stIFrame"]:has(iframe[height="0"]){
  display:none!important;
  height:0!important;
  margin:0!important;
  padding:0!important;
}
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section.main,
[data-testid="stMainBlockContainer"]{
  padding-top:0!important;
  margin-top:0!important;
  border-top:0!important;
  outline:0!important;
  box-shadow:none!important;
}
.stApp::before,.stApp::after,
[data-testid="stAppViewContainer"]::before,[data-testid="stAppViewContainer"]::after,
[data-testid="stMain"]::before,[data-testid="stMain"]::after,
section.main::before,section.main::after{
  display:none!important;
  content:none!important;
  border:0!important;
  box-shadow:none!important;
}

/* 서비스 상단 헤더 & 히어로 배너 */
.top-nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.brand-wrap{display:flex;align-items:center;gap:9px}
.brand-logo{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:10px;background:#191F28;color:#fff;font-size:16px;font-weight:900;box-shadow:0 4px 12px rgba(25,31,40,.18)}
.brand-name{font-size:21px;font-weight:900;letter-spacing:-.03em;color:var(--ink)}
.brand-en{font-size:11px;font-weight:800;letter-spacing:.08em;color:#4E5968;background:#E9EDF3;padding:3px 8px;border-radius:999px}
.top-sub{font-size:12.5px;font-weight:650;color:var(--muted)}

.hero-banner{
  background:linear-gradient(135deg,#FFFFFF 0%,#F2F7FF 100%);
  border:1px solid #E2ECFF;
  border-radius:20px;
  padding:18px 20px;
  margin-bottom:8px;
  box-shadow:0 6px 20px rgba(49,130,246,.05);
}
.hero-kicker{font-size:12px;font-weight:750;color:var(--brand);margin-bottom:4px}
.hero-headline{font-size:21px;font-weight:850;letter-spacing:-.02em;color:var(--ink);line-height:1.35}
.hero-headline b{color:var(--brand)}
.hero-stats{display:flex;flex-wrap:wrap;align-items:center;gap:7px;margin-top:11px}
.stat-pill{display:inline-flex;align-items:center;gap:4px;background:#fff;border:1px solid #E5EAF2;padding:5px 10px;border-radius:999px;font-size:12px;font-weight:700;color:var(--sub);white-space:nowrap}
.stat-pill strong{color:var(--ink);font-weight:850}

/* 상단 쿠팡 파트너스 고지 바 */
.top-disclosure{
  margin:0 2px 10px;
  padding:7px 12px;
  background:#FFFFFF;
  border:1px solid #E5E9F0;
  border-radius:10px;
  font-size:11.5px;
  font-weight:600;
  color:var(--sub);
  text-align:center;
  word-break:keep-all;
}

/* 검색창 & 셀렉트박스 */
div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  border:1.5px solid #DCE3EC!important;
  outline:0!important;
  background:#fff!important;
  box-shadow:0 2px 8px rgba(15,23,42,.03)!important;
  border-radius:13px!important;
  transition:border-color .15s,box-shadow .15s!important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
div[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within{
  border-color:var(--brand)!important;
  box-shadow:0 0 0 3px rgba(49,130,246,.14)!important;
}
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] div[role="combobox"],
div[data-testid="stSelectbox"] div[role="combobox"] *{
  background:#fff!important;
  color:var(--ink)!important;
  -webkit-text-fill-color:var(--ink)!important;
  border:0!important;
  outline:0!important;
  font-size:14px!important;
}
div[data-testid="stSelectbox"] svg{fill:var(--sub)!important;color:var(--sub)!important}

.result-bar{display:flex;align-items:center;justify-content:space-between;margin:6px 2px 10px;font-size:13px;color:var(--sub);font-weight:650}

/* 기본 컨테이너 & 버튼 */
div[data-testid="stVerticalBlockBorderWrapper"]{border:1px solid #EAECEF!important;outline:0!important;background:#fff!important;border-radius:18px!important;box-shadow:0 4px 16px rgba(15,23,42,.04)!important;padding:16px!important;margin-bottom:12px!important}
.stButton>button,.stLinkButton>a{min-height:40px!important;border-radius:11px!important;font-weight:750!important;font-size:13px!important;transition:all .15s!important}
.stButton>button[kind="primary"],.stLinkButton>a[kind="primary"]{background:var(--brand)!important;border-color:var(--brand)!important;color:#fff!important}
.stButton>button[kind="primary"]:hover,.stLinkButton>a[kind="primary"]:hover{background:var(--brand-dark)!important;border-color:var(--brand-dark)!important}
.stButton>button[kind="secondary"],.stLinkButton>a[kind="secondary"]{background:#F2F4F7!important;border:1px solid #E5E8EB!important;color:#333D4B!important}
.stButton>button[kind="secondary"]:hover,.stLinkButton>a[kind="secondary"]:hover{background:#E8ECF2!important}

div[data-testid="stForm"]{border:1px solid #DCE7F7!important;background:#F8FAFD!important;border-radius:16px!important;padding:16px!important}
div[data-testid="stForm"] input,div[data-testid="stForm"] textarea,div[data-testid="stForm"] div[role="combobox"]{background:#fff!important;color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important}

/* 상품 그리드 & 카드 */
.st-key-product_grid{width:100%!important;max-width:100%!important;box-sizing:border-box!important}
.st-key-product_grid [data-testid="stHorizontalBlock"]{
  display:flex!important;
  gap:16px!important;
  align-items:stretch!important;
  width:100%!important;
  max-width:100%!important;
  margin:0!important;
  padding:0!important;
  box-sizing:border-box!important;
}
.st-key-product_grid [data-testid="stColumn"],
.st-key-product_grid [data-testid="column"]{
  flex:1 1 0%!important;
  width:0!important;
  min-width:0!important;
  padding:0!important;
  display:flex!important;
  flex-direction:column!important;
  box-sizing:border-box!important;
}

.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"]{
  width:100%!important;
  box-sizing:border-box!important;
  border:1px solid #E5E9F0!important;
  background:#fff!important;
  border-radius:18px!important;
  box-shadow:0 4px 18px rgba(15,23,42,.04)!important;
  padding:14px 14px 20px!important;
  margin-bottom:16px!important;
}
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"]{
  gap:10px!important;
  padding-bottom:2px!important;
}

/* 썸네일 영역: 가림 없이 선명하게 + 카드 테두리와 동심원 곡률(12px) */
.video-thumbnail-wrap{
  position:relative;
  display:block;
  width:100%!important;
  aspect-ratio:16 / 9!important;
  margin:0!important;
  border-radius:12px!important;
  border:1px solid rgba(15,23,42,.07)!important;
  background:#F1F4F8!important;
  overflow:hidden!important;
  box-sizing:border-box!important;
}
.video-thumbnail{
  display:block;
  width:100%!important;
  height:100%!important;
  object-fit:cover!important;
  object-position:center center!important;
}
.product-placeholder{
  width:100%!important;
  aspect-ratio:16 / 9!important;
  margin:0!important;
  border-radius:12px!important;
  border:1px solid rgba(15,23,42,.06)!important;
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:6px;
  overflow:hidden!important;
  box-sizing:border-box!important;
}
.product-placeholder span{font-size:38px}
.product-placeholder small{font-size:12px;font-weight:800}

/* 썸네일 하단 채널 출처 + 브랜드/카테고리 한 줄 바 */
.card-source-bar{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:6px;
  margin:8px 0 3px;
  min-width:0;
}
.source-chip{
  display:inline-flex;
  align-items:center;
  gap:4px;
  min-width:0;
  max-width:62%;
  padding:2px 7px;
  border-radius:6px;
  background:#F2F5FA;
  color:#333D4B;
  font-size:11px;
  font-weight:750;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.source-chip b{color:#FF0033;font-size:9px;flex-shrink:0}
.brand-eyebrow{
  font-size:11px;
  font-weight:700;
  color:var(--muted);
  letter-spacing:-.01em;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  text-align:right;
}

/* 카드 타이포그래피 & 뱃지 (2줄 기준 최소 높이 통일로 버튼 가로 정렬) */
.product-title{font-size:15.5px;font-weight:850;color:var(--ink);line-height:1.38;height:43px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card-meta-row{display:flex;flex-wrap:wrap;align-items:flex-start;align-content:flex-start;gap:4px;margin:7px 0 6px;min-height:46px}
.badge{display:inline-flex;align-items:center;height:21px;color:#245FB5;background:#EDF4FF;padding:0 7px;border-radius:6px;font-size:10.5px;font-weight:750}
.purchase-dot{display:inline-flex;align-items:center;gap:4px;height:21px;padding:0 7px;border-radius:6px;font-size:10.5px;font-weight:750}
.purchase-dot i{display:inline-block;width:5px;height:5px;border-radius:50%}
.purchase-buy{color:#146C43;background:#EBF8F2}.purchase-buy i{background:#198754}
.purchase-provided{color:#8A5A00;background:#FFF7E0}.purchase-provided i{background:#E09F00}
.purchase-ad,.purchase-unknown{color:#B42318;background:#FFF0F0}.purchase-ad i,.purchase-unknown i{background:#E5484D}

/* 장단점 요약 박스 */
.card-summary-wrap{margin:0;display:flex;flex-direction:column;gap:5px;height:74px;justify-content:flex-start;overflow:hidden}
.st-key-product_grid .summary-line{display:-webkit-box!important;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin:0!important;padding:7px 9px!important;border-radius:8px;font-size:12px!important;line-height:1.4!important;word-break:keep-all!important}
.card-summary-wrap.has-two .summary-line{-webkit-line-clamp:1!important;padding:6px 9px!important}
.summary-pro{background:#F0F9F4;color:#15653E}
.summary-con{background:#FFF4F4;color:#A61B22}
.summary-reason{background:#F5F7FA;color:#4E5968}

/* 쇼핑몰 고유 브랜드 컬러 버튼 (1줄 2~3열 깔끔 배치) */
.shop-btn-grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:6px;
  width:100%;
  margin-top:4px;
}
.shop-btn-grid.cols-3{
  grid-template-columns:repeat(3,minmax(0,1fr));
}
.shop-btn{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:0;
  min-height:37px;
  padding:4px 5px;
  border-radius:9px;
  font-size:12px;
  font-weight:800;
  text-decoration:none!important;
  white-space:nowrap;
  letter-spacing:-.02em;
  transition:filter .15s;
}
.shop-btn:hover{
  filter:brightness(0.92);
}
.shop-btn-naver{
  background:#03C75A!important;
  border:1px solid #03C75A!important;
  color:#FFFFFF!important;
}
.shop-btn-coupang{
  background:#E61E2B!important;
  border:1px solid #E61E2B!important;
  color:#FFFFFF!important;
}
.shop-btn-musinsa{
  background:#111111!important;
  border:1px solid #111111!important;
  color:#FFFFFF!important;
}
.shop-btn-zigzag{
  background:#E847AE!important;
  border:1px solid #E847AE!important;
  color:#FFFFFF!important;
}
.shop-btn-ably{
  background:#FF5160!important;
  border:1px solid #FF5160!important;
  color:#FFFFFF!important;
}

/* 상세 비교 아코디언 */
.st-key-product_grid [data-testid="stExpander"]{margin-top:2px!important;margin-bottom:4px!important;border:1px solid #ECEEF2!important;border-radius:10px!important;background:#FAFBFD!important}
.st-key-product_grid [data-testid="stExpander"] summary{min-height:35px!important;padding:5px 10px!important;font-size:12.5px!important;font-weight:700!important;color:var(--sub)!important}
.st-key-product_grid [data-testid="stExpanderDetails"]{padding:10px 11px!important;max-height:240px!important;overflow-y:auto!important;background:#fff!important}
.exp-section-title{font-size:11px;font-weight:800;color:var(--muted);margin:0 0 5px}
.exp-point{font-size:12px;line-height:1.4;padding:5px 8px;border-radius:7px;margin-bottom:4px;word-break:keep-all}
.exp-pro{background:#F0F9F4;color:#15653E}
.exp-con{background:#FFF4F4;color:#A61B22}
.exp-divider{height:1px;background:#EDF1F6;margin:8px 0}
.exp-rec-item{padding:6px 0;border-bottom:1px solid #F2F4F8}
.exp-rec-item:last-child{border-bottom:0;padding-bottom:0}
.exp-rec-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:2px}
.exp-channel{font-size:12px;font-weight:800;color:var(--ink)}
.exp-video-link{flex-shrink:0;font-size:11px;font-weight:750;color:var(--brand)!important;background:#EDF4FF;padding:2px 8px;border-radius:999px;text-decoration:none!important}
.exp-video-title{font-size:11px;color:var(--muted);line-height:1.35;margin-bottom:3px}
.exp-evidence{font-size:12px;color:#333D4B;line-height:1.4;word-break:keep-all}

/* 페이지네이션 번호 바 (PC·모바일 공통 1줄 가로 정렬) */
.st-key-pagination_bar{margin:10px 0 4px!important}
.st-key-pagination_bar [data-testid="stHorizontalBlock"]{
  display:flex!important;
  flex-direction:row!important;
  flex-wrap:nowrap!important;
  justify-content:center!important;
  align-items:center!important;
  gap:6px!important;
  width:100%!important;
  max-width:460px!important;
  margin:0 auto!important;
}
.st-key-pagination_bar [data-testid="stColumn"],
.st-key-pagination_bar [data-testid="column"]{
  flex:0 0 auto!important;
  width:auto!important;
  min-width:38px!important;
  max-width:none!important;
  padding:0!important;
  margin:0!important;
}
.st-key-pagination_bar .stButton>button{
  min-width:38px!important;
  min-height:38px!important;
  padding:0 11px!important;
  border-radius:10px!important;
  font-size:13px!important;
  font-weight:800!important;
}
.st-key-pagination_bar .stButton>button[kind="secondary"]{
  background:#fff!important;
  border:1px solid #DCE3EC!important;
  color:#333D4B!important;
}
.st-key-pagination_bar .stButton>button[kind="secondary"]:hover{
  border-color:var(--brand)!important;
  color:var(--brand)!important;
}

/* 하단 쿠팡 파트너스 필수 고지 푸터 */
.site-footer{
  margin-top:18px;
  margin-bottom:12px;
  padding:15px 18px;
  background:#fff;
  border:1px solid #E5E8EB;
  border-radius:14px;
  text-align:center;
  color:var(--sub);
  font-size:12.5px;
  font-weight:650;
  line-height:1.6;
  word-break:keep-all;
}
.site-footer-sub{
  display:block;
  margin-top:3px;
  font-size:11.5px;
  font-weight:500;
  color:var(--muted);
}

/* 관리자 통계 카드 */
.metric{background:#fff;border:1px solid #EAECEF;border-radius:15px;padding:14px;min-height:90px}
.metric-label{color:var(--muted);font-size:12px;font-weight:700}
.metric-value{color:var(--brand);font-size:24px;font-weight:900;margin-top:4px}
.status-row{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #EDF1F6;font-size:13px}
.status-row:last-child{border-bottom:0}
.error-box{background:#FFF0F0;color:#A61B22;padding:10px;border-radius:10px;font-size:12px;margin:6px 0;word-break:break-word}

/* 태블릿 & 모바일 반응형 */
@media(max-width:900px) and (min-width:641px){
  .st-key-product_grid [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
  .st-key-product_grid [data-testid="stColumn"],
  .st-key-product_grid [data-testid="column"]{flex:0 0 calc(50% - 8px)!important;width:calc(50% - 8px)!important;min-width:calc(50% - 8px)!important}
}
@media(max-width:640px){
  .block-container{padding:.75rem .75rem 3rem!important;width:100%!important;max-width:100%!important}
  .top-nav{margin-bottom:9px}
  .top-sub{display:none!important}
  .hero-banner{padding:14px 14px}
  .hero-headline{font-size:17.5px}
  .hero-stats{
    flex-wrap:nowrap!important;
    gap:4px!important;
    margin-top:9px!important;
    overflow-x:auto!important;
  }
  .stat-pill{
    padding:4px 7px!important;
    font-size:10.5px!important;
    gap:3px!important;
    letter-spacing:-.03em!important;
    flex-shrink:0!important;
  }
  .top-disclosure{font-size:10.5px;padding:6px 8px}
  .st-key-filter_bar [data-testid="stHorizontalBlock"]{
    display:grid!important;
    grid-template-columns:1fr 1fr!important;
    gap:7px!important;
    width:100%!important;
    margin:0!important;
  }
  .st-key-filter_bar [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child,
  .st-key-filter_bar [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child{
    grid-column:1 / -1!important;
    width:100%!important;
    min-width:0!important;
  }
  .st-key-filter_bar [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  .st-key-filter_bar [data-testid="stHorizontalBlock"] > [data-testid="column"]{
    width:100%!important;
    min-width:0!important;
  }
  .st-key-product_grid > div > [data-testid="stHorizontalBlock"]{
    display:grid!important;
    grid-template-columns:minmax(0,1fr)!important;
    gap:12px!important;
    width:100%!important;
    margin:0!important;
  }
  .st-key-product_grid > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  .st-key-product_grid > div > [data-testid="stHorizontalBlock"] > [data-testid="column"]{
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    flex:none!important;
    margin:0!important;
    padding:0!important;
  }
  .st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"]{padding:12px 12px 18px!important}
  .st-key-product_grid .product-title{height:auto!important;min-height:0!important}
  .st-key-product_grid .card-meta-row{min-height:0!important}
  .card-summary-wrap{height:auto!important;min-height:0!important}
  .st-key-pagination_bar [data-testid="stHorizontalBlock"]{gap:4px!important}
  .st-key-pagination_bar [data-testid="stColumn"],
  .st-key-pagination_bar [data-testid="column"]{min-width:34px!important}
  .st-key-pagination_bar .stButton>button{min-width:34px!important;min-height:36px!important;padding:0 8px!important;font-size:12.5px!important}
  .site-footer{padding:13px 12px;font-size:11.5px}
  .site-footer-sub{font-size:10.5px}
}
</style>
""", unsafe_allow_html=True)

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Streamlit Secrets에 SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY를 등록하세요.")
    st.stop()

if "page" not in st.session_state:
    st.session_state.page = "home"

should_scroll_top = bool(st.session_state.pop("scroll_to_top", False))
scroll_js = (
    "const main = doc.querySelector('section.main');"
    "if (main) main.scrollTo({top: 0, behavior: 'smooth'});"
    "window.parent.scrollTo({top: 0, behavior: 'smooth'});"
    if should_scroll_top
    else ""
)
components.html(
    "<script>"
    "(function(){"
    "  const doc = window.parent.document;"
    "  if (!doc.getElementById('edition-hide-chrome')) {"
    "    const st = doc.createElement('style');"
    "    st.id = 'edition-hide-chrome';"
    "    st.textContent = '"
    "      header, [data-testid=\"stHeader\"], [data-testid=\"stAppHeader\"], [data-testid=\"stDecoration\"], [data-testid=\"stToolbar\"] { display:none!important; height:0!important; border:0!important; box-shadow:none!important; }"
    "      .stApp, [data-testid=\"stAppViewContainer\"], [data-testid=\"stMain\"], section.main, [data-testid=\"stMainBlockContainer\"] { box-shadow:none!important; border-top:0!important; outline:0!important; }"
    "      [data-testid=\"stMain\"]::before, [data-testid=\"stMain\"]::after, section.main::before, section.main::after { display:none!important; content:none!important; box-shadow:none!important; border:0!important; }"
    "    ';"
    "    doc.head.appendChild(st);"
    "  }"
    "  const cleanTopChrome = () => {"
    "    doc.querySelectorAll('header, [data-testid=\"stHeader\"], [data-testid=\"stAppHeader\"], [data-testid=\"stDecoration\"]').forEach(el => {"
    "      el.style.setProperty('display', 'none', 'important');"
    "      el.style.setProperty('border', 'none', 'important');"
    "      el.style.setProperty('box-shadow', 'none', 'important');"
    "    });"
    "    doc.querySelectorAll('.stApp, [data-testid=\"stAppViewContainer\"], [data-testid=\"stMain\"], section.main').forEach(el => {"
    "      el.style.setProperty('box-shadow', 'none', 'important');"
    "      el.style.setProperty('border-top', '0', 'important');"
    "    });"
    "    doc.querySelectorAll('div, section, header').forEach(el => {"
    "      const r = el.getBoundingClientRect();"
    "      if (r.top >= -2 && r.top <= 6 && r.height > 0 && r.height <= 5 && r.width >= window.parent.innerWidth * 0.8) {"
    "        el.style.setProperty('display', 'none', 'important');"
    "      }"
    "    });"
    "  };"
    "  cleanTopChrome();"
    "  if (!window.parent.__editionChromeObserver) {"
    "    window.parent.__editionChromeObserver = new MutationObserver(cleanTopChrome);"
    "    window.parent.__editionChromeObserver.observe(doc.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'style'] });"
    "  }"
    f"  {scroll_js}"
    "})();"
    "</script>",
    height=0,
)

admin_query = str(st.query_params.get("admin", "")).strip() == "1"
if admin_query and not st.session_state.get("show_admin_bar"):
    st.session_state.show_admin_bar = True

st.markdown(
    '<div class="top-nav">'
    '<div class="brand-wrap">'
    '<span class="brand-logo">✦</span>'
    '<span class="brand-name">에디션 픽</span>'
    '<span class="brand-en">EDITION PICK</span>'
    '</div>'
    '<span class="top-sub">실사용 리뷰 데이터 기반 엄선 아카이브</span>'
    '</div>',
    unsafe_allow_html=True,
)

if st.session_state.get("show_admin_bar") or st.session_state.page != "home":
    nav = st.columns(4)
    for column, key, label in zip(nav, ["home", "dashboard", "review", "manage"], ["에디션 홈", "운영 통계", "상품 검수", "상품 관리"]):
        if column.button(label, type="primary" if st.session_state.page == key else "secondary", use_container_width=True):
            st.session_state.page = key
            st.rerun()


def require_admin():
    password = secret("ADMIN_PASSWORD")
    if not password:
        st.error("Streamlit Secrets에 ADMIN_PASSWORD가 없습니다.")
        return False
    if st.session_state.get("admin_authenticated"):
        return True
    with st.container(border=True):
        entered = st.text_input("관리자 비밀번호", type="password")
        if st.button("관리자 로그인", type="primary", use_container_width=True):
            if entered == password:
                st.session_state.admin_authenticated = True
                st.rerun()
            st.error("비밀번호가 맞지 않습니다.")
    return False


def is_single_product_video(product, rec):
    """영상 제목에 브랜드나 모델명이 직접 포함되어 단품/집중 리뷰인지 판별한다."""
    title_norm = norm_key((rec.get("video") or {}).get("title"))
    if not title_norm:
        return False
    brand_norm = norm_key(product.get("brand"))
    model_norm = norm_key(product.get("model"))
    return bool(
        (len(brand_norm) >= 2 and brand_norm in title_norm)
        or (len(model_norm) >= 2 and model_norm in title_norm)
    )


def get_representative_rec(product):
    recommendations = product.get("recommendations") or []
    ranked = sorted(
        recommendations,
        key=lambda rec: (
            1 if is_single_product_video(product, rec) else 0,
            int((rec.get("video") or {}).get("view_count") or 0),
            float(rec.get("confidence") or 0),
            str((rec.get("video") or {}).get("published_at") or ""),
        ),
        reverse=True,
    )
    return next((rec for rec in ranked if rec.get("video_id")), None)


def render_product_visual(product, representative=None):
    """1순위: 관리자 검증 이미지 -> 2순위: 단품 리뷰 영상 썸네일 -> 3순위: 최고 조회수 영상 썸네일."""
    image_url = str(product.get("image_url") or "").strip()
    if product.get("image_verified") and image_url.startswith(("https://", "http://")):
        st.markdown(
            '<div class="video-thumbnail-wrap">'
            f'<img class="video-thumbnail" src="{safe(image_url)}" alt="{safe(product.get("canonical_name"))}">'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    if representative is None:
        representative = get_representative_rec(product)
    if representative:
        video_id = safe(representative["video_id"])
        hd_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        fallback_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        st.markdown(
            '<div class="video-thumbnail-wrap">'
            f'<img class="video-thumbnail" src="{hd_url}" onerror="this.onerror=null;this.src=\'{fallback_url}\';" alt="추천 영상 썸네일">'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    category = product.get("category") or "기타"
    icon, background, color = CATEGORY_VISUALS.get(category, CATEGORY_VISUALS["기타"])
    st.markdown(
        f'<div class="product-placeholder" style="background:{background};color:{color}">'
        f'<span>{icon}</span><small>{safe(category)}</small></div>',
        unsafe_allow_html=True,
    )


def recommendation_summary(recommendations):
    purchase_counts = Counter()
    pros = Counter()
    cons = Counter()
    for rec in recommendations:
        purchase_counts[str(rec.get("purchase_type") or "확인되지 않음").strip()] += 1
        for value in rec.get("pros") or []:
            text = re.sub(r"\s+", " ", str(value).strip())
            if is_meaningful_point(text):
                pros[text] += 1
        for value in rec.get("cons") or []:
            text = re.sub(r"\s+", " ", str(value).strip())
            if is_meaningful_point(text):
                cons[text] += 1
    return {
        "purchase_counts": purchase_counts,
        "pros": [text for text, _ in pros.most_common(3)],
        "cons": [text for text, _ in cons.most_common(3)],
    }


def render_purchase_badges(counts):
    labels = [
        ("직접 구매", "내돈내산", "purchase-buy"),
        ("제품 제공", "제품제공", "purchase-provided"),
        ("유료 광고", "유료광고", "purchase-ad"),
    ]
    parts = []
    for key, label, css_class in labels:
        count = int(counts.get(key, 0))
        if count:
            parts.append(f'<span class="purchase-dot {css_class}"><i></i>{label} {count}</span>')
    return "".join(parts)


def render_product_card(product):
    recs = product["recommendations"]
    pid = safe(product.get("product_id"))
    representative = get_representative_rec(product)
    channel_count = len({r.get("channel_id") for r in recs if r.get("channel_id")})
    rep_channel = ((representative or {}).get("channel") or {}).get("channel_name") or (
        ((recs[0].get("channel") or {}).get("channel_name") if recs else "") or "유튜버 추천"
    )
    source_label = f"{rep_channel} 외 {channel_count - 1}명" if channel_count > 1 else rep_channel

    with st.container(border=True):
        render_product_visual(product, representative=representative)
        st.markdown(
            '<div class="card-source-bar">'
            f'<span class="source-chip"><b>▶</b> {safe(source_label)}</span>'
            f'<span class="brand-eyebrow">{safe(product.get("brand"))} · {safe(product.get("category") or "기타")}</span>'
            '</div>'
            f'<div class="product-title">{safe(product.get("canonical_name"))}</div>',
            unsafe_allow_html=True,
        )
        confidence = max([float(r.get("confidence") or 0) for r in recs] or [0])
        summary = recommendation_summary(recs)
        purchase_html = render_purchase_badges(summary["purchase_counts"])
        st.markdown(
            '<div class="card-meta-row">'
            f'<span class="badge">유튜버 {channel_count}명</span>'
            f'<span class="badge">영상 {len(recs)}개</span>'
            f'<span class="badge">신뢰도 {confidence:.0%}</span>'
            f'{purchase_html}'
            '</div>',
            unsafe_allow_html=True,
        )

        pro_line = summary["pros"][0] if summary["pros"] else ""
        con_line = summary["cons"][0] if summary["cons"] else ""
        fallback_reason = next(
            (
                re.sub(r"\s+", " ", str(r.get("reason") or "").strip())
                for r in recs
                if is_meaningful_point(r.get("reason"))
            ),
            "",
        )

        summary_blocks = []
        if pro_line:
            summary_blocks.append(f'<div class="summary-line summary-pro">👍 {safe(pro_line)}</div>')
        if con_line:
            summary_blocks.append(f'<div class="summary-line summary-con">👎 {safe(con_line)}</div>')
        if not summary_blocks and fallback_reason:
            summary_blocks.append(f'<div class="summary-line summary-reason">💡 {safe(fallback_reason)}</div>')
        if summary_blocks:
            wrap_cls = "card-summary-wrap has-two" if len(summary_blocks) >= 2 else "card-summary-wrap"
            st.markdown(f'<div class="{wrap_cls}">{"".join(summary_blocks)}</div>', unsafe_allow_html=True)

        mall_buttons = detect_product_malls(product)
        grid_cls = "shop-btn-grid cols-3" if len(mall_buttons) >= 3 else "shop-btn-grid"
        btn_html = "".join(
            f'<a class="shop-btn {safe(btn["css"])}" href="?go={safe(btn["mall"])}&pid={pid}" target="_blank" rel="noopener noreferrer">{safe(btn["label"])}</a>'
            for btn in mall_buttons
        )
        st.markdown(f'<div class="{grid_cls}">{btn_html}</div>', unsafe_allow_html=True)

        with st.expander(f"영상 근거 · 장단점 비교 ({len(recs)}개)"):
            exp_parts = []
            if summary["pros"] or summary["cons"]:
                exp_parts.append('<div class="exp-section-title">핵심 장단점 요약</div>')
                for value in summary["pros"]:
                    exp_parts.append(f'<div class="exp-point exp-pro">👍 {safe(value)}</div>')
                for value in summary["cons"]:
                    exp_parts.append(f'<div class="exp-point exp-con">👎 {safe(value)}</div>')
                exp_parts.append('<div class="exp-divider"></div>')
            for rec in recs:
                channel = rec.get("channel", {})
                video = rec.get("video", {})
                ch_name = safe(channel.get("channel_name") or "알 수 없는 채널")
                v_title = safe(video.get("title") or "제목 없음")
                v_id = safe(rec.get("video_id") or "")
                link_html = (
                    f'<a class="exp-video-link" href="https://youtu.be/{v_id}" target="_blank" rel="noopener noreferrer">영상 보기 ↗</a>'
                    if v_id else ""
                )
                ev_text = clean_evidence_text(rec.get("evidence"))
                ev_html = f'<div class="exp-evidence">{safe(ev_text)}</div>' if ev_text else ""
                exp_parts.append(
                    '<div class="exp-rec-item">'
                    f'<div class="exp-rec-head"><span class="exp-channel">{ch_name}</span>{link_html}</div>'
                    f'<div class="exp-video-title">{v_title}</div>'
                    f'{ev_html}'
                    '</div>'
                )
            st.markdown("".join(exp_parts), unsafe_allow_html=True)


def render_home():
    products = load_public_data()
    channel_ids = {r.get("channel_id") for p in products for r in p["recommendations"] if r.get("channel_id")}
    video_ids = {r.get("video_id") for p in products for r in p["recommendations"] if r.get("video_id")}
    st.markdown(
        '<div class="hero-banner">'
        '<div class="hero-kicker">실제 리뷰 영상 데이터 기반 엄선 큐레이션</div>'
        f'<div class="hero-headline">에디션 픽이 검증한 추천 아이템 <b>{len(products):,}개</b></div>'
        '<div class="hero-stats">'
        f'<span class="stat-pill">📺 분석 채널 <strong>{len(channel_ids):,}개</strong></span>'
        f'<span class="stat-pill">🎬 근거 영상 <strong>{len(video_ids):,}개</strong></span>'
        '<span class="stat-pill">✦ 매일 자동 업데이트</span>'
        '</div>'
        '</div>'
        '<div class="top-disclosure">이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</div>',
        unsafe_allow_html=True,
    )
    with st.container(key="filter_bar"):
        a, b, c = st.columns([1.8, 1, 0.9])
        keyword = a.text_input("검색", placeholder="상품명, 브랜드, 유튜버 검색", label_visibility="collapsed")
        categories = sorted({p.get("category") or "기타" for p in products})
        category = b.selectbox("카테고리", ["전체 카테고리"] + categories, label_visibility="collapsed")
        sort_by = c.selectbox("정렬", ["추천 많은순", "최신 등록순"], label_visibility="collapsed")

    clean_kw = keyword.strip()
    filter_sig = (clean_kw, category, sort_by)
    if st.session_state.get("last_filter_sig") != filter_sig:
        st.session_state.last_filter_sig = filter_sig
        st.session_state.catalog_page = 1

    if len(clean_kw) >= 2 and clean_kw != st.session_state.get("last_logged_keyword"):
        st.session_state.last_logged_keyword = clean_kw
        log_event("search", search_query=clean_kw)

    scored_items = []
    for product in products:
        if category != "전체 카테고리" and (product.get("category") or "기타") != category:
            continue
        match_score = score_product_search(product, clean_kw)
        if clean_kw and match_score <= 0:
            continue
        scored_items.append((match_score, product))

    if clean_kw:
        if sort_by == "최신 등록순":
            scored_items.sort(key=lambda item: (item[0], str(item[1].get("created_at") or "")), reverse=True)
        else:
            scored_items.sort(
                key=lambda item: (
                    item[0],
                    len({r.get("channel_id") for r in item[1]["recommendations"]}),
                    len(item[1]["recommendations"]),
                ),
                reverse=True,
            )
    elif sort_by == "최신 등록순":
        scored_items.sort(key=lambda item: str(item[1].get("created_at") or ""), reverse=True)

    shown = [item[1] for item in scored_items]

    st.markdown(
        f'<div class="result-bar"><span>검색 결과 <b>{len(shown):,}</b>개</span><span>공식 쇼핑몰별 최저가 비교</span></div>',
        unsafe_allow_html=True,
    )

    page_size = 24
    pages = max(1, (len(shown) + page_size - 1) // page_size)
    page = min(max(int(st.session_state.get("catalog_page", 1)), 1), pages)
    page_products = shown[(page - 1) * page_size:page * page_size]

    with st.container(key="product_grid"):
        for start in range(0, len(page_products), 3):
            cols = st.columns(3, gap="medium")
            for col, product in zip(cols, page_products[start:start + 3]):
                with col:
                    render_product_card(product)

    if pages > 1:
        page_nums = get_page_numbers(page, pages)
        with st.container(key="pagination_bar"):
            p_cols = st.columns(len(page_nums) + 2)
            if p_cols[0].button("‹", key="page_prev", disabled=page <= 1, use_container_width=True):
                st.session_state.catalog_page = page - 1
                st.session_state.scroll_to_top = True
                st.rerun()
            for idx, num in enumerate(page_nums, start=1):
                is_curr = num == page
                if p_cols[idx].button(
                    str(num),
                    key=f"page_num_{num}",
                    type="primary" if is_curr else "secondary",
                    use_container_width=True,
                ):
                    if not is_curr:
                        st.session_state.catalog_page = num
                        st.session_state.scroll_to_top = True
                        st.rerun()
            if p_cols[-1].button("›", key="page_next", disabled=page >= pages, use_container_width=True):
                st.session_state.catalog_page = page + 1
                st.session_state.scroll_to_top = True
                st.rerun()

    st.markdown(
        '<div class="site-footer">'
        '이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.'
        '<span class="site-footer-sub">에디션 픽(EDITION PICK)은 유튜브 공개 리뷰 영상을 분석해 상품 정보를 제공하며, 실제 가격·재고 및 거래 조건은 각 쇼핑몰 페이지를 따릅니다.</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    _, admin_col = st.columns([5, 1])
    with admin_col:
        toggle_label = "관리자 닫기" if st.session_state.get("show_admin_bar") else "관리자"
        if st.button(toggle_label, key="toggle_admin_footer", use_container_width=True):
            st.session_state.show_admin_bar = not st.session_state.get("show_admin_bar", False)
            st.rerun()


def render_dashboard():
    if not require_admin():
        return
    products, videos, channels, queries, recs, click_logs, click_logs_ready = load_admin_data()
    ps, vs = count_by(products, "review_status"), count_by(videos, "analysis_status")
    active = sum(1 for c in channels if c.get("status") == "active")
    qerrors = sum(1 for q in queries if int(q.get("error_count") or 0) > 0 or q.get("last_error"))
    metrics = [
        ("전체 채널", len(channels), f"활성 {active}"),
        ("전체 영상", len(videos), f"AI 대기 {vs.get('queued',0)}"),
        ("공개 상품", ps.get("approved", 0), f"검수 {ps.get('pending',0)}"),
        ("검색어", len(queries), f"오류 {qerrors}"),
    ]
    for col, (label, value, sub) in zip(st.columns(4), metrics):
        col.markdown(
            f'<div class="metric"><div class="metric-label">{label}</div>'
            f'<div class="metric-value">{value:,}</div><div class="brand-eyebrow">{sub}</div></div>',
            unsafe_allow_html=True,
        )

    st.subheader("방문자 클릭 · 검색 통계")
    if not click_logs_ready:
        st.info("Supabase에 click_logs 테이블을 생성하면 상품별 쇼핑몰 클릭 순위와 방문자 검색어 통계가 자동으로 집계됩니다.")
    else:
        coupang_clicks = [x for x in click_logs if x.get("event_type") == "coupang_click"]
        naver_clicks = [x for x in click_logs if x.get("event_type") == "naver_click"]
        fashion_clicks = [x for x in click_logs if x.get("event_type") in {"musinsa_click", "zigzag_click", "ably_click"}]
        search_logs = [x for x in click_logs if x.get("event_type") == "search" and x.get("search_query")]

        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        for col, (lbl, val) in zip(
            [c_m1, c_m2, c_m3, c_m4],
            [
                ("쿠팡 클릭", len(coupang_clicks)),
                ("네이버쇼핑 클릭", len(naver_clicks)),
                ("패션·뷰티몰 클릭", len(fashion_clicks)),
                ("방문자 검색", len(search_logs)),
            ],
        ):
            col.markdown(
                f'<div class="metric"><div class="metric-label">{lbl}</div>'
                f'<div class="metric-value">{val:,}</div></div>',
                unsafe_allow_html=True,
            )

        product_lookup = {p["product_id"]: p for p in products}
        click_counts = Counter()
        coupang_by_item = Counter()
        naver_by_item = Counter()
        fashion_by_item = Counter()
        label_by_item = {}
        for row in coupang_clicks + naver_clicks + fashion_clicks:
            key = row.get("product_id") or row.get("product_name") or "unknown"
            click_counts[key] += 1
            ev_type = row.get("event_type")
            if ev_type == "coupang_click":
                coupang_by_item[key] += 1
            elif ev_type == "naver_click":
                naver_by_item[key] += 1
            else:
                fashion_by_item[key] += 1
            p_info = product_lookup.get(row.get("product_id"))
            label_by_item[key] = (p_info or {}).get("canonical_name") or row.get("product_name") or "이름 없음"

        cl_left, cl_right = st.columns(2)
        with cl_left:
            with st.container(border=True):
                st.markdown("**클릭 많은 상품 TOP 15 (제휴 링크 우선 대상)**")
                if not click_counts:
                    st.caption("아직 기록된 상품 클릭이 없습니다.")
                for key, total in click_counts.most_common(15):
                    p_info = product_lookup.get(key) or {}
                    extra_links, _ = parse_extra_partner_links(p_info)
                    has_any_partner = bool(p_info.get("affiliate_verified") or any(extra_links.values()))
                    linked = "✅ 제휴연결" if has_any_partner else "미연결"
                    extra_str = f" · 패션뷰티 {fashion_by_item[key]}" if fashion_by_item[key] else ""
                    st.markdown(
                        f'<div class="status-row">'
                        f'<span>{safe(label_by_item.get(key))} <small style="color:#8B95A1">({linked})</small></span>'
                        f'<b>쿠팡 {coupang_by_item[key]} · 네이버 {naver_by_item[key]}{extra_str}</b>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
        with cl_right:
            with st.container(border=True):
                st.markdown("**방문자 인기 검색어 TOP 15**")
                sq_counts = Counter(str(r.get("search_query")).strip() for r in search_logs)
                if not sq_counts:
                    st.caption("아직 기록된 검색어가 없습니다.")
                for q_text, cnt in sq_counts.most_common(15):
                    st.markdown(
                        f'<div class="status-row"><span>{safe(q_text)}</span><b>{cnt:,}회</b></div>',
                        unsafe_allow_html=True,
                    )

    st.subheader("영상 처리 현황")
    l, r = st.columns(2)
    with l:
        with st.container(border=True):
            for key in ["pending", "queued", "analyzed", "no_product", "rejected_generic", "skipped_non_product", "ai_error"]:
                st.markdown(f'<div class="status-row"><span>{key}</span><b>{vs.get(key,0):,}</b></div>', unsafe_allow_html=True)
    with r:
        with st.container(border=True):
            for key in ["approved", "pending", "hidden", "merged"]:
                st.markdown(f'<div class="status-row"><span>상품 {key}</span><b>{ps.get(key,0):,}</b></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="status-row"><span>추천 기록</span><b>{len(recs):,}</b></div>', unsafe_allow_html=True)
    st.subheader("최근 오류")
    errors = [v for v in videos if v.get("analysis_status") == "ai_error" and v.get("analysis_error")][:10]
    qrows = [q for q in queries if q.get("last_error")][:10]
    if not errors and not qrows:
        st.success("현재 기록된 최근 오류가 없습니다.")
    for row in errors:
        st.markdown(f'<div class="error-box"><b>영상:</b> {safe(row.get("title"))}<br>{safe(row.get("analysis_error"))}</div>', unsafe_allow_html=True)
    for row in qrows:
        st.markdown(f'<div class="error-box"><b>검색어:</b> {safe(row.get("query_text"))}<br>{safe(row.get("last_error"))}</div>', unsafe_allow_html=True)
    if st.button("통계 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


def product_form(product, prefix, allow_hide=False):
    pid = product["product_id"]
    extra_links, existing_memo = parse_extra_partner_links(product)
    with st.form(f"{prefix}_{pid}"):
        name = st.text_input("상품명", value=product.get("canonical_name") or "", key=f"{prefix}_name_{pid}")
        c1, c2 = st.columns(2)
        brand = c1.text_input("브랜드", value=product.get("brand") or "", key=f"{prefix}_brand_{pid}")
        model = c2.text_input("모델", value=product.get("model") or "", key=f"{prefix}_model_{pid}")
        current = product.get("category") if product.get("category") in CATEGORIES else "기타"
        category = st.selectbox("카테고리", CATEGORIES, index=CATEGORIES.index(current), key=f"{prefix}_cat_{pid}")
        keyword = st.text_input("검색 키워드", value=product.get("search_keyword") or product.get("canonical_name") or "", key=f"{prefix}_kw_{pid}")
        coupang_url = st.text_input(
            "쿠팡 파트너스 링크",
            value=product.get("coupang_url") or "",
            placeholder="https://link.coupang.com/...",
            key=f"{prefix}_cp_{pid}",
        )
        affiliate_verified = st.checkbox(
            "쿠팡 제휴 링크 확인 완료",
            value=bool(product.get("affiliate_verified")),
            key=f"{prefix}_aff_{pid}",
        )
        p1, p2, p3 = st.columns(3)
        musinsa_url = p1.text_input(
            "무신사 파트너 링크 (선택)",
            value=extra_links.get("musinsa") or "",
            placeholder="https://...",
            key=f"{prefix}_ms_{pid}",
        )
        zigzag_url = p2.text_input(
            "지그재그 파트너 링크 (선택)",
            value=extra_links.get("zigzag") or "",
            placeholder="https://...",
            key=f"{prefix}_zz_{pid}",
        )
        ably_url = p3.text_input(
            "에이블리 파트너 링크 (선택)",
            value=extra_links.get("ably") or "",
            placeholder="https://...",
            key=f"{prefix}_ab_{pid}",
        )
        image_url = st.text_input("이미지 URL", value=product.get("image_url") or "", placeholder="https://...", key=f"{prefix}_img_{pid}")
        source = st.selectbox(
            "이미지 출처",
            IMAGE_SOURCES,
            index=IMAGE_SOURCES.index(product.get("image_source")) if product.get("image_source") in IMAGE_SOURCES else 0,
            format_func=lambda x: IMAGE_SOURCE_LABELS[x],
            key=f"{prefix}_src_{pid}",
        )
        verified = st.checkbox("정확한 상품 이미지 확인 완료", value=bool(product.get("image_verified")), key=f"{prefix}_ver_{pid}")
        image_note = st.text_input("이미지 메모", value=product.get("image_note") or "", key=f"{prefix}_note_{pid}")
        visible = st.checkbox("홈에 공개", value=bool(product.get("is_visible")), key=f"{prefix}_vis_{pid}") if allow_hide else True
        save = st.form_submit_button("상품 정보 저장" if allow_hide else "승인 후 공개", type="primary", use_container_width=True)
    if not save:
        return
    if not name.strip() or not brand.strip():
        st.error("상품명과 브랜드를 입력하세요.")
        return
    if affiliate_verified and not coupang_url.strip().startswith("https://link.coupang.com/"):
        st.error("쿠팡 제휴 링크는 https://link.coupang.com/ 으로 시작해야 합니다.")
        return
    for label, url_val in [("무신사", musinsa_url), ("지그재그", zigzag_url), ("에이블리", ably_url)]:
        if url_val.strip() and not url_val.strip().startswith(("http://", "https://")):
            st.error(f"{label} 파트너 링크는 http 또는 https 주소여야 합니다.")
            return
    if verified and not image_url.strip().startswith(("http://", "https://")):
        st.error("확인된 이미지는 http 또는 https URL이 필요합니다.")
        return
    serialized_extra = serialize_extra_partner_links(
        {"musinsa": musinsa_url.strip(), "zigzag": zigzag_url.strip(), "ably": ably_url.strip()},
        memo=existing_memo,
    )
    api_patch(
        "products",
        {
            "canonical_name": name.strip(),
            "normalized_name": re.sub(r"[^0-9a-z가-힣]+", "", name.lower()),
            "brand": brand.strip(),
            "model": model.strip(),
            "category": category,
            "search_keyword": keyword.strip() or name.strip(),
            "coupang_url": coupang_url.strip() or None,
            "affiliate_verified": bool(affiliate_verified and coupang_url.strip().startswith("https://link.coupang.com/")),
            "affiliate_note": serialized_extra,
            "image_url": image_url.strip() or None,
            "image_source": source or None,
            "image_verified": bool(verified and image_url.strip()),
            "image_checked_at": datetime.now(timezone.utc).isoformat() if verified and image_url.strip() else None,
            "image_note": image_note.strip() or None,
            "review_status": "approved" if visible else "hidden",
            "is_visible": bool(visible),
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "review_note": "관리자 상품 관리에서 수정",
        },
        {"product_id": f"eq.{pid}"},
    )
    st.cache_data.clear()
    st.success("저장했습니다.")
    st.rerun()


def render_review():
    if not require_admin():
        return
    products, _, _, _, _, _, _ = load_admin_data()
    pending = [p for p in products if p.get("review_status") == "pending"]
    st.subheader(f"검수 대기 상품 {len(pending)}개")
    if not pending:
        st.success("검수 대기 상품이 없습니다.")
        return
    for product in pending:
        with st.container(border=True):
            st.markdown(f"### {safe(product.get('canonical_name'))}")
            st.caption(f"식별 점수 {int(product.get('identity_score') or 0)}/100 · {product.get('review_note') or '사유 없음'}")
            product_form(product, "review", allow_hide=False)


def render_manage():
    if not require_admin():
        return
    products, _, _, _, _, _, _ = load_admin_data()
    items = [p for p in products if p.get("review_status") in {"approved", "hidden"}]
    st.subheader("상품 관리")
    st.caption("승인·숨김 상품을 검색해 쿠팡·무신사·지그재그·에이블리 파트너 링크와 상품 정보를 수정합니다.")
    c1, c2 = st.columns([1.7, 1])
    keyword = c1.text_input("관리 상품 검색", placeholder="상품명·브랜드·모델 검색", label_visibility="collapsed", key="manage_search")
    status = c2.selectbox("관리 상태", ["전체", "공개", "숨김"], label_visibility="collapsed", key="manage_status")
    needle = keyword.strip().lower()
    filtered = []
    for product in items:
        if status == "공개" and not product.get("is_visible"):
            continue
        if status == "숨김" and product.get("is_visible"):
            continue
        text = " ".join(str(product.get(k) or "") for k in ("canonical_name", "brand", "model", "category")).lower()
        if needle and needle not in text:
            continue
        filtered.append(product)
    st.caption(f"검색 결과 {len(filtered)}개 · 한 화면 최대 20개")
    if not filtered:
        st.info("조건에 맞는 상품이 없습니다.")
        return
    for product in filtered[:20]:
        with st.container(border=True):
            title, status_col = st.columns([4, 1])
            title.markdown(f"### {safe(product.get('canonical_name'))}")
            status_col.caption("공개" if product.get("is_visible") else "숨김")
            preview, editor = st.columns([1, 2])
            with preview:
                render_product_visual(product)
            with editor:
                product_form(product, "manage", allow_hide=True)


try:
    if st.session_state.page == "home":
        render_home()
    elif st.session_state.page == "dashboard":
        render_dashboard()
    elif st.session_state.page == "review":
        render_review()
    else:
        render_manage()
except Exception as exc:
    st.error(str(exc))

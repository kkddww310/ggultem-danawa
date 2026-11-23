import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import quote

import requests
import streamlit as st

st.set_page_config(page_title="꿀템 다나와 · 유튜버 검증 최저가 비교", page_icon="🛍️", layout="wide")


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


def count_by(rows, key):
    return Counter(str(row.get(key) or "unknown") for row in rows)


def is_meaningful_point(text):
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if len(cleaned) < 2:
        return False
    return not any(pattern in cleaned for pattern in INVALID_POINT_PATTERNS)


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
    """외부 쇼핑몰 링크(?go=coupang|naver&pid=...) 클릭 시 로그를 남기고 즉시 이동시킨다."""
    go_type = str(st.query_params.get("go", "")).strip()
    go_pid = str(st.query_params.get("pid", "")).strip()
    if go_type not in {"coupang", "naver"} or not go_pid:
        return

    rows = []
    try:
        rows = api_get(
            "products",
            "product_id,canonical_name,search_keyword,coupang_url,affiliate_verified",
            {"product_id": f"eq.{go_pid}", "limit": "1"},
        )
    except Exception:
        rows = []

    product = rows[0] if rows else {}
    product_name = str(product.get("canonical_name") or product.get("search_keyword") or "").strip()
    query_name = quote(product_name)

    if go_type == "coupang":
        affiliate = bool(
            product.get("affiliate_verified")
            and str(product.get("coupang_url") or "").startswith("https://link.coupang.com/")
        )
        target_url = product["coupang_url"] if affiliate else f"https://www.coupang.com/np/search?q={query_name}"
        event_type = "coupang_click"
    else:
        target_url = f"https://search.shopping.naver.com/search/all?query={query_name}"
        event_type = "naver_click"

    log_event(event_type, product_id=go_pid if product else None, product_name=product_name or None)
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
        "product_id,canonical_name,brand,model,category,search_keyword,coupang_url,affiliate_verified,image_url,image_source,image_verified,image_checked_at,image_note,created_at",
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
#MainMenu,footer,[data-testid="stHeader"]{visibility:hidden}

/* 서비스 상단 헤더 & 히어로 배너 */
.top-nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.brand-wrap{display:flex;align-items:center;gap:9px}
.brand-logo{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:10px;background:var(--brand);color:#fff;font-size:18px;box-shadow:0 4px 12px rgba(49,130,246,.25)}
.brand-name{font-size:22px;font-weight:900;letter-spacing:-.03em;color:var(--ink)}
.brand-tag{font-size:11px;font-weight:750;color:var(--brand);background:var(--soft);padding:3px 8px;border-radius:999px}

.hero-banner{
  background:linear-gradient(135deg,#FFFFFF 0%,#F2F7FF 100%);
  border:1px solid #E2ECFF;
  border-radius:20px;
  padding:20px 22px;
  margin-bottom:14px;
  box-shadow:0 6px 20px rgba(49,130,246,.05);
}
.hero-kicker{font-size:12px;font-weight:750;color:var(--brand);margin-bottom:4px}
.hero-headline{font-size:21px;font-weight:850;letter-spacing:-.02em;color:var(--ink);line-height:1.35}
.hero-headline b{color:var(--brand)}
.hero-stats{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.stat-pill{display:inline-flex;align-items:center;gap:5px;background:#fff;border:1px solid #E5EAF2;padding:5px 11px;border-radius:999px;font-size:12px;font-weight:700;color:var(--sub)}
.stat-pill strong{color:var(--ink);font-weight:850}

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
.st-key-product_grid [data-testid="stHorizontalBlock"]{gap:16px!important;align-items:stretch!important;width:100%!important;margin:0!important}
.st-key-product_grid [data-testid="stColumn"],
.st-key-product_grid [data-testid="column"]{min-width:0!important;display:flex!important;flex-direction:column!important}

.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"]{
  border:1px solid #E6E9EF!important;
  background:#fff!important;
  border-radius:18px!important;
  box-shadow:0 6px 20px rgba(15,23,42,.045)!important;
  padding:0 14px 14px!important;
  margin-bottom:14px!important;
  overflow:hidden!important;
}
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] > div,
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"]{
  padding-top:0!important;
  margin-top:0!important;
}
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] > div:first-child,
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] > div:first-child [data-testid="stMarkdownContainer"]{
  padding-top:0!important;
  margin-top:0!important;
}

/* 썸네일 영역 + 채널 오버레이 칩 */
.video-thumbnail-wrap{
  position:relative;
  display:block;
  width:calc(100% + 28px)!important;
  aspect-ratio:16 / 9!important;
  margin:-8px -14px 11px!important;
  background:#111827!important;
  overflow:hidden!important;
}
.video-thumbnail-wrap::after{
  content:"";
  position:absolute;
  inset:0;
  background:linear-gradient(180deg,rgba(0,0,0,0) 58%,rgba(0,0,0,.55) 100%);
  pointer-events:none;
}
.video-thumbnail{
  display:block;
  width:100%!important;
  height:100%!important;
  object-fit:cover!important;
  object-position:center center!important;
}
.thumb-chip{
  position:absolute;
  left:10px;
  bottom:9px;
  z-index:2;
  display:inline-flex;
  align-items:center;
  gap:5px;
  max-width:calc(100% - 20px);
  padding:4px 9px;
  border-radius:999px;
  background:rgba(17,24,39,.78);
  backdrop-filter:blur(4px);
  color:#fff;
  font-size:11px;
  font-weight:700;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.thumb-chip b{color:#60A5FA;font-size:10px}
.product-placeholder{
  width:calc(100% + 28px)!important;
  aspect-ratio:16 / 9!important;
  margin:-8px -14px 11px!important;
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:6px;
}
.product-placeholder span{font-size:38px}
.product-placeholder small{font-size:12px;font-weight:800}
.st-key-product_grid [data-testid="stImage"]{
  width:calc(100% + 28px)!important;
  margin:-8px -14px 11px!important;
  overflow:hidden!important;
}
.st-key-product_grid [data-testid="stImage"] img{
  width:100%!important;
  aspect-ratio:16 / 9!important;
  object-fit:cover!important;
  padding:0!important;
}

/* 카드 타이포그래피 & 뱃지 */
.brand-eyebrow{font-size:11px;font-weight:750;color:var(--muted);letter-spacing:-.01em;margin-bottom:2px}
.product-title{font-size:15.5px;font-weight:850;color:var(--ink);line-height:1.38;min-height:43px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card-meta-row{display:flex;flex-wrap:wrap;align-items:center;gap:4px;margin:7px 0 8px}
.badge{display:inline-flex;align-items:center;height:21px;color:#245FB5;background:#EDF4FF;padding:0 7px;border-radius:6px;font-size:10.5px;font-weight:750}
.purchase-dot{display:inline-flex;align-items:center;gap:4px;height:21px;padding:0 7px;border-radius:6px;font-size:10.5px;font-weight:750}
.purchase-dot i{display:inline-block;width:5px;height:5px;border-radius:50%}
.purchase-buy{color:#146C43;background:#EBF8F2}.purchase-buy i{background:#198754}
.purchase-provided{color:#8A5A00;background:#FFF7E0}.purchase-provided i{background:#E09F00}
.purchase-ad,.purchase-unknown{color:#B42318;background:#FFF0F0}.purchase-ad i,.purchase-unknown i{background:#E5484D}

/* 장단점 요약 박스 */
.card-summary-wrap{margin:4px 0 10px;display:flex;flex-direction:column;gap:5px;min-height:74px;justify-content:center}
.st-key-product_grid .summary-line{display:block!important;margin:0!important;padding:7px 9px!important;border-radius:8px;font-size:12px!important;line-height:1.42!important;word-break:keep-all!important}
.summary-pro{background:#F0F9F4;color:#15653E}
.summary-con{background:#FFF4F4;color:#A61B22}
.summary-reason{background:#F5F7FA;color:#4E5968}

/* 쇼핑 버튼 2열 그리드 */
.shop-btn-grid{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:8px;
  width:100%;
  margin-top:2px;
}
.shop-btn{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-height:38px;
  padding:5px 6px;
  border-radius:10px;
  font-size:12.5px;
  font-weight:750;
  text-decoration:none!important;
  white-space:nowrap;
  transition:all .15s;
}
.shop-btn-primary{
  background:var(--brand)!important;
  border:1px solid var(--brand)!important;
  color:#fff!important;
}
.shop-btn-primary:hover{
  background:var(--brand-dark)!important;
  border-color:var(--brand-dark)!important;
}
.shop-btn-secondary{
  background:#F2F4F7!important;
  border:1px solid #E5E8EB!important;
  color:#333D4B!important;
}
.shop-btn-secondary:hover{
  background:#E8ECF2!important;
}

/* 상세 비교 아코디언 */
.st-key-product_grid [data-testid="stExpander"]{margin-top:8px!important;border:1px solid #ECEEF2!important;border-radius:10px!important;background:#FAFBFD!important}
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
  .st-key-product_grid [data-testid="column"]{flex:0 0 calc(50% - 8px)!important;min-width:calc(50% - 8px)!important}
}
@media(max-width:640px){
  .block-container{padding:.75rem .75rem 3rem!important;width:100%!important;max-width:100%!important}
  .hero-banner{padding:16px}
  .hero-headline{font-size:18px}
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
  .st-key-product_grid .product-title{min-height:0!important}
  .card-summary-wrap{min-height:0!important}
}
</style>
""", unsafe_allow_html=True)

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Streamlit Secrets에 SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY를 등록하세요.")
    st.stop()

if "page" not in st.session_state:
    st.session_state.page = "home"

admin_query = str(st.query_params.get("admin", "")).strip() == "1"
if admin_query and not st.session_state.get("show_admin_bar"):
    st.session_state.show_admin_bar = True

st.markdown(
    '<div class="top-nav">'
    '<div class="brand-wrap">'
    '<span class="brand-logo">🛍️</span>'
    '<span class="brand-name">꿀템 다나와</span>'
    '<span class="brand-tag">유튜버 검증</span>'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)

if st.session_state.get("show_admin_bar") or st.session_state.page != "home":
    nav = st.columns(4)
    for column, key, label in zip(nav, ["home", "dashboard", "review", "manage"], ["꿀템 홈", "운영 통계", "상품 검수", "상품 관리"]):
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


def render_product_visual(product):
    """1순위: 관리자 검증 이미지 -> 2순위: 단품 리뷰 영상 썸네일 -> 3순위: 최고 조회수 영상 썸네일."""
    image_url = str(product.get("image_url") or "").strip()
    if product.get("image_verified") and image_url.startswith(("https://", "http://")):
        st.image(image_url, use_container_width=True)
        return

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
    representative = next((rec for rec in ranked if rec.get("video_id")), None)
    if representative:
        video_id = safe(representative["video_id"])
        channel_name = safe((representative.get("channel") or {}).get("channel_name") or "유튜버 추천")
        hd_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        fallback_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        st.markdown(
            '<div class="video-thumbnail-wrap">'
            f'<img class="video-thumbnail" src="{hd_url}" onerror="this.onerror=null;this.src=\'{fallback_url}\';" alt="추천 영상 썸네일">'
            f'<span class="thumb-chip"><b>▶</b> {channel_name}</span>'
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
    with st.container(border=True):
        render_product_visual(product)
        st.markdown(
            f'<div class="brand-eyebrow">{safe(product.get("brand"))} · {safe(product.get("category") or "기타")}</div>'
            f'<div class="product-title">{safe(product.get("canonical_name"))}</div>',
            unsafe_allow_html=True,
        )
        channel_count = len({r.get("channel_id") for r in recs if r.get("channel_id")})
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
            st.markdown(f'<div class="card-summary-wrap">{"".join(summary_blocks)}</div>', unsafe_allow_html=True)

        affiliate = bool(
            product.get("affiliate_verified")
            and str(product.get("coupang_url") or "").startswith("https://link.coupang.com/")
        )
        naver_cls = "shop-btn shop-btn-secondary" if affiliate else "shop-btn shop-btn-primary"
        coupang_cls = "shop-btn shop-btn-primary" if affiliate else "shop-btn shop-btn-secondary"
        coupang_label = "쿠팡 최저가" if affiliate else "쿠팡 검색"

        st.markdown(
            '<div class="shop-btn-grid">'
            f'<a class="{naver_cls}" href="?go=naver&pid={pid}" target="_blank" rel="noopener noreferrer">네이버쇼핑</a>'
            f'<a class="{coupang_cls}" href="?go=coupang&pid={pid}" target="_blank" rel="noopener noreferrer">{coupang_label}</a>'
            '</div>',
            unsafe_allow_html=True,
        )

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
                ev_text = re.sub(r"\s+", " ", str(rec.get("evidence") or "").strip())
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
        '<div class="hero-kicker">실제 리뷰 영상 기반 자동 큐레이션</div>'
        f'<div class="hero-headline">유튜버가 직접 검증한 꿀템 <b>{len(products):,}개</b></div>'
        '<div class="hero-stats">'
        f'<span class="stat-pill">📺 분석 채널 <strong>{len(channel_ids):,}개</strong></span>'
        f'<span class="stat-pill">🎬 근거 영상 <strong>{len(video_ids):,}개</strong></span>'
        '<span class="stat-pill">⚡ 매일 자동 업데이트</span>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    a, b, c = st.columns([1.8, 1, 0.9])
    keyword = a.text_input("검색", placeholder="상품명, 브랜드, 유튜버 검색", label_visibility="collapsed")
    categories = sorted({p.get("category") or "기타" for p in products})
    category = b.selectbox("카테고리", ["전체 카테고리"] + categories, label_visibility="collapsed")
    sort_by = c.selectbox("정렬", ["추천 많은순", "최신 등록순"], label_visibility="collapsed")

    clean_kw = keyword.strip()
    if len(clean_kw) >= 2 and clean_kw != st.session_state.get("last_logged_keyword"):
        st.session_state.last_logged_keyword = clean_kw
        log_event("search", search_query=clean_kw)

    shown = []
    for product in products:
        names = " ".join(r.get("channel", {}).get("channel_name", "") for r in product["recommendations"])
        text = " ".join([product.get("canonical_name", ""), product.get("brand", ""), product.get("model", ""), names]).lower()
        if category != "전체 카테고리" and (product.get("category") or "기타") != category:
            continue
        if clean_kw and clean_kw.lower() not in text:
            continue
        shown.append(product)

    if sort_by == "최신 등록순":
        shown.sort(key=lambda p: str(p.get("created_at") or ""), reverse=True)

    st.markdown(
        f'<div class="result-bar"><span>검색 결과 <b>{len(shown):,}</b>개</span><span>네이버 · 쿠팡에서 가격 확인</span></div>',
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
        p1, p2, p3 = st.columns([1, 1.2, 1])
        if p1.button("← 이전 페이지", disabled=page <= 1, use_container_width=True):
            st.session_state.catalog_page = page - 1
            st.rerun()
        p2.markdown(f'<div style="text-align:center;padding:10px;font-size:13px;font-weight:750;color:#4E5968">{page} / {pages}</div>', unsafe_allow_html=True)
        if p3.button("다음 페이지 →", disabled=page >= pages, use_container_width=True):
            st.session_state.catalog_page = page + 1
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
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
        st.info("Supabase에 click_logs 테이블을 생성하면 상품별 쿠팡·네이버 클릭 순위와 방문자 검색어 통계가 자동으로 집계됩니다.")
    else:
        coupang_clicks = [x for x in click_logs if x.get("event_type") == "coupang_click"]
        naver_clicks = [x for x in click_logs if x.get("event_type") == "naver_click"]
        search_logs = [x for x in click_logs if x.get("event_type") == "search" and x.get("search_query")]

        c_m1, c_m2, c_m3 = st.columns(3)
        for col, (lbl, val) in zip(
            [c_m1, c_m2, c_m3],
            [("쿠팡 클릭", len(coupang_clicks)), ("네이버쇼핑 클릭", len(naver_clicks)), ("방문자 검색", len(search_logs))],
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
        label_by_item = {}
        for row in coupang_clicks + naver_clicks:
            key = row.get("product_id") or row.get("product_name") or "unknown"
            click_counts[key] += 1
            if row.get("event_type") == "coupang_click":
                coupang_by_item[key] += 1
            else:
                naver_by_item[key] += 1
            p_info = product_lookup.get(row.get("product_id"))
            label_by_item[key] = (p_info or {}).get("canonical_name") or row.get("product_name") or "이름 없음"

        cl_left, cl_right = st.columns(2)
        with cl_left:
            with st.container(border=True):
                st.markdown("**클릭 많은 상품 TOP 15 (쿠팡 링크 우선 대상)**")
                if not click_counts:
                    st.caption("아직 기록된 상품 클릭이 없습니다.")
                for key, total in click_counts.most_common(15):
                    p_info = product_lookup.get(key) or {}
                    linked = "✅ 제휴연결" if p_info.get("affiliate_verified") else "미연결"
                    st.markdown(
                        f'<div class="status-row">'
                        f'<span>{safe(label_by_item.get(key))} <small style="color:#8B95A1">({linked})</small></span>'
                        f'<b>쿠팡 {coupang_by_item[key]} · 네이버 {naver_by_item[key]}</b>'
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
    if verified and not image_url.strip().startswith(("http://", "https://")):
        st.error("확인된 이미지는 http 또는 https URL이 필요합니다.")
        return
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
    st.caption("승인·숨김 상품을 검색해 쿠팡 제휴 링크, 이미지, 상품 정보와 공개 상태를 수정합니다.")
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

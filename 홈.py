import html
import re
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import quote

import requests
import streamlit as st

st.set_page_config(page_title="꿀템 다나와", page_icon="🛍️", layout="centered")


def secret(name):
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


SUPABASE_URL = secret("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = secret("SUPABASE_SERVICE_ROLE_KEY")


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
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}", headers=headers(), params=query, timeout=30
    )
    if not response.ok:
        raise RuntimeError(f"{table} 조회 실패: HTTP {response.status_code} · {response.text[:250]}")
    return response.json()


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


def count_by(rows, key):
    return Counter(str(row.get(key) or "unknown") for row in rows)


def number(value):
    value = int(value or 0)
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f}억"
    if value >= 10_000:
        return f"{value / 10_000:.1f}만"
    return f"{value:,}"


@st.cache_data(ttl=300, show_spinner=False)
def load_public_data():
    products = api_get(
        "products",
        "product_id,canonical_name,brand,model,category,search_keyword,coupang_url,affiliate_verified,image_url,image_source,image_verified,image_checked_at,image_note,created_at",
        {"review_status": "eq.approved", "is_visible": "eq.true", "order": "created_at.desc", "limit": "1000"},
    )
    recs = api_get(
        "recommendations",
        "recommendation_id,product_id,video_id,channel_id,reason,pros,cons,evidence,confidence,purchase_type,created_at",
        {"order": "created_at.desc", "limit": "5000"},
    )
    videos = api_get("videos", "video_id,title,view_count,published_at", {"limit": "5000"})
    channels = api_get("channels", "channel_id,channel_name,subscriber_count", {"limit": "5000"})
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
        key=lambda p: (
            len({r.get("channel_id") for r in p["recommendations"]}),
            len(p["recommendations"]),
        ),
        reverse=True,
    )
    return products


@st.cache_data(ttl=60, show_spinner=False)
def load_admin_data():
    products = api_get(
        "products",
        "product_id,canonical_name,brand,model,category,search_keyword,identity_score,review_status,is_visible,review_note,coupang_url,coupang_product_name,affiliate_verified,affiliate_note,image_url,image_source,image_verified,image_checked_at,image_note,created_at",
        {"order": "created_at.desc", "limit": "5000"},
    )
    videos = api_get(
        "videos",
        "video_id,channel_id,title,analysis_status,analysis_error,product_score,created_at,published_at",
        {"order": "created_at.desc", "limit": "10000"},
    )
    channels = api_get(
        "channels",
        "channel_id,channel_name,status,scan_priority,total_scanned_videos,product_candidate_videos,extracted_product_count,last_scanned_at,next_video_scan_at",
        {"limit": "10000"},
    )
    queries = api_get(
        "discovery_queries",
        "query_id,query_text,category,enabled,run_count,channels_found,active_channels_found,error_count,last_error,last_run_at,next_run_at",
        {"limit": "1000"},
    )
    recs = api_get(
        "recommendations",
        "recommendation_id,product_id,video_id,channel_id,confidence,created_at",
        {"limit": "10000"},
    )
    return products, videos, channels, queries, recs


st.markdown("""
<style>
:root {
  --brand: #3182F6;
  --brand-hover: #1B64DA;
  --brand-soft: #EAF3FF;
  --brand-border: #CFE2FF;
  --ink: #191F28;
  --muted: #6B7684;
  --line: #E5EAF0;
  --surface: #FFFFFF;
  --canvas: #F5F7FA;
  --danger: #D92D20;
  --danger-soft: #FFF0F0;
}

.stApp { background: var(--canvas); color: var(--ink); }
.block-container { max-width: 1180px; padding: 1rem 1rem 4rem; }
#MainMenu, footer, [data-testid="stHeader"] { visibility: hidden; }

.title { color: var(--brand); font-size: 25px; font-weight: 900; margin: 4px 0 14px; }
.hero, .card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 20px;
  box-shadow: 0 5px 18px rgba(49, 130, 246, .06);
  margin-bottom: 12px;
}
.hero b { color: var(--brand); font-size: 31px; }
.muted { color: var(--muted); font-size: 13px; }
.product-title { color: var(--ink); font-size: 17px; font-weight: 850; line-height: 1.35; }
.badge {
  display: inline-block;
  color: #245FB5;
  background: var(--brand-soft);
  border: 1px solid var(--brand-border);
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 11px;
  margin: 5px 5px 5px 0;
}
.reason { background: #F8FAFD; border-left: 3px solid var(--brand); border-radius: 10px; padding: 11px 12px; margin: 9px 0; color: #4E5968; font-size: 13px; }
.metric { background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 15px; box-shadow: 0 3px 13px rgba(49,130,246,.05); min-height: 94px; }
.metric-label { color: var(--muted); font-size: 12px; font-weight: 700; }
.metric-value { color: var(--brand); font-size: 25px; font-weight: 900; margin-top: 5px; }
.status-row { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #EEF1F4; font-size:13px; }
.status-row:last-child { border:0; }
.error-box { background:var(--danger-soft); color:#A61B22; padding:10px; border-radius:10px; font-size:12px; margin:6px 0; word-break:break-word; }

[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--surface);
  border: 1px solid var(--line) !important;
  border-radius: 18px !important;
  box-shadow: 0 4px 16px rgba(49,130,246,.055) !important;
  padding: 17px !important;
  margin-bottom: 12px !important;
}

.stButton > button,
.stLinkButton > a {
  min-height: 43px !important;
  border-radius: 12px !important;
  font-weight: 780 !important;
  transition: background .16s ease, border-color .16s ease, transform .12s ease !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"],
.stLinkButton > a[kind="primary"],
.stLinkButton > a[data-testid="stBaseLinkButton-primary"] {
  background: var(--brand) !important;
  border: 1px solid var(--brand) !important;
  color: #FFFFFF !important;
}
.stButton > button[kind="primary"] *,
.stButton > button[data-testid="stBaseButton-primary"] *,
.stLinkButton > a[kind="primary"] *,
.stLinkButton > a[data-testid="stBaseLinkButton-primary"] * {
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
}
.stButton > button[kind="secondary"],
.stButton > button[data-testid="stBaseButton-secondary"],
.stLinkButton > a[kind="secondary"],
.stLinkButton > a[data-testid="stBaseLinkButton-secondary"] {
  background: var(--brand-soft) !important;
  border: 1px solid var(--brand-border) !important;
  color: #245FB5 !important;
}
.stButton > button[kind="secondary"] *,
.stButton > button[data-testid="stBaseButton-secondary"] *,
.stLinkButton > a[kind="secondary"] *,
.stLinkButton > a[data-testid="stBaseLinkButton-secondary"] * {
  color: #245FB5 !important;
  -webkit-text-fill-color: #245FB5 !important;
}
.stButton > button:hover, .stLinkButton > a:hover { transform: translateY(-1px); filter: brightness(.98); }

[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stSelectbox"] div[data-baseweb="select"] {
  background: #FFFFFF !important;
  border: 1px solid #DCE3EB !important;
  border-radius: 12px !important;
  color: var(--ink) !important;
  box-shadow: none !important;
}
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div,
[data-testid="stTextInput"] input::placeholder {
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
  border-color: var(--brand) !important;
  box-shadow: 0 0 0 3px rgba(49,130,246,.12) !important;
}
[data-testid="stExpander"] { border: 1px solid var(--line) !important; border-radius: 13px !important; background: #FBFCFE !important; }
[data-testid="stAlert"] { border-radius: 13px !important; border: 0 !important; }

/* 반응형 간격과 텍스트 크기 */
@media (max-width: 900px) {
  .block-container { max-width: 760px; padding-left: .8rem; padding-right: .8rem; }
  .hero b { font-size: 27px; }
}
@media (max-width: 600px) {
  .block-container { padding: .65rem .55rem 3rem; }
  .title { font-size: 22px; }
  .hero, .card { padding: 15px; border-radius: 16px; }
  .hero b { font-size: 24px; }
  .product-title { font-size: 16px; }
  .stButton > button, .stLinkButton > a { min-height: 46px !important; }
}

/* ===== Streamlit 입력창 검은 배경 최종 보정 ===== */
[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stTextInput"] div[data-baseweb="base-input"],
[data-testid="stTextInput"] div[data-baseweb="input"] > div,
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"],
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[role="combobox"],
[data-testid="stSelectbox"] div[role="combobox"] > div,
[data-testid="stNumberInput"] div[data-baseweb="input"],
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
  background-color: #FFFFFF !important;
  background: #FFFFFF !important;
  color: #191F28 !important;
  -webkit-text-fill-color: #191F28 !important;
  caret-color: #3182F6 !important;
  opacity: 1 !important;
}

[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stSelectbox"] div[data-baseweb="select"],
[data-testid="stNumberInput"] div[data-baseweb="input"],
[data-testid="stTextArea"] textarea {
  border: 1px solid #DCE3EB !important;
  border-radius: 12px !important;
  box-shadow: none !important;
  overflow: hidden !important;
}

[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
  color: #8B95A1 !important;
  -webkit-text-fill-color: #8B95A1 !important;
  opacity: 1 !important;
}

[data-testid="stSelectbox"] svg,
[data-testid="stTextInput"] svg,
[data-testid="stNumberInput"] svg {
  fill: #4E5968 !important;
  color: #4E5968 !important;
}

[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
[data-testid="stTextInput"] label,
[data-testid="stSelectbox"] label,
[data-testid="stNumberInput"] label,
[data-testid="stTextArea"] label {
  color: #4E5968 !important;
  -webkit-text-fill-color: #4E5968 !important;
  opacity: 1 !important;
  font-weight: 700 !important;
}

[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within,
[data-testid="stNumberInput"] div[data-baseweb="input"]:focus-within,
[data-testid="stTextArea"] textarea:focus {
  border-color: #3182F6 !important;
  box-shadow: 0 0 0 3px rgba(49,130,246,.14) !important;
}

/* 관리자 폼은 흰색 배경과 선명한 라벨을 사용 */
[data-testid="stForm"] {
  background: #F8FAFD !important;
  border: 1px solid #DCE3EB !important;
  border-radius: 16px !important;
  padding: 18px !important;
}
[data-testid="stForm"] input,
[data-testid="stForm"] textarea,
[data-testid="stForm"] div[role="combobox"],
[data-testid="stForm"] div[data-baseweb="input"],
[data-testid="stForm"] div[data-baseweb="select"],
[data-testid="stForm"] div[data-baseweb="base-input"] {
  background: #FFFFFF !important;
  background-color: #FFFFFF !important;
  color: #191F28 !important;
  -webkit-text-fill-color: #191F28 !important;
}

/* 승인과 숨김 버튼을 의미에 맞게 구분 */
[data-testid="stForm"] button[kind="primary"],
[data-testid="stForm"] button[data-testid="stBaseButton-primary"] {
  background: #3182F6 !important;
  border-color: #3182F6 !important;
  color: #FFFFFF !important;
}
[data-testid="stForm"] button[kind="primary"] *,
[data-testid="stForm"] button[data-testid="stBaseButton-primary"] * {
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
}
[data-testid="stForm"] button[kind="secondary"],
[data-testid="stForm"] button[data-testid="stBaseButton-secondary"] {
  background: #FFF0F0 !important;
  border: 1px solid #FFD1D1 !important;
  color: #C92A2A !important;
}
[data-testid="stForm"] button[kind="secondary"] *,
[data-testid="stForm"] button[data-testid="stBaseButton-secondary"] * {
  color: #C92A2A !important;
  -webkit-text-fill-color: #C92A2A !important;
}

/* 브라우저 다크 테마의 강제 색상 반영 방지 */
input, textarea, select {
  color-scheme: light !important;
}


/* ===== 카드 테두리·카테고리·전체 관리자 UI 최종 조정 ===== */

/* 상품/통계/검수 카드의 진한 네모 테두리를 제거하고 부드러운 카드로 통일 */
[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"] > div,
[data-testid="stForm"],
[data-testid="stExpander"] {
  border-color: #E7EDF5 !important;
}
[data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid #E7EDF5 !important;
  border-radius: 20px !important;
  background: #FFFFFF !important;
  box-shadow: 0 7px 24px rgba(49,130,246,.065) !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
  border-color: #D5E5FB !important;
  box-shadow: 0 9px 28px rgba(49,130,246,.095) !important;
}

/* 펼치기 영역 역시 검은 외곽선 대신 옅은 청회색 */
[data-testid="stExpander"] {
  background: #F9FBFE !important;
  border: 1px solid #DFE8F3 !important;
  border-radius: 13px !important;
  box-shadow: none !important;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary * {
  color: #344054 !important;
  -webkit-text-fill-color: #344054 !important;
}

/* 검색창: 붉거나 검은 외곽선이 남지 않도록 강제 */
[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stTextInput"] div[data-baseweb="base-input"],
[data-testid="stTextInput"] div[data-baseweb="input"] > div,
[data-testid="stTextInput"] input {
  background: #FFFFFF !important;
  background-color: #FFFFFF !important;
  color: #191F28 !important;
  -webkit-text-fill-color: #191F28 !important;
  border-color: transparent !important;
  outline: none !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stTextInput"] div[data-baseweb="base-input"] {
  border: 1px solid #DCE5F0 !important;
  border-radius: 13px !important;
  box-shadow: 0 2px 8px rgba(49,130,246,.045) !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
[data-testid="stTextInput"] div[data-baseweb="base-input"]:focus-within {
  border-color: #79AEFA !important;
  box-shadow: 0 0 0 3px rgba(49,130,246,.13) !important;
}

/* 카테고리 선택창의 모든 중첩 요소를 밝은 배경으로 강제 */
[data-testid="stSelectbox"],
[data-testid="stSelectbox"] > div,
[data-testid="stSelectbox"] div[data-baseweb="select"],
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[role="combobox"],
[data-testid="stSelectbox"] div[role="combobox"] > div,
[data-testid="stSelectbox"] input,
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[role="listbox"],
[role="option"] {
  background-color: #FFFFFF !important;
  background: #FFFFFF !important;
  color: #191F28 !important;
  -webkit-text-fill-color: #191F28 !important;
  opacity: 1 !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] {
  border: 1px solid #DCE5F0 !important;
  border-radius: 13px !important;
  box-shadow: 0 2px 8px rgba(49,130,246,.045) !important;
  overflow: hidden !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
  border-color: #79AEFA !important;
  box-shadow: 0 0 0 3px rgba(49,130,246,.13) !important;
}
[data-testid="stSelectbox"] svg {
  fill: #5D6B7A !important;
  color: #5D6B7A !important;
}
[role="option"]:hover,
[role="option"][aria-selected="true"] {
  background: #EAF3FF !important;
  color: #245FB5 !important;
  -webkit-text-fill-color: #245FB5 !important;
}

/* 운영 통계의 메트릭 및 상태 네모 */
.metric {
  border: 1px solid #E7EDF5 !important;
  background: linear-gradient(180deg,#FFFFFF 0%,#FBFDFF 100%) !important;
  box-shadow: 0 6px 18px rgba(49,130,246,.055) !important;
}
.status-row {
  border-bottom: 1px solid #EDF1F6 !important;
}

/* 상품 검수 폼: 회색 큰 네모 대신 옅은 파란 배경 */
[data-testid="stForm"] {
  background: #F7FAFF !important;
  border: 1px solid #DDE9F8 !important;
  border-radius: 17px !important;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.7) !important;
}
[data-testid="stForm"] input,
[data-testid="stForm"] textarea,
[data-testid="stForm"] div[role="combobox"],
[data-testid="stForm"] div[data-baseweb="input"],
[data-testid="stForm"] div[data-baseweb="base-input"],
[data-testid="stForm"] div[data-baseweb="select"] {
  background: #FFFFFF !important;
  color: #191F28 !important;
  -webkit-text-fill-color: #191F28 !important;
}

/* 버튼은 메인 파랑/보조 연파랑/숨김 연빨강으로 고정 */
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"],
.stLinkButton > a[kind="primary"],
.stLinkButton > a[data-testid="stBaseLinkButton-primary"] {
  background: #3182F6 !important;
  border-color: #3182F6 !important;
  color: #FFFFFF !important;
}
.stButton > button[kind="secondary"],
.stButton > button[data-testid="stBaseButton-secondary"],
.stLinkButton > a[kind="secondary"],
.stLinkButton > a[data-testid="stBaseLinkButton-secondary"] {
  background: #EDF5FF !important;
  border: 1px solid #D4E6FF !important;
  color: #245FB5 !important;
}
[data-testid="stForm"] button[kind="secondary"],
[data-testid="stForm"] button[data-testid="stBaseButton-secondary"] {
  background: #FFF1F2 !important;
  border: 1px solid #FFD6D9 !important;
  color: #C92A2A !important;
}

/* 라벨과 텍스트가 흐려지지 않도록 */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] *,
[data-testid="stForm"] label,
[data-testid="stForm"] label * {
  color: #4E5968 !important;
  -webkit-text-fill-color: #4E5968 !important;
  opacity: 1 !important;
}

/* 브라우저 다크 모드가 Streamlit 폼을 덮지 못하게 */
input, textarea, select, option {
  color-scheme: light !important;
}


/* ===== 상품 목록: PC 3열 / 태블릿 2열 / 모바일 1열 ===== */
.st-key-product_grid [data-testid="stHorizontalBlock"] {
  gap: 16px !important;
  align-items: stretch !important;
}
.st-key-product_grid [data-testid="column"] {
  min-width: 0 !important;
  display: flex !important;
  flex-direction: column !important;
}
.st-key-product_grid [data-testid="column"] > div {
  width: 100% !important;
}
.st-key-product_grid [data-testid="stVerticalBlockBorderWrapper"] {
  height: 100% !important;
  min-height: 345px !important;
  padding: 16px !important;
}
.st-key-product_grid .product-title {
  min-height: 48px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.st-key-product_grid .reason {
  min-height: 70px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.st-key-product_grid [data-testid="stButton"] button,
.st-key-product_grid [data-testid="stLinkButton"] a {
  width: 100% !important;
}

@media (max-width: 900px) and (min-width: 601px) {
  .st-key-product_grid [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
  }
  .st-key-product_grid [data-testid="column"] {
    flex: 0 0 calc(50% - 8px) !important;
    width: calc(50% - 8px) !important;
    min-width: calc(50% - 8px) !important;
  }
}

@media (max-width: 600px) {
  .st-key-product_grid [data-testid="stHorizontalBlock"] {
    flex-direction: column !important;
    gap: 12px !important;
  }
  .st-key-product_grid [data-testid="column"] {
    flex: 0 0 100% !important;
    width: 100% !important;
    min-width: 100% !important;
  }
  .st-key-product_grid [data-testid="stVerticalBlockBorderWrapper"] {
    min-height: 0 !important;
  }
  .st-key-product_grid .product-title,
  .st-key-product_grid .reason {
    min-height: 0 !important;
  }
}


/* ===== 검색창·카테고리 비비드 오렌지 테두리 ===== */
[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stTextInput"] div[data-baseweb="base-input"] {
  background: #FFFFFF !important;
  border: 2px solid #FF7A00 !important;
  border-radius: 13px !important;
  box-shadow: 0 2px 9px rgba(255,122,0,.11) !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"]:hover,
[data-testid="stTextInput"] div[data-baseweb="base-input"]:hover {
  border-color: #FF6200 !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
[data-testid="stTextInput"] div[data-baseweb="base-input"]:focus-within {
  border-color: #FF5A00 !important;
  box-shadow: 0 0 0 4px rgba(255,122,0,.17) !important;
}

[data-testid="stSelectbox"] div[data-baseweb="select"] {
  background: #FFFFFF !important;
  border: 2px solid #FF7A00 !important;
  border-radius: 13px !important;
  box-shadow: 0 2px 9px rgba(255,122,0,.11) !important;
  overflow: hidden !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"]:hover {
  border-color: #FF6200 !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
  border-color: #FF5A00 !important;
  box-shadow: 0 0 0 4px rgba(255,122,0,.17) !important;
}
[data-testid="stSelectbox"] svg {
  fill: #FF6A00 !important;
  color: #FF6A00 !important;
}
[role="option"]:hover,
[role="option"][aria-selected="true"] {
  background: #FFF2E8 !important;
  color: #C94F00 !important;
  -webkit-text-fill-color: #C94F00 !important;
}


/* ===== 검은 테두리 완전 제거: 최종 우선순위 ===== */

/* 상품, 운영 통계, 상품 검수의 외곽 네모 */
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"] > div,
div[data-testid="stVerticalBlockBorderWrapper"] > div > div {
  border: 0 !important;
  outline: 0 !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: #FFFFFF !important;
  border-radius: 20px !important;
  box-shadow: 0 7px 24px rgba(49,130,246,.085) !important;
}

/* 펼치기 영역의 검은 선 제거 */
div[data-testid="stExpander"],
div[data-testid="stExpander"] > details,
div[data-testid="stExpander"] summary {
  border: 0 !important;
  outline: 0 !important;
}
div[data-testid="stExpander"] > details {
  background: #F8FBFF !important;
  border-radius: 13px !important;
  box-shadow: inset 0 0 0 1px #DDE9F8 !important;
}

/* 검색창: 모든 내부 검은 border와 outline 제거 후 주황 외곽선 하나만 표시 */
div[data-testid="stTextInput"],
div[data-testid="stTextInput"] > div,
div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stTextInput"] div[data-baseweb="base-input"],
div[data-testid="stTextInput"] div[data-baseweb="input"] > div,
div[data-testid="stTextInput"] input {
  outline: 0 !important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"] *,
div[data-testid="stTextInput"] div[data-baseweb="base-input"] * {
  border: 0 !important;
  outline: 0 !important;
  box-shadow: none !important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stTextInput"] div[data-baseweb="base-input"] {
  background: #FFFFFF !important;
  border: 2px solid #FF7A00 !important;
  border-radius: 14px !important;
  box-shadow: 0 3px 12px rgba(255,122,0,.14) !important;
  overflow: hidden !important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
div[data-testid="stTextInput"] div[data-baseweb="base-input"]:focus-within {
  border-color: #FF5A00 !important;
  box-shadow: 0 0 0 4px rgba(255,122,0,.18) !important;
}

/* 카테고리: 검은 오른쪽 영역과 검은 테두리를 모두 흰색/주황색으로 교체 */
div[data-testid="stSelectbox"],
div[data-testid="stSelectbox"] > div,
div[data-testid="stSelectbox"] div[data-baseweb="select"],
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stSelectbox"] div[role="combobox"],
div[data-testid="stSelectbox"] div[role="combobox"] > div,
div[data-testid="stSelectbox"] div[aria-haspopup="listbox"],
div[data-testid="stSelectbox"] input {
  background: #FFFFFF !important;
  background-color: #FFFFFF !important;
  color: #191F28 !important;
  -webkit-text-fill-color: #191F28 !important;
  outline: 0 !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] *,
div[data-testid="stSelectbox"] div[role="combobox"] * {
  border: 0 !important;
  outline: 0 !important;
  box-shadow: none !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] {
  border: 2px solid #FF7A00 !important;
  border-radius: 14px !important;
  box-shadow: 0 3px 12px rgba(255,122,0,.14) !important;
  overflow: hidden !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
  border-color: #FF5A00 !important;
  box-shadow: 0 0 0 4px rgba(255,122,0,.18) !important;
}
div[data-testid="stSelectbox"] svg {
  fill: #FF6A00 !important;
  color: #FF6A00 !important;
}

/* 카테고리 펼침 메뉴 */
div[data-baseweb="popover"],
div[data-baseweb="popover"] > div,
ul[role="listbox"],
li[role="option"] {
  background: #FFFFFF !important;
  color: #191F28 !important;
  -webkit-text-fill-color: #191F28 !important;
  border-color: #FFE0C2 !important;
}
li[role="option"]:hover,
li[role="option"][aria-selected="true"] {
  background: #FFF1E5 !important;
  color: #C94F00 !important;
  -webkit-text-fill-color: #C94F00 !important;
}

/* 검수 폼의 외곽선도 검정 대신 파란 그림자로 통일 */
div[data-testid="stForm"] {
  border: 0 !important;
  outline: 0 !important;
  background: #F7FAFF !important;
  border-radius: 18px !important;
  box-shadow: inset 0 0 0 1px #DDE9F8, 0 5px 18px rgba(49,130,246,.055) !important;
}


/* ===== 피치 오렌지 최종 테마: #F28A3A ===== */
:root {
  --peach-orange: #F28A3A;
  --peach-orange-dark: #E67527;
  --peach-orange-soft: #FFF2E8;
  --peach-orange-glow: rgba(242,138,58,.22);
}

/* 상품 카드와 관리자/통계 카드: 검은 선 제거 */
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stForm"] {
  border: none !important;
  outline: none !important;
}
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] {
  box-shadow: 0 8px 26px rgba(49,130,246,.10) !important;
  background: #FFFFFF !important;
}

/* 검색 입력: border 대신 inset shadow를 써서 브라우저 기본 검정선을 완전히 덮음 */
div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stTextInput"] div[data-baseweb="base-input"] {
  border: none !important;
  outline: none !important;
  background: #FFFFFF !important;
  box-shadow: inset 0 0 0 2px var(--peach-orange), 0 4px 14px rgba(242,138,58,.10) !important;
  border-radius: 14px !important;
  overflow: hidden !important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"] *,
div[data-testid="stTextInput"] div[data-baseweb="base-input"] *,
div[data-testid="stTextInput"] input {
  border: none !important;
  outline: none !important;
  background: #FFFFFF !important;
  color: #191F28 !important;
  -webkit-text-fill-color: #191F28 !important;
  box-shadow: none !important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
div[data-testid="stTextInput"] div[data-baseweb="base-input"]:focus-within {
  box-shadow: inset 0 0 0 2px var(--peach-orange-dark), 0 0 0 4px var(--peach-orange-glow) !important;
}

/* 카테고리 선택: 오른쪽 검정 영역을 포함해 모든 자식 배경을 흰색으로 강제 */
div[data-testid="stSelectbox"] div[data-baseweb="select"] {
  border: none !important;
  outline: none !important;
  background: #FFFFFF !important;
  box-shadow: inset 0 0 0 2px var(--peach-orange), 0 4px 14px rgba(242,138,58,.10) !important;
  border-radius: 14px !important;
  overflow: hidden !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] *,
div[data-testid="stSelectbox"] div[role="combobox"],
div[data-testid="stSelectbox"] div[role="combobox"] *,
div[data-testid="stSelectbox"] div[aria-haspopup="listbox"],
div[data-testid="stSelectbox"] div[aria-haspopup="listbox"] * {
  border: none !important;
  outline: none !important;
  background: #FFFFFF !important;
  background-color: #FFFFFF !important;
  color: #191F28 !important;
  -webkit-text-fill-color: #191F28 !important;
  box-shadow: none !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
  box-shadow: inset 0 0 0 2px var(--peach-orange-dark), 0 0 0 4px var(--peach-orange-glow) !important;
}
div[data-testid="stSelectbox"] svg,
div[data-testid="stSelectbox"] [data-baseweb="icon"] {
  fill: var(--peach-orange-dark) !important;
  color: var(--peach-orange-dark) !important;
  background: transparent !important;
}

/* 펼친 카테고리 메뉴 */
div[data-baseweb="popover"],
div[data-baseweb="popover"] > div,
ul[role="listbox"],
li[role="option"] {
  background: #FFFFFF !important;
  color: #191F28 !important;
  -webkit-text-fill-color: #191F28 !important;
  border: none !important;
}
div[data-baseweb="popover"] > div {
  box-shadow: 0 10px 30px rgba(25,31,40,.13), inset 0 0 0 1px #FFD9BD !important;
  border-radius: 12px !important;
}
li[role="option"]:hover,
li[role="option"][aria-selected="true"] {
  background: var(--peach-orange-soft) !important;
  color: #B94F09 !important;
  -webkit-text-fill-color: #B94F09 !important;
}

/* 펼치기 상자는 검은 테두리 없이 옅은 파란 내부선 */
div[data-testid="stExpander"],
div[data-testid="stExpander"] > details,
div[data-testid="stExpander"] summary {
  border: none !important;
  outline: none !important;
}
div[data-testid="stExpander"] > details {
  box-shadow: inset 0 0 0 1px #DDE9F8 !important;
  border-radius: 13px !important;
  background: #F9FBFE !important;
}

/* 브라우저의 자동 다크 폼 렌더링 차단 */
input, select, textarea, option { color-scheme: only light !important; }


/* ===== 상품 이미지 영역 ===== */
.product-placeholder {
  width: 100%;
  aspect-ratio: 1 / 1;
  min-height: 170px;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 14px;
  overflow: hidden;
}
.product-placeholder span { font-size: 58px; line-height: 1; }
.product-placeholder small { font-size: 13px; font-weight: 800; letter-spacing: .02em; }
.st-key-product_grid [data-testid="stImage"] img {
  width: 100% !important;
  aspect-ratio: 1 / 1 !important;
  object-fit: contain !important;
  background: #FFFFFF !important;
  border-radius: 16px !important;
  padding: 10px !important;
  box-shadow: inset 0 0 0 1px #EDF1F6 !important;
}
@media (max-width: 600px) {
  .product-placeholder { min-height: 210px; }
}

</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">🛍️ 꿀템 다나와</div>', unsafe_allow_html=True)
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Streamlit Secrets에 SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY를 등록하세요.")
    st.stop()

if "page" not in st.session_state:
    st.session_state.page = "home"
nav = st.columns(3)
for column, key, label in zip(nav, ["home", "dashboard", "review"], ["꿀템 홈", "운영 통계", "상품 검수"]):
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
            else:
                st.error("비밀번호가 맞지 않습니다.")
    return False


CATEGORY_VISUALS = {
    "IT·전자": ("🖥️", "#EAF3FF", "#3182F6"),
    "뷰티": ("🧴", "#FFF1E8", "#E67527"),
    "생활·살림": ("🏠", "#EEF8F3", "#218B61"),
    "주방": ("🍳", "#FFF6DF", "#BD7500"),
    "패션": ("👕", "#F4EEFF", "#7652C7"),
    "여행": ("🧳", "#EAF8FA", "#167C8C"),
    "자동차": ("🚗", "#EEF1F5", "#4E5968"),
    "운동·건강": ("🏃", "#FFF0F0", "#C92A2A"),
    "육아": ("🧸", "#FFF4E8", "#D06A19"),
    "반려동물": ("🐾", "#F4F7EA", "#6E832B"),
    "기타": ("🛍️", "#F1F4F8", "#5D6B7A"),
}


def render_product_visual(product):
    image_url = str(product.get("image_url") or "").strip()
    verified = bool(product.get("image_verified"))
    if verified and image_url.startswith(("https://", "http://")):
        st.image(image_url, use_container_width=True)
        return

    category = product.get("category") or "기타"
    icon, background, color = CATEGORY_VISUALS.get(category, CATEGORY_VISUALS["기타"])
    st.markdown(
        f'<div class="product-placeholder" style="background:{background};color:{color}">'
        f'<span>{icon}</span><small>{safe(category)}</small></div>',
        unsafe_allow_html=True,
    )


def render_product_card(product):
    recs = product["recommendations"]
    with st.container(border=True):
        render_product_visual(product)
        st.markdown(
            f'<div class="product-title">{safe(product.get("canonical_name"))}</div>'
            f'<div class="muted">{safe(product.get("brand"))} · '
            f'{safe(product.get("category") or "기타")}</div>',
            unsafe_allow_html=True,
        )
        channel_count = len({r.get("channel_id") for r in recs if r.get("channel_id")})
        confidence = max([float(r.get("confidence") or 0) for r in recs] or [0])
        st.markdown(
            f'<span class="badge">유튜버 {channel_count}명</span>'
            f'<span class="badge">영상 {len(recs)}개</span>'
            f'<span class="badge">신뢰도 {confidence:.0%}</span>',
            unsafe_allow_html=True,
        )
        if recs and recs[0].get("reason"):
            st.markdown(
                f'<div class="reason">{safe(recs[0]["reason"])}</div>',
                unsafe_allow_html=True,
            )

        query_name = quote(str(product.get("canonical_name") or product.get("search_keyword") or ""))
        st.link_button(
            "네이버쇼핑 확인",
            f"https://search.shopping.naver.com/search/all?query={query_name}",
            type="primary",
            use_container_width=True,
        )
        affiliate = bool(
            product.get("affiliate_verified")
            and str(product.get("coupang_url") or "").startswith("https://link.coupang.com/")
        )
        coupang_url = (
            product.get("coupang_url")
            if affiliate
            else f"https://www.coupang.com/np/search?q={query_name}"
        )
        st.link_button(
            "쿠팡 파트너스 구매" if affiliate else "쿠팡에서 검색",
            coupang_url,
            use_container_width=True,
        )

        with st.expander(f"추천 근거와 영상 {len(recs)}건"):
            channel_groups = {}
            for rec in recs:
                channel = rec.get("channel", {})
                channel_id = rec.get("channel_id") or channel.get("channel_id") or "unknown"
                channel_groups.setdefault(
                    channel_id,
                    {"channel": channel, "recommendations": []},
                )["recommendations"].append(rec)

            for group_index, group in enumerate(channel_groups.values(), 1):
                channel = group["channel"]
                channel_recs = group["recommendations"]
                st.markdown(f"**{safe(channel.get('channel_name') or '알 수 없는 채널')}**")
                st.caption(
                    f"구독자 {number(channel.get('subscriber_count'))} · "
                    f"관련 영상 {len(channel_recs)}개"
                )
                seen_evidence = set()
                for rec in channel_recs:
                    evidence = str(rec.get("evidence") or "").strip()
                    if evidence and evidence not in seen_evidence:
                        seen_evidence.add(evidence)
                        st.write(f"• {evidence}")
                for video_index, rec in enumerate(channel_recs, 1):
                    video = rec.get("video", {})
                    st.markdown(
                        f"**{video_index}. {safe(video.get('title') or '제목을 확인할 수 없는 영상')}**"
                    )
                    if rec.get("video_id"):
                        st.link_button(
                            f"원본 영상 {video_index} 보기",
                            f"https://youtu.be/{rec['video_id']}",
                            key=f"video_{product['product_id']}_{rec['recommendation_id']}",
                            use_container_width=True,
                        )
                if group_index < len(channel_groups):
                    st.divider()


def render_home():
    products = load_public_data()
    channel_ids = {r.get("channel_id") for p in products for r in p["recommendations"] if r.get("channel_id")}
    video_ids = {r.get("video_id") for p in products for r in p["recommendations"] if r.get("video_id")}
    st.markdown(f'<div class="hero"><div class="muted">유튜버 영상에서 검증된 상품</div><b>{len(products):,}개</b><div class="muted">추천 채널 {len(channel_ids):,}개 · 추천 영상 {len(video_ids):,}개 · 자동 업데이트</div></div>', unsafe_allow_html=True)
    a, b = st.columns([1.5, 1])
    keyword = a.text_input("검색", placeholder="상품·브랜드·유튜버 검색", label_visibility="collapsed")
    categories = sorted({p.get("category") or "기타" for p in products})
    category = b.selectbox("카테고리", ["전체"] + categories, label_visibility="collapsed")
    shown = []
    for product in products:
        names = " ".join(r.get("channel", {}).get("channel_name", "") for r in product["recommendations"])
        text = " ".join([product.get("canonical_name", ""), product.get("brand", ""), product.get("model", ""), names]).lower()
        if category != "전체" and (product.get("category") or "기타") != category:
            continue
        if keyword and keyword.lower() not in text:
            continue
        shown.append(product)
    st.caption(f"상품 {len(shown)}개")
    # 페이지당 24개: PC 3열 × 8행, 태블릿 2열, 모바일 1열
    page_size = 24
    total_pages = max(1, (len(shown) + page_size - 1) // page_size)
    current_page = int(st.session_state.get("catalog_page", 1))
    current_page = min(max(current_page, 1), total_pages)
    st.session_state.catalog_page = current_page

    start_index = (current_page - 1) * page_size
    page_products = shown[start_index:start_index + page_size]

    with st.container(key="product_grid"):
        for row_start in range(0, len(page_products), 3):
            columns = st.columns(3, gap="medium")
            row_products = page_products[row_start:row_start + 3]
            for column, product in zip(columns, row_products):
                with column:
                    render_product_card(product)

    if total_pages > 1:
        previous_col, page_col, next_col = st.columns([1, 1.2, 1])
        if previous_col.button(
            "← 이전",
            disabled=current_page <= 1,
            use_container_width=True,
            key="catalog_previous",
        ):
            st.session_state.catalog_page = current_page - 1
            st.rerun()
        page_col.markdown(
            f'<div style="text-align:center;padding:11px;color:#4E5968;font-weight:750">'
            f'{current_page} / {total_pages}</div>',
            unsafe_allow_html=True,
        )
        if next_col.button(
            "다음 →",
            disabled=current_page >= total_pages,
            use_container_width=True,
            key="catalog_next",
        ):
            st.session_state.catalog_page = current_page + 1
            st.rerun()


def render_dashboard():
    if not require_admin():
        return
    products, videos, channels, queries, recs = load_admin_data()
    product_status = count_by(products, "review_status")
    video_status = count_by(videos, "analysis_status")
    active_channels = sum(1 for c in channels if c.get("status") == "active")
    query_errors = sum(1 for q in queries if int(q.get("error_count") or 0) > 0 or q.get("last_error"))
    cols = st.columns(4)
    metrics = [
        ("전체 채널", len(channels), f"활성 {active_channels}"),
        ("전체 영상", len(videos), f"AI 대기 {video_status.get('queued', 0)}"),
        ("공개 상품", product_status.get("approved", 0), f"검수 {product_status.get('pending', 0)}"),
        ("검색어", len(queries), f"오류 {query_errors}"),
    ]
    for col, (label, value, sub) in zip(cols, metrics):
        col.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value:,}</div><div class="muted">{sub}</div></div>', unsafe_allow_html=True)

    st.subheader("영상 처리 현황")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            for key in ["pending", "queued", "analyzed", "no_product", "rejected_generic", "skipped_non_product", "ai_error"]:
                st.markdown(f'<div class="status-row"><span>{key}</span><b>{video_status.get(key, 0):,}</b></div>', unsafe_allow_html=True)
    with right:
        with st.container(border=True):
            for key in ["approved", "pending", "hidden", "merged"]:
                st.markdown(f'<div class="status-row"><span>상품 {key}</span><b>{product_status.get(key, 0):,}</b></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="status-row"><span>추천 기록</span><b>{len(recs):,}</b></div>', unsafe_allow_html=True)

    st.subheader("채널 우선순위")
    priority = Counter(int(c.get("scan_priority") or 0) for c in channels if c.get("status") == "active")
    with st.container(border=True):
        for value in [5, 4, 3, 2, 1]:
            days = {5: "매일", 4: "3일", 3: "3일", 2: "7일", 1: "30일"}[value]
            st.markdown(f'<div class="status-row"><span>우선순위 {value} · {days}마다</span><b>{priority.get(value, 0)}개</b></div>', unsafe_allow_html=True)

    st.subheader("최근 오류")
    errors = [v for v in videos if v.get("analysis_status") == "ai_error" and v.get("analysis_error")][:10]
    query_error_rows = [q for q in queries if q.get("last_error")][:10]
    if not errors and not query_error_rows:
        st.success("현재 기록된 최근 오류가 없습니다.")
    for row in errors:
        st.markdown(f'<div class="error-box"><b>영상:</b> {safe(row.get("title"))}<br>{safe(row.get("analysis_error"))}</div>', unsafe_allow_html=True)
    for row in query_error_rows:
        st.markdown(f'<div class="error-box"><b>검색어:</b> {safe(row.get("query_text"))}<br>{safe(row.get("last_error"))}</div>', unsafe_allow_html=True)

    if st.button("통계 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


def render_review():
    if not require_admin():
        return
    products, videos, channels, queries, recs = load_admin_data()
    pending = [p for p in products if p.get("review_status") == "pending"]
    st.subheader(f"검수 대기 상품 {len(pending)}개")
    if not pending:
        st.success("검수 대기 상품이 없습니다.")
        return
    for product in pending:
        pid = product["product_id"]
        with st.container(border=True):
            st.markdown(f"### {safe(product.get('canonical_name'))}")
            st.caption(f"식별 점수 {int(product.get('identity_score') or 0)}/100 · {product.get('review_note') or '사유 없음'}")
            with st.form(f"review_{pid}"):
                name = st.text_input("상품명", value=product.get("canonical_name") or "")
                c1, c2 = st.columns(2)
                brand = c1.text_input("브랜드", value=product.get("brand") or "")
                model = c2.text_input("모델", value=product.get("model") or "")
                category = st.text_input("카테고리", value=product.get("category") or "기타")
                keyword = st.text_input("검색 키워드", value=product.get("search_keyword") or name)
                st.markdown("**대표 이미지 관리**")
                image_url = st.text_input(
                    "이미지 URL",
                    value=product.get("image_url") or "",
                    placeholder="https://...",
                )
                image_source = st.selectbox(
                    "이미지 출처",
                    ["", "brand_official", "affiliate", "manual", "youtube_thumbnail"],
                    index=(
                        ["", "brand_official", "affiliate", "manual", "youtube_thumbnail"].index(product.get("image_source"))
                        if product.get("image_source") in ["", "brand_official", "affiliate", "manual", "youtube_thumbnail"]
                        else 0
                    ),
                    format_func=lambda value: {
                        "": "출처 미선택",
                        "brand_official": "브랜드 공식",
                        "affiliate": "제휴사 제공",
                        "manual": "직접 업로드·확인",
                        "youtube_thumbnail": "유튜브 썸네일",
                    }[value],
                )
                image_verified = st.checkbox(
                    "정확한 상품 이미지 확인 완료",
                    value=bool(product.get("image_verified")),
                )
                image_note = st.text_input(
                    "이미지 메모",
                    value=product.get("image_note") or "",
                    placeholder="색상·용량·세대 차이 확인",
                )
                note = st.text_input("관리 메모", value=product.get("review_note") or "")
                approve_col, hide_col = st.columns(2)
                approve = approve_col.form_submit_button("승인 후 공개", type="primary", use_container_width=True)
                hide = hide_col.form_submit_button("숨김 처리", use_container_width=True)
            if approve:
                api_patch("products", {"canonical_name": name.strip(), "normalized_name": re.sub(r"[^0-9a-z가-힣]+", "", name.lower()), "brand": brand.strip(), "model": model.strip(), "category": category.strip() or "기타", "search_keyword": keyword.strip() or name.strip(), "image_url": image_url.strip() or None, "image_source": image_source or None, "image_verified": bool(image_verified and image_url.strip().startswith(("https://", "http://"))), "image_checked_at": datetime.now(timezone.utc).isoformat() if image_verified and image_url.strip().startswith(("https://", "http://")) else None, "image_note": image_note.strip() or None, "review_status": "approved", "is_visible": True, "reviewed_at": datetime.now(timezone.utc).isoformat(), "review_note": note.strip() or "관리자 승인"}, {"product_id": f"eq.{pid}"})
                st.cache_data.clear(); st.rerun()
            if hide:
                api_patch("products", {"review_status": "hidden", "is_visible": False, "reviewed_at": datetime.now(timezone.utc).isoformat(), "review_note": note.strip() or "관리자 숨김"}, {"product_id": f"eq.{pid}"})
                st.cache_data.clear(); st.rerun()


try:
    if st.session_state.page == "home":
        render_home()
    elif st.session_state.page == "dashboard":
        render_dashboard()
    else:
        render_review()
except Exception as exc:
    st.error(str(exc))

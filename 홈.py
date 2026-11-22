import html
import re
from datetime import datetime, timezone
from urllib.parse import quote

import requests
import streamlit as st

st.set_page_config(page_title="꿀템 다나와", page_icon="🛍️", layout="centered")

# =========================================================
# Supabase 설정
# =========================================================
def get_secret(name):
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""

SUPABASE_URL = get_secret("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = get_secret("SUPABASE_SERVICE_ROLE_KEY")


def supabase_headers():
    headers = {
        "apikey": SUPABASE_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    # 구형 service_role JWT도 지원
    if SUPABASE_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
    return headers


def api_get(table, select="*", params=None, timeout=30):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Streamlit Secrets에 SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY가 없습니다.")
    query = {"select": select}
    if params:
        query.update(params)
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=supabase_headers(),
        params=query,
        timeout=timeout,
    )
    if not response.ok:
        raise RuntimeError(f"Supabase 조회 실패: HTTP {response.status_code} · {response.text[:300]}")
    return response.json()


def api_patch(table, values, params=None, timeout=30):
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**supabase_headers(), "Prefer": "return=representation"},
        params=params or {},
        json=values,
        timeout=timeout,
    )
    if not response.ok:
        raise RuntimeError(
            f"Supabase 수정 실패: HTTP {response.status_code} · {response.text[:300]}"
        )
    return response.json() if response.text else []


@st.cache_data(ttl=300, show_spinner=False)
def load_catalog():
    products = api_get(
        "products",
        (
            "product_id,canonical_name,normalized_name,brand,model,category,"
            "search_keyword,review_status,is_visible,created_at"
        ),
        {
            "review_status": "eq.approved",
            "is_visible": "eq.true",
            "order": "created_at.desc",
            "limit": "1000",
        },
    )
    recommendations = api_get(
        "recommendations",
        "recommendation_id,product_id,video_id,channel_id,reason,pros,cons,evidence,start_sec,confidence,purchase_type,created_at",
        {"order": "created_at.desc", "limit": "5000"},
    )
    video_ids = sorted({x.get("video_id") for x in recommendations if x.get("video_id")})
    channel_ids = sorted({x.get("channel_id") for x in recommendations if x.get("channel_id")})

    videos = []
    for i in range(0, len(video_ids), 100):
        ids = video_ids[i:i + 100]
        if ids:
            videos.extend(api_get(
                "videos",
                "video_id,channel_id,title,published_at,view_count,product_score,analysis_status",
                {"video_id": f"in.({','.join(ids)})", "limit": "100"},
            ))

    channels = []
    for i in range(0, len(channel_ids), 100):
        ids = channel_ids[i:i + 100]
        if ids:
            channels.extend(api_get(
                "channels",
                "channel_id,channel_name,subscriber_count,primary_category,status",
                {"channel_id": f"in.({','.join(ids)})", "limit": "100"},
            ))

    videos_by_id = {x["video_id"]: x for x in videos}
    channels_by_id = {x["channel_id"]: x for x in channels}
    recs_by_product = {}
    for rec in recommendations:
        enriched = dict(rec)
        enriched["video"] = videos_by_id.get(rec.get("video_id"), {})
        enriched["channel"] = channels_by_id.get(rec.get("channel_id"), {})
        recs_by_product.setdefault(rec.get("product_id"), []).append(enriched)

    catalog = []
    for product in products:
        item = dict(product)
        item["recommendations"] = recs_by_product.get(product["product_id"], [])
        item["channel_count"] = len({x.get("channel_id") for x in item["recommendations"] if x.get("channel_id")})
        item["video_count"] = len({x.get("video_id") for x in item["recommendations"] if x.get("video_id")})
        item["max_confidence"] = max([float(x.get("confidence") or 0) for x in item["recommendations"]] or [0])
        catalog.append(item)

    catalog.sort(key=lambda x: (x["channel_count"], x["video_count"], x["max_confidence"]), reverse=True)
    return catalog


@st.cache_data(ttl=60, show_spinner=False)
def load_pending_products():
    products = api_get(
        "products",
        (
            "product_id,canonical_name,normalized_name,brand,model,category,"
            "search_keyword,review_status,is_visible,review_note,created_at"
        ),
        {"review_status": "eq.pending", "order": "created_at.asc", "limit": "500"},
    )
    recommendations = api_get(
        "recommendations",
        (
            "recommendation_id,product_id,video_id,channel_id,reason,pros,cons,"
            "evidence,confidence,purchase_type"
        ),
        {"limit": "5000"},
    )
    videos = api_get("videos", "video_id,title", {"limit": "5000"})
    channels = api_get(
        "channels", "channel_id,channel_name,subscriber_count", {"limit": "5000"}
    )
    video_map = {row["video_id"]: row for row in videos}
    channel_map = {row["channel_id"]: row for row in channels}
    grouped = {}
    for rec in recommendations:
        grouped.setdefault(rec.get("product_id"), []).append(rec)
    for product in products:
        product["recommendations"] = []
        for rec in grouped.get(product["product_id"], []):
            item = dict(rec)
            item["video"] = video_map.get(rec.get("video_id"), {})
            item["channel"] = channel_map.get(rec.get("channel_id"), {})
            product["recommendations"].append(item)
    return products


def safe(value):
    return html.escape(str(value or ""), quote=True)


def human_number(value):
    try:
        number = int(value or 0)
    except Exception:
        return "0"
    if number >= 100_000_000:
        return f"{number / 100_000_000:.1f}억"
    if number >= 10_000:
        return f"{number / 10_000:.1f}만"
    return f"{number:,}"


def timestamp(sec):
    try:
        sec = max(0, int(sec or 0))
    except Exception:
        sec = 0
    minute, second = divmod(sec, 60)
    hour, minute = divmod(minute, 60)
    return f"{hour:02d}:{minute:02d}:{second:02d}" if hour else f"{minute:02d}:{second:02d}"


def youtube_url(rec):
    video_id = rec.get("video_id", "")
    sec = int(rec.get("start_sec") or 0)
    return f"https://youtu.be/{video_id}?t={sec}"


def icon_for(text):
    value = (text or "").lower()
    if any(x in value for x in ("청소기", "냉장고", "매트", "생활", "살림")):
        return "🏠", "#EBF8FF"
    if any(x in value for x in ("모니터", "태블릿", "노트북", "충전", "it", "전자")):
        return "💻", "#F3EEFF"
    if any(x in value for x in ("화장", "뷰티", "쿠션", "립", "크림")):
        return "💄", "#FFEFF4"
    if any(x in value for x in ("음식", "주방", "조리")):
        return "🍳", "#FFF4E5"
    return "🛍️", "#F2F4F6"


st.markdown("""
<style>
:root { color-scheme: light !important; }
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background:#F2F4F6 !important; color:#191F28 !important;
  font-family:-apple-system,BlinkMacSystemFont,"Pretendard","Noto Sans KR",sans-serif !important;
}
[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer { visibility:hidden; }
.block-container { max-width:560px !important; padding:1rem 1rem 4rem !important; }
.hero { background:#fff; border:1px solid #E7EBF0; border-radius:24px; padding:22px; box-shadow:0 3px 14px rgba(25,31,40,.05); margin-bottom:14px; }
.app-title { font-size:21px; font-weight:900; color:#191F28; margin-bottom:15px; }
.hero-label { font-size:13px; font-weight:700; color:#8B95A1; }
.hero-count { font-size:34px; line-height:1.25; font-weight:900; color:#191F28; }
.hero-meta { font-size:13px; color:#4E5968; margin-top:8px; }
.notice { background:#FFF8E6; border:1px solid #FFE0A3; color:#7A4B00; border-radius:14px; padding:12px 14px; font-size:12.5px; line-height:1.5; margin-bottom:14px; }
.product-head { display:flex; gap:13px; align-items:center; margin:4px 0 12px; }
.product-icon { width:48px; height:48px; min-width:48px; border-radius:15px; display:flex; align-items:center; justify-content:center; font-size:23px; }
.product-name { font-size:16px; font-weight:800; color:#191F28; line-height:1.35; }
.product-sub { font-size:12.5px; color:#6B7684; margin-top:3px; }
.badge { display:inline-block; padding:3px 8px; border-radius:99px; background:#E8F3FF; color:#2F6FD6; font-size:11px; font-weight:750; margin:0 5px 5px 0; }
.reason { background:#F7F8FA; border-radius:12px; padding:11px 12px; color:#4E5968; font-size:12.5px; line-height:1.5; margin:8px 0; }
div[data-testid="stVerticalBlockBorderWrapper"] { background:#fff !important; border:1px solid #E7EBF0 !important; border-radius:20px !important; box-shadow:0 3px 14px rgba(25,31,40,.045) !important; padding:18px !important; margin-bottom:12px !important; }
[data-testid="stTextInput"] div[data-baseweb="input"], [data-testid="stSelectbox"] div[data-baseweb="select"] { background:#fff !important; border:1px solid #DDE2E8 !important; border-radius:14px !important; overflow:hidden !important; }
[data-testid="stTextInput"] input, [data-testid="stSelectbox"] div, [data-testid="stSelectbox"] span { background:#fff !important; color:#191F28 !important; -webkit-text-fill-color:#191F28 !important; }
[data-testid="stTextInput"] input::placeholder { color:#8B95A1 !important; -webkit-text-fill-color:#8B95A1 !important; opacity:1 !important; }
[data-testid="stSelectbox"] svg { fill:#4E5968 !important; color:#4E5968 !important; }
ul[data-baseweb="menu"], ul[data-baseweb="menu"] li, div[data-baseweb="popover"], div[data-baseweb="popover"] * { background:#fff !important; color:#191F28 !important; }
.stButton > button, .stLinkButton > a { border:none !important; border-radius:13px !important; min-height:42px !important; font-weight:750 !important; box-shadow:none !important; }
.stLinkButton > a[kind="primary"] { background:#4C82EE !important; color:#fff !important; }
.stLinkButton > a[kind="primary"] * { color:#fff !important; -webkit-text-fill-color:#fff !important; }
.stLinkButton > a[kind="secondary"] { background:#E8F3FF !important; color:#2F6FD6 !important; }
.stLinkButton > a[kind="secondary"] * { color:#2F6FD6 !important; -webkit-text-fill-color:#2F6FD6 !important; }
[data-testid="stExpander"] details { background:#fff !important; border:1px solid #E7EBF0 !important; border-radius:14px !important; }
[data-testid="stExpander"] * { color:#191F28 !important; }

/* ===== UI polish override ===== */
.block-container { max-width:620px !important; padding:0.45rem 1rem 4rem !important; }
.app-title { display:flex; align-items:center; gap:8px; margin:4px 2px 14px; font-size:22px; letter-spacing:-.4px; }
.hero { border:none !important; border-radius:26px !important; padding:24px !important; box-shadow:0 8px 28px rgba(34,55,80,.075) !important; }
.notice { background:#F7F9FC !important; border:none !important; color:#5B6573 !important; border-radius:16px !important; padding:13px 15px !important; }
.notice b { color:#344054 !important; }

div[data-testid="stVerticalBlockBorderWrapper"] {
  border:none !important; outline:none !important; border-radius:22px !important;
  box-shadow:0 5px 22px rgba(34,55,80,.07) !important; padding:20px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div { border:none !important; outline:none !important; box-shadow:none !important; }
.product-name { font-size:17px !important; letter-spacing:-.25px; }
.badge { background:#EEF5FF !important; color:#2D6CD3 !important; padding:4px 9px !important; }
.reason { background:#F7F9FB !important; border:0 !important; padding:12px 14px !important; }

/* search/select: one soft border only */
[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stSelectbox"] div[data-baseweb="select"] {
  border:1px solid #E1E6EC !important; outline:none !important; border-radius:14px !important;
  box-shadow:0 1px 2px rgba(16,24,40,.025) !important; min-height:48px !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"] > div,
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[role="combobox"],
[data-testid="stSelectbox"] div[role="combobox"] > div {
  border:none !important; outline:none !important; box-shadow:none !important; background:#fff !important;
}
[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
  border-color:#72A4FF !important; box-shadow:0 0 0 3px rgba(76,130,238,.12) !important;
}

/* buttons */
.stLinkButton > a { min-height:46px !important; border-radius:14px !important; font-size:13.5px !important; }
.stLinkButton > a[kind="primary"] { background:#4C82EE !important; }
.stLinkButton > a[kind="secondary"] { background:#EEF5FF !important; color:#2D6CD3 !important; }

/* expander: eliminate red/black focus ring */
[data-testid="stExpander"], [data-testid="stExpander"] details,
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary:focus,
[data-testid="stExpander"] summary:focus-visible {
  border:none !important; outline:none !important; box-shadow:none !important;
}
[data-testid="stExpander"] details { background:#F8FAFC !important; border-radius:14px !important; overflow:hidden !important; }
[data-testid="stExpander"] summary { background:#F8FAFC !important; padding:2px 4px !important; }
[data-testid="stExpander"] summary:hover { background:#F2F6FA !important; }
[data-testid="stExpander"] details[open] { box-shadow:inset 0 0 0 1px #E8EDF2 !important; }

/* refresh button */
.stButton > button { background:#F2F4F6 !important; color:#4E5968 !important; border:none !important; min-height:44px !important; }
.stButton > button * { color:#4E5968 !important; -webkit-text-fill-color:#4E5968 !important; }

@media (max-width:640px) {
  .block-container { padding:.25rem .75rem 3rem !important; }
  .hero { padding:20px !important; }
  div[data-testid="stVerticalBlockBorderWrapper"] { padding:16px !important; }
  .product-name { font-size:15.5px !important; }
  .hero-count { font-size:31px !important; }
}


/* ===== 관리자 검수 화면 가독성 개선 ===== */
[data-testid="stForm"] {
  background:#F8FAFC !important;
  border:1px solid #E7ECF2 !important;
  border-radius:18px !important;
  padding:18px !important;
  box-shadow:none !important;
}

/* 관리자 폼 라벨 */
[data-testid="stForm"] [data-testid="stWidgetLabel"],
[data-testid="stForm"] [data-testid="stWidgetLabel"] p,
[data-testid="stForm"] label,
[data-testid="stForm"] label p {
  color:#4E5968 !important;
  -webkit-text-fill-color:#4E5968 !important;
  font-size:13px !important;
  font-weight:750 !important;
  opacity:1 !important;
}

/* 관리자 입력창: 검은 외곽선 제거 */
[data-testid="stForm"] [data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stForm"] [data-testid="stSelectbox"] div[data-baseweb="select"] {
  background:#FFFFFF !important;
  border:1px solid #DDE3EA !important;
  border-radius:13px !important;
  outline:none !important;
  box-shadow:0 1px 2px rgba(16,24,40,.025) !important;
  min-height:46px !important;
  overflow:hidden !important;
}
[data-testid="stForm"] [data-testid="stTextInput"] div[data-baseweb="input"] > div,
[data-testid="stForm"] [data-testid="stTextInput"] input,
[data-testid="stForm"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stForm"] [data-testid="stSelectbox"] div[role="combobox"],
[data-testid="stForm"] [data-testid="stSelectbox"] div[role="combobox"] > div {
  background:#FFFFFF !important;
  border:none !important;
  outline:none !important;
  box-shadow:none !important;
  color:#191F28 !important;
  -webkit-text-fill-color:#191F28 !important;
}
[data-testid="stForm"] [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
[data-testid="stForm"] [data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
  border-color:#72A4FF !important;
  box-shadow:0 0 0 3px rgba(49,130,246,.12) !important;
}

/* 관리자 승인/숨김 버튼 */
[data-testid="stForm"] button[kind="primary"],
[data-testid="stForm"] button[data-testid="stBaseButton-primary"] {
  background:#3182F6 !important;
  border:1px solid #3182F6 !important;
  color:#FFFFFF !important;
  min-height:46px !important;
  border-radius:13px !important;
}
[data-testid="stForm"] button[kind="primary"] *,
[data-testid="stForm"] button[data-testid="stBaseButton-primary"] * {
  color:#FFFFFF !important;
  -webkit-text-fill-color:#FFFFFF !important;
}
[data-testid="stForm"] button[kind="secondary"],
[data-testid="stForm"] button[data-testid="stBaseButton-secondary"] {
  background:#FFF0F2 !important;
  border:1px solid #FFD5DB !important;
  color:#C92A2A !important;
  min-height:46px !important;
  border-radius:13px !important;
}
[data-testid="stForm"] button[kind="secondary"] *,
[data-testid="stForm"] button[data-testid="stBaseButton-secondary"] * {
  color:#C92A2A !important;
  -webkit-text-fill-color:#C92A2A !important;
}
[data-testid="stForm"] button:hover { filter:brightness(.985) !important; }

/* 관리자 카드 제목과 안내 박스 */
[data-testid="stAlert"] {
  border:none !important;
  border-radius:14px !important;
  background:#EAF3FF !important;
  color:#295FA8 !important;
}
[data-testid="stAlert"] * {
  color:#295FA8 !important;
  -webkit-text-fill-color:#295FA8 !important;
}

/* 상단 내비게이션 버튼 대비 */
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
  background:#3182F6 !important;
  color:#FFFFFF !important;
}
.stButton > button[kind="primary"] *,
.stButton > button[data-testid="stBaseButton-primary"] * {
  color:#FFFFFF !important;
  -webkit-text-fill-color:#FFFFFF !important;
}
.stButton > button[kind="secondary"],
.stButton > button[data-testid="stBaseButton-secondary"] {
  background:#EEF1F5 !important;
  color:#4E5968 !important;
}
.stButton > button[kind="secondary"] *,
.stButton > button[data-testid="stBaseButton-secondary"] * {
  color:#4E5968 !important;
  -webkit-text-fill-color:#4E5968 !important;
}

</style>
""", unsafe_allow_html=True)

def render_home():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Streamlit Secrets에 SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY를 등록해 주세요.")
        st.stop()

    try:
        with st.spinner("자동 수집된 꿀템을 불러오는 중..."):
            catalog = load_catalog()
    except Exception as error:
        st.error(str(error))
        st.info("SUPABASE_URL에는 /rest/v1 없이 https://프로젝트ID.supabase.co 까지만 입력해야 합니다.")
        st.stop()

    all_channels = {
        rec.get("channel", {}).get("channel_id")
        for item in catalog for rec in item["recommendations"]
        if rec.get("channel", {}).get("channel_id")
    }
    all_videos = {
        rec.get("video_id") for item in catalog for rec in item["recommendations"] if rec.get("video_id")
    }

    st.markdown(f"""
    <div class="hero">
      <div class="hero-label">유튜버 영상에서 자동 검증된 상품</div>
      <div class="hero-count">{len(catalog):,}개</div>
      <div class="hero-meta">실제 채널 {len(all_channels):,}개 · 추천 영상 {len(all_videos):,}개 · 매일 자동 업데이트</div>
    </div>
    <div class="notice"><b>데이터 안내</b><br>유튜브 영상 제목·설명과 AI 분석을 바탕으로 정리한 상품입니다. 구매 전 모델명과 판매 정보를 다시 확인해 주세요.</div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1.45, 1])
    keyword = c1.text_input("상품 검색", placeholder="🔍 상품·브랜드·유튜버 검색", label_visibility="collapsed")
    categories = sorted({x.get("category") or "기타" for x in catalog})
    selected_category = c2.selectbox("카테고리", ["전체"] + categories, label_visibility="collapsed")

    filtered = []
    for item in catalog:
        if selected_category != "전체" and (item.get("category") or "기타") != selected_category:
            continue
        channel_names = " ".join(rec.get("channel", {}).get("channel_name", "") for rec in item["recommendations"])
        haystack = " ".join([
            item.get("canonical_name", ""), item.get("brand", ""), item.get("model", ""),
            item.get("category", ""), item.get("search_keyword", ""), channel_names,
        ]).lower()
        if keyword and keyword.lower() not in haystack:
            continue
        filtered.append(item)

    st.caption(f"검증 상품 {len(filtered)}개 · 데이터는 5분마다 자동 갱신")

    if not filtered:
        with st.container(border=True):
            st.write("조건에 맞는 자동 수집 상품이 아직 없습니다.")

    for item in filtered:
        recs = item["recommendations"]
        icon, icon_bg = icon_for(f"{item.get('canonical_name')} {item.get('category')}")
        with st.container(border=True):
            st.markdown(
                f'<div class="product-head"><div class="product-icon" style="background:{icon_bg}">{icon}</div>'
                f'<div><div class="product-name">{safe(item.get("canonical_name"))}</div>'
                f'<div class="product-sub">{safe(item.get("brand"))} · {safe(item.get("category") or "기타")}</div></div></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<span class="badge">유튜버 {item["channel_count"]}명</span>'
                f'<span class="badge">추천 영상 {item["video_count"]}개</span>'
                f'<span class="badge">근거 신뢰도 {item["max_confidence"]:.0%}</span>',
                unsafe_allow_html=True,
            )

            if recs and recs[0].get("reason"):
                st.markdown(f'<div class="reason">{safe(recs[0]["reason"])}</div>', unsafe_allow_html=True)

            # 관리자가 검수한 최종 상품명만 판매처 검색어로 사용한다.
            # 브랜드와 모델을 다시 붙이면 같은 문구가 두 번 입력될 수 있다.
            search_name = str(
                item.get("canonical_name")
                or item.get("search_keyword")
                or ""
            ).strip()
            encoded = quote(search_name)
            b1, b2 = st.columns(2)
            b1.link_button(
                "네이버쇼핑 확인",
                f"https://search.shopping.naver.com/search/all?query={encoded}&sort=price_asc",
                type="primary",
                use_container_width=True,
            )
            b2.link_button(
                "쿠팡에서 검색",
                f"https://www.coupang.com/np/search?q={encoded}",
                type="secondary",
                use_container_width=True,
            )

            with st.expander(f"추천 근거와 영상 {len(recs)}건"):
                for index, rec in enumerate(recs, 1):
                    channel = rec.get("channel", {})
                    video = rec.get("video", {})
                    channel_name = channel.get("channel_name") or "알 수 없는 채널"
                    subscribers = human_number(channel.get("subscriber_count"))
                    confidence = float(rec.get("confidence") or 0)
                    st.markdown(f"**{index}. {safe(channel_name)}** · 구독자 {subscribers} · 신뢰도 {confidence:.0%}")
                    if video.get("title"):
                        st.caption(video["title"])
                    if rec.get("evidence"):
                        st.write(f"근거: {rec['evidence']}")
                    pros = rec.get("pros") or []
                    cons = rec.get("cons") or []
                    if pros:
                        st.write("좋았던 점: " + " · ".join(str(x) for x in pros))
                    if cons:
                        st.write("아쉬운 점: " + " · ".join(str(x) for x in cons))
                    st.caption(f"구매 형태: {rec.get('purchase_type') or '확인되지 않음'}")
                    st.link_button(
                        f"▶ {timestamp(rec.get('start_sec'))}부터 영상 보기",
                        youtube_url(rec),
                        key=f"video_{item['product_id']}_{rec['recommendation_id']}",
                        use_container_width=True,
                    )
                    if index < len(recs):
                        st.divider()

    if st.button("최신 데이터 다시 불러오기", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

def render_admin():
    admin_password = get_secret("ADMIN_PASSWORD")
    if not admin_password:
        st.error("Streamlit Secrets에 ADMIN_PASSWORD를 등록해 주세요.")
        return

    if not st.session_state.get("admin_authenticated", False):
        with st.container(border=True):
            st.subheader("관리자 로그인")
            entered = st.text_input("관리자 비밀번호", type="password", key="admin_password_input")
            if st.button("로그인", type="primary", use_container_width=True):
                if entered == admin_password:
                    st.session_state.admin_authenticated = True
                    st.rerun()
                else:
                    st.error("비밀번호가 맞지 않습니다.")
        return

    head1, head2 = st.columns([3, 1])
    head1.subheader("검수 대기 상품")
    if head2.button("로그아웃", use_container_width=True):
        st.session_state.admin_authenticated = False
        st.rerun()

    try:
        pending = load_pending_products()
    except Exception as error:
        st.error(str(error))
        return

    st.caption(f"승인 또는 숨김 처리가 필요한 상품 {len(pending)}개")
    if not pending:
        st.success("현재 검수 대기 상품이 없습니다.")
        return

    category_options = [
        "IT·전자", "뷰티", "패션", "생활·살림", "주방", "여행", "자동차",
        "운동·건강", "육아", "반려동물", "기타"
    ]

    for product in pending:
        product_id = product["product_id"]
        with st.container(border=True):
            st.markdown(f"### {safe(product.get('canonical_name'))}")
            recs = product.get("recommendations", [])
            if recs:
                rec = recs[0]
                channel = rec.get("channel", {})
                video = rec.get("video", {})
                st.caption(
                    f"{channel.get('channel_name') or '알 수 없는 채널'} · "
                    f"AI 신뢰도 {float(rec.get('confidence') or 0):.0%}"
                )
                if video.get("title"):
                    st.write(f"영상: {video['title']}")
                if rec.get("reason"):
                    st.info(rec["reason"])
                if rec.get("evidence"):
                    st.caption(f"근거: {rec['evidence']}")
                if rec.get("video_id"):
                    st.link_button(
                        "원본 영상 확인",
                        f"https://youtu.be/{rec['video_id']}",
                        use_container_width=True,
                    )

            with st.form(key=f"review_form_{product_id}"):
                edited_name = st.text_input(
                    "상품명", value=product.get("canonical_name") or ""
                )
                left, right = st.columns(2)
                edited_brand = left.text_input(
                    "브랜드", value=product.get("brand") or ""
                )
                edited_model = right.text_input(
                    "모델", value=product.get("model") or ""
                )
                current_category = product.get("category") or "기타"
                category_index = (
                    category_options.index(current_category)
                    if current_category in category_options else len(category_options) - 1
                )
                edited_category = st.selectbox(
                    "카테고리", category_options, index=category_index
                )
                edited_keyword = st.text_input(
                    "검색 키워드",
                    value=product.get("search_keyword") or product.get("canonical_name") or "",
                )
                review_note = st.text_input(
                    "관리 메모", value=product.get("review_note") or ""
                )
                approve_col, hide_col = st.columns(2)
                approve = approve_col.form_submit_button(
                    "승인 후 공개", type="primary", use_container_width=True
                )
                hide = hide_col.form_submit_button(
                    "숨김 처리", use_container_width=True
                )

            if approve:
                clean_name = edited_name.strip()
                normalized = re.sub(r"[^0-9a-z가-힣]+", "", clean_name.lower())
                if len(normalized) < 4:
                    st.error("상품명이 너무 짧습니다.")
                else:
                    try:
                        api_patch(
                            "products",
                            {
                                "canonical_name": clean_name,
                                "normalized_name": normalized,
                                "brand": edited_brand.strip(),
                                "model": edited_model.strip(),
                                "category": edited_category,
                                "search_keyword": edited_keyword.strip() or clean_name,
                                "review_status": "approved",
                                "is_visible": True,
                                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                                "review_note": review_note.strip() or "관리자 승인",
                            },
                            {"product_id": f"eq.{product_id}"},
                        )
                        st.cache_data.clear()
                        st.success("승인했습니다.")
                        st.rerun()
                    except Exception as error:
                        st.error(str(error))

            if hide:
                try:
                    api_patch(
                        "products",
                        {
                            "review_status": "hidden",
                            "is_visible": False,
                            "reviewed_at": datetime.now(timezone.utc).isoformat(),
                            "review_note": review_note.strip() or "관리자 숨김",
                        },
                        {"product_id": f"eq.{product_id}"},
                    )
                    st.cache_data.clear()
                    st.success("숨김 처리했습니다.")
                    st.rerun()
                except Exception as error:
                    st.error(str(error))


st.markdown('<div class="app-title">🛍️ 꿀템 다나와</div>', unsafe_allow_html=True)
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Streamlit Secrets에 SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY를 등록해 주세요.")
    st.stop()

if "page" not in st.session_state:
    st.session_state.page = "home"
nav_home, nav_admin = st.columns(2)
if nav_home.button(
    "꿀템 홈",
    type="primary" if st.session_state.page == "home" else "secondary",
    use_container_width=True,
):
    st.session_state.page = "home"
    st.rerun()
if nav_admin.button(
    "관리자 검수",
    type="primary" if st.session_state.page == "admin" else "secondary",
    use_container_width=True,
):
    st.session_state.page = "admin"
    st.rerun()

if st.session_state.page == "admin":
    render_admin()
else:
    render_home()

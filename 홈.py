import html
import re
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import quote

import requests
import streamlit as st

st.set_page_config(page_title="꿀템 다나와", page_icon="🛍️", layout="wide")


def secret(name):
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


SUPABASE_URL = secret("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = secret("SUPABASE_SERVICE_ROLE_KEY")
CATEGORIES = ["IT·전자", "뷰티", "패션", "생활·살림", "주방", "여행", "자동차", "운동·건강", "육아", "반려동물", "기타"]
IMAGE_SOURCES = ["", "brand_official", "affiliate", "manual", "youtube_thumbnail"]
IMAGE_SOURCE_LABELS = {"": "출처 미선택", "brand_official": "브랜드 공식", "affiliate": "제휴사 제공", "manual": "직접 확인", "youtube_thumbnail": "유튜브 썸네일"}
CATEGORY_VISUALS = {
    "IT·전자": ("🖥️", "#EAF3FF", "#3182F6"), "뷰티": ("🧴", "#FFF1E8", "#E67527"),
    "패션": ("👕", "#F4EEFF", "#7652C7"), "생활·살림": ("🏠", "#EEF8F3", "#218B61"),
    "주방": ("🍳", "#FFF6DF", "#BD7500"), "여행": ("🧳", "#EAF8FA", "#167C8C"),
    "자동차": ("🚗", "#EEF1F5", "#4E5968"), "운동·건강": ("🏃", "#FFF0F0", "#C92A2A"),
    "육아": ("🧸", "#FFF4E8", "#D06A19"), "반려동물": ("🐾", "#F4F7EA", "#6E832B"),
    "기타": ("🛍️", "#F1F4F8", "#5D6B7A"),
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


def api_patch(table, values, params):
    response = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers("return=representation"), params=params, json=values, timeout=30)
    if not response.ok:
        raise RuntimeError(f"{table} 수정 실패: HTTP {response.status_code} · {response.text[:250]}")
    return response.json() if response.text else []


def safe(value):
    return html.escape(str(value or ""), quote=True)


def number(value):
    value = int(value or 0)
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f}억"
    if value >= 10_000:
        return f"{value / 10_000:.1f}만"
    return f"{value:,}"


def count_by(rows, key):
    return Counter(str(row.get(key) or "unknown") for row in rows)


@st.cache_data(ttl=300, show_spinner=False)
def load_public_data():
    products = api_get("products", "product_id,canonical_name,brand,model,category,search_keyword,coupang_url,affiliate_verified,image_url,image_source,image_verified,image_checked_at,image_note,created_at", {"review_status": "eq.approved", "is_visible": "eq.true", "order": "created_at.desc", "limit": "1000"})
    recs = api_get("recommendations", "recommendation_id,product_id,video_id,channel_id,reason,pros,cons,evidence,confidence,purchase_type,created_at", {"order": "created_at.desc", "limit": "5000"})
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
    products.sort(key=lambda p: (len({r.get("channel_id") for r in p["recommendations"]}), len(p["recommendations"])), reverse=True)
    return products


@st.cache_data(ttl=60, show_spinner=False)
def load_admin_data():
    products = api_get("products", "product_id,canonical_name,brand,model,category,search_keyword,identity_score,review_status,is_visible,review_note,coupang_url,coupang_product_name,affiliate_verified,affiliate_note,image_url,image_source,image_verified,image_checked_at,image_note,created_at", {"order": "created_at.desc", "limit": "5000"})
    videos = api_get("videos", "video_id,channel_id,title,analysis_status,analysis_error,product_score,created_at,published_at", {"order": "created_at.desc", "limit": "10000"})
    channels = api_get("channels", "channel_id,channel_name,status,scan_priority,total_scanned_videos,product_candidate_videos,extracted_product_count,last_scanned_at,next_video_scan_at", {"limit": "10000"})
    queries = api_get("discovery_queries", "query_id,query_text,category,enabled,run_count,channels_found,active_channels_found,error_count,last_error,last_run_at,next_run_at", {"limit": "1000"})
    recs = api_get("recommendations", "recommendation_id,product_id,video_id,channel_id,confidence,created_at", {"limit": "10000"})
    return products, videos, channels, queries, recs


st.markdown("""
<style>
:root{--brand:#3182F6;--soft:#EAF3FF;--ink:#191F28;--muted:#6B7684;--orange:#F28A3A;--orange-dark:#E67527;--canvas:#F5F7FA}
.stApp{background:var(--canvas);color:var(--ink)} .block-container{max-width:1220px;padding:1rem 1rem 4rem} #MainMenu,footer,[data-testid="stHeader"]{visibility:hidden}
.title{color:var(--brand);font-size:27px;font-weight:900;margin:4px 0 14px}.hero{background:#fff;border-radius:20px;padding:22px;box-shadow:0 6px 22px rgba(49,130,246,.07);margin-bottom:14px}.hero b{color:var(--brand);font-size:32px}.muted{color:var(--muted);font-size:13px}.product-title{font-size:17px;font-weight:850;line-height:1.35;min-height:48px}.badge{display:inline-block;color:#245FB5;background:#EAF3FF;border:1px solid #CFE2FF;padding:4px 9px;border-radius:999px;font-size:11px;margin:5px 5px 5px 0}.reason{background:#F8FAFD;border-left:3px solid var(--brand);border-radius:10px;padding:11px 12px;margin:9px 0;color:#4E5968;font-size:13px;min-height:70px}.metric{background:#fff;border-radius:16px;padding:15px;box-shadow:0 5px 17px rgba(49,130,246,.06);min-height:94px}.metric-label{color:var(--muted);font-size:12px;font-weight:700}.metric-value{color:var(--brand);font-size:25px;font-weight:900;margin-top:5px}.status-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #EDF1F6;font-size:13px}.error-box{background:#FFF0F0;color:#A61B22;padding:10px;border-radius:10px;font-size:12px;margin:6px 0;word-break:break-word}
div[data-testid="stVerticalBlockBorderWrapper"]{border:0!important;outline:0!important;background:#fff!important;border-radius:20px!important;box-shadow:0 8px 26px rgba(49,130,246,.08)!important;padding:16px!important;margin-bottom:12px!important}
.stButton>button,.stLinkButton>a{min-height:43px!important;border-radius:12px!important;font-weight:780!important}.stButton>button[kind="primary"],.stLinkButton>a[kind="primary"]{background:var(--brand)!important;border-color:var(--brand)!important;color:#fff!important}.stButton>button[kind="secondary"],.stLinkButton>a[kind="secondary"]{background:#EDF5FF!important;border-color:#D4E6FF!important;color:#245FB5!important}
div[data-testid="stTextInput"] div[data-baseweb="input"],div[data-testid="stSelectbox"] div[data-baseweb="select"]{border:0!important;outline:0!important;background:#fff!important;box-shadow:inset 0 0 0 2px var(--orange),0 4px 14px rgba(242,138,58,.10)!important;border-radius:14px!important;overflow:hidden!important}div[data-testid="stTextInput"] input,div[data-testid="stSelectbox"] div[role="combobox"],div[data-testid="stSelectbox"] div[role="combobox"] *{background:#fff!important;color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;border:0!important;outline:0!important}div[data-testid="stSelectbox"] svg{fill:var(--orange-dark)!important;color:var(--orange-dark)!important}
.product-placeholder{width:100%;height:210px;border-radius:15px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;margin-bottom:13px;overflow:hidden}.product-placeholder span{font-size:42px}.product-placeholder small{font-size:12px;font-weight:800}.st-key-product_grid [data-testid="stImage"]{height:210px!important;overflow:hidden!important;border-radius:15px!important;margin-bottom:13px!important}.st-key-product_grid [data-testid="stImage"] img{width:100%!important;height:210px!important;object-fit:contain!important;background:#fff!important;border-radius:15px!important;padding:8px!important}.st-key-product_grid [data-testid="stHorizontalBlock"]{gap:16px!important;align-items:stretch!important}.st-key-product_grid [data-testid="column"]{min-width:0!important;display:flex!important;flex-direction:column!important}
div[data-testid="stForm"]{border:0!important;background:#F7FAFF!important;border-radius:18px!important;box-shadow:inset 0 0 0 1px #DDE9F8!important;padding:17px!important}div[data-testid="stForm"] input,div[data-testid="stForm"] textarea,div[data-testid="stForm"] div[role="combobox"]{background:#fff!important;color:#191F28!important;-webkit-text-fill-color:#191F28!important}
@media(max-width:900px) and (min-width:601px){.st-key-product_grid [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}.st-key-product_grid [data-testid="column"]{flex:0 0 calc(50% - 8px)!important;min-width:calc(50% - 8px)!important}.product-placeholder,.st-key-product_grid [data-testid="stImage"],.st-key-product_grid [data-testid="stImage"] img{height:190px!important}}
@media(max-width:600px){.block-container{padding:.65rem .55rem 3rem}.st-key-product_grid [data-testid="stHorizontalBlock"]{flex-direction:column!important}.st-key-product_grid [data-testid="column"]{width:100%!important;min-width:100%!important}.product-placeholder,.st-key-product_grid [data-testid="stImage"],.st-key-product_grid [data-testid="stImage"] img{height:210px!important}.product-title,.reason{min-height:0}.title{font-size:22px}}

.thumbnail-source-badge {
  display: inline-block;
  position: relative;
  margin-top: -43px;
  margin-left: 9px;
  margin-bottom: 17px;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(25,31,40,.78);
  color: #FFFFFF;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  z-index: 2;
}

/* 영상 썸네일은 상품 사진과 구분해 16:9 전체폭 중앙 정렬 */
.video-thumbnail-wrap {
  position: relative;
  width: 100%;
  height: 210px;
  margin: 0 0 13px 0;
  border-radius: 15px;
  overflow: hidden;
  background: #111827;
  box-shadow: inset 0 0 0 1px rgba(25,31,40,.08);
}
.video-thumbnail {
  display: block;
  width: 100%;
  height: 100%;
  margin: 0 auto;
  object-fit: cover;
  object-position: center center;
}
.video-thumbnail-label {
  position: absolute;
  left: 10px;
  bottom: 10px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(25,31,40,.82);
  color: #FFFFFF;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  backdrop-filter: blur(4px);
}
@media (max-width: 900px) and (min-width: 601px) {
  .video-thumbnail-wrap { height: 190px; }
}
@media (max-width: 600px) {
  .video-thumbnail-wrap { height: 210px; }
}

/* 쇼핑 이동 버튼은 한 줄 2열로 압축 */
.st-key-product_grid [data-testid="stLinkButton"] a {
  min-height: 42px !important;
  padding-left: 8px !important;
  padding-right: 8px !important;
  white-space: nowrap !important;
  font-size: 14px !important;
}
@media (max-width: 600px) {
  .st-key-product_grid [data-testid="stLinkButton"] a {
    min-height: 44px !important;
    font-size: 14px !important;
  }
}

.purchase-badge{display:inline-block;margin:4px 5px 5px 0;padding:4px 8px;border-radius:999px;background:#FFF2E8;color:#B94F09;border:1px solid #FFD9BD;font-size:11px;font-weight:800}
.summary-line{margin-top:6px;padding:8px 10px;border-radius:9px;font-size:12px;line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.summary-pro{background:#EEF8F3;color:#176B49}.summary-con{background:#FFF3F3;color:#A61B22}

/* ===== 간결한 상품 카드 최종 보정 ===== */
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] {
  padding: 13px !important;
  border-radius: 18px !important;
}
.st-key-product_grid .product-title {
  min-height: 44px !important;
  margin-top: 2px !important;
  font-size: 16px !important;
  line-height: 1.38 !important;
}
.st-key-product_grid .muted {
  margin-top: 2px !important;
  font-size: 12px !important;
}
.st-key-product_grid .badge,
.st-key-product_grid .purchase-badge {
  padding: 3px 7px !important;
  margin: 4px 3px 3px 0 !important;
  font-size: 10px !important;
}
.st-key-product_grid .summary-line {
  margin: 6px 0 8px !important;
  padding: 7px 9px !important;
  min-height: 0 !important;
  font-size: 12px !important;
  -webkit-line-clamp: 1 !important;
}
.st-key-product_grid [data-testid="stLinkButton"] a {
  min-height: 38px !important;
  font-size: 13px !important;
  padding: 6px 7px !important;
}
.st-key-product_grid [data-testid="stExpander"] {
  margin-top: 7px !important;
  border-radius: 11px !important;
}
.st-key-product_grid [data-testid="stExpander"] summary {
  min-height: 38px !important;
  padding-top: 6px !important;
  padding-bottom: 6px !important;
  font-size: 13px !important;
}
.video-thumbnail-wrap,
.product-placeholder,
.st-key-product_grid [data-testid="stImage"],
.st-key-product_grid [data-testid="stImage"] img {
  height: 180px !important;
  min-height: 180px !important;
  max-height: 180px !important;
}
.video-thumbnail-label {
  left: 8px !important;
  bottom: 8px !important;
  padding: 5px 8px !important;
  font-size: 10px !important;
}
@media (max-width: 900px) and (min-width: 601px) {
  .video-thumbnail-wrap,
  .product-placeholder,
  .st-key-product_grid [data-testid="stImage"],
  .st-key-product_grid [data-testid="stImage"] img {
    height: 175px !important;
    min-height: 175px !important;
    max-height: 175px !important;
  }
}
@media (max-width: 600px) {
  .st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] { padding: 14px !important; }
  .video-thumbnail-wrap,
  .product-placeholder,
  .st-key-product_grid [data-testid="stImage"],
  .st-key-product_grid [data-testid="stImage"] img {
    height: 200px !important;
    min-height: 200px !important;
    max-height: 200px !important;
  }
  .st-key-product_grid .product-title { min-height: 0 !important; }
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">🛍️ 꿀템 다나와</div>', unsafe_allow_html=True)
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Streamlit Secrets에 SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY를 등록하세요.")
    st.stop()

if "page" not in st.session_state:
    st.session_state.page = "home"
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


def render_product_visual(product):
    """검증 상품 이미지 -> 대표 추천 영상 썸네일 -> 카테고리 기본 이미지 순으로 표시."""
    image_url = str(product.get("image_url") or "").strip()
    if product.get("image_verified") and image_url.startswith(("https://", "http://")):
        st.image(image_url, use_container_width=True)
        return

    recommendations = product.get("recommendations") or []
    ranked = sorted(
        recommendations,
        key=lambda rec: (
            float(rec.get("confidence") or 0),
            int((rec.get("video") or {}).get("view_count") or 0),
            str((rec.get("video") or {}).get("published_at") or ""),
        ),
        reverse=True,
    )
    representative = next((rec for rec in ranked if rec.get("video_id")), None)
    if representative:
        video_id = safe(representative["video_id"])
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        st.markdown(
            '<div class="video-thumbnail-wrap">'
            f'<img class="video-thumbnail" src="{thumbnail_url}" alt="추천 영상 썸네일">'
            '<span class="video-thumbnail-label">추천 영상 이미지</span>'
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
            if len(text) >= 2:
                pros[text] += 1
        for value in rec.get("cons") or []:
            text = re.sub(r"\s+", " ", str(value).strip())
            if len(text) >= 2:
                cons[text] += 1
    return {
        "purchase_counts": purchase_counts,
        "pros": [text for text, _ in pros.most_common(3)],
        "cons": [text for text, _ in cons.most_common(3)],
    }


def render_purchase_badges(counts):
    labels = [("직접 구매", "직접 구매"), ("제품 제공", "제품 제공"), ("유료 광고", "유료 광고"), ("확인되지 않음", "미확인")]
    parts = []
    for key, label in labels:
        count = int(counts.get(key, 0))
        if count:
            parts.append(f'<span class="purchase-badge">{label} {count}</span>')
    if parts:
        st.markdown("".join(parts), unsafe_allow_html=True)


def render_product_card(product):
    recs = product["recommendations"]
    with st.container(border=True):
        render_product_visual(product)
        st.markdown(f'<div class="product-title">{safe(product.get("canonical_name"))}</div><div class="muted">{safe(product.get("brand"))} · {safe(product.get("category") or "기타")}</div>', unsafe_allow_html=True)
        channel_count = len({r.get("channel_id") for r in recs if r.get("channel_id")})
        confidence = max([float(r.get("confidence") or 0) for r in recs] or [0])
        st.markdown(f'<span class="badge">유튜버 {channel_count}명</span><span class="badge">영상 {len(recs)}개</span><span class="badge">신뢰도 {confidence:.0%}</span>', unsafe_allow_html=True)
        summary = recommendation_summary(recs)
        render_purchase_badges(summary["purchase_counts"])
        if summary["pros"]:
            st.markdown(f'<div class="summary-line summary-pro">장점 · {safe(summary["pros"][0])}</div>', unsafe_allow_html=True)
        query_name = quote(str(product.get("canonical_name") or product.get("search_keyword") or ""))
        affiliate = bool(
            product.get("affiliate_verified")
            and str(product.get("coupang_url") or "").startswith("https://link.coupang.com/")
        )
        coupang_url = (
            product.get("coupang_url")
            if affiliate
            else f"https://www.coupang.com/np/search?q={query_name}"
        )
        shop_left, shop_right = st.columns(2, gap="small")
        with shop_left:
            st.link_button(
                "네이버쇼핑",
                f"https://search.shopping.naver.com/search/all?query={query_name}",
                type="primary",
                use_container_width=True,
            )
        with shop_right:
            st.link_button(
                "쿠팡 구매" if affiliate else "쿠팡 검색",
                coupang_url,
                use_container_width=True,
            )
        with st.expander(f"상세 비교 · 영상 {len(recs)}개"):
            if summary["pros"] or summary["cons"]:
                st.markdown("**영상 통합 요약**")
                if summary["pros"]:
                    st.markdown("**공통 장점**")
                    for value in summary["pros"]:
                        st.write(f"• {value}")
                if summary["cons"]:
                    st.markdown("**공통 아쉬움**")
                    for value in summary["cons"]:
                        st.write(f"• {value}")
                st.divider()
            for rec in recs:
                channel = rec.get("channel", {})
                video = rec.get("video", {})
                st.markdown(f"**{safe(channel.get('channel_name') or '알 수 없는 채널')}**")
                st.caption(video.get("title") or "제목 없음")
                if rec.get("evidence"):
                    st.write(rec["evidence"])
                if rec.get("video_id"):
                    st.link_button("원본 영상 보기", f"https://youtu.be/{rec['video_id']}", key=f"v_{rec['recommendation_id']}", use_container_width=True)


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
        if p1.button("← 이전", disabled=page <= 1, use_container_width=True):
            st.session_state.catalog_page = page - 1; st.rerun()
        p2.markdown(f'<div style="text-align:center;padding:11px">{page} / {pages}</div>', unsafe_allow_html=True)
        if p3.button("다음 →", disabled=page >= pages, use_container_width=True):
            st.session_state.catalog_page = page + 1; st.rerun()


def render_dashboard():
    if not require_admin(): return
    products, videos, channels, queries, recs = load_admin_data()
    ps, vs = count_by(products, "review_status"), count_by(videos, "analysis_status")
    active = sum(1 for c in channels if c.get("status") == "active")
    qerrors = sum(1 for q in queries if int(q.get("error_count") or 0) > 0 or q.get("last_error"))
    metrics = [("전체 채널", len(channels), f"활성 {active}"), ("전체 영상", len(videos), f"AI 대기 {vs.get('queued',0)}"), ("공개 상품", ps.get("approved",0), f"검수 {ps.get('pending',0)}"), ("검색어", len(queries), f"오류 {qerrors}")]
    for col, (label, value, sub) in zip(st.columns(4), metrics):
        col.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value:,}</div><div class="muted">{sub}</div></div>', unsafe_allow_html=True)
    st.subheader("영상 처리 현황")
    l, r = st.columns(2)
    with l:
        with st.container(border=True):
            for key in ["pending","queued","analyzed","no_product","rejected_generic","skipped_non_product","ai_error"]:
                st.markdown(f'<div class="status-row"><span>{key}</span><b>{vs.get(key,0):,}</b></div>', unsafe_allow_html=True)
    with r:
        with st.container(border=True):
            for key in ["approved","pending","hidden","merged"]:
                st.markdown(f'<div class="status-row"><span>상품 {key}</span><b>{ps.get(key,0):,}</b></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="status-row"><span>추천 기록</span><b>{len(recs):,}</b></div>', unsafe_allow_html=True)
    st.subheader("최근 오류")
    errors = [v for v in videos if v.get("analysis_status") == "ai_error" and v.get("analysis_error")][:10]
    qrows = [q for q in queries if q.get("last_error")][:10]
    if not errors and not qrows: st.success("현재 기록된 최근 오류가 없습니다.")
    for row in errors: st.markdown(f'<div class="error-box"><b>영상:</b> {safe(row.get("title"))}<br>{safe(row.get("analysis_error"))}</div>', unsafe_allow_html=True)
    for row in qrows: st.markdown(f'<div class="error-box"><b>검색어:</b> {safe(row.get("query_text"))}<br>{safe(row.get("last_error"))}</div>', unsafe_allow_html=True)
    if st.button("통계 새로고침", use_container_width=True): st.cache_data.clear(); st.rerun()


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
        image_url = st.text_input("이미지 URL", value=product.get("image_url") or "", placeholder="https://...", key=f"{prefix}_img_{pid}")
        source = st.selectbox("이미지 출처", IMAGE_SOURCES, index=IMAGE_SOURCES.index(product.get("image_source")) if product.get("image_source") in IMAGE_SOURCES else 0, format_func=lambda x: IMAGE_SOURCE_LABELS[x], key=f"{prefix}_src_{pid}")
        verified = st.checkbox("정확한 상품 이미지 확인 완료", value=bool(product.get("image_verified")), key=f"{prefix}_ver_{pid}")
        image_note = st.text_input("이미지 메모", value=product.get("image_note") or "", key=f"{prefix}_note_{pid}")
        visible = st.checkbox("홈에 공개", value=bool(product.get("is_visible")), key=f"{prefix}_vis_{pid}") if allow_hide else True
        save = st.form_submit_button("상품 정보 저장" if allow_hide else "승인 후 공개", type="primary", use_container_width=True)
    if not save: return
    if not name.strip() or not brand.strip(): st.error("상품명과 브랜드를 입력하세요."); return
    if verified and not image_url.strip().startswith(("http://", "https://")): st.error("확인된 이미지는 http 또는 https URL이 필요합니다."); return
    api_patch("products", {"canonical_name":name.strip(),"normalized_name":re.sub(r"[^0-9a-z가-힣]+","",name.lower()),"brand":brand.strip(),"model":model.strip(),"category":category,"search_keyword":keyword.strip() or name.strip(),"image_url":image_url.strip() or None,"image_source":source or None,"image_verified":bool(verified and image_url.strip()),"image_checked_at":datetime.now(timezone.utc).isoformat() if verified and image_url.strip() else None,"image_note":image_note.strip() or None,"review_status":"approved" if visible else "hidden","is_visible":bool(visible),"reviewed_at":datetime.now(timezone.utc).isoformat(),"review_note":"관리자 상품 관리에서 수정"},{"product_id":f"eq.{pid}"})
    st.cache_data.clear(); st.success("저장했습니다."); st.rerun()


def render_review():
    if not require_admin(): return
    products, _, _, _, _ = load_admin_data()
    pending = [p for p in products if p.get("review_status") == "pending"]
    st.subheader(f"검수 대기 상품 {len(pending)}개")
    if not pending: st.success("검수 대기 상품이 없습니다."); return
    for product in pending:
        with st.container(border=True):
            st.markdown(f"### {safe(product.get('canonical_name'))}")
            st.caption(f"식별 점수 {int(product.get('identity_score') or 0)}/100 · {product.get('review_note') or '사유 없음'}")
            product_form(product, "review", allow_hide=False)


def render_manage():
    if not require_admin(): return
    products, _, _, _, _ = load_admin_data()
    items = [p for p in products if p.get("review_status") in {"approved", "hidden"}]
    st.subheader("상품 관리")
    st.caption("승인·숨김 상품을 검색해 이미지, 상품 정보와 공개 상태를 수정합니다.")
    c1, c2 = st.columns([1.7, 1])
    keyword = c1.text_input("관리 상품 검색", placeholder="상품명·브랜드·모델 검색", label_visibility="collapsed", key="manage_search")
    status = c2.selectbox("관리 상태", ["전체", "공개", "숨김"], label_visibility="collapsed", key="manage_status")
    needle = keyword.strip().lower()
    filtered = []
    for product in items:
        if status == "공개" and not product.get("is_visible"): continue
        if status == "숨김" and product.get("is_visible"): continue
        text = " ".join(str(product.get(k) or "") for k in ("canonical_name","brand","model","category")).lower()
        if needle and needle not in text: continue
        filtered.append(product)
    st.caption(f"검색 결과 {len(filtered)}개 · 한 화면 최대 20개")
    if not filtered: st.info("조건에 맞는 상품이 없습니다."); return
    for product in filtered[:20]:
        with st.container(border=True):
            title, status_col = st.columns([4,1])
            title.markdown(f"### {safe(product.get('canonical_name'))}")
            status_col.caption("공개" if product.get("is_visible") else "숨김")
            preview, editor = st.columns([1,2])
            with preview: render_product_visual(product)
            with editor: product_form(product, "manage", allow_hide=True)


try:
    if st.session_state.page == "home": render_home()
    elif st.session_state.page == "dashboard": render_dashboard()
    elif st.session_state.page == "review": render_review()
    else: render_manage()
except Exception as exc:
    st.error(str(exc))

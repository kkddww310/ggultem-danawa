import html
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


@st.cache_data(ttl=300, show_spinner=False)
def load_catalog():
    products = api_get(
        "products",
        "product_id,canonical_name,normalized_name,brand,model,category,search_keyword,created_at",
        {"order": "created_at.desc", "limit": "1000"},
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
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-title">🛍️ 꿀템 다나와</div>', unsafe_allow_html=True)

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
<div class="notice"><b>광고 안내</b><br>향후 쿠팡 파트너스 링크가 포함될 수 있으며, 이에 따른 일정액의 수수료를 제공받을 수 있습니다. 구매 가격에는 영향을 주지 않습니다.</div>
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

st.caption(f"상품 {len(filtered)}개 · 최근 5분 캐시")

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

        search_name = item.get("search_keyword") or item.get("canonical_name")
        encoded = quote(search_name)
        b1, b2 = st.columns(2)
        b1.link_button(
            "네이버 가격 비교",
            f"https://search.shopping.naver.com/search/all?query={encoded}&sort=price_asc",
            type="primary",
            use_container_width=True,
        )
        b2.link_button(
            "쿠팡 가격 확인",
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

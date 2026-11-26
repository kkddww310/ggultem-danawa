import streamlit as st
import streamlit.components.v1 as components

from ui.admin import render_dashboard, render_manage, render_review
from ui.common import (
    SUPABASE_KEY,
    SUPABASE_URL,
    build_product_visual_html,
    get_page_numbers,
    get_representative_rec,
    handle_click_redirect,
    inject_styles,
    load_public_catalog,
    log_event,
    recommendation_summary,
    render_footer,
    safe,
    score_product_search,
)
from ui.detail import render_product_detail

st.set_page_config(page_title="에디션 픽 EDITION PICK · 검증된 리뷰 큐레이션", page_icon="✦", layout="wide")

if str(st.query_params.get("health", "")).strip() == "1":
    st.markdown("OK")
    st.stop()

handle_click_redirect()
inject_styles()

st.markdown(
    """
<style>
/* 상단 브랜드 바 & 슬림 히어로 배너 */
.top-nav {
  padding: 8px 2px 10px !important;
  margin-bottom: 2px !important;
}
.hero-banner {
  background: linear-gradient(135deg, #151A23 0%, #222B3B 100%) !important;
  border: 0 !important;
  border-radius: 16px !important;
  padding: 15px 20px !important;
  margin-bottom: 10px !important;
  box-shadow: 0 8px 22px rgba(21, 26, 35, 0.10) !important;
  display: flex !important;
  flex-wrap: wrap !important;
  align-items: center !important;
  justify-content: space-between !important;
  gap: 10px !important;
}
.hero-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hero-kicker {
  display: inline-block !important;
  width: fit-content !important;
  font-size: 10.5px !important;
  font-weight: 800 !important;
  letter-spacing: 0.04em !important;
  color: #7DB4FF !important;
  background: rgba(125, 180, 255, 0.14) !important;
  padding: 3px 9px !important;
  border-radius: 999px !important;
  margin: 0 !important;
}
.hero-headline {
  font-size: 19px !important;
  font-weight: 850 !important;
  color: #FFFFFF !important;
  letter-spacing: -0.025em !important;
  line-height: 1.3 !important;
  margin: 0 !important;
}
.hero-headline b {
  color: #7DB4FF !important;
}
.hero-stats {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 6px !important;
  margin: 0 !important;
}
.hero-banner .stat-pill {
  background: rgba(255, 255, 255, 0.09) !important;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  color: #D5DCE6 !important;
  font-size: 11.5px !important;
  padding: 4px 10px !important;
}
.hero-banner .stat-pill strong {
  color: #FFFFFF !important;
}

/* 검색창 & 원클릭 카테고리 칩 바 */
div[data-testid="stTextInput"] {
  margin-bottom: -4px !important;
}
div[data-testid="stTextInput"] input {
  border-radius: 12px !important;
  min-height: 42px !important;
  font-size: 13.5px !important;
}
.st-key-chip_bar {
  margin: 4px 0 8px !important;
}
.st-key-chip_bar [data-testid="stHorizontalBlock"] {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 6px !important;
  align-items: center !important;
  width: 100% !important;
}
.st-key-chip_bar [data-testid="stColumn"],
.st-key-chip_bar [data-testid="column"] {
  flex: 0 0 auto !important;
  width: auto !important;
  min-width: 0 !important;
  max-width: none !important;
  padding: 0 !important;
}
.st-key-chip_bar .stButton > button {
  min-height: 33px !important;
  padding: 0 13px !important;
  border-radius: 999px !important;
  font-size: 12.5px !important;
  font-weight: 750 !important;
  letter-spacing: -0.02em !important;
  white-space: nowrap !important;
}
.st-key-chip_bar .stButton > button[kind="primary"] {
  background: #191F28 !important;
  border: 1px solid #191F28 !important;
  color: #FFFFFF !important;
}
.st-key-chip_bar .stButton > button[kind="secondary"] {
  background: #FFFFFF !important;
  border: 1px solid #E2E6EC !important;
  color: #4E5968 !important;
}
.st-key-chip_bar .stButton > button[kind="secondary"]:hover {
  border-color: #191F28 !important;
  color: #191F28 !important;
}

/* 아카이브 헤더 + 정렬 탭 바 */
.st-key-archive_head_bar {
  margin: 12px 0 6px !important;
}
.st-key-archive_head_bar [data-testid="stHorizontalBlock"] {
  align-items: center !important;
}
.st-key-sort_bar [data-testid="stHorizontalBlock"] {
  display: flex !important;
  flex-wrap: wrap !important;
  justify-content: flex-end !important;
  gap: 5px !important;
}
.st-key-sort_bar [data-testid="stColumn"],
.st-key-sort_bar [data-testid="column"] {
  flex: 0 0 auto !important;
  width: auto !important;
  min-width: 0 !important;
  max-width: none !important;
  padding: 0 !important;
}
.st-key-sort_bar .stButton > button {
  min-height: 29px !important;
  padding: 0 10px !important;
  border-radius: 8px !important;
  font-size: 11.5px !important;
  font-weight: 750 !important;
  letter-spacing: -0.02em !important;
  white-space: nowrap !important;
}
.st-key-sort_bar .stButton > button[kind="primary"] {
  background: #191F28 !important;
  border: 1px solid #191F28 !important;
  color: #FFFFFF !important;
}
.st-key-sort_bar .stButton > button[kind="secondary"] {
  background: #F4F6F9 !important;
  border: 1px solid transparent !important;
  color: #6B7684 !important;
}
.st-key-sort_bar .stButton > button[kind="secondary"]:hover {
  background: #EAEFF5 !important;
  color: #191F28 !important;
}

/* 섹션 헤더 */
.curated-sec-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 10px;
  margin: 14px 2px 9px;
}
.curated-sec-title {
  font-size: 17px;
  font-weight: 900;
  color: #191F28;
  letter-spacing: -0.025em;
  line-height: 1.25;
}
.curated-sec-sub {
  font-size: 12px;
  font-weight: 600;
  color: #8B95A1;
}

/* 5열 TOP 5 그리드 & 4열 중복 검증템 그리드 */
.top5-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.grid-4 {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 13px;
  margin-bottom: 16px;
}
.rail-card {
  background: #FFFFFF;
  border: 1px solid #E6E9EF;
  border-radius: 15px;
  padding: 10px 10px 12px;
  box-shadow: 0 3px 12px rgba(15, 23, 42, 0.035);
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.rail-card:hover {
  transform: translateY(-3px);
  border-color: #C7D2E0;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.08);
}

/* 썸네일 스테이지 + 상단 배지 가독성 보호 그라데이션 */
.thumb-stage {
  position: relative;
  width: 100%;
  border-radius: 11px;
  overflow: hidden;
}
.thumb-stage::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 44px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.36) 0%, rgba(15, 23, 42, 0) 100%);
  pointer-events: none;
  z-index: 2;
}
.thumb-stage .video-thumbnail-wrap,
.thumb-stage .product-placeholder {
  margin: 0 !important;
  border-radius: 11px !important;
}
.thumb-stage a[href*="youtu"],
.thumb-stage .thumb-play-badge,
.thumb-stage .video-play-chip {
  display: none !important;
}
.rank-flag {
  position: absolute;
  top: 7px;
  left: 7px;
  z-index: 3;
  min-width: 24px;
  height: 24px;
  padding: 0 6px;
  border-radius: 7px;
  background: rgba(25, 31, 40, 0.92);
  color: #FFFFFF;
  font-size: 12px;
  font-weight: 900;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
  pointer-events: none;
}
.rank-flag.top1 {
  background: #3182F6;
}
.trust-flag {
  position: absolute;
  top: 7px;
  right: 7px;
  z-index: 3;
  padding: 3px 7px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: -0.02em;
  pointer-events: none;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.18);
}
.trust-self {
  background: #146C43;
  color: #FFFFFF;
}
.trust-clean {
  background: rgba(25, 31, 40, 0.88);
  color: #FFFFFF;
}
.trust-prov {
  background: #FFF7E0;
  color: #7A4F00;
}

/* 카드 본문 타이포그래피 */
.store-card-link {
  display: flex;
  flex-direction: column;
  flex: 1;
  text-decoration: none !important;
  color: inherit !important;
  padding-top: 8px;
}
.store-brand-line {
  font-size: 11px;
  font-weight: 750;
  color: #8B95A1;
  margin-bottom: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.store-title {
  font-size: 14.5px;
  font-weight: 850;
  color: #191F28;
  line-height: 1.34;
  letter-spacing: -0.02em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 39px;
  margin-bottom: 7px;
}
.store-quote {
  background: #F6F8FB;
  border-left: 2.5px solid #3182F6;
  border-radius: 0 8px 8px 0;
  padding: 7px 9px;
  margin-bottom: 8px;
}
.store-quote-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  padding: 0 !important;
  margin: 0 !important;
  font-size: 11.5px;
  font-weight: 650;
  color: #333D4B;
  line-height: 1.42;
  min-height: calc(11.5px * 1.42 * 2);
  word-break: keep-all;
}
.store-foot {
  margin-top: auto;
  padding-top: 6px;
  border-top: 1px solid #F1F3F6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  font-weight: 700;
  color: #6B7684;
}
.store-channel {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.store-cta {
  color: #3182F6;
  font-weight: 800;
  white-space: nowrap;
  flex-shrink: 0;
}

/* 하단 전체 그리드 카드 */
.st-key-product_grid .product-card {
  background: #FFFFFF !important;
  border: 1px solid #E6E9EF !important;
  border-radius: 15px !important;
  padding: 11px 11px 13px !important;
  box-shadow: 0 3px 12px rgba(15, 23, 42, 0.03) !important;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease !important;
  display: flex !important;
  flex-direction: column !important;
  height: 100% !important;
}
.st-key-product_grid .product-card:hover {
  transform: translateY(-3px) !important;
  border-color: #C7D2E0 !important;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.08) !important;
}

@media (max-width: 1024px) {
  .top5-grid, .grid-4 {
    display: flex;
    overflow-x: auto;
    gap: 12px;
    padding-bottom: 8px;
    scroll-snap-type: x mandatory;
  }
  .top5-grid .rail-card, .grid-4 .rail-card {
    flex: 0 0 245px;
    width: 245px;
    scroll-snap-align: start;
  }
}
@media (max-width: 640px) {
  .hero-banner {
    padding: 14px 15px !important;
  }
  .hero-headline {
    font-size: 17px !important;
  }
  .store-title, .store-quote-text {
    min-height: 0;
  }
  .st-key-sort_bar [data-testid="stHorizontalBlock"] {
    justify-content: flex-start !important;
  }
}
</style>
""",
    unsafe_allow_html=True,
)

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Streamlit Secrets에 SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY를 등록하세요.")
    st.stop()

if "page" not in st.session_state:
    st.session_state.page = "home"
if "detail_pid" not in st.session_state:
    st.session_state.detail_pid = ""
if "selected_chip" not in st.session_state:
    st.session_state.selected_chip = "전체"
if "sort_mode" not in st.session_state:
    st.session_state.sort_mode = "추천순"

view_param = str(st.query_params.get("view", "")).strip()
pid_param = str(st.query_params.get("pid", "")).strip()
if view_param == "detail" and pid_param:
    st.session_state.page = "home"
    st.session_state.detail_pid = pid_param

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
    "  const enhancePage = () => {"
    "    doc.querySelectorAll('header, [data-testid=\"stHeader\"], [data-testid=\"stAppHeader\"], [data-testid=\"stDecoration\"]').forEach(el => {"
    "      if (el.style.display !== 'none') {"
    "        el.style.setProperty('display', 'none', 'important');"
    "        el.style.setProperty('border', 'none', 'important');"
    "        el.style.setProperty('box-shadow', 'none', 'important');"
    "      }"
    "    });"
    "  };"
    "  enhancePage();"
    "  if (!window.parent.__editionChromeObserver) {"
    "    window.parent.__editionChromeObserver = new MutationObserver(enhancePage);"
    "    window.parent.__editionChromeObserver.observe(doc.body, { childList: true, subtree: true });"
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
    '<a class="brand-wrap" href="?" target="_self">'
    '<span class="brand-logo">✦</span>'
    '<span class="brand-name">에디션 픽</span>'
    '<span class="brand-en">EDITION PICK</span>'
    '</a>'
    '<span class="top-sub">광고 없는 실사용 리뷰 큐레이션</span>'
    '</div>',
    unsafe_allow_html=True,
)

if st.session_state.get("show_admin_bar") or st.session_state.page != "home":
    nav = st.columns(4)
    for column, key, label in zip(nav, ["home", "dashboard", "review", "manage"], ["에디션 홈", "운영 통계", "상품 검수", "상품 관리"]):
        if column.button(label, type="primary" if st.session_state.page == key else "secondary", use_container_width=True):
            st.query_params.clear()
            st.session_state.detail_pid = ""
            st.session_state.page = key
            st.rerun()


def get_trust_overlay_badge(summary):
    counts = summary.get("purchase_counts") or {}
    buy_cnt = int(counts.get("직접 구매", 0))
    ad_cnt = int(counts.get("유료 광고", 0))
    prov_cnt = int(counts.get("제품 제공", 0))

    if buy_cnt >= 1:
        return f'<span class="trust-flag trust-self">내돈내산 {buy_cnt}</span>'
    if ad_cnt == 0 and prov_cnt >= 1:
        return f'<span class="trust-flag trust-prov">제품제공 {prov_cnt}</span>'
    if ad_cnt == 0:
        return '<span class="trust-flag trust-clean">광고 0%</span>'
    return ""


def get_hook_highlight(summary):
    pros = summary.get("pros") or []
    reasons = summary.get("reasons") or []
    raw_line = pros[0] if pros else (reasons[0] if reasons else "실사용 리뷰로 검증된 추천 아이템")
    cleaned = str(raw_line).strip().rstrip(".")
    return safe(cleaned)


def get_primary_video_id(product):
    rep = get_representative_rec(product)
    return str((rep or {}).get("video_id") or "")


def get_latest_published_at(product):
    dates = [
        str((r.get("video") or {}).get("published_at") or "")
        for r in (product.get("recommendations") or [])
    ]
    return max(dates) if dates else ""


def arrange_diverse_visuals(items, window=6):
    """연속된 2줄(6칸) 안에 같은 영상 썸네일이 겹치지 않도록 배치 순서 조정."""
    remaining = list(items)
    result = []
    recent_vids = []
    while remaining:
        picked_idx = 0
        for idx, prod in enumerate(remaining):
            vid = get_primary_video_id(prod)
            if not vid or vid not in recent_vids:
                picked_idx = idx
                break
        chosen = remaining.pop(picked_idx)
        result.append(chosen)
        c_vid = get_primary_video_id(chosen)
        if c_vid:
            recent_vids.append(c_vid)
            if len(recent_vids) > window:
                recent_vids.pop(0)
    return result


def pick_diverse_top_items(candidates, limit=5):
    """같은 유튜버나 같은 영상 썸네일이 상단 랭킹에 도배되지 않도록 다채널·다영상 우선 선발."""
    selected = []
    selected_pids = set()
    used_vids = set()
    used_channels = set()

    for product in candidates:
        pid = str(product.get("product_id") or "")
        rep = get_representative_rec(product, exclude_video_ids=used_vids)
        vid = str((rep or {}).get("video_id") or "")
        ch_key = str((rep or {}).get("channel_id") or ((rep or {}).get("channel") or {}).get("channel_name") or "")
        if vid and vid not in used_vids and (not ch_key or ch_key not in used_channels):
            selected.append(product)
            selected_pids.add(pid)
            used_vids.add(vid)
            if ch_key:
                used_channels.add(ch_key)
            if len(selected) >= limit:
                return selected

    for product in candidates:
        pid = str(product.get("product_id") or "")
        if pid in selected_pids:
            continue
        rep = get_representative_rec(product, exclude_video_ids=used_vids)
        vid = str((rep or {}).get("video_id") or "")
        if vid and vid not in used_vids:
            selected.append(product)
            selected_pids.add(pid)
            used_vids.add(vid)
            if len(selected) >= limit:
                return selected

    for product in candidates:
        pid = str(product.get("product_id") or "")
        if pid not in selected_pids:
            selected.append(product)
            selected_pids.add(pid)
            if len(selected) >= limit:
                break
    return selected


def build_store_card_inner_html(product, used_video_ids=None, rank=None):
    recs = product["recommendations"]
    raw_pid = str(product.get("product_id") or "").strip()
    pid = safe(raw_pid)
    detail_href = f"?view=detail&pid={pid}"
    representative = get_representative_rec(product, exclude_video_ids=used_video_ids)
    if used_video_ids is not None and not product.get("image_verified") and representative and representative.get("video_id"):
        used_video_ids.add(str(representative["video_id"]))

    channel_count = product.get("_channel_count") or len({r.get("channel_id") for r in recs if r.get("channel_id")})
    rep_channel = ((representative or {}).get("channel") or {}).get("channel_name") or (
        ((recs[0].get("channel") or {}).get("channel_name") if recs else "") or "유튜버 추천"
    )
    source_label = f"{rep_channel} 외 {channel_count - 1}명" if channel_count > 1 else rep_channel

    visual_html = build_product_visual_html(product, representative=representative, detail_href=detail_href, is_detail=False)
    summary = product.get("_summary") or recommendation_summary(recs)
    trust_html = get_trust_overlay_badge(summary)
    rank_html = ""
    if rank is not None:
        top_cls = " top1" if rank == 1 else ""
        rank_html = f'<span class="rank-flag{top_cls}">{rank}</span>'

    highlight_html = get_hook_highlight(summary)

    return (
        f'<div class="thumb-stage">{rank_html}{trust_html}{visual_html}</div>'
        f'<a class="store-card-link" href="{detail_href}" target="_self" aria-label="{safe(product.get("canonical_name"))} 상세 비교 보기">'
        f'<div class="store-brand-line">{safe(product.get("brand"))} · {safe(product.get("category") or "기타")}</div>'
        f'<div class="store-title">{safe(product.get("canonical_name"))}</div>'
        f'<div class="store-quote"><span class="store-quote-text">{highlight_html}</span></div>'
        '<div class="store-foot">'
        f'<span class="store-channel">▶ {safe(source_label)}</span>'
        '<span class="store-cta">비교하기 ›</span>'
        '</div>'
        '</a>'
    )


def render_product_card(product, used_video_ids=None):
    inner = build_store_card_inner_html(product, used_video_ids=used_video_ids, rank=None)
    st.markdown(f'<article class="product-card">{inner}</article>', unsafe_allow_html=True)


def render_curated_section(title, subtitle, items, show_rank=False, grid_cls="top5-grid"):
    if not items:
        return
    st.markdown(
        '<div class="curated-sec-head">'
        f'<div class="curated-sec-title">{safe(title)}</div>'
        f'<div class="curated-sec-sub">{safe(subtitle)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    used_vids = set()
    cards_html = []
    for idx, product in enumerate(items, start=1):
        inner = build_store_card_inner_html(product, used_video_ids=used_vids, rank=idx if show_rank else None)
        cards_html.append(f'<article class="rail-card">{inner}</article>')
    st.markdown(f'<div class="{grid_cls}">{"".join(cards_html)}</div>', unsafe_allow_html=True)


def render_home():
    products = load_public_catalog()
    channel_ids = {r.get("channel_id") for p in products for r in p["recommendations"] if r.get("channel_id")}
    video_ids = {r.get("video_id") for p in products for r in p["recommendations"] if r.get("video_id")}
    st.markdown(
        '<div class="hero-banner">'
        '<div class="hero-left">'
        '<div class="hero-kicker">NO-AD REVIEW ARCHIVE · 실사용 교차 검증</div>'
        f'<div class="hero-headline">유튜버들이 직접 검증한 추천 아이템 <b>{len(products):,}개</b></div>'
        '</div>'
        '<div class="hero-stats">'
        f'<span class="stat-pill">분석 채널 <strong>{len(channel_ids):,}개</strong></span>'
        f'<span class="stat-pill">근거 영상 <strong>{len(video_ids):,}개</strong></span>'
        '<span class="stat-pill">내돈내산 우선 랭킹</span>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    keyword = st.text_input(
        "검색",
        placeholder="궁금한 상품명, 브랜드, 유튜버를 검색해 보세요",
        label_visibility="collapsed",
    )

    existing_cats = sorted({p.get("category") or "기타" for p in products})
    preferred_order = ["IT·전자", "뷰티", "패션", "생활·살림", "주방", "운동·건강", "여행", "자동차", "육아", "반려동물", "기타"]
    ordered_cats = [c for c in preferred_order if c in existing_cats] + [c for c in existing_cats if c not in preferred_order]
    chip_options = ["전체", "🔥 내돈내산"] + ordered_cats

    current_chip = st.session_state.get("selected_chip", "전체")
    if current_chip not in chip_options:
        current_chip = "전체"
        st.session_state.selected_chip = "전체"

    with st.container(key="chip_bar"):
        chip_cols = st.columns(len(chip_options))
        for col, chip_label in zip(chip_cols, chip_options):
            is_selected = current_chip == chip_label
            if col.button(
                chip_label,
                key=f"chip_{chip_label}",
                type="primary" if is_selected else "secondary",
            ):
                if not is_selected:
                    st.session_state.selected_chip = chip_label
                    st.session_state.catalog_page = 1
                    st.rerun()

    sort_options = ["추천순", "내돈내산순", "중복추천순", "최신리뷰순"]
    current_sort = st.session_state.get("sort_mode", "추천순")
    if current_sort not in sort_options:
        current_sort = "추천순"
        st.session_state.sort_mode = "추천순"

    clean_kw = keyword.strip()
    filter_sig = (clean_kw, current_chip, current_sort)
    if st.session_state.get("last_filter_sig") != filter_sig:
        st.session_state.last_filter_sig = filter_sig
        st.session_state.catalog_page = 1

    if len(clean_kw) >= 2 and clean_kw != st.session_state.get("last_logged_keyword"):
        st.session_state.last_logged_keyword = clean_kw
        log_event("search", search_query=clean_kw)

    is_default_landing = (not clean_kw) and (current_chip == "전체") and (current_sort == "추천순")
    top_ids = set()

    if is_default_landing:
        self_buy_pool = [
            p for p in products
            if p.get("_has_self_buy") and int((p.get("_summary") or {}).get("purchase_counts", {}).get("유료 광고", 0)) == 0
        ]
        if len(self_buy_pool) < 5:
            self_buy_pool = [p for p in products if p.get("_has_self_buy")]
        top_self_buy = pick_diverse_top_items(self_buy_pool, limit=5)

        render_curated_section(
            "🔥 실시간 내돈내산 TOP 5",
            "광고 없이 서로 다른 유튜버가 직접 구매해 극찬한 1~5위",
            top_self_buy,
            show_rank=True,
            grid_cls="top5-grid",
        )
        top_ids = {str(p.get("product_id")) for p in top_self_buy}

        multi_verified_pool = [
            p for p in products
            if str(p.get("product_id")) not in top_ids
            and int(p.get("_channel_count") or 0) >= 2
            and int((p.get("_summary") or {}).get("purchase_counts", {}).get("유료 광고", 0)) == 0
        ]
        multi_verified = pick_diverse_top_items(multi_verified_pool, limit=4)
        if len(multi_verified) >= 4:
            render_curated_section(
                "✨ 광고 0% · 2명 이상 중복 검증템",
                "서로 다른 채널이 동시에 인정한 실패 없는 선택",
                multi_verified,
                show_rank=False,
                grid_cls="grid-4",
            )

    scored_items = []
    for product in products:
        if is_default_landing and str(product.get("product_id")) in top_ids:
            continue
        if current_chip == "🔥 내돈내산":
            if not product.get("_has_self_buy"):
                continue
        elif current_chip != "전체":
            if (product.get("category") or "기타") != current_chip:
                continue

        match_score = score_product_search(product, clean_kw)
        if clean_kw and match_score <= 0:
            continue
        scored_items.append((match_score, product))

    if current_sort == "내돈내산순":
        scored_items.sort(
            key=lambda item: (
                item[0] if clean_kw else 0,
                int((item[1].get("_summary") or {}).get("purchase_counts", {}).get("직접 구매", 0)),
                -int((item[1].get("_summary") or {}).get("purchase_counts", {}).get("유료 광고", 0)),
                item[1].get("_quality_score", 0),
            ),
            reverse=True,
        )
    elif current_sort == "중복추천순":
        scored_items.sort(
            key=lambda item: (
                item[0] if clean_kw else 0,
                int(item[1].get("_channel_count") or 0),
                len(item[1].get("recommendations") or []),
                item[1].get("_quality_score", 0),
            ),
            reverse=True,
        )
    elif current_sort == "최신리뷰순":
        scored_items.sort(
            key=lambda item: (
                item[0] if clean_kw else 0,
                get_latest_published_at(item[1]),
                item[1].get("_quality_score", 0),
            ),
            reverse=True,
        )
    elif clean_kw:
        scored_items.sort(
            key=lambda item: (
                item[0],
                item[1].get("_quality_score", 0),
                item[1].get("_channel_count", 0),
                len(item[1]["recommendations"]),
            ),
            reverse=True,
        )

    raw_shown = [item[1] for item in scored_items]
    shown = arrange_diverse_visuals(raw_shown, window=6) if current_sort == "추천순" and not clean_kw else raw_shown

    grid_title = "더 많은 검증 아이템" if is_default_landing else f"{current_chip} 추천 아이템"
    with st.container(key="archive_head_bar"):
        h_left, h_right = st.columns([1.4, 1.6])
        h_left.markdown(
            f'<div class="curated-sec-title" style="margin:2px 0;">{safe(grid_title)} <span style="color:#3182F6">{len(shown):,}</span></div>',
            unsafe_allow_html=True,
        )
        with h_right:
            with st.container(key="sort_bar"):
                s_cols = st.columns(len(sort_options))
                for s_col, s_label in zip(s_cols, sort_options):
                    is_s_curr = current_sort == s_label
                    if s_col.button(
                        s_label,
                        key=f"sort_{s_label}",
                        type="primary" if is_s_curr else "secondary",
                    ):
                        if not is_s_curr:
                            st.session_state.sort_mode = s_label
                            st.session_state.catalog_page = 1
                            st.rerun()

    page_size = 24
    pages = max(1, (len(shown) + page_size - 1) // page_size)
    page = min(max(int(st.session_state.get("catalog_page", 1)), 1), pages)
    page_products = shown[(page - 1) * page_size:page * page_size]

    used_video_ids = set()
    with st.container(key="product_grid"):
        for start in range(0, len(page_products), 3):
            cols = st.columns(3, gap="medium")
            for col, product in zip(cols, page_products[start:start + 3]):
                with col:
                    render_product_card(product, used_video_ids=used_video_ids)

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

    render_footer()

    _, admin_col = st.columns([5, 1])
    with admin_col:
        toggle_label = "관리자 닫기" if st.session_state.get("show_admin_bar") else "관리자"
        if st.button(toggle_label, key="toggle_admin_footer", use_container_width=True):
            st.session_state.show_admin_bar = not st.session_state.get("show_admin_bar", False)
            st.rerun()


try:
    active_detail_pid = str(st.session_state.get("detail_pid") or "").strip()
    if st.session_state.page == "home" and active_detail_pid:
        render_product_detail(active_detail_pid)
    elif st.session_state.page == "home":
        render_home()
    elif st.session_state.page == "dashboard":
        render_dashboard()
    elif st.session_state.page == "review":
        render_review()
    else:
        render_manage()
except Exception as exc:
    st.error(str(exc))

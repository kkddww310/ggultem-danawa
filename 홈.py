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

# 무신사·크림(KREAM) 스타일 큐레이션 스토어 오버라이드 CSS
st.markdown(
    """
<style>
/* 히어로 배너: 매거진·랭킹 스토어 톤으로 압축 */
.hero-banner {
  background: linear-gradient(135deg, #161B24 0%, #232C3D 100%) !important;
  border: 0 !important;
  border-radius: 20px !important;
  padding: 22px 24px !important;
  margin-bottom: 14px !important;
  box-shadow: 0 10px 28px rgba(22, 27, 36, 0.12) !important;
}
.hero-kicker {
  display: inline-block !important;
  font-size: 11px !important;
  font-weight: 800 !important;
  letter-spacing: 0.04em !important;
  color: #7DB4FF !important;
  background: rgba(125, 180, 255, 0.14) !important;
  padding: 4px 10px !important;
  border-radius: 999px !important;
  margin-bottom: 8px !important;
}
.hero-headline {
  font-size: 22px !important;
  font-weight: 850 !important;
  color: #FFFFFF !important;
  letter-spacing: -0.025em !important;
  line-height: 1.35 !important;
}
.hero-headline b {
  color: #7DB4FF !important;
}
.hero-stats {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 8px !important;
  margin-top: 12px !important;
}
.hero-banner .stat-pill {
  background: rgba(255, 255, 255, 0.09) !important;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  color: #D5DCE6 !important;
  font-size: 12px !important;
  padding: 5px 11px !important;
}
.hero-banner .stat-pill strong {
  color: #FFFFFF !important;
}

/* 가로 원클릭 카테고리 칩 바 */
.st-key-chip_bar {
  margin: 6px 0 14px !important;
}
.st-key-chip_bar [data-testid="stHorizontalBlock"] {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 7px !important;
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
  min-height: 36px !important;
  padding: 0 14px !important;
  border-radius: 999px !important;
  font-size: 13px !important;
  font-weight: 750 !important;
  letter-spacing: -0.02em !important;
  white-space: nowrap !important;
}
.st-key-chip_bar .stButton > button[kind="primary"] {
  background: #191F28 !important;
  border: 1px solid #191F28 !important;
  color: #FFFFFF !important;
  box-shadow: 0 4px 10px rgba(25, 31, 40, 0.16) !important;
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

/* 섹션 헤더 */
.curated-sec-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 10px;
  margin: 18px 2px 11px;
}
.curated-sec-title {
  font-size: 18px;
  font-weight: 900;
  color: #191F28;
  letter-spacing: -0.025em;
  line-height: 1.25;
}
.curated-sec-sub {
  font-size: 12.5px;
  font-weight: 600;
  color: #8B95A1;
}

/* 가로 스크롤 큐레이션 레일 (TOP 5 & 중복 검증템) */
.h-rail {
  display: flex;
  gap: 14px;
  overflow-x: auto;
  padding: 2px 2px 12px;
  margin-bottom: 10px;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
}
.h-rail::-webkit-scrollbar {
  height: 6px;
}
.h-rail::-webkit-scrollbar-thumb {
  background: #D6DCE5;
  border-radius: 999px;
}
.rail-card {
  flex: 0 0 272px;
  width: 272px;
  scroll-snap-align: start;
  background: #FFFFFF;
  border: 1px solid #E6E9EF;
  border-radius: 16px;
  padding: 11px 11px 14px;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
  display: flex;
  flex-direction: column;
}
.rail-card:hover {
  transform: translateY(-3px);
  border-color: #C7D2E0;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

/* 썸네일 스테이지 + 순위 배지 + 단일 투명도 배지 */
.thumb-stage {
  position: relative;
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
}
.thumb-stage .video-thumbnail-wrap,
.thumb-stage .product-placeholder {
  margin: 0 !important;
  border-radius: 12px !important;
}
/* 썸네일 우측 하단 '영상 보기' 오버레이 숨김으로 시선 분산 제거 */
.thumb-stage a[href*="youtu"],
.thumb-stage .thumb-play-badge,
.thumb-stage .video-play-chip {
  display: none !important;
}
.rank-flag {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 3;
  min-width: 26px;
  height: 26px;
  padding: 0 7px;
  border-radius: 8px;
  background: #191F28;
  color: #FFFFFF;
  font-size: 13px;
  font-weight: 900;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.25);
  pointer-events: none;
}
.rank-flag.top1 {
  background: #3182F6;
}
.trust-flag {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 3;
  padding: 3px 8px;
  border-radius: 7px;
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: -0.02em;
  backdrop-filter: blur(6px);
  pointer-events: none;
}
.trust-self {
  background: rgba(20, 108, 67, 0.92);
  color: #FFFFFF;
}
.trust-clean {
  background: rgba(25, 31, 40, 0.84);
  color: #FFFFFF;
}
.trust-prov {
  background: rgba(255, 247, 224, 0.95);
  color: #7A4F00;
  border: 1px solid rgba(224, 159, 0, 0.35);
}

/* 카드 본문 링크 & 타이포그래피 (다이어트 버전) */
.store-card-link {
  display: flex;
  flex-direction: column;
  flex: 1;
  text-decoration: none !important;
  color: inherit !important;
  padding-top: 9px;
}
.store-eyebrow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: #8B95A1;
  margin-bottom: 4px;
}
.store-eyebrow span:first-child {
  color: #4E5968;
  font-weight: 750;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.store-eyebrow span:last-child {
  white-space: nowrap;
  flex-shrink: 0;
}
.store-title {
  font-size: 15.5px;
  font-weight: 850;
  color: #191F28;
  line-height: 1.36;
  letter-spacing: -0.02em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 42px;
  margin-bottom: 8px;
}
.store-quote {
  background: #F6F8FB;
  border-left: 2.5px solid #191F28;
  border-radius: 0 8px 8px 0;
  padding: 7px 9px;
  font-size: 12px;
  font-weight: 600;
  color: #333D4B;
  line-height: 1.42;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 46px;
  word-break: keep-all;
  margin-bottom: 9px;
}
.store-foot {
  margin-top: auto;
  padding-top: 7px;
  border-top: 1px solid #F1F3F6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11.5px;
  font-weight: 700;
  color: #6B7684;
}
.store-cta {
  color: #3182F6;
  font-weight: 800;
}

/* 그리드 카드 컨테이너 여백 & 호버 */
.st-key-product_grid .product-card {
  background: #FFFFFF !important;
  border: 1px solid #E6E9EF !important;
  border-radius: 16px !important;
  padding: 12px 12px 14px !important;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.035) !important;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease !important;
  display: flex !important;
  flex-direction: column !important;
  height: 100% !important;
}
.st-key-product_grid .product-card:hover {
  transform: translateY(-3px) !important;
  border-color: #C7D2E0 !important;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08) !important;
}

@media (max-width: 640px) {
  .hero-banner {
    padding: 16px 15px !important;
  }
  .hero-headline {
    font-size: 18px !important;
  }
  .rail-card {
    flex: 0 0 245px;
    width: 245px;
  }
  .store-title, .store-quote {
    min-height: 0;
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
    """카드 썸네일 우측 상단에 붙는 단일 핵심 신뢰 배지."""
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


def get_hook_quote(summary):
    """설명을 나열하지 않고 궁금증을 유발하는 유튜버 한 줄 코멘트 추출."""
    reasons = summary.get("reasons") or []
    pros = summary.get("pros") or []
    raw_line = reasons[0] if reasons else (pros[0] if pros else "실사용 리뷰로 검증된 추천 아이템")
    cleaned = str(raw_line).strip().rstrip(".")
    return f"“{safe(cleaned)}”"


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

    quote_html = get_hook_quote(summary)

    return (
        f'<div class="thumb-stage">{rank_html}{trust_html}{visual_html}</div>'
        f'<a class="store-card-link" href="{detail_href}" target="_self" aria-label="{safe(product.get("canonical_name"))} 상세 비교 보기">'
        '<div class="store-eyebrow">'
        f'<span>▶ {safe(source_label)}</span>'
        f'<span>{safe(product.get("brand"))} · {safe(product.get("category") or "기타")}</span>'
        '</div>'
        f'<div class="store-title">{safe(product.get("canonical_name"))}</div>'
        f'<div class="store-quote">{quote_html}</div>'
        '<div class="store-foot">'
        f'<span>유튜버 {channel_count}명 · 영상 {len(recs)}개</span>'
        '<span class="store-cta">장단점·최저가 ›</span>'
        '</div>'
        '</a>'
    )


def render_product_card(product, used_video_ids=None):
    inner = build_store_card_inner_html(product, used_video_ids=used_video_ids, rank=None)
    st.markdown(f'<article class="product-card">{inner}</article>', unsafe_allow_html=True)


def render_horizontal_rail(title, subtitle, items, show_rank=False):
    if not items:
        return
    st.markdown(
        '<div class="curated-sec-head">'
        f'<div class="curated-sec-title">{safe(title)}</div>'
        f'<div class="curated-sec-sub">{safe(subtitle)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    cards_html = []
    for idx, product in enumerate(items, start=1):
        inner = build_store_card_inner_html(product, used_video_ids=None, rank=idx if show_rank else None)
        cards_html.append(f'<article class="rail-card">{inner}</article>')
    st.markdown(f'<div class="h-rail">{"".join(cards_html)}</div>', unsafe_allow_html=True)


def render_home():
    products = load_public_catalog()
    channel_ids = {r.get("channel_id") for p in products for r in p["recommendations"] if r.get("channel_id")}
    video_ids = {r.get("video_id") for p in products for r in p["recommendations"] if r.get("video_id")}
    st.markdown(
        '<div class="hero-banner">'
        '<div class="hero-kicker">NO-AD REVIEW ARCHIVE · 실사용 교차 검증</div>'
        f'<div class="hero-headline">유튜버들이 직접 검증한 추천 아이템 <b>{len(products):,}개</b></div>'
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

    # 원클릭 가로 카테고리 칩 바
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

    clean_kw = keyword.strip()
    filter_sig = (clean_kw, current_chip)
    if st.session_state.get("last_filter_sig") != filter_sig:
        st.session_state.last_filter_sig = filter_sig
        st.session_state.catalog_page = 1

    if len(clean_kw) >= 2 and clean_kw != st.session_state.get("last_logged_keyword"):
        st.session_state.last_logged_keyword = clean_kw
        log_event("search", search_query=clean_kw)

    scored_items = []
    for product in products:
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

    if clean_kw:
        scored_items.sort(
            key=lambda item: (
                item[0],
                item[1].get("_quality_score", 0),
                item[1].get("_channel_count", 0),
                len(item[1]["recommendations"]),
            ),
            reverse=True,
        )

    shown = [item[1] for item in scored_items]

    page_size = 24
    pages = max(1, (len(shown) + page_size - 1) // page_size)
    page = min(max(int(st.session_state.get("catalog_page", 1)), 1), pages)

    # 기본 홈 첫 페이지에서만 탐색형 가로 큐레이션 섹션 노출
    is_default_landing = (not clean_kw) and (current_chip == "전체") and (page == 1)
    if is_default_landing:
        top_self_buy = [
            p for p in products
            if p.get("_has_self_buy") and int((p.get("_summary") or {}).get("purchase_counts", {}).get("유료 광고", 0)) == 0
        ][:5]
        if len(top_self_buy) < 5:
            top_self_buy = [p for p in products if p.get("_has_self_buy")][:5]
        render_horizontal_rail(
            "🔥 실시간 내돈내산 TOP 5",
            "광고 없이 유튜버가 직접 구매해 극찬한 1~5위",
            top_self_buy,
            show_rank=True,
        )

        top_ids = {str(p.get("product_id")) for p in top_self_buy}
        multi_verified = [
            p for p in products
            if str(p.get("product_id")) not in top_ids
            and int(p.get("_channel_count") or 0) >= 2
            and int((p.get("_summary") or {}).get("purchase_counts", {}).get("유료 광고", 0)) == 0
        ][:8]
        if len(multi_verified) >= 3:
            render_horizontal_rail(
                "✨ 광고 0% · 2명 이상 중복 검증템",
                "서로 다른 채널이 동시에 인정한 실패 없는 선택",
                multi_verified,
                show_rank=False,
            )

    grid_title = "전체 검증 아카이브" if is_default_landing else f"{current_chip} 추천 아이템"
    st.markdown(
        '<div class="curated-sec-head">'
        f'<div class="curated-sec-title">{safe(grid_title)} <span style="color:#3182F6">{len(shown):,}</span></div>'
        '<div class="curated-sec-sub">카드를 누르면 상세 장단점과 최저가가 열립니다</div>'
        '</div>',
        unsafe_allow_html=True,
    )

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

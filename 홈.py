import streamlit as st
import streamlit.components.v1 as components

from ui.admin import render_dashboard, render_manage, render_review
from ui.common import (
    SUPABASE_KEY,
    SUPABASE_URL,
    build_mall_buttons_html,
    build_product_visual_html,
    get_page_numbers,
    get_representative_rec,
    handle_click_redirect,
    inject_styles,
    load_public_catalog,
    log_event,
    recommendation_summary,
    render_footer,
    render_purchase_badges,
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

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Streamlit Secrets에 SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY를 등록하세요.")
    st.stop()

if "page" not in st.session_state:
    st.session_state.page = "home"
if "detail_pid" not in st.session_state:
    st.session_state.detail_pid = ""
if "only_self_buy" not in st.session_state:
    st.session_state.only_self_buy = False

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
    "    doc.querySelectorAll('[data-testid=\"stSelectbox\"] input').forEach(inp => {"
    "      if (inp.getAttribute('inputmode') !== 'none') {"
    "        inp.setAttribute('inputmode', 'none');"
    "        inp.setAttribute('readonly', 'readonly');"
    "        inp.setAttribute('autocomplete', 'off');"
    "        inp.style.setProperty('caret-color', 'transparent', 'important');"
    "        inp.style.setProperty('cursor', 'pointer', 'important');"
    "      }"
    "    });"
    "  };"
    "  enhancePage();"
    "  let rafScheduled = false;"
    "  const scheduleEnhance = () => {"
    "    if (rafScheduled) return;"
    "    rafScheduled = true;"
    "    window.parent.requestAnimationFrame(() => {"
    "      rafScheduled = false;"
    "      enhancePage();"
    "    });"
    "  };"
    "  if (!window.parent.__editionChromeObserver) {"
    "    window.parent.__editionChromeObserver = new MutationObserver(scheduleEnhance);"
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
    '<span class="top-sub">실사용 리뷰 데이터 기반 엄선 아카이브</span>'
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


def render_product_card(product, used_video_ids=None):
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
    purchase_html = render_purchase_badges(summary["purchase_counts"])

    pro_line = summary["pros"][0] if summary["pros"] else ""
    con_line = summary["cons"][0] if summary["cons"] else ""
    fallback_reason = summary["reasons"][0] if summary["reasons"] else ""

    summary_blocks = []
    if pro_line:
        summary_blocks.append(
            f'<div class="summary-line summary-pro"><span class="sum-tag sum-tag-pro">장점</span><span class="summary-text">{safe(pro_line)}</span></div>'
        )
    if con_line:
        summary_blocks.append(
            f'<div class="summary-line summary-con"><span class="sum-tag sum-tag-con">체크</span><span class="summary-text">{safe(con_line)}</span></div>'
        )
    if not summary_blocks and fallback_reason:
        summary_blocks.append(
            f'<div class="summary-line summary-reason"><span class="sum-tag sum-tag-fit">추천</span><span class="summary-text">{safe(fallback_reason)}</span></div>'
        )
    summary_html = f'<div class="card-summary-wrap">{"".join(summary_blocks)}</div>' if summary_blocks else ""
    mall_buttons_html = build_mall_buttons_html(product)

    st.markdown(
        '<article class="product-card">'
        f'{visual_html}'
        f'<a class="card-body-link" href="{detail_href}" target="_self" aria-label="{safe(product.get("canonical_name"))} 상세 비교 보기">'
        '<div class="card-source-bar">'
        f'<span class="source-chip"><b>▶</b> {safe(source_label)}</span>'
        f'<span class="brand-eyebrow">{safe(product.get("brand"))} · {safe(product.get("category") or "기타")}</span>'
        '</div>'
        f'<div class="product-title">{safe(product.get("canonical_name"))}</div>'
        '<div class="card-meta-row">'
        f'<span class="badge">유튜버 {channel_count}명</span>'
        f'<span class="badge">영상 {len(recs)}개</span>'
        f'{purchase_html}'
        '</div>'
        f'{summary_html}'
        '</a>'
        f'{mall_buttons_html}'
        '</article>',
        unsafe_allow_html=True,
    )


def render_home():
    products = load_public_catalog()
    channel_ids = {r.get("channel_id") for p in products for r in p["recommendations"] if r.get("channel_id")}
    video_ids = {r.get("video_id") for p in products for r in p["recommendations"] if r.get("video_id")}
    st.markdown(
        '<div class="hero-banner">'
        '<div class="hero-kicker">실제 리뷰 영상 데이터 기반 엄선 큐레이션</div>'
        f'<div class="hero-headline">에디션 픽이 검증한 추천 아이템 <b>{len(products):,}개</b></div>'
        '<div class="hero-stats">'
        f'<span class="stat-pill">분석 채널 <strong>{len(channel_ids):,}개</strong></span>'
        f'<span class="stat-pill">근거 영상 <strong>{len(video_ids):,}개</strong></span>'
        '<span class="stat-pill"><i class="live-dot"></i> 매일 자동 업데이트</span>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    with st.container(key="filter_bar"):
        a, b = st.columns([3, 1], gap="small")
        keyword = a.text_input("검색", placeholder="상품명, 브랜드, 유튜버 검색", label_visibility="collapsed")
        categories = sorted({p.get("category") or "기타" for p in products})
        category = b.selectbox("카테고리", ["전체"] + categories, label_visibility="collapsed")

    only_self_buy = bool(st.session_state.get("only_self_buy", False))
    clean_kw = keyword.strip()
    filter_sig = (clean_kw, category, only_self_buy)
    if st.session_state.get("last_filter_sig") != filter_sig:
        st.session_state.last_filter_sig = filter_sig
        st.session_state.catalog_page = 1

    if len(clean_kw) >= 2 and clean_kw != st.session_state.get("last_logged_keyword"):
        st.session_state.last_logged_keyword = clean_kw
        log_event("search", search_query=clean_kw)

    scored_items = []
    for product in products:
        if category != "전체" and (product.get("category") or "기타") != category:
            continue
        if only_self_buy and not product.get("_has_self_buy"):
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

    with st.container(key="result_bar"):
        r_left, r_right = st.columns([1.4, 1])
        r_left.markdown(
            f'<div class="result-count-text">검색 결과 <b>{len(shown):,}</b>개</div>',
            unsafe_allow_html=True,
        )
        with r_right:
            if st.button(
                "내돈내산",
                key="self_buy_toggle",
                type="primary" if only_self_buy else "secondary",
            ):
                st.session_state.only_self_buy = not only_self_buy
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

import math

import streamlit as st
import streamlit.components.v1 as components

from ui.admin import render_admin_page
from ui.common import (
    AFFILIATE_DISCLOSURE,
    CATEGORIES,
    SUPABASE_KEY,
    SUPABASE_URL,
    get_page_numbers,
    get_representative_rec,
    handle_click_redirect,
    inject_styles,
    load_public_data,
    log_event,
    open_product_detail,
    recommendation_summary,
    render_footer,
    render_mall_buttons,
    render_product_visual,
    render_purchase_badges,
    safe,
    score_product_search,
)
from ui.detail import render_product_detail

st.set_page_config(
    page_title="에디션 픽 EDITION PICK · 유튜버 추천템 최저가 비교",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

handle_click_redirect()
inject_styles()

if "page" not in st.session_state:
    st.session_state.page = "home"
if "detail_pid" not in st.session_state:
    st.session_state.detail_pid = ""
if "home_page" not in st.session_state:
    st.session_state.home_page = 1

qp_page = str(st.query_params.get("page", "")).strip()
qp_view = str(st.query_params.get("view", "")).strip()
qp_pid = str(st.query_params.get("pid", "")).strip()

if qp_page == "admin":
    st.session_state.page = "admin"
    st.session_state.detail_pid = ""
elif qp_view == "detail" and qp_pid:
    st.session_state.page = "home"
    st.session_state.detail_pid = qp_pid

if st.session_state.get("scroll_to_top"):
    st.session_state.scroll_to_top = False
    components.v1.html("<script>window.parent.scrollTo(0, 0);</script>", height=0)


def render_top_header():
    st.markdown(
        '<div class="top-nav">'
        '<a class="brand-wrap" href="?" target="_self">'
        '<span class="brand-logo">E</span>'
        '<span class="brand-name">에디션 픽</span>'
        '<span class="brand-en">EDITION PICK</span>'
        '</a>'
        '<span class="top-sub">유튜버 실사용 추천템 · 다나와형 최저가 비교</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_home():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Streamlit Secrets에 `SUPABASE_URL` 및 `SUPABASE_SERVICE_ROLE_KEY`가 설정되어 있지 않습니다.")
        return

    products = load_public_data()

    all_channels = {
        r.get("channel_id")
        for p in products
        for r in (p.get("recommendations") or [])
        if r.get("channel_id")
    }
    all_videos = {
        r.get("video_id")
        for p in products
        for r in (p.get("recommendations") or [])
        if r.get("video_id")
    }

    st.markdown(
        '<div class="hero-banner">'
        '<div class="hero-kicker">YOUTUBE CURATED SHOPPING COMPARISON</div>'
        '<div class="hero-headline">유튜버들이 직접 쓰고 추천한 <b>진짜 인생템</b>만 모았습니다</div>'
        '<div class="hero-stats">'
        f'<span class="stat-pill">검증 추천템 <strong>{len(products):,}개</strong></span>'
        f'<span class="stat-pill">분석 유튜버 <strong>{len(all_channels):,}명</strong></span>'
        f'<span class="stat-pill">근거 리뷰 영상 <strong>{len(all_videos):,}편</strong></span>'
        '</div>'
        '</div>'
        f'<div class="top-disclosure">{safe(AFFILIATE_DISCLOSURE)}</div>',
        unsafe_allow_html=True,
    )

    with st.container(key="filter_bar"):
        f_col1, f_col2, f_col3 = st.columns([2.2, 1, 1], gap="small")
        with f_col1:
            search_input = st.text_input(
                "상품 검색",
                placeholder="상품명, 브랜드, 유튜버, 키워드 검색 (예: 로지텍, 선크림, 가방...)",
                label_visibility="collapsed",
                key="home_search_input",
            )
        with f_col2:
            selected_cat = st.selectbox(
                "카테고리",
                ["전체"] + CATEGORIES,
                label_visibility="collapsed",
                key="home_cat_select",
            )
        with f_col3:
            sort_option = st.selectbox(
                "정렬",
                ["추천 유튜버순", "근거 영상순", "내돈내산 우선", "최신 등록순"],
                label_visibility="collapsed",
                key="home_sort_select",
            )

    q_clean = search_input.strip()
    filter_sig = f"{q_clean}|{selected_cat}|{sort_option}"
    if st.session_state.get("last_filter_sig") != filter_sig:
        st.session_state.last_filter_sig = filter_sig
        st.session_state.home_page = 1

    if q_clean and st.session_state.get("last_logged_search") != q_clean:
        st.session_state.last_logged_search = q_clean
        log_event("search", search_query=q_clean)

    filtered = []
    for p in products:
        if selected_cat != "전체" and (p.get("category") or "기타") != selected_cat:
            continue
        score = score_product_search(p, q_clean) if q_clean else 1
        if score <= 0:
            continue
        filtered.append((score, p))

    if sort_option == "근거 영상순":
        filtered.sort(
            key=lambda item: (
                item[0] if q_clean else 0,
                len(item[1].get("recommendations") or []),
                len({r.get("channel_id") for r in (item[1].get("recommendations") or [])}),
            ),
            reverse=True,
        )
    elif sort_option == "내돈내산 우선":
        filtered.sort(
            key=lambda item: (
                item[0] if q_clean else 0,
                sum(
                    1 for r in (item[1].get("recommendations") or [])
                    if str(r.get("purchase_type") or "").strip() == "직접 구매"
                ),
                len({r.get("channel_id") for r in (item[1].get("recommendations") or [])}),
            ),
            reverse=True,
        )
    elif sort_option == "최신 등록순":
        filtered.sort(
            key=lambda item: (
                item[0] if q_clean else 0,
                str(item[1].get("created_at") or ""),
            ),
            reverse=True,
        )
    else:
        filtered.sort(
            key=lambda item: (
                item[0] if q_clean else 0,
                len({r.get("channel_id") for r in (item[1].get("recommendations") or [])}),
                len(item[1].get("recommendations") or []),
            ),
            reverse=True,
        )

    matched_products = [p for _, p in filtered]
    total_items = len(matched_products)
    page_size = 12
    total_pages = max(1, math.ceil(total_items / page_size))
    current_page = max(1, min(int(st.session_state.home_page), total_pages))
    st.session_state.home_page = current_page

    st.markdown(
        '<div class="result-bar">'
        f'<span>총 <b>{total_items:,}개</b>의 추천 상품</span>'
        f'<span>{current_page} / {total_pages} 페이지</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not matched_products:
        st.info("조건에 일치하는 추천 상품이 없습니다. 다른 검색어나 카테고리를 선택해 보세요.")
    else:
        start_idx = (current_page - 1) * page_size
        page_items = matched_products[start_idx:start_idx + page_size]

        with st.container(key="product_grid"):
            for row_start in range(0, len(page_items), 3):
                row_slice = page_items[row_start:row_start + 3]
                cols = st.columns(3, gap="medium")
                for col, product in zip(cols, row_slice):
                    pid = str(product.get("product_id"))
                    recs = product.get("recommendations") or []
                    representative = get_representative_rec(product)
                    ch_name = ((representative or {}).get("channel") or {}).get("channel_name") or "유튜버 추천"
                    channel_count = len({r.get("channel_id") for r in recs if r.get("channel_id")})
                    summary = recommendation_summary(recs)
                    purchase_html = render_purchase_badges(summary["purchase_counts"])

                    summary_lines = []
                    if summary["pros"]:
                        summary_lines.append(f'<div class="summary-line summary-pro">👍 {safe(summary["pros"][0])}</div>')
                    if summary["cons"]:
                        summary_lines.append(f'<div class="summary-line summary-con">👎 {safe(summary["cons"][0])}</div>')
                    if not summary_lines and summary["reasons"]:
                        summary_lines.append(f'<div class="summary-line summary-reason">💡 {safe(summary["reasons"][0])}</div>')

                    with col:
                        with st.container(border=True):
                            render_product_visual(product, representative=representative)
                            st.markdown(
                                '<div class="card-info-block">'
                                '<div class="card-source-bar">'
                                f'<span class="source-chip"><b>▶</b> {safe(ch_name)}</span>'
                                f'<span class="brand-eyebrow">{safe(product.get("brand"))}</span>'
                                '</div>'
                                f'<div class="product-title">{safe(product.get("canonical_name"))}</div>'
                                '<div class="card-meta-row">'
                                f'<span class="badge">유튜버 {channel_count}명 추천</span>'
                                f'<span class="badge">{safe(product.get("category") or "기타")}</span>'
                                f'{purchase_html}'
                                '</div>'
                                f'<div class="card-summary-wrap">{"".join(summary_lines)}</div>'
                                '</div>',
                                unsafe_allow_html=True,
                            )
                            render_mall_buttons(product)
                            if st.button("상세 비교 · 리뷰 보기 →", key=f"detail_btn_{pid}", use_container_width=True):
                                open_product_detail(pid)

        if total_pages > 1:
            page_nums = get_page_numbers(current_page, total_pages)
            nav_items = [("prev", "‹", max(1, current_page - 1))]
            for pn in page_nums:
                nav_items.append((f"p_{pn}", str(pn), pn))
            nav_items.append(("next", "›", min(total_pages, current_page + 1)))

            with st.container(key="pagination_bar"):
                p_cols = st.columns(len(nav_items))
                for col, (btn_key, label, target_page) in zip(p_cols, nav_items):
                    is_active = label.isdigit() and int(label) == current_page
                    disabled = (btn_key == "prev" and current_page <= 1) or (btn_key == "next" and current_page >= total_pages)
                    with col:
                        if st.button(
                            label,
                            key=f"pg_{btn_key}",
                            type="primary" if is_active else "secondary",
                            disabled=disabled,
                        ):
                            st.session_state.home_page = target_page
                            st.session_state.scroll_to_top = True
                            st.rerun()

    render_footer()

    _, admin_col, _ = st.columns([5, 1, 5])
    with admin_col:
        if st.button("관리자", key="footer_admin_btn", type="secondary", use_container_width=True):
            st.session_state.page = "admin"
            st.session_state.detail_pid = ""
            st.query_params["page"] = "admin"
            st.rerun()


render_top_header()

if st.session_state.page == "admin":
    render_admin_page()
elif st.session_state.detail_pid:
    render_product_detail(st.session_state.detail_pid)
else:
    render_home()

import streamlit as st

from ui.scoring import (
    AFFILIATE_DISCLOSURE,
    CATEGORY_VISUALS,
    detect_product_malls,
    get_representative_rec,
    safe,
)


def build_product_visual_html(product, representative=None, detail_href="", is_detail=False):
    """썸네일 HTML 생성 (detail_href가 있으면 썸네일 클릭 시 상세페이지 이동, 영상 배지는 유튜브 이동)."""
    if representative is None:
        representative = get_representative_rec(product)
    video_id = safe((representative or {}).get("video_id") or "")
    video_href = f"https://youtu.be/{video_id}" if video_id else ""
    badge_html = (
        f'<a class="thumb-video-badge" href="{video_href}" target="_blank" rel="noopener noreferrer" title="추천 유튜브 영상 바로 보기">▶ 영상 보기</a>'
        if video_href else ""
    )
    loading_attr = ' loading="eager"' if is_detail else ' loading="lazy" decoding="async"'
    title_safe = safe(product.get("canonical_name"))

    def wrap_link(inner_html):
        if detail_href:
            return f'<a class="card-thumb-link" href="{detail_href}" target="_self" aria-label="{title_safe} 상세 비교 보기">{inner_html}</a>'
        return inner_html

    image_url = str(product.get("image_url") or "").strip()
    if product.get("image_verified") and image_url.startswith(("https://", "http://")):
        img_tag = f'<img class="video-thumbnail"{loading_attr} src="{safe(image_url)}" alt="{title_safe}">'
        return f'<div class="video-thumbnail-wrap">{wrap_link(img_tag)}{badge_html}</div>'

    if video_id:
        if is_detail:
            hd_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
            fallback_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            img_tag = f'<img class="video-thumbnail"{loading_attr} src="{hd_url}" onerror="this.onerror=null;this.src=\'{fallback_url}\';" alt="추천 영상 썸네일">'
        else:
            img_tag = f'<img class="video-thumbnail"{loading_attr} src="https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" alt="추천 영상 썸네일">'
        return f'<div class="video-thumbnail-wrap">{wrap_link(img_tag)}{badge_html}</div>'

    category = product.get("category") or "기타"
    tag_en, background, color = CATEGORY_VISUALS.get(category, CATEGORY_VISUALS["기타"])
    placeholder = (
        f'<div class="product-placeholder" style="background:{background};color:{color}">'
        f'<span>{safe(tag_en)}</span><small>{safe(category)}</small></div>'
    )
    return wrap_link(placeholder)


def render_product_visual(product, representative=None, link_to_detail=False, is_detail=False):
    detail_href = f"?view=detail&pid={safe(product.get('product_id'))}" if link_to_detail else ""
    st.markdown(
        build_product_visual_html(product, representative=representative, detail_href=detail_href, is_detail=is_detail),
        unsafe_allow_html=True,
    )


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


def build_mall_buttons_html(product):
    pid = safe(product.get("product_id"))
    mall_buttons = detect_product_malls(product)
    if len(mall_buttons) == 1:
        grid_cls = "shop-btn-grid cols-1"
    elif len(mall_buttons) >= 3:
        grid_cls = "shop-btn-grid cols-3"
    else:
        grid_cls = "shop-btn-grid"
    btn_html = "".join(
        f'<a class="shop-btn {safe(btn["css"])}" href="?go={safe(btn["mall"])}&pid={pid}" target="_blank" rel="noopener noreferrer">{safe(btn["label"])}</a>'
        for btn in mall_buttons
    )
    return f'<div class="{grid_cls}">{btn_html}</div>'


def render_mall_buttons(product):
    st.markdown(build_mall_buttons_html(product), unsafe_allow_html=True)


def open_product_detail(product_id):
    pid_str = str(product_id).strip()
    st.session_state.page = "home"
    st.session_state.detail_pid = pid_str
    st.session_state.scroll_to_top = True
    st.query_params["view"] = "detail"
    st.query_params["pid"] = pid_str
    st.rerun()


def render_footer():
    st.markdown(
        '<div class="site-footer">'
        f'{safe(AFFILIATE_DISCLOSURE)}'
        '<span class="site-footer-sub">에디션 픽(EDITION PICK)은 유튜브 공개 리뷰 영상을 분석해 상품 정보를 제공하며, 실제 가격·재고 및 거래 조건은 각 쇼핑몰 페이지를 따릅니다.</span>'
        '</div>',
        unsafe_allow_html=True,
    )

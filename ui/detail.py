import re

import streamlit as st

from ui.common import (
    MALL_META,
    build_product_visual_html,
    clean_evidence_text,
    detect_product_malls,
    format_korean_count,
    get_related_products,
    is_meaningful_point,
    load_product_detail_recs,
    load_public_catalog,
    log_event,
    recommendation_summary,
    render_footer,
    render_purchase_badges,
    safe,
    sort_recommendations,
)


def render_danawa_price_table(product):
    """상세 페이지용 다나와 스타일 쇼핑몰별 최저가 비교 리스트."""
    pid = safe(product.get("product_id"))
    malls = detect_product_malls(product, include_all_default=True)
    rows_html = []
    for item in malls:
        mall_key = item["mall"]
        meta = MALL_META[mall_key]
        status_label = "공식 제휴 최저가 링크" if item["is_partner"] else "쇼핑몰 실시간 최저가 검색"
        partner_tag = '<span class="danawa-partner-badge">제휴연결</span>' if item["is_partner"] else ""
        btn_label = "최저가 보러가기 →" if item["is_partner"] else "가격 비교하기 →"
        rows_html.append(
            '<div class="danawa-row">'
            '<div class="danawa-mall-info">'
            f'<span class="mall-pill {safe(meta["badge_css"])}">{safe(meta["short"])}</span>'
            '<div class="danawa-desc-wrap">'
            f'<div class="danawa-tag-row"><span class="danawa-status-tag">{status_label}</span>{partner_tag}</div>'
            f'<div class="danawa-benefit">{safe(meta["benefit"])}</div>'
            '</div>'
            '</div>'
            f'<a class="danawa-go-btn" href="?go={safe(mall_key)}&pid={pid}" target="_blank" rel="noopener noreferrer">{btn_label}</a>'
            '</div>'
        )
    st.markdown(
        '<div class="danawa-box">'
        '<div class="danawa-head"><span>쇼핑몰별 최저가 비교</span><span>클릭 시 공식몰·검색 페이지 이동</span></div>'
        f'{"".join(rows_html)}'
        '</div>',
        unsafe_allow_html=True,
    )


def render_product_detail(pid):
    products = load_public_catalog()
    product = next((p for p in products if str(p.get("product_id")) == pid), None)

    if st.button("← 전체 목록으로", key="detail_back_btn", type="secondary"):
        st.session_state.detail_pid = ""
        st.query_params.clear()
        st.session_state.scroll_to_top = True
        st.rerun()

    if not product:
        st.warning("요청하신 상품 정보를 찾을 수 없거나 현재 비공개 상태입니다.")
        return

    if st.session_state.get("last_viewed_pid") != pid:
        st.session_state.last_viewed_pid = pid
        log_event("product_view", product_id=pid, product_name=product.get("canonical_name"))

    detail_recs = load_product_detail_recs(pid) or (product.get("recommendations") or [])
    recs = sort_recommendations(product, detail_recs)
    channel_count = len({r.get("channel_id") for r in recs if r.get("channel_id")})
    summary = recommendation_summary(recs)
    category = product.get("category") or "기타"

    st.markdown(
        f'<div class="detail-breadcrumb">에디션 픽 &gt; {safe(category)} &gt; {safe(product.get("brand"))}</div>',
        unsafe_allow_html=True,
    )

    purchase_html = render_purchase_badges(summary["purchase_counts"])
    model_text = str(product.get("model") or "").strip()
    brand_line = f"{product.get('brand')} · {category}" + (f" · {model_text}" if model_text else "")

    counts = summary["purchase_counts"]
    total_recs = max(1, len(recs))
    buy_cnt = int(counts.get("직접 구매", 0))
    prov_cnt = int(counts.get("제품 제공", 0))
    ad_cnt = int(counts.get("유료 광고", 0))
    unk_cnt = max(0, len(recs) - buy_cnt - prov_cnt - ad_cnt)
    buy_pct = round(buy_cnt / total_recs * 100)
    prov_pct = round(prov_cnt / total_recs * 100)
    ad_pct = round(ad_cnt / total_recs * 100)
    unk_pct = max(0, 100 - buy_pct - prov_pct - ad_pct)

    st.markdown(
        '<div class="detail-hero-card">'
        f'<div class="detail-brand-line">{safe(brand_line)}</div>'
        f'<div class="detail-title">{safe(product.get("canonical_name"))}</div>'
        '<div class="detail-badges">'
        f'<span class="badge">유튜버 {channel_count}명 추천</span>'
        f'<span class="badge">근거 영상 {len(recs)}개</span>'
        f'{purchase_html}'
        '</div>'
        '<div class="trust-box">'
        '<div class="trust-box-head"><span>리뷰 구매 방식 투명도 분석</span>'
        f'<span>내돈내산 비중 {buy_pct}%</span></div>'
        '<div class="trust-bar">'
        f'<div class="trust-seg-buy" style="width:{buy_pct}%"></div>'
        f'<div class="trust-seg-prov" style="width:{prov_pct}%"></div>'
        f'<div class="trust-seg-ad" style="width:{ad_pct}%"></div>'
        f'<div class="trust-seg-unk" style="width:{unk_pct}%"></div>'
        '</div>'
        '<div class="trust-legend">'
        f'<span>직접 구매(내돈내산) {buy_cnt}건</span>'
        f'<span>제품 제공 {prov_cnt}건</span>'
        f'<span>유료 광고 {ad_cnt}건</span>'
        f'<span>표기 미확인 {unk_cnt}건</span>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    render_danawa_price_table(product)
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    if summary["reasons"]:
        fit_html = "".join(
            f'<div class="recommend-fit-item">✦ {safe(reason)}</div>'
            for reason in summary["reasons"]
        )
        st.markdown(
            '<div class="detail-section">'
            '<div class="detail-section-title"><span>이런 분께 추천해요</span><span class="detail-section-sub">유튜버 선정 근거 요약</span></div>'
            f'<div class="recommend-fit-list">{fit_html}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    pros_list = summary["all_pros"]
    cons_list = summary["all_cons"]
    if pros_list or cons_list:
        pro_items_html = "".join(
            f'<div class="pc-item">• {safe(text)}'
            + (f'<span class="pc-count">{cnt}명 언급</span>' if cnt > 1 else "")
            + '</div>'
            for text, cnt in pros_list
        ) or '<div class="pc-item">수집된 장점 요약이 아직 없습니다.</div>'

        con_items_html = "".join(
            f'<div class="pc-item">• {safe(text)}'
            + (f'<span class="pc-count">{cnt}명 언급</span>' if cnt > 1 else "")
            + '</div>'
            for text, cnt in cons_list
        ) or '<div class="pc-item">영상에서 특별히 지적된 단점이 없습니다.</div>'

        st.markdown(
            '<div class="detail-section">'
            '<div class="detail-section-title"><span>핵심 장단점 한눈에 비교</span><span class="detail-section-sub">실사용 리뷰 기반 추출</span></div>'
            '<div class="pros-cons-grid">'
            f'<div class="pc-col pc-col-pro"><div class="pc-col-title">좋았던 점 (장점)</div>{pro_items_html}</div>'
            f'<div class="pc-col pc-col-con"><div class="pc-col-title">아쉬운 점 (체크포인트)</div>{con_items_html}</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    if recs:
        matrix_rows = []
        for rec in recs:
            ch_name = safe((rec.get("channel") or {}).get("channel_name") or "알 수 없는 채널")
            p_type = str(rec.get("purchase_type") or "확인되지 않음").strip()
            p_badge = render_purchase_badges({p_type: 1}) or '<span class="purchase-dot purchase-unknown"><i></i>표기 미확인</span>'
            r_txt = re.sub(r"\s+", " ", str(rec.get("reason") or "").strip())
            reason_cell = safe(r_txt) if is_meaningful_point(r_txt) else "-"
            p_points = [re.sub(r"\s+", " ", str(x).strip()) for x in (rec.get("pros") or []) if is_meaningful_point(x)]
            c_points = [re.sub(r"\s+", " ", str(x).strip()) for x in (rec.get("cons") or []) if is_meaningful_point(x)]
            point_lines = []
            if p_points:
                point_lines.append(f"장점 · {safe(' / '.join(p_points[:2]))}")
            if c_points:
                point_lines.append(f"체크 · {safe(' / '.join(c_points[:2]))}")
            points_cell = "<br>".join(point_lines) if point_lines else "-"
            matrix_rows.append(
                f"<tr><td><b>{ch_name}</b></td><td>{p_badge}</td><td>{reason_cell}</td><td>{points_cell}</td></tr>"
            )
        st.markdown(
            '<div class="detail-section">'
            '<div class="detail-section-title"><span>유튜버별 평가 한눈에 대조</span><span class="detail-section-sub">구매 방식 · 추천 포인트 · 장단점 비교</span></div>'
            '<div class="matrix-scroll">'
            '<table class="creator-matrix">'
            '<thead><tr><th>유튜버 채널</th><th>구매 방식</th><th>선정 이유 · 추천 대상</th><th>핵심 장단점 포인트</th></tr></thead>'
            f'<tbody>{"".join(matrix_rows)}</tbody>'
            '</table>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    review_cards_html = []
    for rec in recs:
        channel = rec.get("channel") or {}
        video = rec.get("video") or {}
        ch_name = safe(channel.get("channel_name") or "알 수 없는 채널")
        subs_txt = format_korean_count(channel.get("subscriber_count"))
        views_txt = format_korean_count(video.get("view_count"))
        stat_parts = []
        if subs_txt:
            stat_parts.append(f"구독자 {subs_txt}명")
        if views_txt:
            stat_parts.append(f"조회수 {views_txt}회")
        stat_html = f'<span class="creator-stat">{" · ".join(stat_parts)}</span>' if stat_parts else ""

        p_type = str(rec.get("purchase_type") or "확인되지 않음").strip()
        p_badge = render_purchase_badges({p_type: 1})

        v_id = safe(rec.get("video_id") or "")
        thumb_html = ""
        if v_id:
            hd_url = f"https://i.ytimg.com/vi/{v_id}/maxresdefault.jpg"
            fb_url = f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg"
            thumb_html = (
                '<div class="creator-thumb-box">'
                f'<a class="creator-thumb-link" href="https://youtu.be/{v_id}" target="_blank" rel="noopener noreferrer">'
                f'<img class="creator-thumb-img" src="{hd_url}" onerror="this.onerror=null;this.src=\'{fb_url}\';" alt="리뷰 영상 썸네일">'
                '</a>'
                '</div>'
            )

        v_btn = (
            f'<a class="creator-video-btn" href="https://youtu.be/{v_id}" target="_blank" rel="noopener noreferrer">▶ 원문 영상 ↗</a>'
            if v_id else ""
        )
        v_title = safe(video.get("title") or "영상 제목 정보 없음")
        reason_txt = re.sub(r"\s+", " ", str(rec.get("reason") or "").strip())
        reason_html = f'<div class="creator-reason">{safe(reason_txt)}</div>' if is_meaningful_point(reason_txt) else ""

        ev_txt = clean_evidence_text(rec.get("evidence"))
        ev_html = f'<div class="creator-evidence">“{safe(ev_txt)}”</div>' if ev_txt else ""

        tag_parts = []
        for p in (rec.get("pros") or []):
            pt = re.sub(r"\s+", " ", str(p).strip())
            if is_meaningful_point(pt):
                tag_parts.append(f'<span class="ctag-pro">장점 · {safe(pt)}</span>')
        for c in (rec.get("cons") or []):
            ct = re.sub(r"\s+", " ", str(c).strip())
            if is_meaningful_point(ct):
                tag_parts.append(f'<span class="ctag-con">체크 · {safe(ct)}</span>')
        tags_html = f'<div class="creator-tags">{"".join(tag_parts)}</div>' if tag_parts else ""

        review_cards_html.append(
            '<div class="creator-review-card">'
            f'{thumb_html}'
            '<div class="creator-review-body">'
            '<div class="creator-head">'
            f'<div class="creator-name-wrap"><span class="creator-name">{ch_name}</span>{stat_html}{p_badge}</div>'
            f'{v_btn}'
            '</div>'
            f'<div class="creator-video-title">{v_title}</div>'
            f'{reason_html}'
            f'{ev_html}'
            f'{tags_html}'
            '</div>'
            '</div>'
        )

    st.markdown(
        '<div class="detail-section">'
        f'<div class="detail-section-title"><span>유튜버 · 영상별 상세 리뷰 비교</span><span class="detail-section-sub">총 {len(recs)}개 영상</span></div>'
        f'{"".join(review_cards_html)}'
        '</div>',
        unsafe_allow_html=True,
    )

    related, related_label = get_related_products(product, products, limit=3)
    if related:
        st.markdown(f"#### 같은 {safe(related_label)} 인기 추천템")
        with st.container(key="related_grid"):
            r_cols = st.columns(3, gap="medium")
            for col, rp in zip(r_cols, related):
                raw_r_pid = str(rp.get("product_id") or "").strip()
                r_href = f"?view=detail&pid={safe(raw_r_pid)}"
                r_recs = rp.get("recommendations") or []
                r_ch_cnt = rp.get("_channel_count") or len({r.get("channel_id") for r in r_recs if r.get("channel_id")})
                r_visual = build_product_visual_html(rp, detail_href=r_href, is_detail=False)
                with col:
                    st.markdown(
                        '<article class="product-card">'
                        f'{r_visual}'
                        f'<a class="card-body-link" href="{r_href}" target="_self" aria-label="{safe(rp.get("canonical_name"))} 상세 비교 보기">'
                        f'<div class="related-brand">{safe(rp.get("brand"))} · 유튜버 {r_ch_cnt}명 추천</div>'
                        f'<div class="related-name">{safe(rp.get("canonical_name"))}</div>'
                        '</a>'
                        '</article>',
                        unsafe_allow_html=True,
                    )

    render_footer()

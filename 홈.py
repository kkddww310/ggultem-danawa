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
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
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
    labels = [
        ("직접 구매", "직접구매", "purchase-buy"),
        ("제품 제공", "제품제공", "purchase-provided"),
        ("유료 광고", "유료광고", "purchase-ad"),
    ]
    parts = []
    for key, label, css_class in labels:
        count = int(counts.get(key, 0))
        if count:
            parts.append(f'<span class="purchase-dot {css_class}"><i></i>{label} {count}</span>')
    return "".join(parts)


def render_product_card(product):
    recs = product["recommendations"]
    with st.container(border=True):
        render_product_visual(product)
        st.markdown(f'<div class="product-title">{safe(product.get("canonical_name"))}</div><div class="muted">{safe(product.get("brand"))} · {safe(product.get("category") or "기타")}</div>', unsafe_allow_html=True)
        channel_count = len({r.get("channel_id") for r in recs if r.get("channel_id")})
        confidence = max([float(r.get("confidence") or 0) for r in recs] or [0])
        summary = recommendation_summary(recs)
        purchase_html = render_purchase_badges(summary["purchase_counts"])
        st.markdown(
            '<div class="card-meta-row">'
            f'<span class="badge">유튜버 {channel_count}명</span>'
            f'<span class="badge">영상 {len(recs)}개</span>'
            f'<span class="badge">신뢰도 {confidence:.0%}</span>'
            f'{purchase_html}'
            '</div>',
            unsafe_allow_html=True,
        )

        pro_line = summary["pros"][0] if summary["pros"] else ""
        con_line = summary["cons"][0] if summary["cons"] else ""
        fallback_reason = next((str(r.get("reason") or "").strip() for r in recs if str(r.get("reason") or "").strip()), "")

        summary_blocks = []
        if pro_line:
            summary_blocks.append(f'<div class="summary-line summary-pro">👍 {safe(pro_line)}</div>')
        if con_line:
            summary_blocks.append(f'<div class="summary-line summary-con">👎 {safe(con_line)}</div>')
        if not summary_blocks and fallback_reason:
            summary_blocks.append(f'<div class="summary-line summary-reason">💡 {safe(fallback_reason)}</div>')
        if summary_blocks:
            st.markdown(f'<div class="card-summary-wrap">{"".join(summary_blocks)}</div>', unsafe_allow_html=True)

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
                st.markdown("**영상에서 추출한 통합 요약**")
                st.caption("아래 장단점은 연결된 추천 영상의 AI 추출 결과입니다.")
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

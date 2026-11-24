import re
from collections import Counter
from datetime import datetime, timezone

import streamlit as st

from ui.common import (
    CATEGORIES,
    IMAGE_SOURCES,
    IMAGE_SOURCE_LABELS,
    api_get_all,
    api_patch,
    count_by,
    parse_extra_partner_links,
    render_product_visual,
    safe,
    secret,
    serialize_extra_partner_links,
)


@st.cache_data(ttl=60, show_spinner=False)
def load_admin_data():
    products = api_get_all(
        "products",
        "product_id,canonical_name,brand,model,category,search_keyword,identity_score,review_status,is_visible,review_note,coupang_url,coupang_product_name,affiliate_verified,affiliate_note,image_url,image_source,image_verified,image_checked_at,image_note,created_at",
        {"order": "created_at.desc"},
        max_rows=5000,
    )
    videos = api_get_all(
        "videos",
        "video_id,channel_id,title,analysis_status,analysis_error,product_score,created_at,published_at",
        {"order": "created_at.desc"},
        max_rows=10000,
    )
    channels = api_get_all(
        "channels",
        "channel_id,channel_name,status,scan_priority,total_scanned_videos,product_candidate_videos,extracted_product_count,last_scanned_at,next_video_scan_at",
        max_rows=10000,
    )
    queries = api_get_all(
        "discovery_queries",
        "query_id,query_text,category,enabled,run_count,channels_found,active_channels_found,error_count,last_error,last_run_at,next_run_at",
        max_rows=2000,
    )
    recs = api_get_all(
        "recommendations",
        "recommendation_id,product_id,video_id,channel_id,confidence,created_at",
        max_rows=10000,
    )
    try:
        click_logs = api_get_all(
            "click_logs",
            "log_id,event_type,product_id,product_name,search_query,created_at",
            {"order": "created_at.desc"},
            max_rows=10000,
        )
        click_logs_ready = True
    except Exception:
        click_logs = []
        click_logs_ready = False

    return products, videos, channels, queries, recs, click_logs, click_logs_ready


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


def render_dashboard():
    if not require_admin():
        return
    products, videos, channels, queries, recs, click_logs, click_logs_ready = load_admin_data()
    ps, vs = count_by(products, "review_status"), count_by(videos, "analysis_status")
    active = sum(1 for c in channels if c.get("status") == "active")
    qerrors = sum(1 for q in queries if int(q.get("error_count") or 0) > 0 or q.get("last_error"))
    metrics = [
        ("전체 채널", len(channels), f"활성 {active}"),
        ("전체 영상", len(videos), f"AI 대기 {vs.get('queued',0)}"),
        ("공개 상품", ps.get("approved", 0), f"검수 {ps.get('pending',0)}"),
        ("검색어", len(queries), f"오류 {qerrors}"),
    ]
    for col, (label, value, sub) in zip(st.columns(4), metrics):
        col.markdown(
            f'<div class="metric"><div class="metric-label">{label}</div>'
            f'<div class="metric-value">{value:,}</div><div class="brand-eyebrow">{sub}</div></div>',
            unsafe_allow_html=True,
        )

    st.subheader("방문자 클릭 · 검색 통계")
    if not click_logs_ready:
        st.info("Supabase에 click_logs 테이블을 생성하면 상품별 쇼핑몰 클릭 순위와 방문자 검색어 통계가 자동으로 집계됩니다.")
    else:
        coupang_clicks = [x for x in click_logs if x.get("event_type") == "coupang_click"]
        naver_clicks = [x for x in click_logs if x.get("event_type") == "naver_click"]
        extra_clicks = [
            x for x in click_logs
            if x.get("event_type") in {"oliveyoung_click", "musinsa_click", "29cm_click", "zigzag_click", "ably_click"}
        ]
        search_logs = [x for x in click_logs if x.get("event_type") == "search" and x.get("search_query")]

        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        for col, (lbl, val) in zip(
            [c_m1, c_m2, c_m3, c_m4],
            [
                ("쿠팡 클릭", len(coupang_clicks)),
                ("네이버쇼핑 클릭", len(naver_clicks)),
                ("올리브영·패션몰 클릭", len(extra_clicks)),
                ("방문자 검색", len(search_logs)),
            ],
        ):
            col.markdown(
                f'<div class="metric"><div class="metric-label">{lbl}</div>'
                f'<div class="metric-value">{val:,}</div></div>',
                unsafe_allow_html=True,
            )

        product_lookup = {p["product_id"]: p for p in products}
        click_counts = Counter()
        coupang_by_item = Counter()
        naver_by_item = Counter()
        extra_by_item = Counter()
        label_by_item = {}
        for row in coupang_clicks + naver_clicks + extra_clicks:
            key = row.get("product_id") or row.get("product_name") or "unknown"
            click_counts[key] += 1
            ev_type = row.get("event_type")
            if ev_type == "coupang_click":
                coupang_by_item[key] += 1
            elif ev_type == "naver_click":
                naver_by_item[key] += 1
            else:
                extra_by_item[key] += 1
            p_info = product_lookup.get(row.get("product_id"))
            label_by_item[key] = (p_info or {}).get("canonical_name") or row.get("product_name") or "이름 없음"

        cl_left, cl_right = st.columns(2)
        with cl_left:
            with st.container(border=True):
                st.markdown("**클릭 많은 상품 TOP 15 (제휴 링크 우선 대상)**")
                if not click_counts:
                    st.caption("아직 기록된 상품 클릭이 없습니다.")
                for key, total in click_counts.most_common(15):
                    p_info = product_lookup.get(key) or {}
                    extra_links, _ = parse_extra_partner_links(p_info)
                    has_any_partner = bool(p_info.get("affiliate_verified") or any(extra_links.values()))
                    linked = "✅ 제휴연결" if has_any_partner else "미연결"
                    extra_str = f" · 제휴몰 {extra_by_item[key]}" if extra_by_item[key] else ""
                    st.markdown(
                        f'<div class="status-row">'
                        f'<span>{safe(label_by_item.get(key))} <small style="color:#8B95A1">({linked})</small></span>'
                        f'<b>쿠팡 {coupang_by_item[key]} · 네이버 {naver_by_item[key]}{extra_str}</b>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
        with cl_right:
            with st.container(border=True):
                st.markdown("**방문자 인기 검색어 TOP 15**")
                sq_counts = Counter(str(r.get("search_query")).strip() for r in search_logs)
                if not sq_counts:
                    st.caption("아직 기록된 검색어가 없습니다.")
                for q_text, cnt in sq_counts.most_common(15):
                    st.markdown(
                        f'<div class="status-row"><span>{safe(q_text)}</span><b>{cnt:,}회</b></div>',
                        unsafe_allow_html=True,
                    )

    st.subheader("영상 처리 현황")
    l, r = st.columns(2)
    with l:
        with st.container(border=True):
            for key in ["pending", "queued", "analyzed", "no_product", "rejected_generic", "skipped_non_product", "ai_error"]:
                st.markdown(f'<div class="status-row"><span>{key}</span><b>{vs.get(key,0):,}</b></div>', unsafe_allow_html=True)
    with r:
        with st.container(border=True):
            for key in ["approved", "pending", "hidden", "merged"]:
                st.markdown(f'<div class="status-row"><span>상품 {key}</span><b>{ps.get(key,0):,}</b></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="status-row"><span>추천 기록</span><b>{len(recs):,}</b></div>', unsafe_allow_html=True)
    st.subheader("최근 오류")
    errors = [v for v in videos if v.get("analysis_status") == "ai_error" and v.get("analysis_error")][:10]
    qrows = [q for q in queries if q.get("last_error")][:10]
    if not errors and not qrows:
        st.success("현재 기록된 최근 오류가 없습니다.")
    for row in errors:
        st.markdown(f'<div class="error-box"><b>영상:</b> {safe(row.get("title"))}<br>{safe(row.get("analysis_error"))}</div>', unsafe_allow_html=True)
    for row in qrows:
        st.markdown(f'<div class="error-box"><b>검색어:</b> {safe(row.get("query_text"))}<br>{safe(row.get("last_error"))}</div>', unsafe_allow_html=True)
    if st.button("통계 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


def product_form(product, prefix, allow_hide=False):
    pid = product["product_id"]
    extra_links, existing_memo = parse_extra_partner_links(product)
    with st.form(f"{prefix}_{pid}"):
        name = st.text_input("상품명", value=product.get("canonical_name") or "", key=f"{prefix}_name_{pid}")
        c1, c2 = st.columns(2)
        brand = c1.text_input("브랜드", value=product.get("brand") or "", key=f"{prefix}_brand_{pid}")
        model = c2.text_input("모델", value=product.get("model") or "", key=f"{prefix}_model_{pid}")
        current = product.get("category") if product.get("category") in CATEGORIES else "기타"
        category = st.selectbox("카테고리", CATEGORIES, index=CATEGORIES.index(current), key=f"{prefix}_cat_{pid}")
        keyword = st.text_input("검색 키워드", value=product.get("search_keyword") or product.get("canonical_name") or "", key=f"{prefix}_kw_{pid}")
        coupang_url = st.text_input(
            "쿠팡 파트너스 링크",
            value=product.get("coupang_url") or "",
            placeholder="https://link.coupang.com/...",
            key=f"{prefix}_cp_{pid}",
        )
        affiliate_verified = st.checkbox(
            "쿠팡 제휴 링크 확인 완료",
            value=bool(product.get("affiliate_verified")),
            key=f"{prefix}_aff_{pid}",
        )
        m1, m2 = st.columns(2)
        naver_url = m1.text_input(
            "네이버 쇼핑 커넥트 링크 (선택)",
            value=extra_links.get("naver") or "",
            placeholder="https://...",
            key=f"{prefix}_nv_{pid}",
        )
        oliveyoung_url = m2.text_input(
            "올리브영 쇼핑 큐레이터 링크 (입력 시 버튼 생성)",
            value=extra_links.get("oliveyoung") or "",
            placeholder="https://...",
            key=f"{prefix}_oy_{pid}",
        )
        p1, p2, p3, p4 = st.columns(4)
        musinsa_url = p1.text_input(
            "무신사 (선택)",
            value=extra_links.get("musinsa") or "",
            placeholder="https://...",
            key=f"{prefix}_ms_{pid}",
        )
        cm29_url = p2.text_input(
            "29CM (선택)",
            value=extra_links.get("29cm") or "",
            placeholder="https://...",
            key=f"{prefix}_29_{pid}",
        )
        zigzag_url = p3.text_input(
            "지그재그 (선택)",
            value=extra_links.get("zigzag") or "",
            placeholder="https://...",
            key=f"{prefix}_zz_{pid}",
        )
        ably_url = p4.text_input(
            "에이블리 (선택)",
            value=extra_links.get("ably") or "",
            placeholder="https://...",
            key=f"{prefix}_ab_{pid}",
        )
        image_url = st.text_input("이미지 URL", value=product.get("image_url") or "", placeholder="https://...", key=f"{prefix}_img_{pid}")
        source = st.selectbox(
            "이미지 출처",
            IMAGE_SOURCES,
            index=IMAGE_SOURCES.index(product.get("image_source")) if product.get("image_source") in IMAGE_SOURCES else 0,
            format_func=lambda x: IMAGE_SOURCE_LABELS[x],
            key=f"{prefix}_src_{pid}",
        )
        verified = st.checkbox("정확한 상품 이미지 확인 완료", value=bool(product.get("image_verified")), key=f"{prefix}_ver_{pid}")
        image_note = st.text_input("이미지 메모", value=product.get("image_note") or "", key=f"{prefix}_note_{pid}")
        visible = st.checkbox("홈에 공개", value=bool(product.get("is_visible")), key=f"{prefix}_vis_{pid}") if allow_hide else True
        save = st.form_submit_button("상품 정보 저장" if allow_hide else "승인 후 공개", type="primary", use_container_width=True)
    if not save:
        return
    if not name.strip() or not brand.strip():
        st.error("상품명과 브랜드를 입력하세요.")
        return
    if affiliate_verified and not coupang_url.strip().startswith("https://link.coupang.com/"):
        st.error("쿠팡 제휴 링크는 https://link.coupang.com/ 으로 시작해야 합니다.")
        return
    for label, url_val in [
        ("네이버 쇼핑 커넥트", naver_url),
        ("올리브영", oliveyoung_url),
        ("무신사", musinsa_url),
        ("29CM", cm29_url),
        ("지그재그", zigzag_url),
        ("에이블리", ably_url),
    ]:
        if url_val.strip() and not url_val.strip().startswith(("http://", "https://")):
            st.error(f"{label} 파트너 링크는 http 또는 https 주소여야 합니다.")
            return
    if verified and not image_url.strip().startswith(("http://", "https://")):
        st.error("확인된 이미지는 http 또는 https URL이 필요합니다.")
        return
    serialized_extra = serialize_extra_partner_links(
        {
            "naver": naver_url.strip(),
            "oliveyoung": oliveyoung_url.strip(),
            "musinsa": musinsa_url.strip(),
            "29cm": cm29_url.strip(),
            "zigzag": zigzag_url.strip(),
            "ably": ably_url.strip(),
        },
        memo=existing_memo,
    )
    api_patch(
        "products",
        {
            "canonical_name": name.strip(),
            "normalized_name": re.sub(r"[^0-9a-z가-힣]+", "", name.lower()),
            "brand": brand.strip(),
            "model": model.strip(),
            "category": category,
            "search_keyword": keyword.strip() or name.strip(),
            "coupang_url": coupang_url.strip() or None,
            "affiliate_verified": bool(affiliate_verified and coupang_url.strip().startswith("https://link.coupang.com/")),
            "affiliate_note": serialized_extra,
            "image_url": image_url.strip() or None,
            "image_source": source or None,
            "image_verified": bool(verified and image_url.strip()),
            "image_checked_at": datetime.now(timezone.utc).isoformat() if verified and image_url.strip() else None,
            "image_note": image_note.strip() or None,
            "review_status": "approved" if visible else "hidden",
            "is_visible": bool(visible),
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "review_note": "관리자 상품 관리에서 수정",
        },
        {"product_id": f"eq.{pid}"},
    )
    st.cache_data.clear()
    st.success("저장했습니다.")
    st.rerun()


def render_review():
    if not require_admin():
        return
    products, _, _, _, _, _, _ = load_admin_data()
    pending = [p for p in products if p.get("review_status") == "pending"]
    st.subheader(f"검수 대기 상품 {len(pending)}개")
    if not pending:
        st.success("검수 대기 상품이 없습니다.")
        return
    for product in pending:
        with st.container(border=True):
            st.markdown(f"### {safe(product.get('canonical_name'))}")
            st.caption(f"식별 점수 {int(product.get('identity_score') or 0)}/100 · {product.get('review_note') or '사유 없음'}")
            product_form(product, "review", allow_hide=False)


def render_manage():
    if not require_admin():
        return
    products, _, _, _, _, _, _ = load_admin_data()
    items = [p for p in products if p.get("review_status") in {"approved", "hidden"}]
    st.subheader("상품 관리")
    st.caption("승인·숨김 상품을 검색해 쿠팡·네이버 커넥트·올리브영·패션몰 파트너 링크와 상품 정보를 수정합니다.")
    c1, c2 = st.columns([1.7, 1])
    keyword = c1.text_input("관리 상품 검색", placeholder="상품명·브랜드·모델 검색", label_visibility="collapsed", key="manage_search")
    status = c2.selectbox("관리 상태", ["전체", "공개", "숨김"], label_visibility="collapsed", key="manage_status")
    needle = keyword.strip().lower()
    filtered = []
    for product in items:
        if status == "공개" and not product.get("is_visible"):
            continue
        if status == "숨김" and product.get("is_visible"):
            continue
        text = " ".join(str(product.get(k) or "") for k in ("canonical_name", "brand", "model", "category")).lower()
        if needle and needle not in text:
            continue
        filtered.append(product)
    st.caption(f"검색 결과 {len(filtered)}개 · 한 화면 최대 20개")
    if not filtered:
        st.info("조건에 맞는 상품이 없습니다.")
        return
    for product in filtered[:20]:
        with st.container(border=True):
            title, status_col = st.columns([4, 1])
            title.markdown(f"### {safe(product.get('canonical_name'))}")
            status_col.caption("공개" if product.get("is_visible") else "숨김")
            preview, editor = st.columns([1, 2])
            with preview:
                render_product_visual(product)
            with editor:
                product_form(product, "manage", allow_hide=True)

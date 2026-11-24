from collections import Counter
from datetime import datetime, timezone

import streamlit as st

from ui.common import (
    CATEGORIES,
    EXTRA_MALLS,
    IMAGE_SOURCES,
    IMAGE_SOURCE_LABELS,
    MALL_META,
    api_get_all,
    api_patch,
    count_by,
    load_public_data,
    norm_key,
    parse_extra_partner_links,
    render_footer,
    render_product_visual,
    safe,
    secret,
    serialize_extra_partner_links,
)

ADMIN_PASSWORD = secret("ADMIN_PASSWORD")


@st.cache_data(ttl=60, show_spinner=False)
def load_admin_data():
    products = api_get_all(
        "products",
        "product_id,canonical_name,normalized_name,brand,model,category,search_keyword,coupang_url,affiliate_verified,affiliate_note,image_url,image_source,image_verified,image_checked_at,image_note,identity_score,review_status,is_visible,review_note,created_at",
        {"order": "created_at.desc"},
        max_rows=3000,
    )
    videos = api_get_all(
        "videos",
        "video_id,title,analysis_status,analysis_error,product_score,created_at",
        {"order": "created_at.desc"},
        max_rows=5000,
    )
    channels = api_get_all(
        "channels",
        "channel_id,channel_name,subscriber_count",
        {},
        max_rows=2000,
    )
    recs = api_get_all(
        "recommendations",
        "recommendation_id,product_id,video_id,channel_id,reason,pros,cons,evidence,confidence,purchase_type,created_at",
        {"order": "created_at.desc"},
        max_rows=10000,
    )
    video_map = {v["video_id"]: v for v in videos}
    channel_map = {c["channel_id"]: c for c in channels}
    grouped = {}
    for rec in recs:
        item = dict(rec)
        item["video"] = video_map.get(rec.get("video_id"), {})
        item["channel"] = channel_map.get(rec.get("channel_id"), {})
        grouped.setdefault(rec.get("product_id"), []).append(item)
    for p in products:
        p["recommendations"] = grouped.get(p["product_id"], [])
    return products, videos, channels, recs


@st.cache_data(ttl=60, show_spinner=False)
def load_click_stats():
    try:
        return api_get_all(
            "click_logs",
            "event_type,product_id,product_name,search_query,created_at",
            {"order": "created_at.desc"},
            max_rows=5000,
        )
    except Exception:
        return []


def clear_all_caches():
    load_admin_data.clear()
    load_click_stats.clear()
    load_public_data.clear()


def render_admin_page():
    if st.button("← 서비스 홈으로", key="admin_back_home", type="secondary"):
        st.session_state.page = "home"
        st.session_state.detail_pid = ""
        st.query_params.clear()
        st.rerun()

    st.markdown("### 관리자 콘솔 · 운영 통계 및 상품 관리")

    if not ADMIN_PASSWORD:
        st.error("Streamlit Secrets에 `ADMIN_PASSWORD`가 설정되어 있지 않습니다.")
        return

    if not st.session_state.get("admin_authed"):
        with st.form("admin_login_form"):
            pw = st.text_input("관리자 비밀번호", type="password", placeholder="비밀번호를 입력하세요")
            submitted = st.form_submit_button("로그인", type="primary")
            if submitted:
                if pw == ADMIN_PASSWORD:
                    st.session_state.admin_authed = True
                    st.rerun()
                else:
                    st.error("비밀번호가 일치하지 않습니다.")
        render_footer()
        return

    top_c1, top_c2 = st.columns([4, 1])
    with top_c1:
        st.caption("상품 검수, 다중 쇼핑몰 제휴 링크 등록, 이미지 검수 및 클릭·검색어 통계를 관리합니다.")
    with top_c2:
        if st.button("🔄 통계 새로고침", key="admin_refresh_btn", use_container_width=True):
            clear_all_caches()
            st.rerun()

    products, videos, channels, recs = load_admin_data()
    logs = load_click_stats()

    approved_visible = [p for p in products if p.get("review_status") == "approved" and p.get("is_visible")]
    pending_products = [p for p in products if p.get("review_status") == "pending"]
    video_status_counts = count_by(videos, "analysis_status")

    tab_stats, tab_pending, tab_manage = st.tabs([
        "📊 운영 통계 · 클릭 분석",
        f"✅ 검수 대기 ({len(pending_products)})",
        f"🛠️ 상품 · 제휴 링크 관리 ({len(products)})",
    ])

    with tab_stats:
        mall_click_keys = [f"{m}_click" for m in MALL_META.keys()]
        total_outbound = sum(1 for row in logs if row.get("event_type") in mall_click_keys)
        total_views = sum(1 for row in logs if row.get("event_type") == "product_view")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(
                f'<div class="metric"><div class="metric-label">공개 중인 추천 상품</div>'
                f'<div class="metric-value">{len(approved_visible):,}개</div></div>',
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f'<div class="metric"><div class="metric-label">승인 대기 상품</div>'
                f'<div class="metric-value">{len(pending_products):,}개</div></div>',
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f'<div class="metric"><div class="metric-label">분석 완료 영상</div>'
                f'<div class="metric-value">{video_status_counts.get("analyzed", 0):,}개</div></div>',
                unsafe_allow_html=True,
            )
        with m4:
            st.markdown(
                f'<div class="metric"><div class="metric-label">쇼핑몰 이동 클릭 (누적)</div>'
                f'<div class="metric-value">{total_outbound:,}회</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        col_left, col_right = st.columns(2, gap="medium")
        with col_left:
            with st.container(border=True):
                st.markdown("**쇼핑몰별 아웃바운드 클릭 통계**")
                event_counts = count_by(logs, "event_type")
                rows_html = [
                    f'<div class="status-row"><span>👀 상품 상세 비교 조회</span><b>{total_views:,}회</b></div>'
                ]
                for mall_key, meta in MALL_META.items():
                    cnt = event_counts.get(f"{mall_key}_click", 0)
                    rows_html.append(
                        f'<div class="status-row"><span>{safe(meta["label"])} 이동</span><b>{cnt:,}회</b></div>'
                    )
                st.markdown("".join(rows_html), unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown("**인기 검색어 TOP 15**")
                search_counter = Counter(
                    str(r.get("search_query") or "").strip()
                    for r in logs
                    if r.get("event_type") == "search" and str(r.get("search_query") or "").strip()
                )
                if not search_counter:
                    st.caption("아직 수집된 검색 로그가 없습니다.")
                else:
                    s_rows = "".join(
                        f'<div class="status-row"><span>{idx}. {safe(q)}</span><b>{cnt:,}회</b></div>'
                        for idx, (q, cnt) in enumerate(search_counter.most_common(15), start=1)
                    )
                    st.markdown(s_rows, unsafe_allow_html=True)

        with col_right:
            with st.container(border=True):
                st.markdown("**클릭 인기 상품 TOP 10**")
                click_prod_counter = Counter(
                    str(r.get("product_name") or "").strip()
                    for r in logs
                    if r.get("event_type") in mall_click_keys and str(r.get("product_name") or "").strip()
                )
                if not click_prod_counter:
                    st.caption("아직 쇼핑몰 이동 클릭 데이터가 없습니다.")
                else:
                    p_rows = "".join(
                        f'<div class="status-row"><span>{idx}. {safe(name)}</span><b>{cnt:,}회</b></div>'
                        for idx, (name, cnt) in enumerate(click_prod_counter.most_common(10), start=1)
                    )
                    st.markdown(p_rows, unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown("**영상 수집 · AI 분석 파이프라인 현황**")
                status_labels = [
                    ("analyzed", "분석 완료 (analyzed)"),
                    ("queued", "분석 대기열 (queued)"),
                    ("pending", "점수 산정 대기 (pending)"),
                    ("skipped_non_product", "비쇼핑 영상 제외"),
                    ("no_product", "추출 상품 없음"),
                    ("rejected_generic", "일반명사 제외"),
                    ("ai_error", "AI 분석 오류 (ai_error)"),
                ]
                v_rows = "".join(
                    f'<div class="status-row"><span>{label}</span><b>{video_status_counts.get(key, 0):,}개</b></div>'
                    for key, label in status_labels
                )
                st.markdown(v_rows, unsafe_allow_html=True)

                err_videos = [v for v in videos if v.get("analysis_status") == "ai_error"][:5]
                if err_videos:
                    st.markdown("**최근 AI 분석 오류 내역 (최대 5건)**")
                    for ev in err_videos:
                        st.markdown(
                            f'<div class="error-box"><b>{safe(ev.get("video_id"))}</b> · {safe(ev.get("title"))}<br>'
                            f'{safe(ev.get("analysis_error"))}</div>',
                            unsafe_allow_html=True,
                        )

    with tab_pending:
        if not pending_products:
            st.info("현재 검수 대기 중인 신규 상품이 없습니다.")
        else:
            st.caption("AI가 추출했으나 식별 점수가 기준 미만인 상품입니다. 상품명·카테고리를 다듬어 승인하거나 반려할 수 있습니다.")
            for p in pending_products[:30]:
                pid = str(p.get("product_id"))
                with st.container(border=True):
                    c_img, c_body = st.columns([1, 2.4], gap="medium")
                    with c_img:
                        render_product_visual(p)
                        st.caption(f"식별점수: {p.get('identity_score', 0)}점")
                    with c_body:
                        with st.form(f"pending_form_{pid}"):
                            f1, f2, f3 = st.columns([2, 1, 1])
                            new_name = f1.text_input("상품명", value=str(p.get("canonical_name") or ""))
                            new_brand = f2.text_input("브랜드", value=str(p.get("brand") or ""))
                            cur_cat = p.get("category") if p.get("category") in CATEGORIES else "기타"
                            new_cat = f3.selectbox("카테고리", CATEGORIES, index=CATEGORIES.index(cur_cat))

                            new_kw = st.text_input("쇼핑몰 검색 키워드", value=str(p.get("search_keyword") or new_name))
                            if p.get("review_note"):
                                st.caption(f"메모: {p.get('review_note')}")

                            b1, b2 = st.columns(2)
                            approve_btn = b1.form_submit_button("✅ 승인 및 공개", type="primary", use_container_width=True)
                            reject_btn = b2.form_submit_button("🚫 반려 처리", type="secondary", use_container_width=True)

                            if approve_btn:
                                clean_name = new_name.strip() or str(p.get("canonical_name") or "")
                                api_patch(
                                    "products",
                                    {
                                        "canonical_name": clean_name,
                                        "normalized_name": norm_key(clean_name),
                                        "brand": new_brand.strip() or "기타",
                                        "category": new_cat,
                                        "search_keyword": new_kw.strip() or clean_name,
                                        "review_status": "approved",
                                        "is_visible": True,
                                        "review_note": "관리자 수동 승인",
                                    },
                                    {"product_id": f"eq.{pid}"},
                                )
                                clear_all_caches()
                                st.success("승인 및 공개 처리되었습니다.")
                                st.rerun()

                            if reject_btn:
                                api_patch(
                                    "products",
                                    {
                                        "review_status": "rejected",
                                        "is_visible": False,
                                        "review_note": "관리자 반려",
                                    },
                                    {"product_id": f"eq.{pid}"},
                                )
                                clear_all_caches()
                                st.warning("반려 처리되었습니다.")
                                st.rerun()

    with tab_manage:
        fc1, fc2, fc3 = st.columns([2, 1, 1])
        m_query = fc1.text_input("상품명 · 브랜드 검색", key="admin_manage_search", placeholder="예: 로지텍, 선크림, 가방...")
        m_status = fc2.selectbox("상태 필터", ["공개중", "비공개", "반려됨", "전체"], key="admin_manage_status")
        m_cat = fc3.selectbox("카테고리", ["전체"] + CATEGORIES, key="admin_manage_cat")

        filtered = products
        if m_status == "공개중":
            filtered = [p for p in filtered if p.get("review_status") == "approved" and p.get("is_visible")]
        elif m_status == "비공개":
            filtered = [p for p in filtered if p.get("review_status") == "approved" and not p.get("is_visible")]
        elif m_status == "반려됨":
            filtered = [p for p in filtered if p.get("review_status") == "rejected"]

        if m_cat != "전체":
            filtered = [p for p in filtered if (p.get("category") or "기타") == m_cat]

        if m_query.strip():
            q_low = m_query.strip().lower()
            filtered = [
                p for p in filtered
                if q_low in str(p.get("canonical_name") or "").lower()
                or q_low in str(p.get("brand") or "").lower()
                or q_low in str(p.get("search_keyword") or "").lower()
            ]

        st.caption(f"검색 결과: 총 {len(filtered):,}개 (최대 30개씩 표시)")

        for p in filtered[:30]:
            pid = str(p.get("product_id"))
            extra_links, extra_memo = parse_extra_partner_links(p)
            has_coupang = bool(p.get("affiliate_verified") and str(p.get("coupang_url") or "").startswith("https://link.coupang.com/"))
            partner_badges = []
            if has_coupang:
                partner_badges.append("쿠팡")
            for mk in EXTRA_MALLS:
                if extra_links.get(mk):
                    partner_badges.append(MALL_META[mk]["short"])
            partner_tag = f" · 제휴[{','.join(partner_badges)}]" if partner_badges else ""
            vis_tag = "🟢 공개" if p.get("is_visible") else "⚪ 비공개"

            with st.expander(f"{vis_tag} | [{p.get('category') or '기타'}] {p.get('canonical_name')}{partner_tag}"):
                with st.form(f"edit_prod_form_{pid}"):
                    r1c1, r1c2, r1c3, r1c4 = st.columns([2.2, 1, 1, 1])
                    e_name = r1c1.text_input("공식 상품명", value=str(p.get("canonical_name") or ""))
                    e_brand = r1c2.text_input("브랜드", value=str(p.get("brand") or ""))
                    e_model = r1c3.text_input("모델명", value=str(p.get("model") or ""))
                    cur_c = p.get("category") if p.get("category") in CATEGORIES else "기타"
                    e_cat = r1c4.selectbox("카테고리", CATEGORIES, index=CATEGORIES.index(cur_c))

                    r2c1, r2c2, r2c3 = st.columns([2, 1, 1])
                    e_kw = r2c1.text_input("쇼핑몰 기본 검색어", value=str(p.get("search_keyword") or ""))
                    status_opts = ["approved", "pending", "rejected"]
                    cur_st = p.get("review_status") if p.get("review_status") in status_opts else "approved"
                    e_status = r2c2.selectbox("검수 상태", status_opts, index=status_opts.index(cur_st))
                    e_visible = r2c3.checkbox("사이트에 공개", value=bool(p.get("is_visible")))

                    st.markdown("**제휴 파트너 링크 등록 (비워두면 해당 쇼핑몰 실시간 검색으로 연결)**")
                    e_coupang = st.text_input(
                        "쿠팡 파트너스 단축 URL (https://link.coupang.com/...)",
                        value=str(p.get("coupang_url") or ""),
                    )
                    l1, l2, l3 = st.columns(3)
                    e_naver = l1.text_input("네이버 쇼핑 커넥트 URL", value=extra_links.get("naver", ""))
                    e_oy = l2.text_input("올리브영 큐레이터 URL", value=extra_links.get("oliveyoung", ""))
                    e_musinsa = l3.text_input("무신사 큐레이터 URL", value=extra_links.get("musinsa", ""))

                    l4, l5, l6 = st.columns(3)
                    e_29cm = l4.text_input("29CM 제휴 URL", value=extra_links.get("29cm", ""))
                    e_zigzag = l5.text_input("지그재그 제휴 URL", value=extra_links.get("zigzag", ""))
                    e_ably = l6.text_input("에이블리 제휴 URL", value=extra_links.get("ably", ""))

                    st.markdown("**대표 상품 이미지 설정 (비워두면 유튜브 영상 썸네일 자동 사용)**")
                    im1, im2, im3 = st.columns([2.2, 1, 0.8])
                    e_img_url = im1.text_input("상품 이미지 URL", value=str(p.get("image_url") or ""))
                    cur_src = p.get("image_source") if p.get("image_source") in IMAGE_SOURCES else ""
                    e_img_src = im2.selectbox(
                        "이미지 출처",
                        IMAGE_SOURCES,
                        index=IMAGE_SOURCES.index(cur_src),
                        format_func=lambda x: IMAGE_SOURCE_LABELS.get(x, x),
                    )
                    e_img_ver = im3.checkbox("이미지 승인", value=bool(p.get("image_verified")))
                    e_memo = st.text_input("관리자 메모", value=extra_memo)

                    if st.form_submit_button("💾 변경사항 저장", type="primary"):
                        clean_name = e_name.strip() or str(p.get("canonical_name") or "")
                        cp_url = e_coupang.strip()
                        cp_verified = cp_url.startswith("https://link.coupang.com/")
                        new_extra = {
                            "naver": e_naver,
                            "oliveyoung": e_oy,
                            "musinsa": e_musinsa,
                            "29cm": e_29cm,
                            "zigzag": e_zigzag,
                            "ably": e_ably,
                        }
                        img_url_clean = e_img_url.strip()
                        patch_payload = {
                            "canonical_name": clean_name,
                            "normalized_name": norm_key(clean_name),
                            "brand": e_brand.strip() or "기타",
                            "model": e_model.strip(),
                            "category": e_cat,
                            "search_keyword": e_kw.strip() or clean_name,
                            "review_status": e_status,
                            "is_visible": bool(e_visible),
                            "coupang_url": cp_url or None,
                            "affiliate_verified": cp_verified,
                            "affiliate_note": serialize_extra_partner_links(new_extra, e_memo),
                            "image_url": img_url_clean or None,
                            "image_source": e_img_src or None,
                            "image_verified": bool(e_img_ver and img_url_clean.startswith(("https://", "http://"))),
                            "image_checked_at": datetime.now(timezone.utc).isoformat() if img_url_clean else None,
                        }
                        api_patch("products", patch_payload, {"product_id": f"eq.{pid}"})
                        clear_all_caches()
                        st.success("상품 정보가 저장되었습니다.")
                        st.rerun()

    render_footer()

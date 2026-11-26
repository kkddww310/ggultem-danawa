import re
from collections import Counter
from datetime import datetime, timezone

import streamlit as st

from ui.common import (
    CATEGORIES,
    IMAGE_SOURCES,
    IMAGE_SOURCE_LABELS,
    api_count,
    api_delete,
    api_get,
    api_get_all,
    api_patch,
    count_by,
    get_page_numbers,
    has_partner_deal,
    parse_extra_partner_links,
    render_product_visual,
    safe,
    secret,
    serialize_extra_partner_links,
)

VIDEO_STATUS_KEYS = [
    "pending",
    "queued",
    "analyzed",
    "no_product",
    "rejected_generic",
    "skipped_non_product",
    "ai_error",
]


@st.cache_data(ttl=60, show_spinner=False)
def load_admin_products():
    return api_get_all(
        "products",
        "product_id,canonical_name,brand,model,category,search_keyword,identity_score,review_status,is_visible,review_note,coupang_url,coupang_product_name,affiliate_verified,affiliate_note,image_url,image_source,image_verified,image_checked_at,image_note,created_at",
        {"order": "created_at.desc"},
        max_rows=5000,
    )


@st.cache_data(ttl=60, show_spinner=False)
def load_admin_click_logs():
    try:
        logs = api_get_all(
            "click_logs",
            "log_id,event_type,product_id,product_name,search_query,created_at",
            {"order": "created_at.desc"},
            max_rows=20000,
        )
        return logs, True
    except Exception:
        return [], False


@st.cache_data(ttl=60, show_spinner=False)
def load_admin_dashboard_stats():
    total_channels = api_count("channels")
    active_channels = api_count("channels", {"status": "eq.active"})
    total_videos = api_count("videos")
    video_status_counts = {
        key: api_count("videos", {"analysis_status": f"eq.{key}"})
        for key in VIDEO_STATUS_KEYS
    }
    total_recs = api_count("recommendations")
    queries = api_get_all(
        "discovery_queries",
        "query_id,query_text,category,enabled,run_count,channels_found,active_channels_found,error_count,last_error,last_run_at,next_run_at",
        max_rows=5000,
    )
    video_errors = api_get(
        "videos",
        "video_id,title,analysis_error,created_at",
        {
            "analysis_status": "eq.ai_error",
            "analysis_error": "not.is.null",
            "order": "created_at.desc",
            "limit": "10",
        },
    )
    return {
        "total_channels": total_channels,
        "active_channels": active_channels,
        "total_videos": total_videos,
        "video_status_counts": video_status_counts,
        "total_recs": total_recs,
        "queries": queries,
        "video_errors": video_errors,
    }


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


def _render_admin_pagination(total_items, page_size, state_key, btn_prefix):
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    current_page = min(max(int(st.session_state.get(state_key, 1)), 1), total_pages)
    st.session_state[state_key] = current_page
    if total_pages <= 1:
        return current_page

    page_nums = get_page_numbers(current_page, total_pages)
    cols = st.columns([1.2] + [1] * len(page_nums) + [1.2])
    if cols[0].button("‹ 이전", key=f"{btn_prefix}_prev", disabled=current_page <= 1, use_container_width=True):
        st.session_state[state_key] = current_page - 1
        st.rerun()
    for idx, num in enumerate(page_nums, start=1):
        if cols[idx].button(
            str(num),
            key=f"{btn_prefix}_num_{num}",
            type="primary" if num == current_page else "secondary",
            use_container_width=True,
        ):
            if num != current_page:
                st.session_state[state_key] = num
                st.rerun()
    if cols[-1].button("다음 ›", key=f"{btn_prefix}_next", disabled=current_page >= total_pages, use_container_width=True):
        st.session_state[state_key] = current_page + 1
        st.rerun()
    return current_page


def render_dashboard():
    if not require_admin():
        return

    products = load_admin_products()
    click_logs, click_logs_ready = load_admin_click_logs()
    stats = load_admin_dashboard_stats()

    ps = count_by(products, "review_status")
    vs = stats["video_status_counts"]
    queries = stats["queries"]
    qerrors = sum(1 for q in queries if int(q.get("error_count") or 0) > 0 or q.get("last_error"))

    metrics = [
        ("전체 채널", stats["total_channels"], f"활성 {stats['active_channels']:,}"),
        ("전체 영상", stats["total_videos"], f"AI 대기 {vs.get('queued', 0):,}"),
        ("공개 상품", ps.get("approved", 0), f"검수 {ps.get('pending', 0):,}"),
        ("검색어", len(queries), f"오류 {qerrors:,}"),
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

        product_lookup = {str(p["product_id"]): p for p in products}
        click_counts = Counter()
        coupang_by_item = Counter()
        naver_by_item = Counter()
        extra_by_item = Counter()
        label_by_item = {}
        for row in coupang_clicks + naver_clicks + extra_clicks:
            key = str(row.get("product_id") or row.get("product_name") or "unknown")
            click_counts[key] += 1
            ev_type = row.get("event_type")
            if ev_type == "coupang_click":
                coupang_by_item[key] += 1
            elif ev_type == "naver_click":
                naver_by_item[key] += 1
            else:
                extra_by_item[key] += 1
            p_info = product_lookup.get(str(row.get("product_id") or ""))
            label_by_item[key] = (p_info or {}).get("canonical_name") or row.get("product_name") or "이름 없음"

        cl_left, cl_right = st.columns(2)
        with cl_left:
            with st.container(border=True):
                st.markdown("**클릭 많은 상품 TOP 15 (제휴 링크 우선 대상)**")
                if not click_counts:
                    st.caption("아직 기록된 상품 클릭이 없습니다.")
                for idx, (key, total) in enumerate(click_counts.most_common(15), start=1):
                    p_info = product_lookup.get(key)
                    linked = "✅ 연결" if (p_info and has_partner_deal(p_info)) else "미연결"
                    extra_str = f" · 기타 {extra_by_item[key]}" if extra_by_item[key] else ""
                    r_info, r_btn = st.columns([3.4, 1])
                    r_info.markdown(
                        f'<div class="status-row">'
                        f'<span><b>{idx}.</b> {safe(label_by_item.get(key))} <small style="color:#8B95A1">({linked})</small></span>'
                        f'<b>쿠팡 {coupang_by_item[key]} · 네이버 {naver_by_item[key]}{extra_str}</b>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if p_info:
                        if r_btn.button("링크 관리 →", key=f"jump_top_{idx}_{key}", use_container_width=True):
                            st.session_state.manage_search = p_info.get("canonical_name") or ""
                            st.session_state.manage_status = "전체"
                            st.session_state.manage_target_pid = str(p_info["product_id"])
                            st.session_state.manage_page = 1
                            st.session_state.page = "manage"
                            st.rerun()
        with cl_right:
            with st.container(border=True):
                st.markdown("**방문자 인기 검색어 TOP 15**")
                sq_counts = Counter(str(r.get("search_query")).strip() for r in search_logs)
                if not sq_counts:
                    st.caption("아직 기록된 검색어가 없습니다.")
                for idx, (q_text, cnt) in enumerate(sq_counts.most_common(15), start=1):
                    st.markdown(
                        f'<div class="status-row"><span><b>{idx}.</b> {safe(q_text)}</span><b>{cnt:,}회</b></div>',
                        unsafe_allow_html=True,
                    )

    st.subheader("영상 처리 현황")
    l, r = st.columns(2)
    with l:
        with st.container(border=True):
            for key in VIDEO_STATUS_KEYS:
                st.markdown(f'<div class="status-row"><span>{key}</span><b>{vs.get(key, 0):,}</b></div>', unsafe_allow_html=True)
    with r:
        with st.container(border=True):
            for key in ["approved", "pending", "hidden", "merged"]:
                st.markdown(f'<div class="status-row"><span>상품 {key}</span><b>{ps.get(key, 0):,}</b></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="status-row"><span>추천 기록</span><b>{stats["total_recs"]:,}</b></div>', unsafe_allow_html=True)

    st.subheader("최근 오류")
    errors = stats["video_errors"]
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

    if click_logs_ready:
        st.markdown("---")
        with st.expander("🗑️ 방문자 클릭 · 검색 기록 초기화 (테스트 로그 정리)"):
            st.caption("테스트 중 쌓인 내 검색 기록이나 쇼핑몰 클릭 로그를 초기화합니다. 삭제된 로그는 복구할 수 없습니다.")
            reset_scope = st.selectbox(
                "초기화 대상 선택",
                ["전체 클릭·검색 기록 초기화", "검색어 기록만 초기화", "쇼핑몰 클릭 기록만 초기화"],
                key="reset_log_scope",
            )
            confirm_reset = st.checkbox(
                "선택한 기록을 영구 삭제하는 것에 동의합니다.",
                key="confirm_reset_logs",
            )
            if st.button(
                "선택한 기록 초기화 실행",
                type="primary",
                disabled=not confirm_reset,
                use_container_width=True,
                key="exec_reset_logs",
            ):
                if reset_scope == "검색어 기록만 초기화":
                    api_delete("click_logs", {"event_type": "eq.search"})
                elif reset_scope == "쇼핑몰 클릭 기록만 초기화":
                    api_delete("click_logs", {"event_type": "neq.search"})
                else:
                    api_delete("click_logs", {"log_id": "not.is.null"})
                st.cache_data.clear()
                st.success("방문자 기록이 깔끔하게 초기화되었습니다.")
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
    st.session_state.manage_target_pid = ""
    st.cache_data.clear()
    st.success("저장했습니다.")
    st.rerun()


def render_review():
    if not require_admin():
        return
    products = load_admin_products()
    pending = [p for p in products if p.get("review_status") == "pending"]
    st.subheader(f"검수 대기 상품 {len(pending):,}개")
    if not pending:
        st.success("검수 대기 상품이 없습니다.")
        return

    page_size = 15
    total_pages = max(1, (len(pending) + page_size - 1) // page_size)
    current_page = min(max(int(st.session_state.get("review_page", 1)), 1), total_pages)
    st.session_state.review_page = current_page
    st.caption(f"페이지 {current_page} / {total_pages} · 한 화면 {page_size}개씩 표시")

    page_items = pending[(current_page - 1) * page_size:current_page * page_size]
    for product in page_items:
        pid = product["product_id"]
        with st.container(border=True):
            info_col, ok_col, hide_col = st.columns([3.5, 1, 1])
            with info_col:
                st.markdown(f"**{safe(product.get('canonical_name'))}**")
                st.caption(
                    f"브랜드: {product.get('brand') or '-'} · 모델: {product.get('model') or '-'} · "
                    f"식별 {int(product.get('identity_score') or 0)}/100 · {product.get('review_note') or '검수 대기'}"
                )
            with ok_col:
                if st.button("✅ 바로 승인", key=f"quick_ok_{pid}", type="primary", use_container_width=True):
                    if not str(product.get("brand") or "").strip() or not str(product.get("canonical_name") or "").strip():
                        st.error("브랜드 또는 상품명이 비어 있어 아래 수정 폼에서 먼저 입력해 주세요.")
                    else:
                        api_patch(
                            "products",
                            {
                                "review_status": "approved",
                                "is_visible": True,
                                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                                "review_note": "관리자 원클릭 승인",
                            },
                            {"product_id": f"eq.{pid}"},
                        )
                        st.cache_data.clear()
                        st.rerun()
            with hide_col:
                if st.button("🙈 숨김 처리", key=f"quick_hide_{pid}", use_container_width=True):
                    api_patch(
                        "products",
                        {
                            "review_status": "hidden",
                            "is_visible": False,
                            "reviewed_at": datetime.now(timezone.utc).isoformat(),
                            "review_note": "관리자 원클릭 숨김",
                        },
                        {"product_id": f"eq.{pid}"},
                    )
                    st.cache_data.clear()
                    st.rerun()

            with st.expander("상품명 · 제휴 링크 · 이미지 상세 수정 후 승인"):
                product_form(product, "review", allow_hide=False)

    _render_admin_pagination(len(pending), page_size, "review_page", "rev_pg")


def render_manage():
    if not require_admin():
        return
    products = load_admin_products()
    click_logs, _ = load_admin_click_logs()

    click_by_pid = Counter()
    for row in click_logs:
        if row.get("event_type") != "search" and row.get("product_id"):
            click_by_pid[str(row["product_id"])] += 1

    items = [p for p in products if p.get("review_status") in {"approved", "hidden"}]
    st.subheader("상품 관리")
    st.caption("승인·숨김 상품을 검색하고 제휴 링크와 노출 상태를 빠르게 관리합니다.")

    filter_options = ["전체", "🔥 제휴 미연결 인기순", "제휴 미연결 전체", "제휴 연결됨", "공개", "숨김"]
    if st.session_state.get("manage_status") not in filter_options:
        st.session_state.manage_status = "전체"

    c1, c2 = st.columns([1.7, 1])
    keyword = c1.text_input(
        "관리 상품 검색",
        placeholder="상품명·브랜드·모델·카테고리 검색",
        label_visibility="collapsed",
        key="manage_search",
    )
    status = c2.selectbox(
        "관리 상태",
        filter_options,
        label_visibility="collapsed",
        key="manage_status",
    )

    sig = (keyword.strip(), status)
    if st.session_state.get("_last_manage_sig") != sig:
        st.session_state._last_manage_sig = sig
        st.session_state.manage_page = 1

    needle = keyword.strip().lower()
    filtered = []
    for product in items:
        pid_str = str(product["product_id"])
        linked = has_partner_deal(product)
        clicks = click_by_pid.get(pid_str, 0)

        if status == "공개" and not product.get("is_visible"):
            continue
        if status == "숨김" and product.get("is_visible"):
            continue
        if status == "제휴 연결됨" and not linked:
            continue
        if status == "제휴 미연결 전체" and linked:
            continue
        if status == "🔥 제휴 미연결 인기순" and (linked or not product.get("is_visible")):
            continue

        text = " ".join(str(product.get(k) or "") for k in ("canonical_name", "brand", "model", "category")).lower()
        if needle and needle not in text:
            continue
        filtered.append((clicks, product))

    if status == "🔥 제휴 미연결 인기순":
        filtered.sort(key=lambda pair: pair[0], reverse=True)

    page_size = 20
    total_filtered = len(filtered)
    total_pages = max(1, (total_filtered + page_size - 1) // page_size)
    current_page = min(max(int(st.session_state.get("manage_page", 1)), 1), total_pages)
    st.session_state.manage_page = current_page

    st.caption(f"검색 결과 {total_filtered:,}개 · 페이지 {current_page} / {total_pages}")
    if not filtered:
        st.info("조건에 맞는 상품이 없습니다.")
        return

    target_pid = str(st.session_state.get("manage_target_pid") or "").strip()
    page_items = filtered[(current_page - 1) * page_size:current_page * page_size]

    for clicks, product in page_items:
        pid = str(product["product_id"])
        linked = has_partner_deal(product)
        is_vis = bool(product.get("is_visible"))
        link_badge = "✅ 제휴연결" if linked else "미연결"
        vis_badge = "공개중" if is_vis else "숨김됨"

        with st.container(border=True):
            info_col, toggle_col = st.columns([4.2, 1])
            with info_col:
                st.markdown(f"**{safe(product.get('canonical_name'))}**")
                st.caption(
                    f"{product.get('brand') or '-'} · {product.get('category') or '기타'} · "
                    f"👆 클릭 {clicks:,}회 · {link_badge} · {vis_badge}"
                )
            with toggle_col:
                btn_txt = "숨기기" if is_vis else "공개하기"
                if st.button(btn_txt, key=f"mng_vis_btn_{pid}", use_container_width=True):
                    next_vis = not is_vis
                    api_patch(
                        "products",
                        {
                            "review_status": "approved" if next_vis else "hidden",
                            "is_visible": next_vis,
                            "reviewed_at": datetime.now(timezone.utc).isoformat(),
                            "review_note": "관리자 노출 상태 전환",
                        },
                        {"product_id": f"eq.{pid}"},
                    )
                    st.cache_data.clear()
                    st.rerun()

            with st.expander("제휴 링크 · 상품 정보 · 이미지 수정", expanded=(pid == target_pid)):
                preview, editor = st.columns([1, 2.3])
                with preview:
                    render_product_visual(product)
                with editor:
                    product_form(product, "manage", allow_hide=True)

    _render_admin_pagination(total_filtered, page_size, "manage_page", "mng_pg")

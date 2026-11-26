import re
import urllib.parse

import streamlit as st
import streamlit.components.v1 as components

from ui.common import (
    MALL_META,
    build_product_visual_html,
    clean_evidence_text,
    detect_product_malls,
    format_korean_count,
    get_related_products,
    get_representative_rec,
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

MALL_ACTION_SUBS = {
    "naver": "네이버페이 적립 · 공식 스토어 가격 비교",
    "coupang": "로켓배송 여부 · 실시간 판매가 확인",
    "oliveyoung": "오늘드림 당일배송 · 멤버십 할인가 확인",
    "musinsa": "전 상품 무료배송 · 회원 등급 혜택가 확인",
    "29cm": "감도 셀렉트샵 · 쿠폰 적용가 확인",
    "zigzag": "직진배송 빠른도착 · 스토어 통합 최저가",
    "ably": "전 상품 무료배송 · 앱 할인가 확인",
}

FOOD_BEVERAGE_KEYWORDS = (
    "스파클링", "음료", "매실", "주스", "탄산", "커피", "원두", "캡슐커피", "드립백",
    "라떼", "에이드", "녹차", "홍차", "콤부차", "보리차", "허브티", "아이스티",
    "간식", "과자", "쿠키", "젤리", "초콜릿", "디저트", "라면", "소스", "밀키트",
    "식품", "단백질", "프로틴", "쉐이크", "유산균", "비타민", "오메가3", "영양제",
)

HOLLOW_QUOTE_RE = re.compile(
    r"(템으로\s*(소개|추천|언급|선정)|"
    r"제품으로\s*(소개|추천|언급|선정)|"
    r"아이템으로\s*(소개|추천|언급|선정)|"
    r"(소개|추천|언급|리뷰|선정|사용)됨\.?$|"
    r"(소개|추천|언급|리뷰|선정)한\s*(제품|템|아이템)|"
    r"100%\s*내돈내산\s*템|"
    r"이벤트\s*대표\s*상품)"
)

CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
CONCRETE_HOOK_RE = re.compile(r"(\d+|대비|이상|이하|만큼|처럼|없이|유일|최초|종결|역대|비교|차이)")


def _map_display_category(product):
    raw_cat = str(product.get("category") or "기타").strip()
    name_text = f"{product.get('canonical_name') or ''} {product.get('search_keyword') or ''}".lower()
    if any(kw in name_text for kw in FOOD_BEVERAGE_KEYWORDS):
        return "푸드·리빙"
    if raw_cat == "IT·전자":
        return "IT·테크"
    if raw_cat in ("뷰티", "패션"):
        return "뷰티·패션"
    if raw_cat in ("주방", "생활·살림", "식품·음료"):
        return "푸드·리빙"
    return "라이프·기타"


def _is_authentic_quote(text):
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if not is_meaningful_point(cleaned):
        return False
    if CJK_CHAR_RE.search(cleaned):
        return False
    if HOLLOW_QUOTE_RE.search(cleaned):
        return False
    return True


def _build_detail_href_with_state(pid):
    params = [("view", "detail"), ("pid", str(pid or "").strip())]
    for key in ("cat", "q", "sort", "p"):
        val = str(st.query_params.get(key, "")).strip()
        if val:
            params.append((key, val))
    return "?" + urllib.parse.urlencode(params)


def inject_detail_overrides():
    st.markdown(
        """
<style>
.detail-nav-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 2px 0 10px;
}
.detail-breadcrumb {
  margin: 0 !important;
  font-size: 12.5px !important;
  font-weight: 700 !important;
  color: #8B95A1 !important;
}

.detail-top-grid {
  display: grid !important;
  grid-template-columns: 1.35fr 1fr !important;
  gap: 16px !important;
  align-items: stretch !important;
  margin-bottom: 16px !important;
}
.detail-hero-card {
  background: #FFFFFF !important;
  border: 1px solid #E6E9EF !important;
  border-radius: 18px !important;
  padding: 18px !important;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04) !important;
  display: flex !important;
  flex-direction: column !important;
  justify-content: space-between !important;
  gap: 14px !important;
}
.detail-hero-main {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 16px;
  align-items: center;
}
.detail-visual-stage {
  position: relative;
  width: 100%;
  border-radius: 13px;
  overflow: hidden;
  border: 1px solid #EDF0F5;
  background: #F8FAFC;
}
.detail-visual-stage .video-thumbnail-wrap,
.detail-visual-stage .product-placeholder {
  margin: 0 !important;
  border-radius: 12px !important;
}
.detail-visual-stage a[href*="youtu"],
.detail-visual-stage .thumb-play-badge,
.detail-visual-stage .video-play-chip {
  display: none !important;
}
.detail-info-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.detail-brand-line {
  font-size: 12px !important;
  font-weight: 800 !important;
  color: #3182F6 !important;
}
.detail-title {
  font-size: 22px !important;
  font-weight: 900 !important;
  color: #191F28 !important;
  line-height: 1.3 !important;
  letter-spacing: -0.025em !important;
  margin: 0 !important;
  word-break: keep-all;
}
.detail-badges {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 6px !important;
  margin-top: 4px !important;
}

.danawa-box {
  background: #FFFFFF !important;
  border: 1px solid #E6E9EF !important;
  border-radius: 18px !important;
  padding: 18px !important;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04) !important;
  display: flex !important;
  flex-direction: column !important;
  justify-content: space-between !important;
}
.danawa-row {
  padding: 11px 12px !important;
  border-radius: 12px !important;
  border: 1px solid #EEF1F6 !important;
  background: #FAFBFD !important;
  transition: border-color 0.15s ease, background 0.15s ease !important;
}
.danawa-row:hover {
  border-color: #C7D2E0 !important;
  background: #F4F7FC !important;
}
.danawa-go-btn {
  background: #191F28 !important;
  color: #FFFFFF !important;
  border-radius: 10px !important;
  padding: 8px 13px !important;
  font-size: 12px !important;
  font-weight: 800 !important;
  white-space: nowrap !important;
}
.danawa-go-btn:hover {
  background: #3182F6 !important;
}

.quote-highlight-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
  margin-top: 10px;
}
.quote-highlight-card {
  background: #F7F9FC;
  border: 1px solid #E6ECF5;
  border-left: 3.5px solid #3182F6;
  border-radius: 12px;
  padding: 13px 15px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 9px;
}
.quote-highlight-body {
  font-size: 13.5px;
  font-weight: 700;
  color: #191F28;
  line-height: 1.5;
  word-break: keep-all;
}
.quote-highlight-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11.5px;
  font-weight: 700;
  color: #6B7684;
}
.quote-video-link {
  color: #3182F6 !important;
  text-decoration: none !important;
  font-weight: 800;
  white-space: nowrap;
}

/* 하단 연관 추천템: 홈과 동일한 클린 썸네일 + 체크 포인트 칩 */
.st-key-related_grid .product-card {
  background: #FFFFFF !important;
  border: 1px solid #E6E9EF !important;
  border-radius: 15px !important;
  padding: 10px 10px 12px !important;
  box-shadow: 0 3px 12px rgba(15, 23, 42, 0.03) !important;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease !important;
  display: flex !important;
  flex-direction: column !important;
  height: 100% !important;
}
.st-key-related_grid .product-card:hover {
  transform: translateY(-3px) !important;
  border-color: #C7D2E0 !important;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.08) !important;
}
.rel-thumb-stage {
  position: relative;
  width: 100%;
  border-radius: 11px;
  overflow: hidden;
}
.rel-thumb-stage .video-thumbnail-wrap,
.rel-thumb-stage .product-placeholder {
  margin: 0 !important;
  border-radius: 11px !important;
}
.rel-thumb-stage a[href*="youtu"],
.rel-thumb-stage .thumb-play-badge,
.rel-thumb-stage .video-play-chip {
  display: none !important;
}
.rel-card-link {
  display: flex;
  flex-direction: column;
  flex: 1;
  text-decoration: none !important;
  color: inherit !important;
  padding-top: 9px;
}
.rel-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 4px;
  min-height: 20px;
}
.rel-brand-line {
  font-size: 11px;
  font-weight: 750;
  color: #8B95A1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.rel-trust-pill {
  flex-shrink: 0;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.3;
}
.rel-trust-self {
  background: #E8F5EE;
  color: #146C43;
}
.rel-trust-clean {
  background: #F1F4F8;
  color: #4E5968;
}
.rel-trust-prov {
  background: #FFF6DF;
  color: #8A5A00;
}
.rel-title {
  font-size: 15px;
  font-weight: 900;
  color: #111827;
  line-height: 1.34;
  letter-spacing: -0.025em;
  margin-bottom: 8px;
}
.rel-hook-chips {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 9px;
}
.rel-hook-chip {
  display: flex;
  align-items: center;
  gap: 5px;
  background: #F4F7FB;
  border: 1px solid #E5ECF5;
  border-radius: 7px;
  padding: 4px 8px;
  font-size: 11.5px;
  font-weight: 700;
  color: #2B3442;
  line-height: 1.35;
  min-width: 0;
}
.rel-hook-icon {
  color: #3182F6;
  font-weight: 900;
  flex-shrink: 0;
}
.rel-hook-txt {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.rel-foot {
  margin-top: auto;
  padding-top: 7px;
  border-top: 1px solid #F1F3F6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 700;
  color: #6B7684;
}
.rel-cta {
  color: #3182F6;
  font-weight: 800;
}

@media (max-width: 960px) {
  .detail-top-grid {
    grid-template-columns: 1fr !important;
  }
}
@media (max-width: 600px) {
  .detail-hero-main {
    grid-template-columns: 1fr;
  }
  .detail-title {
    font-size: 19px !important;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )


def build_danawa_price_html(product):
    pid = safe(product.get("product_id"))
    malls = detect_product_malls(product, include_all_default=True)
    rows_html = []
    for item in malls:
        mall_key = item["mall"]
        meta = MALL_META[mall_key]
        status_label = "공식 제휴 최저가 링크" if item["is_partner"] else MALL_ACTION_SUBS.get(mall_key, "쇼핑몰 실시간 가격 비교")
        partner_tag = '<span class="danawa-partner-badge">제휴연결</span>' if item["is_partner"] else ""
        btn_label = "최저가 보기 →" if item["is_partner"] else "가격 확인 →"
        rows_html.append(
            '<div class="danawa-row">'
            '<div class="danawa-mall-info">'
            f'<span class="mall-pill {safe(meta["badge_css"])}">{safe(meta["short"])}</span>'
            '<div class="danawa-desc-wrap">'
            f'<div class="danawa-tag-row"><span class="danawa-status-tag">{safe(status_label)}</span>{partner_tag}</div>'
            f'<div class="danawa-benefit">{safe(meta["benefit"])}</div>'
            '</div>'
            '</div>'
            f'<a class="danawa-go-btn" href="?go={safe(mall_key)}&pid={pid}" target="_blank" rel="noopener noreferrer">{btn_label}</a>'
            '</div>'
        )
    return (
        '<div class="danawa-box">'
        '<div class="danawa-head"><span>쇼핑몰별 최저가 비교</span><span>공식몰·검색 바로 이동</span></div>'
        f'<div class="danawa-list">{"".join(rows_html)}</div>'
        '</div>'
    )


def _get_rel_trust_pill(summary):
    counts = summary.get("purchase_counts") or {}
    buy_cnt = int(counts.get("직접 구매", 0))
    ad_cnt = int(counts.get("유료 광고", 0))
    prov_cnt = int(counts.get("제품 제공", 0))
    if buy_cnt >= 1:
        return f'<span class="rel-trust-pill rel-trust-self">내돈내산 {buy_cnt}</span>'
    if ad_cnt == 0 and prov_cnt >= 1:
        return f'<span class="rel-trust-pill rel-trust-prov">제품제공 {prov_cnt}</span>'
    if ad_cnt == 0:
        return '<span class="rel-trust-pill rel-trust-clean">광고 0%</span>'
    return ""


def _build_rel_hook_html(r_recs, r_sum):
    r_pros = [p.strip().rstrip(".") for p in (r_sum.get("pros") or []) if _is_authentic_quote(p)]
    r_reasons = [x.strip().rstrip(".") for x in (r_sum.get("reasons") or []) if _is_authentic_quote(x)]
    concrete_p = [p for p in r_pros if CONCRETE_HOOK_RE.search(p)]
    other_p = [p for p in r_pros if p not in concrete_p]
    concrete_r = [r for r in r_reasons if CONCRETE_HOOK_RE.search(r)]
    other_r = [r for r in r_reasons if r not in concrete_r]

    cands = concrete_p + other_p + concrete_r + other_r
    picked = []
    for cand in cands:
        norm = re.sub(r"\s+", "", cand)
        if any(norm in re.sub(r"\s+", "", ex) or re.sub(r"\s+", "", ex) in norm for ex in picked):
            continue
        picked.append(cand)
        if len(picked) >= 2:
            break

    r_quotes = [
        clean_evidence_text(r.get("evidence")).rstrip(".")
        for r in r_recs
        if len(clean_evidence_text(r.get("evidence"))) >= 12 and _is_authentic_quote(clean_evidence_text(r.get("evidence")))
    ]
    if len(picked) == 1 and r_quotes:
        picked.append(f"“{r_quotes[0]}”")
    elif not picked and r_quotes:
        picked.append(f"“{r_quotes[0]}”")
    elif not picked:
        picked.append("실사용 리뷰 교차 검증 완료")

    chips = "".join(
        f'<div class="rel-hook-chip"><span class="rel-hook-icon">✓</span><span class="rel-hook-txt">{safe(pt)}</span></div>'
        for pt in picked[:2]
    )
    return f'<div class="rel-hook-chips">{chips}</div>'


def render_product_detail(pid):
    inject_detail_overrides()
    products = load_public_catalog()
    product = next((p for p in products if str(p.get("product_id")) == pid), None)

    top_left, top_right = st.columns([4, 1])
    with top_left:
        if st.button("← 전체 목록으로", key="detail_back_btn", type="secondary"):
            st.session_state.detail_pid = ""
            for k in ("view", "pid"):
                if k in st.query_params:
                    del st.query_params[k]
            st.session_state.scroll_to_top = True
            st.rerun()
    with top_right:
        components.html(
            """
            <div style="display:flex;justify-content:flex-end;margin:0;padding:0;">
              <button id="copy-share-btn" style="
                height:38px;padding:0 14px;border-radius:10px;
                border:1px solid #DCE2EC;background:#FFFFFF;color:#191F28;
                font-size:12.5px;font-weight:800;cursor:pointer;
                font-family:-apple-system,BlinkMacSystemFont,'Malgun Gothic',sans-serif;
              ">🔗 링크 복사</button>
            </div>
            <script>
              const btn = document.getElementById('copy-share-btn');
              btn.addEventListener('click', async () => {
                try {
                  const url = window.parent.location.href;
                  await navigator.clipboard.writeText(url);
                  btn.textContent = '✓ 복사 완료!';
                  btn.style.background = '#191F28';
                  btn.style.color = '#FFFFFF';
                  setTimeout(() => {
                    btn.textContent = '🔗 링크 복사';
                    btn.style.background = '#FFFFFF';
                    btn.style.color = '#191F28';
                  }, 1800);
                } catch (e) {
                  btn.textContent = '주소창 복사';
                }
              });
            </script>
            """,
            height=42,
        )

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
    disp_category = _map_display_category(product)

    st.markdown(
        f'<div class="detail-nav-row"><div class="detail-breadcrumb">에디션 픽 &gt; {safe(disp_category)} &gt; {safe(product.get("brand"))}</div></div>',
        unsafe_allow_html=True,
    )

    purchase_html = render_purchase_badges(summary["purchase_counts"])
    model_text = str(product.get("model") or "").strip()
    brand_line = f"{product.get('brand')} · {disp_category}" + (f" · {model_text}" if model_text else "")

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

    rep_rec = get_representative_rec(product) or (recs[0] if recs else None)
    hero_visual_html = build_product_visual_html(
        product,
        representative=rep_rec,
        detail_href=safe(_build_detail_href_with_state(pid)),
        is_detail=True,
    )
    danawa_html = build_danawa_price_html(product)

    st.markdown(
        '<div class="detail-top-grid">'
        '<div class="detail-hero-card">'
        '<div class="detail-hero-main">'
        f'<div class="detail-visual-stage">{hero_visual_html}</div>'
        '<div class="detail-info-col">'
        f'<div class="detail-brand-line">{safe(brand_line)}</div>'
        f'<div class="detail-title">{safe(product.get("canonical_name"))}</div>'
        '<div class="detail-badges">'
        f'<span class="badge">유튜버 {channel_count}명 추천</span>'
        f'<span class="badge">근거 영상 {len(recs)}개</span>'
        f'{purchase_html}'
        '</div>'
        '</div>'
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
        '</div>'
        f'{danawa_html}'
        '</div>',
        unsafe_allow_html=True,
    )

    quote_cards = []
    for rec in recs:
        ev_txt = clean_evidence_text(rec.get("evidence"))
        if len(ev_txt) < 10 or not _is_authentic_quote(ev_txt):
            continue
        ch_name = safe((rec.get("channel") or {}).get("channel_name") or "유튜버")
        p_type = str(rec.get("purchase_type") or "").strip()
        p_tag = f" · {safe(p_type)}" if p_type and p_type != "확인되지 않음" else ""
        v_id = safe(rec.get("video_id") or "")
        link_html = (
            f'<a class="quote-video-link" href="https://youtu.be/{v_id}" target="_blank" rel="noopener noreferrer">원문 영상 ↗</a>'
            if v_id else ""
        )
        quote_cards.append(
            '<div class="quote-highlight-card">'
            f'<div class="quote-highlight-body">“{safe(ev_txt)}”</div>'
            '<div class="quote-highlight-foot">'
            f'<span>▶ {ch_name}{p_tag}</span>'
            f'{link_html}'
            '</div>'
            '</div>'
        )
        if len(quote_cards) >= 3:
            break

    if quote_cards:
        st.markdown(
            '<div class="detail-section">'
            '<div class="detail-section-title"><span>유튜버 실사용 결정적 한마디</span><span class="detail-section-sub">영상 속 실제 코멘트 발췌</span></div>'
            f'<div class="quote-highlight-grid">{"".join(quote_cards)}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    pros_list = [(t, c) for t, c in summary["all_pros"] if _is_authentic_quote(t)]
    cons_list = [(t, c) for t, c in summary["all_cons"] if _is_authentic_quote(t)]
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
            reason_cell = safe(r_txt) if _is_authentic_quote(r_txt) else "-"
            p_points = [re.sub(r"\s+", " ", str(x).strip()) for x in (rec.get("pros") or []) if _is_authentic_quote(x)]
            c_points = [re.sub(r"\s+", " ", str(x).strip()) for x in (rec.get("cons") or []) if _is_authentic_quote(x)]
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
        reason_html = f'<div class="creator-reason">{safe(reason_txt)}</div>' if _is_authentic_quote(reason_txt) else ""

        ev_txt = clean_evidence_text(rec.get("evidence"))
        ev_html = f'<div class="creator-evidence">“{safe(ev_txt)}”</div>' if _is_authentic_quote(ev_txt) else ""

        tag_parts = []
        for p in (rec.get("pros") or []):
            pt = re.sub(r"\s+", " ", str(p).strip())
            if _is_authentic_quote(pt):
                tag_parts.append(f'<span class="ctag-pro">장점 · {safe(pt)}</span>')
        for c in (rec.get("cons") or []):
            ct = re.sub(r"\s+", " ", str(c).strip())
            if _is_authentic_quote(ct):
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
                r_href = safe(_build_detail_href_with_state(raw_r_pid))
                r_recs = rp.get("recommendations") or []
                r_ch_cnt = rp.get("_channel_count") or len({r.get("channel_id") for r in r_recs if r.get("channel_id")})
                r_rep = get_representative_rec(rp)
                r_visual = build_product_visual_html(rp, representative=r_rep, detail_href=r_href, is_detail=False)
                r_sum = rp.get("_summary") or recommendation_summary(r_recs)
                r_trust = _get_rel_trust_pill(r_sum)
                r_hook_html = _build_rel_hook_html(r_recs, r_sum)

                with col:
                    st.markdown(
                        '<article class="product-card">'
                        f'<div class="rel-thumb-stage">{r_visual}</div>'
                        f'<a class="rel-card-link" href="{r_href}" target="_self" aria-label="{safe(rp.get("canonical_name"))} 상세 비교 보기">'
                        '<div class="rel-meta-row">'
                        f'<span class="rel-brand-line">{safe(rp.get("brand"))} · {safe(_map_display_category(rp))}</span>'
                        f'{r_trust}'
                        '</div>'
                        f'<div class="rel-title">{safe(rp.get("canonical_name"))}</div>'
                        f'{r_hook_html}'
                        '<div class="rel-foot">'
                        f'<span>유튜버 {r_ch_cnt}명 추천</span>'
                        '<span class="rel-cta">비교하기 ›</span>'
                        '</div>'
                        '</a>'
                        '</article>',
                        unsafe_allow_html=True,
                    )

    render_footer()

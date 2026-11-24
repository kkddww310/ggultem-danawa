import html
import json
import re
from collections import Counter
from urllib.parse import quote

import requests
import streamlit as st


def secret(name):
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


SUPABASE_URL = secret("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = secret("SUPABASE_SERVICE_ROLE_KEY")
CATEGORIES = ["IT·전자", "뷰티", "패션", "생활·살림", "주방", "여행", "자동차", "운동·건강", "육아", "반려동물", "기타"]
IMAGE_SOURCES = ["", "brand_official", "affiliate", "manual", "youtube_thumbnail"]
IMAGE_SOURCE_LABELS = {
    "": "출처 미선택",
    "brand_official": "브랜드 공식",
    "affiliate": "제휴사 제공",
    "manual": "직접 확인",
    "youtube_thumbnail": "유튜브 썸네일",
}
CATEGORY_VISUALS = {
    "IT·전자": ("IT", "#EEF3FA", "#335C99"),
    "뷰티": ("BEAUTY", "#FBF1EC", "#9E532B"),
    "패션": ("FASHION", "#F3EFFB", "#5E439C"),
    "생활·살림": ("LIVING", "#EDF6F1", "#266B4E"),
    "주방": ("KITCHEN", "#FAF4E6", "#8C5B0E"),
    "여행": ("TRAVEL", "#EBF5F7", "#20626E"),
    "자동차": ("AUTO", "#EFF1F4", "#475261"),
    "운동·건강": ("HEALTH", "#FAEEEE", "#963333"),
    "육아": ("KIDS", "#FAF2EA", "#99531D"),
    "반려동물": ("PET", "#F2F5EA", "#566624"),
    "기타": ("PICK", "#F1F3F6", "#525E6C"),
}
INVALID_POINT_PATTERNS = (
    "원문에", "명시됨", "후기는 없음", "후기 없음", "언급 없음",
    "정보가 없음", "확인되지 않", "알 수 없", "단점 없음", "장점 없음",
)
SEARCH_SYNONYMS = {
    "태블릿": ["pad", "탭", "아이패드", "갤럭시탭", "tablet"],
    "노트북": ["laptop", "맥북", "macbook", "그램", "갤럭시북"],
    "이어폰": ["버즈", "에어팟", "earbuds", "earphone"],
    "헤드폰": ["헤드셋", "headphone", "headset"],
    "청소기": ["다이슨", "dyson", "로봇청소기", "물걸레"],
    "키보드": ["keyboard"],
    "마우스": ["mouse"],
    "보조배터리": ["파워뱅크", "powerbank", "맥세이프"],
    "패딩": ["다운", "푸퍼", "파카", "점퍼", "down", "puffer", "parka"],
    "가방": ["백", "숄더백", "토트백", "크로스백", "핸드백", "에코백", "백팩", "bag"],
    "신발": ["스니커즈", "운동화", "로퍼", "부츠", "구두", "슬리퍼", "샌들", "shoes", "sneakers"],
}
EXTRA_MALLS = ("naver", "oliveyoung", "musinsa", "29cm", "zigzag", "ably")
MALL_META = {
    "naver": {
        "label": "네이버쇼핑",
        "short": "네이버쇼핑",
        "css": "shop-btn-naver",
        "badge_css": "mall-pill-naver",
        "benefit": "네이버페이 포인트 적립 · 스마트스토어/백화점 가격비교",
    },
    "coupang": {
        "label": "쿠팡 검색",
        "short": "쿠팡",
        "css": "shop-btn-coupang",
        "badge_css": "mall-pill-coupang",
        "benefit": "로켓배송 · 와우회원 무료배송 및 빠른 반품",
    },
    "oliveyoung": {
        "label": "올리브영",
        "short": "올리브영",
        "css": "shop-btn-oliveyoung",
        "badge_css": "mall-pill-oliveyoung",
        "benefit": "오늘드림 당일배송 · 올리브영 공식 멤버십 혜택",
    },
    "musinsa": {
        "label": "무신사",
        "short": "무신사",
        "css": "shop-btn-musinsa",
        "badge_css": "mall-pill-musinsa",
        "benefit": "무신사 전 상품 무료배송 · 회원 등급 할인",
    },
    "29cm": {
        "label": "29CM",
        "short": "29CM",
        "css": "shop-btn-29cm",
        "badge_css": "mall-pill-29cm",
        "benefit": "감도 깊은 셀렉트샵 · 쿠폰 및 적립금 혜택",
    },
    "zigzag": {
        "label": "지그재그",
        "short": "지그재그",
        "css": "shop-btn-zigzag",
        "badge_css": "mall-pill-zigzag",
        "benefit": "직진배송 빠른도착 · 스토어 통합 결제",
    },
    "ably": {
        "label": "에이블리",
        "short": "에이블리",
        "css": "shop-btn-ably",
        "badge_css": "mall-pill-ably",
        "benefit": "전 상품 무료배송 · 앱 전용 할인 쿠폰",
    },
}
AFFILIATE_DISCLOSURE = (
    "에디션 픽은 쿠팡 파트너스, 네이버 쇼핑 커넥트, 올리브영 쇼핑 큐레이터 등 "
    "제휴 마케팅 활동의 일환으로, 링크를 통한 구매 시 일정액의 수수료를 제공받을 수 있습니다."
)


def headers(prefer=None):
    result = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
    if SUPABASE_KEY.startswith("eyJ"):
        result["Authorization"] = f"Bearer {SUPABASE_KEY}"
    if prefer:
        result["Prefer"] = prefer
    return result


def api_get(table, fields="*", params=None):
    query = {"select": fields}
    query.update(params or {})
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers(), params=query, timeout=30)
    if not response.ok:
        raise RuntimeError(f"{table} 조회 실패: HTTP {response.status_code} · {response.text[:250]}")
    return response.json()


def api_post(table, values):
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers("return=minimal"),
        json=values,
        timeout=10,
    )
    if not response.ok:
        raise RuntimeError(f"{table} 저장 실패: HTTP {response.status_code}")


def api_get_all(table, fields="*", params=None, max_rows=10000):
    rows = []
    offset = 0
    step = 1000
    while offset < max_rows:
        query = dict(params or {})
        query["limit"] = str(step)
        query["offset"] = str(offset)
        batch = api_get(table, fields, query)
        rows.extend(batch)
        if len(batch) < step:
            break
        offset += step
    return rows


def fetch_by_ids(table, fields, id_col, ids):
    clean_ids = list(dict.fromkeys(str(i).strip() for i in ids if i))
    rows = []
    for start in range(0, len(clean_ids), 50):
        chunk = clean_ids[start:start + 50]
        rows.extend(api_get(table, fields, {id_col: f"in.({','.join(chunk)})", "limit": "1000"}))
    return rows


def api_patch(table, values, params):
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers("return=representation"),
        params=params,
        json=values,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"{table} 수정 실패: HTTP {response.status_code} · {response.text[:250]}")
    return response.json() if response.text else []


def safe(value):
    return html.escape(str(value or ""), quote=True)


def norm_key(value):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").lower())


def clean_evidence_text(value):
    text = re.sub(r"https?://\S+", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip(" ·,-/")
    return text


def format_korean_count(value):
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    if n >= 10000:
        man = n / 10000
        return f"{man:.1f}만".rstrip("0").rstrip(".")
    if n >= 1000:
        cheon = n / 1000
        return f"{cheon:.1f}천".rstrip("0").rstrip(".")
    return f"{n:,}"


def count_by(rows, key):
    return Counter(str(row.get(key) or "unknown") for row in rows)


def is_meaningful_point(text):
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if len(cleaned) < 2:
        return False
    return not any(pattern in cleaned for pattern in INVALID_POINT_PATTERNS)


def score_product_search(product, query):
    tokens = [t.strip().lower() for t in str(query or "").split() if t.strip()]
    if not tokens:
        return 1

    primary_text = " ".join([
        str(product.get("canonical_name") or ""),
        str(product.get("brand") or ""),
        str(product.get("model") or ""),
        str(product.get("search_keyword") or ""),
    ]).lower()

    meta_text = " ".join([
        str(product.get("category") or ""),
        " ".join(
            str((r.get("channel") or {}).get("channel_name") or "")
            for r in (product.get("recommendations") or [])
        ),
    ]).lower()

    review_parts = []
    for r in (product.get("recommendations") or []):
        reason = str(r.get("reason") or "").strip()
        if is_meaningful_point(reason):
            review_parts.append(reason)
        for p in (r.get("pros") or []):
            if is_meaningful_point(p):
                review_parts.append(str(p))
        for c in (r.get("cons") or []):
            if is_meaningful_point(c):
                review_parts.append(str(c))
    review_text = " ".join(review_parts).lower()

    total_score = 0
    for token in tokens:
        synonyms = SEARCH_SYNONYMS.get(token, [])
        if token in primary_text:
            total_score += 10
        elif any(syn in primary_text for syn in synonyms):
            total_score += 6
        elif token in meta_text:
            total_score += 4
        elif token in review_text or any(syn in review_text for syn in synonyms):
            total_score += 2
        else:
            return 0
    return total_score


def parse_extra_partner_links(product):
    raw = str(product.get("affiliate_note") or "").strip()
    links = {mall: "" for mall in EXTRA_MALLS}
    memo = ""
    if not raw:
        return links, memo
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                for mall in EXTRA_MALLS:
                    url = str(data.get(mall) or "").strip()
                    if url.startswith(("https://", "http://")):
                        links[mall] = url
                memo = str(data.get("memo") or "").strip()
                return links, memo
        except Exception:
            pass
    memo = raw
    return links, memo


def serialize_extra_partner_links(links, memo=""):
    clean_links = {
        mall: str(links.get(mall) or "").strip()
        for mall in EXTRA_MALLS
        if str(links.get(mall) or "").strip().startswith(("https://", "http://"))
    }
    clean_memo = str(memo or "").strip()
    if not clean_links:
        return clean_memo or None
    payload = dict(clean_links)
    if clean_memo:
        payload["memo"] = clean_memo
    return json.dumps(payload, ensure_ascii=False)


def detect_product_malls(product, include_all_default=False):
    extra_links, _ = parse_extra_partner_links(product)
    has_coupang_partner = bool(
        product.get("affiliate_verified")
        and str(product.get("coupang_url") or "").startswith("https://link.coupang.com/")
    )
    has_naver_partner = bool(extra_links.get("naver"))
    category = str(product.get("category") or "").strip()

    buttons = [
        {
            "mall": "naver",
            "label": "네이버 최저가" if has_naver_partner else "네이버쇼핑",
            "css": "shop-btn-naver",
            "is_partner": has_naver_partner,
        }
    ]

    if include_all_default or category != "패션" or has_coupang_partner:
        buttons.append(
            {
                "mall": "coupang",
                "label": "쿠팡 최저가" if has_coupang_partner else "쿠팡 검색",
                "css": "shop-btn-coupang",
                "is_partner": has_coupang_partner,
            }
        )

    if extra_links.get("oliveyoung") or (include_all_default and category == "뷰티"):
        buttons.append(
            {
                "mall": "oliveyoung",
                "label": MALL_META["oliveyoung"]["label"],
                "css": MALL_META["oliveyoung"]["css"],
                "is_partner": bool(extra_links.get("oliveyoung")),
            }
        )

    fashion_malls = ("musinsa", "29cm", "zigzag", "ably")
    registered_fashion = [m for m in fashion_malls if extra_links.get(m)]
    if registered_fashion:
        for mall_key in registered_fashion:
            buttons.append(
                {
                    "mall": mall_key,
                    "label": MALL_META[mall_key]["label"],
                    "css": MALL_META[mall_key]["css"],
                    "is_partner": True,
                }
            )
    elif include_all_default and category == "패션":
        buttons.append(
            {
                "mall": "musinsa",
                "label": MALL_META["musinsa"]["label"],
                "css": MALL_META["musinsa"]["css"],
                "is_partner": False,
            }
        )

    return buttons


def get_page_numbers(current_page, total_pages):
    if total_pages <= 5:
        return list(range(1, total_pages + 1))
    if current_page <= 3:
        return [1, 2, 3, 4, total_pages]
    if current_page >= total_pages - 2:
        return [1, total_pages - 3, total_pages - 2, total_pages - 1, total_pages]
    return [1, current_page - 1, current_page, current_page + 1, total_pages]


def log_event(event_type, product_id=None, product_name=None, search_query=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        payload = {
            "event_type": event_type,
            "product_id": product_id or None,
            "product_name": (str(product_name).strip()[:200] if product_name else None),
            "search_query": (str(search_query).strip()[:120] if search_query else None),
        }
        api_post("click_logs", [payload])
    except Exception:
        pass


def handle_click_redirect():
    go_type = str(st.query_params.get("go", "")).strip()
    go_pid = str(st.query_params.get("pid", "")).strip()
    valid_malls = {"coupang", "naver", "oliveyoung", "musinsa", "29cm", "zigzag", "ably"}
    if go_type not in valid_malls or not go_pid:
        return

    rows = []
    try:
        rows = api_get(
            "products",
            "product_id,canonical_name,search_keyword,coupang_url,affiliate_verified,affiliate_note",
            {"product_id": f"eq.{go_pid}", "limit": "1"},
        )
    except Exception:
        rows = []

    product = rows[0] if rows else {}
    log_name = str(product.get("canonical_name") or product.get("search_keyword") or "").strip()
    search_term = str(product.get("search_keyword") or product.get("canonical_name") or "").strip()
    query_name = quote(search_term)
    extra_links, _ = parse_extra_partner_links(product)

    if go_type == "coupang":
        affiliate = bool(
            product.get("affiliate_verified")
            and str(product.get("coupang_url") or "").startswith("https://link.coupang.com/")
        )
        target_url = product["coupang_url"] if affiliate else f"https://www.coupang.com/np/search?q={query_name}"
    elif go_type == "naver":
        target_url = extra_links.get("naver") or f"https://search.shopping.naver.com/search/all?query={query_name}"
    elif go_type == "oliveyoung":
        target_url = extra_links.get("oliveyoung") or f"https://www.oliveyoung.co.kr/store/search/getSearchMain.do?query={query_name}"
    elif go_type == "musinsa":
        target_url = extra_links.get("musinsa") or f"https://www.musinsa.com/search/goods?keyword={query_name}"
    elif go_type == "29cm":
        target_url = extra_links.get("29cm") or f"https://shop.29cm.co.kr/search?keyword={query_name}"
    elif go_type == "zigzag":
        target_url = extra_links.get("zigzag") or f"https://zigzag.kr/search?keyword={query_name}"
    else:
        target_url = extra_links.get("ably") or f"https://m.a-bly.com/search?keyword={query_name}"

    log_event(f"{go_type}_click", product_id=go_pid if product else None, product_name=log_name or None)
    safe_url = html.escape(target_url, quote=True)
    js_url = json.dumps(target_url)
    st.markdown(
        f'<meta http-equiv="refresh" content="0;url={safe_url}">'
        f'<script>window.location.replace({js_url});</script>'
        f'<div style="padding:32px 16px;text-align:center;font-size:14px;color:#4E5968">'
        f'쇼핑몰 페이지로 이동 중입니다... <a href="{safe_url}">바로 이동하기</a></div>',
        unsafe_allow_html=True,
    )
    st.stop()


@st.cache_data(ttl=300, show_spinner=False)
def load_public_data():
    products = api_get_all(
        "products",
        "product_id,canonical_name,brand,model,category,search_keyword,coupang_url,affiliate_verified,affiliate_note,image_url,image_source,image_verified,image_checked_at,image_note,created_at",
        {"review_status": "eq.approved", "is_visible": "eq.true", "order": "created_at.desc"},
        max_rows=3000,
    )
    recs = api_get_all(
        "recommendations",
        "recommendation_id,product_id,video_id,channel_id,reason,pros,cons,evidence,confidence,purchase_type,created_at",
        {"order": "created_at.desc"},
        max_rows=10000,
    )
    video_ids = [r.get("video_id") for r in recs if r.get("video_id")]
    channel_ids = [r.get("channel_id") for r in recs if r.get("channel_id")]
    videos = fetch_by_ids("videos", "video_id,title,view_count,published_at", "video_id", video_ids)
    channels = fetch_by_ids("channels", "channel_id,channel_name,subscriber_count", "channel_id", channel_ids)
    video_map = {row["video_id"]: row for row in videos}
    channel_map = {row["channel_id"]: row for row in channels}
    grouped = {}
    for rec in recs:
        item = dict(rec)
        item["video"] = video_map.get(rec.get("video_id"), {})
        item["channel"] = channel_map.get(rec.get("channel_id"), {})
        grouped.setdefault(rec.get("product_id"), []).append(item)
    for product in products:
        product["recommendations"] = grouped.get(product["product_id"], [])
    products.sort(
        key=lambda p: (len({r.get("channel_id") for r in p["recommendations"]}), len(p["recommendations"])),
        reverse=True,
    )
    return products


def is_single_product_video(product, rec):
    title_norm = norm_key((rec.get("video") or {}).get("title"))
    if not title_norm:
        return False
    brand_norm = norm_key(product.get("brand"))
    model_norm = norm_key(product.get("model"))
    return bool(
        (len(brand_norm) >= 2 and brand_norm in title_norm)
        or (len(model_norm) >= 2 and model_norm in title_norm)
    )


def sort_recommendations(product, recommendations):
    return sorted(
        recommendations or [],
        key=lambda rec: (
            1 if is_single_product_video(product, rec) else 0,
            int((rec.get("video") or {}).get("view_count") or 0),
            float(rec.get("confidence") or 0),
            str((rec.get("video") or {}).get("published_at") or ""),
        ),
        reverse=True,
    )


def get_representative_rec(product):
    ranked = sort_recommendations(product, product.get("recommendations") or [])
    return next((rec for rec in ranked if rec.get("video_id")), None)


def render_product_visual(product, representative=None, link_to_detail=False):
    if representative is None:
        representative = get_representative_rec(product)
    video_id = safe((representative or {}).get("video_id") or "")
    video_href = f"https://youtu.be/{video_id}" if video_id else ""

    image_url = str(product.get("image_url") or "").strip()
    if product.get("image_verified") and image_url.startswith(("https://", "http://")):
        img_tag = f'<img class="video-thumbnail" src="{safe(image_url)}" alt="{safe(product.get("canonical_name"))}">'
        if link_to_detail:
            badge_html = (
                f'<a class="thumb-video-badge" href="{video_href}" target="_blank" rel="noopener noreferrer" title="추천 유튜브 영상 바로 보기">▶ 영상 보기</a>'
                if video_href else ""
            )
            st.markdown(
                f'<div class="video-thumbnail-wrap thumb-pass-through">{img_tag}{badge_html}</div>',
                unsafe_allow_html=True,
            )
        elif video_href:
            st.markdown(
                f'<a class="video-thumbnail-wrap" href="{video_href}" target="_blank" rel="noopener noreferrer" title="추천 유튜브 영상 바로 보기">'
                f'{img_tag}<span class="thumb-video-badge">▶ 영상 보기</span></a>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f'<div class="video-thumbnail-wrap">{img_tag}</div>', unsafe_allow_html=True)
        return

    if video_id:
        hd_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        fallback_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        img_tag = f'<img class="video-thumbnail" src="{hd_url}" onerror="this.onerror=null;this.src=\'{fallback_url}\';" alt="추천 영상 썸네일">'
        if link_to_detail:
            st.markdown(
                f'<div class="video-thumbnail-wrap thumb-pass-through">{img_tag}'
                f'<a class="thumb-video-badge" href="{video_href}" target="_blank" rel="noopener noreferrer" title="추천 유튜브 영상 바로 보기">▶ 영상 보기</a>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<a class="video-thumbnail-wrap" href="{video_href}" target="_blank" rel="noopener noreferrer" title="추천 유튜브 영상 바로 보기">'
                f'{img_tag}<span class="thumb-video-badge">▶ 영상 보기</span></a>',
                unsafe_allow_html=True,
            )
        return

    category = product.get("category") or "기타"
    tag_en, background, color = CATEGORY_VISUALS.get(category, CATEGORY_VISUALS["기타"])
    pass_cls = " thumb-pass-through" if link_to_detail else ""
    st.markdown(
        f'<div class="product-placeholder{pass_cls}" style="background:{background};color:{color}">'
        f'<span>{safe(tag_en)}</span><small>{safe(category)}</small></div>',
        unsafe_allow_html=True,
    )


def recommendation_summary(recommendations):
    purchase_counts = Counter()
    pros = Counter()
    cons = Counter()
    reasons = []
    seen_reasons = set()
    for rec in recommendations:
        purchase_counts[str(rec.get("purchase_type") or "확인되지 않음").strip()] += 1
        reason_text = re.sub(r"\s+", " ", str(rec.get("reason") or "").strip())
        if is_meaningful_point(reason_text):
            r_key = norm_key(reason_text)
            if r_key and r_key not in seen_reasons:
                seen_reasons.add(r_key)
                reasons.append(reason_text)
        for value in rec.get("pros") or []:
            text = re.sub(r"\s+", " ", str(value).strip())
            if is_meaningful_point(text):
                pros[text] += 1
        for value in rec.get("cons") or []:
            text = re.sub(r"\s+", " ", str(value).strip())
            if is_meaningful_point(text):
                cons[text] += 1
    return {
        "purchase_counts": purchase_counts,
        "pros": [text for text, _ in pros.most_common(3)],
        "cons": [text for text, _ in cons.most_common(3)],
        "all_pros": pros.most_common(12),
        "all_cons": cons.most_common(12),
        "reasons": reasons[:6],
    }


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


def render_mall_buttons(product):
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
    st.markdown(f'<div class="{grid_cls}">{btn_html}</div>', unsafe_allow_html=True)


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


def inject_styles():
    st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

:root{
  --brand:#2563EB;
  --brand-dark:#1D4ED8;
  --soft:#EFF6FF;
  --ink:#14181F;
  --sub:#4B5563;
  --muted:#8A94A6;
  --line:#E6E9EF;
  --canvas:#F6F7F9;
}
html,body,.stApp,button,input,select,textarea{
  font-family:'Pretendard',-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',sans-serif!important;
}
html,body,.stApp{background:var(--canvas);color:var(--ink);overflow-x:hidden!important}
.block-container{max-width:1180px;padding:1.15rem 1rem 4rem;box-sizing:border-box}

#MainMenu,footer,header,header[data-testid="stHeader"],[data-testid="stHeader"],[data-testid="stAppHeader"],
[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],
.viewerBadge_container__r5tak,.styles_viewerBadge__CvC9N{
  display:none!important;visibility:hidden!important;height:0!important;max-height:0!important;min-height:0!important;
  border:0!important;box-shadow:none!important;background:transparent!important;
}
[data-testid="stElementContainer"]:has(iframe[height="0"]),[data-testid="stIFrame"]:has(iframe[height="0"]){
  display:none!important;height:0!important;margin:0!important;padding:0!important;
}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],section.main,[data-testid="stMainBlockContainer"]{
  padding-top:0!important;margin-top:0!important;border-top:0!important;outline:0!important;box-shadow:none!important;
}
.stApp::before,.stApp::after,[data-testid="stAppViewContainer"]::before,[data-testid="stAppViewContainer"]::after,
[data-testid="stMain"]::before,[data-testid="stMain"]::after,section.main::before,section.main::after{
  display:none!important;content:none!important;border:0!important;box-shadow:none!important;
}

/* 상단 브랜드 헤더 */
.top-nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;padding:2px 2px}
.brand-wrap{display:inline-flex;align-items:center;gap:9px;text-decoration:none!important;color:inherit!important}
.brand-logo{display:inline-flex;align-items:center;justify-content:center;width:33px;height:33px;border-radius:10px;background:#14181F;color:#fff;font-size:15px;font-weight:800;box-shadow:0 3px 10px rgba(20,24,31,.14)}
.brand-name{font-size:20px;font-weight:850;letter-spacing:-.03em;color:var(--ink)}
.brand-en{font-size:10.5px;font-weight:750;letter-spacing:.09em;color:#525E6C;background:#ECEFF4;padding:3px 8px;border-radius:999px}
.top-sub{font-size:12.5px;font-weight:600;color:var(--muted);letter-spacing:-.01em}

/* 에디토리얼 히어로 배너 */
.hero-banner{
  background:linear-gradient(135deg,#FFFFFF 0%,#F8FAFC 65%,#F1F5FD 100%);
  border:1px solid #E5E9F2;
  border-radius:18px;
  padding:20px 22px;
  margin-bottom:8px;
  box-shadow:0 4px 18px rgba(15,23,42,.03);
}
.hero-kicker{font-size:11.5px;font-weight:700;color:var(--brand);letter-spacing:-.01em;margin-bottom:5px}
.hero-headline{font-size:21px;font-weight:800;letter-spacing:-.025em;color:var(--ink);line-height:1.35}
.hero-headline b{color:var(--brand);font-weight:850}
.hero-stats{display:flex;flex-wrap:wrap;align-items:center;gap:7px;margin-top:12px}
.stat-pill{display:inline-flex;align-items:center;gap:5px;background:#FFFFFF;border:1px solid #E6EAF0;padding:5px 11px;border-radius:999px;font-size:12px;font-weight:650;color:var(--sub);white-space:nowrap}
.stat-pill strong{color:var(--ink);font-weight:800}
.live-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#1F9D63}

.top-disclosure{
  margin:0 0 12px;
  padding:7px 12px;
  background:#FFFFFF;
  border:1px solid #EAEEF4;
  border-radius:10px;
  font-size:11.5px;
  font-weight:550;
  color:#647082;
  text-align:center;
  word-break:keep-all;
}

/* 검색 & 필터 바 */
div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  border:1px solid #DCE2EC!important;
  outline:0!important;
  background:#fff!important;
  box-shadow:0 1px 4px rgba(15,23,42,.025)!important;
  border-radius:12px!important;
  transition:border-color .15s,box-shadow .15s!important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
div[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within{
  border-color:#2563EB!important;
  box-shadow:0 0 0 3px rgba(37,99,235,.1)!important;
}
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] div[role="combobox"],
div[data-testid="stSelectbox"] div[role="combobox"] *{
  background:#fff!important;
  color:var(--ink)!important;
  -webkit-text-fill-color:var(--ink)!important;
  border:0!important;
  outline:0!important;
  font-size:13.5px!important;
}
div[data-testid="stSelectbox"] svg{fill:var(--sub)!important;color:var(--sub)!important}

.result-bar{display:flex;align-items:center;justify-content:space-between;margin:8px 2px 11px;font-size:12.5px;color:var(--sub);font-weight:600}
.result-bar b{color:var(--ink);font-weight:800}

/* 기본 컨테이너 & 버튼 */
div[data-testid="stVerticalBlockBorderWrapper"]{border:1px solid #E8ECF2!important;outline:0!important;background:#fff!important;border-radius:16px!important;box-shadow:0 2px 12px rgba(15,23,42,.03)!important;padding:16px!important;margin-bottom:12px!important}
.stButton>button,.stLinkButton>a{min-height:39px!important;border-radius:10px!important;font-weight:700!important;font-size:13px!important;transition:all .15s!important}
.stButton>button[kind="primary"],.stLinkButton>a[kind="primary"]{background:#14181F!important;border-color:#14181F!important;color:#fff!important}
.stButton>button[kind="primary"]:hover,.stLinkButton>a[kind="primary"]:hover{background:#2563EB!important;border-color:#2563EB!important}
.stButton>button[kind="secondary"],.stLinkButton>a[kind="secondary"]{background:#F3F5F8!important;border:1px solid #E4E8EF!important;color:#374151!important}
.stButton>button[kind="secondary"]:hover,.stLinkButton>a[kind="secondary"]:hover{background:#E9EDF3!important}

div[data-testid="stForm"]{border:1px solid #E2E8F2!important;background:#F9FAFC!important;border-radius:14px!important;padding:16px!important}
div[data-testid="stForm"] input,div[data-testid="stForm"] textarea,div[data-testid="stForm"] div[role="combobox"]{background:#fff!important;color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important}

/* 상품 그리드 & 카드 동일 높이 정렬 */
.st-key-product_grid,.st-key-related_grid{width:100%!important;max-width:100%!important;box-sizing:border-box!important}
.st-key-product_grid [data-testid="stHorizontalBlock"]{
  display:flex!important;
  gap:15px!important;
  align-items:stretch!important;
  width:100%!important;
  max-width:100%!important;
  margin:0 0 15px 0!important;
  padding:0!important;
  box-sizing:border-box!important;
}
.st-key-product_grid [data-testid="stColumn"],
.st-key-product_grid [data-testid="column"]{
  flex:1 1 0%!important;
  width:0!important;
  min-width:0!important;
  padding:0!important;
  display:flex!important;
  flex-direction:column!important;
  box-sizing:border-box!important;
}
.st-key-product_grid [data-testid="stColumn"] > div,
.st-key-product_grid [data-testid="column"] > div{
  flex:1 1 auto!important;
  display:flex!important;
  flex-direction:column!important;
  height:100%!important;
}
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"],
.st-key-related_grid div[data-testid="stVerticalBlockBorderWrapper"]{
  position:relative!important;
  flex:1 1 auto!important;
  width:100%!important;
  height:100%!important;
  box-sizing:border-box!important;
  border:1px solid #E6EAF0!important;
  background:#FFFFFF!important;
  border-radius:16px!important;
  box-shadow:0 2px 10px rgba(15,23,42,.025)!important;
  padding:12px!important;
  margin-bottom:0!important;
  display:flex!important;
  flex-direction:column!important;
  cursor:pointer!important;
  transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease!important;
}
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"]:hover,
.st-key-related_grid div[data-testid="stVerticalBlockBorderWrapper"]:hover{
  transform:translateY(-2px)!important;
  border-color:#CBD5E1!important;
  box-shadow:0 10px 26px rgba(15,23,42,.07)!important;
}
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"]:hover .product-title,
.st-key-related_grid div[data-testid="stVerticalBlockBorderWrapper"]:hover .related-name{
  color:#1D4ED8!important;
}
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] > div,
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"]{
  flex:1 1 auto!important;
  display:flex!important;
  flex-direction:column!important;
  height:100%!important;
  gap:8px!important;
  padding-bottom:0!important;
}
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:last-child{
  margin-top:auto!important;
  padding-top:2px!important;
}

/* 카드 전체 클릭용 투명 오버레이 링크 (영상 보기 / 쇼핑몰 버튼만 예외) */
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] > div,
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"],
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stElementContainer"],
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdown"],
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"],
.st-key-related_grid div[data-testid="stVerticalBlockBorderWrapper"] > div,
.st-key-related_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"],
.st-key-related_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stElementContainer"],
.st-key-related_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdown"],
.st-key-related_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"]{
  position:static!important;
}
.card-overlay-link{
  position:absolute!important;
  inset:0!important;
  z-index:2!important;
  border-radius:16px!important;
  text-decoration:none!important;
}

/* 썸네일: 이미지·여백은 카드 오버레이로 상세 이동 / 우측 하단 배지만 유튜브 이동 */
.video-thumbnail-wrap{
  position:relative!important;
  display:block;
  width:100%!important;
  aspect-ratio:16 / 9!important;
  margin:0!important;
  border-radius:11px!important;
  border:1px solid rgba(15,23,42,.06)!important;
  background:#F1F3F6!important;
  overflow:hidden!important;
  box-sizing:border-box!important;
}
.video-thumbnail-wrap.thumb-pass-through,
.product-placeholder.thumb-pass-through{
  z-index:3!important;
  pointer-events:none!important;
}
.video-thumbnail{
  display:block;
  width:100%!important;
  height:100%!important;
  object-fit:cover!important;
  object-position:center center!important;
  transition:transform .24s ease!important;
}
.st-key-product_grid div[data-testid="stVerticalBlockBorderWrapper"]:hover .video-thumbnail,
.st-key-related_grid div[data-testid="stVerticalBlockBorderWrapper"]:hover .video-thumbnail,
a.video-thumbnail-wrap:hover .video-thumbnail{
  transform:scale(1.025);
}
.thumb-video-badge{
  position:absolute!important;
  right:8px!important;
  bottom:8px!important;
  z-index:5!important;
  pointer-events:auto!important;
  display:inline-flex!important;
  align-items:center!important;
  gap:4px!important;
  padding:4px 9px!important;
  border-radius:999px!important;
  background:rgba(20,24,31,.78)!important;
  border:1px solid rgba(255,255,255,.16)!important;
  color:#FFFFFF!important;
  font-size:10.5px!important;
  font-weight:750!important;
  letter-spacing:-.01em!important;
  text-decoration:none!important;
  backdrop-filter:blur(6px);
  transition:background-color .15s ease,transform .15s ease!important;
}
.thumb-video-badge:hover{
  background:#DC2626!important;
  transform:scale(1.03);
}
.product-placeholder{
  position:relative!important;
  width:100%!important;
  aspect-ratio:16 / 9!important;
  margin:0!important;
  border-radius:11px!important;
  border:1px solid rgba(15,23,42,.05)!important;
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:4px;
  overflow:hidden!important;
  box-sizing:border-box!important;
}
.product-placeholder span{font-size:13px;font-weight:850;letter-spacing:.12em}
.product-placeholder small{font-size:12px;font-weight:700;opacity:.85}

/* 카드 본문 정보 블록 */
.card-info-block{
  display:flex!important;
  flex-direction:column!important;
  gap:7px!important;
  padding:1px 1px 0!important;
  width:100%!important;
  box-sizing:border-box!important;
}
.card-source-bar{
  display:flex!important;
  flex-direction:row!important;
  align-items:center!important;
  justify-content:space-between!important;
  gap:8px!important;
  width:100%!important;
  min-width:0!important;
}
.source-chip{
  display:inline-flex!important;
  align-items:center!important;
  gap:4px!important;
  min-width:0!important;
  max-width:62%!important;
  padding:2px 7px!important;
  border-radius:6px!important;
  background:#F3F5F8!important;
  color:#374151!important;
  font-size:11px!important;
  font-weight:700!important;
  white-space:nowrap!important;
  overflow:hidden!important;
  text-overflow:ellipsis!important;
}
.source-chip b{color:#DC2626;font-size:8.5px;flex-shrink:0}
.brand-eyebrow{
  display:inline-block!important;
  margin-left:auto!important;
  font-size:11px!important;
  font-weight:650!important;
  color:var(--muted)!important;
  letter-spacing:-.01em!important;
  white-space:nowrap!important;
  overflow:hidden!important;
  text-overflow:ellipsis!important;
  text-align:right!important;
  flex-shrink:0!important;
}

/* 2줄 고정 높이 상품명 */
.product-title{
  font-size:15px!important;
  font-weight:800!important;
  color:var(--ink)!important;
  line-height:1.38!important;
  min-height:2.76em!important;
  display:-webkit-box!important;
  -webkit-line-clamp:2!important;
  -webkit-box-orient:vertical!important;
  overflow:hidden!important;
  word-break:keep-all!important;
  transition:color .15s ease!important;
}

/* 1줄 가로 정렬 메타 배지 행 */
.card-meta-row{
  display:flex!important;
  flex-direction:row!important;
  flex-wrap:nowrap!important;
  align-items:center!important;
  gap:4px!important;
  width:100%!important;
  overflow:hidden!important;
}
.badge{
  display:inline-flex!important;
  align-items:center!important;
  height:21px!important;
  color:#334155!important;
  background:#F1F5F9!important;
  padding:0 6px!important;
  border-radius:6px!important;
  font-size:10.5px!important;
  font-weight:700!important;
  white-space:nowrap!important;
  flex-shrink:0!important;
}
.purchase-dot{
  display:inline-flex!important;
  align-items:center!important;
  gap:4px!important;
  height:21px!important;
  padding:0 6px!important;
  border-radius:6px!important;
  font-size:10.5px!important;
  font-weight:700!important;
  white-space:nowrap!important;
  flex-shrink:0!important;
}
.purchase-dot i{display:inline-block!important;width:5px!important;height:5px!important;border-radius:50%!important;flex-shrink:0!important}
.purchase-buy{color:#166534!important;background:#ECFDF5!important}.purchase-buy i{background:#16A34A!important}
.purchase-provided{color:#854D0E!important;background:#FEFCE8!important}.purchase-provided i{background:#CA8A04!important}
.purchase-ad,.purchase-unknown{color:#991B1B!important;background:#FEF2F2!important}.purchase-ad i,.purchase-unknown i{background:#DC2626!important}

/* 에디토리얼 장단점 요약 */
.card-summary-wrap{
  display:flex!important;
  flex-direction:column!important;
  gap:4px!important;
  width:100%!important;
}
.st-key-product_grid .summary-line{
  display:flex!important;
  flex-direction:row!important;
  align-items:center!important;
  gap:6px!important;
  margin:0!important;
  padding:5px 8px!important;
  border-radius:7px!important;
  font-size:11.5px!important;
  line-height:1.35!important;
  white-space:nowrap!important;
  overflow:hidden!important;
  text-overflow:ellipsis!important;
}
.summary-text{
  min-width:0!important;
  overflow:hidden!important;
  text-overflow:ellipsis!important;
  white-space:nowrap!important;
}
.sum-tag{
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  height:17px!important;
  padding:0 5px!important;
  border-radius:4px!important;
  font-size:10px!important;
  font-weight:800!important;
  flex-shrink:0!important;
  letter-spacing:-.02em!important;
}
.summary-pro{background:#F4F9F6!important;color:#1F513B!important}
.sum-tag-pro{background:#DCFCE7!important;color:#166534!important}
.summary-con{background:#FBF5F5!important;color:#7F2D2D!important}
.sum-tag-con{background:#FEE2E2!important;color:#991B1B!important}
.summary-reason{background:#F5F7FA!important;color:#475569!important}
.sum-tag-fit{background:#E2E8F0!important;color:#334155!important}

/* 톤다운된 쇼핑몰 버튼 (오버레이 링크 위에서 독립 클릭) */
.shop-btn-grid{
  position:relative!important;
  z-index:4!important;
  pointer-events:auto!important;
  display:grid!important;
  grid-template-columns:repeat(2,minmax(0,1fr))!important;
  gap:6px!important;
  width:100%!important;
}
.shop-btn-grid.cols-1{grid-template-columns:minmax(0,1fr)!important}
.shop-btn-grid.cols-3{grid-template-columns:repeat(3,minmax(0,1fr))!important}
.shop-btn{
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  min-width:0!important;
  min-height:36px!important;
  padding:4px 8px!important;
  border-radius:9px!important;
  font-size:12px!important;
  font-weight:750!important;
  text-decoration:none!important;
  white-space:nowrap!important;
  letter-spacing:-.02em!important;
  transition:background-color .15s ease,transform .12s ease!important;
}
.shop-btn:active{transform:scale(0.99)}
.shop-btn-naver{background:#1F9D63!important;border:1px solid #1C8E59!important;color:#FFFFFF!important}
.shop-btn-naver:hover{background:#188553!important}
.shop-btn-coupang{background:#D64545!important;border:1px solid #C53B3B!important;color:#FFFFFF!important}
.shop-btn-coupang:hover{background:#BE3838!important}
.shop-btn-oliveyoung{background:#6E9B26!important;border:1px solid #618A20!important;color:#FFFFFF!important}
.shop-btn-oliveyoung:hover{background:#5C831E!important}
.shop-btn-musinsa{background:#1E2229!important;border:1px solid #15181E!important;color:#FFFFFF!important}
.shop-btn-musinsa:hover{background:#111317!important}
.shop-btn-29cm{background:#333945!important;border:1px solid #282D37!important;color:#FFFFFF!important}
.shop-btn-29cm:hover{background:#232831!important}
.shop-btn-zigzag{background:#C94A96!important;border:1px solid #B63E86!important;color:#FFFFFF!important}
.shop-btn-zigzag:hover{background:#B23B82!important}
.shop-btn-ably{background:#DE5462!important;border:1px solid #CC4755!important;color:#FFFFFF!important}
.shop-btn-ably:hover{background:#C74250!important}

/* 상세 비교 페이지 스타일 */
.detail-breadcrumb{font-size:12px;font-weight:650;color:var(--muted);margin:2px 0 8px}
.detail-brand-line{font-size:13px;font-weight:750;color:var(--brand);margin-bottom:3px}
.detail-title{font-size:22px;font-weight:850;color:var(--ink);line-height:1.32;letter-spacing:-.025em;margin-bottom:8px;word-break:keep-all}
.detail-badges{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}
.trust-box{
  background:#F8FAFC;
  border:1px solid #E6ECF5;
  border-radius:12px;
  padding:10px 12px;
  margin-bottom:10px;
}
.trust-box-head{display:flex;justify-content:space-between;align-items:center;font-size:12px;font-weight:750;color:var(--sub);margin-bottom:6px}
.trust-bar{display:flex;height:7px;border-radius:999px;overflow:hidden;background:#E5E9F0;margin-bottom:6px}
.trust-seg-buy{background:#1F9D63}.trust-seg-prov{background:#CA8A04}.trust-seg-ad{background:#D64545}.trust-seg-unk{background:#94A3B8}
.trust-legend{display:flex;flex-wrap:wrap;gap:10px;font-size:11.5px;font-weight:650;color:var(--sub)}

.danawa-box{border:1px solid #DFE6F0;border-radius:13px;background:#FFFFFF;overflow:hidden}
.danawa-head{display:flex;align-items:center;justify-content:space-between;padding:9px 13px;background:#F6F8FC;border-bottom:1px solid #E6ECF4;font-size:12.5px;font-weight:800;color:var(--ink)}
.danawa-head span:last-child{font-size:11px;font-weight:600;color:var(--muted)}
.danawa-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 13px;border-bottom:1px solid #F1F4F8}
.danawa-row:last-child{border-bottom:0}
.danawa-row:hover{background:#FAFBFD}
.danawa-mall-info{display:flex;align-items:center;gap:9px;min-width:0;flex:1}
.mall-pill{display:inline-flex;align-items:center;justify-content:center;min-width:74px;height:26px;padding:0 9px;border-radius:7px;font-size:11.5px;font-weight:800;color:#FFFFFF;flex-shrink:0}
.mall-pill-naver{background:#1F9D63}.mall-pill-coupang{background:#D64545}.mall-pill-oliveyoung{background:#6E9B26}
.mall-pill-musinsa{background:#1E2229}.mall-pill-29cm{background:#333945}.mall-pill-zigzag{background:#C94A96}.mall-pill-ably{background:#DE5462}
.danawa-desc-wrap{min-width:0;display:flex;flex-direction:column;gap:2px}
.danawa-tag-row{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.danawa-status-tag{font-size:11.5px;font-weight:750;color:var(--ink)}
.danawa-partner-badge{font-size:10px;font-weight:750;color:#1D4ED8;background:#EFF6FF;padding:1px 6px;border-radius:999px}
.danawa-benefit{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.danawa-go-btn{flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;height:33px;padding:0 12px;border-radius:8px;background:#14181F;color:#FFFFFF!important;font-size:12px;font-weight:750;text-decoration:none!important;transition:background-color .15s}
.danawa-go-btn:hover{background:#2563EB}
.detail-cta-note{margin-top:7px;font-size:11px;color:var(--muted);line-height:1.45;word-break:keep-all}

.detail-section{background:#FFFFFF;border:1px solid #E6EAF0;border-radius:16px;padding:16px 18px;margin-bottom:12px;box-shadow:0 2px 12px rgba(15,23,42,.025)}
.detail-section-title{font-size:16px;font-weight:800;color:var(--ink);margin:0 0 11px;display:flex;align-items:center;justify-content:space-between}
.detail-section-sub{font-size:12px;font-weight:600;color:var(--muted)}

.recommend-fit-list{display:flex;flex-direction:column;gap:6px}
.recommend-fit-item{background:#F5F8FD;border:1px solid #E1EAFB;color:#1E3A8A;padding:9px 12px;border-radius:10px;font-size:13px;font-weight:650;line-height:1.45;word-break:keep-all}

.pros-cons-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.pc-col{border-radius:12px;padding:13px}
.pc-col-pro{background:#F4FAF6;border:1px solid #D7EDE0}
.pc-col-con{background:#FCF6F6;border:1px solid #F5DADA}
.pc-col-title{font-size:13.5px;font-weight:800;margin-bottom:8px}
.pc-col-pro .pc-col-title{color:#166534}
.pc-col-con .pc-col-title{color:#991B1B}
.pc-item{font-size:12.5px;line-height:1.45;padding:5px 0;border-bottom:1px dashed rgba(15,23,42,.08);word-break:keep-all}
.pc-item:last-child{border-bottom:0;padding-bottom:0}
.pc-count{display:inline-block;margin-left:5px;padding:1px 6px;border-radius:999px;font-size:10.5px;font-weight:750;background:rgba(255,255,255,.9)}

.matrix-scroll{width:100%;overflow-x:auto;border:1px solid #E6ECF4;border-radius:12px}
.creator-matrix{width:100%;border-collapse:collapse;font-size:12.5px;min-width:620px}
.creator-matrix th{background:#F7F9FC;color:var(--sub);font-weight:750;text-align:left;padding:9px 11px;border-bottom:1px solid #E6EAF0;white-space:nowrap}
.creator-matrix td{padding:9px 11px;border-bottom:1px solid #F1F4F8;vertical-align:top;line-height:1.45;color:var(--ink);word-break:keep-all}
.creator-matrix tr:last-child td{border-bottom:0}

.creator-review-card{display:flex;align-items:flex-start;gap:14px;border:1px solid #E8ECF2;background:#FAFBFD;border-radius:13px;padding:13px;margin-bottom:10px}
.creator-review-card:last-child{margin-bottom:0}
.creator-thumb-link{position:relative;flex-shrink:0;width:210px;aspect-ratio:16 / 9;border-radius:10px;overflow:hidden;border:1px solid rgba(15,23,42,.08);background:#E9EDF3;display:block;text-decoration:none!important}
.creator-thumb-img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .2s ease}
.creator-thumb-link:hover .creator-thumb-img{transform:scale(1.03)}
.creator-thumb-play{position:absolute;right:6px;bottom:6px;padding:3px 8px;border-radius:999px;background:rgba(20,24,31,.78);color:#FFFFFF!important;font-size:10.5px;font-weight:750}
.creator-thumb-link:hover .creator-thumb-play{background:#DC2626}
.creator-review-body{flex:1;min-width:0}
.creator-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px;flex-wrap:wrap}
.creator-name-wrap{display:flex;align-items:center;flex-wrap:wrap;gap:6px}
.creator-name{font-size:14.5px;font-weight:800;color:var(--ink)}
.creator-stat{font-size:11.5px;font-weight:650;color:var(--muted)}
.creator-video-btn{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:999px;background:#14181F;color:#FFFFFF!important;font-size:11px;font-weight:750;text-decoration:none!important}
.creator-video-btn:hover{background:#DC2626}
.creator-video-title{font-size:12.5px;font-weight:650;color:var(--sub);margin-bottom:6px;line-height:1.4}
.creator-reason{font-size:13px;font-weight:700;color:var(--ink);margin-bottom:6px;line-height:1.45;word-break:keep-all}
.creator-evidence{background:#FFFFFF;border-left:3px solid #2563EB;padding:7px 10px;border-radius:0 8px 8px 0;font-size:12px;color:#374151;line-height:1.45;margin-bottom:7px;word-break:keep-all}
.creator-tags{display:flex;flex-wrap:wrap;gap:5px}
.ctag-pro{background:#ECFDF5;color:#166534;padding:3px 8px;border-radius:7px;font-size:11px;font-weight:700}
.ctag-con{background:#FEF2F2;color:#991B1B;padding:3px 8px;border-radius:7px;font-size:11px;font-weight:700}

.st-key-related_grid div[data-testid="stVerticalBlockBorderWrapper"]{padding:11px!important;border-radius:14px!important;margin-bottom:8px!important}
.st-key-related_grid div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"]{gap:6px!important}
.related-brand{font-size:11px;font-weight:700;color:var(--muted)}
.related-name{font-size:13.5px;font-weight:800;color:var(--ink);line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;word-break:keep-all}

.st-key-pagination_bar{margin:10px 0 4px!important}
.st-key-pagination_bar [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;justify-content:center!important;align-items:center!important;gap:6px!important;width:100%!important;max-width:460px!important;margin:0 auto!important}
.st-key-pagination_bar [data-testid="stColumn"],.st-key-pagination_bar [data-testid="column"]{flex:0 0 auto!important;width:auto!important;min-width:38px!important;max-width:none!important;padding:0!important;margin:0!important}
.st-key-pagination_bar .stButton>button{min-width:38px!important;min-height:38px!important;padding:0 11px!important;border-radius:10px!important;font-size:13px!important;font-weight:750!important}
.st-key-pagination_bar .stButton>button[kind="secondary"]{background:#fff!important;border:1px solid #DCE2EC!important;color:#374151!important}
.st-key-pagination_bar .stButton>button[kind="secondary"]:hover{border-color:#2563EB!important;color:#2563EB!important}

.site-footer{margin-top:18px;margin-bottom:12px;padding:15px 18px;background:#fff;border:1px solid #E6EAF0;border-radius:14px;text-align:center;color:var(--sub);font-size:12px;font-weight:600;line-height:1.6;word-break:keep-all}
.site-footer-sub{display:block;margin-top:4px;font-size:11px;font-weight:500;color:var(--muted)}

.metric{background:#fff;border:1px solid #E6EAF0;border-radius:14px;padding:14px;min-height:90px}
.metric-label{color:var(--muted);font-size:12px;font-weight:700}
.metric-value{color:var(--brand);font-size:24px;font-weight:850;margin-top:4px}
.status-row{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #EDF1F6;font-size:13px}
.status-row:last-child{border-bottom:0}
.error-box{background:#FEF2F2;color:#991B1B;padding:10px;border-radius:10px;font-size:12px;margin:6px 0;word-break:break-word}

@media(max-width:900px) and (min-width:641px){
  .st-key-product_grid [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
  .st-key-product_grid [data-testid="stColumn"],.st-key-product_grid [data-testid="column"]{flex:0 0 calc(50% - 8px)!important;width:calc(50% - 8px)!important;min-width:calc(50% - 8px)!important}
}
@media(max-width:640px){
  .block-container{padding:.75rem .75rem 3rem!important;width:100%!important;max-width:100%!important}
  .top-nav{margin-bottom:9px}.top-sub{display:none!important}
  .hero-banner{padding:15px 14px}.hero-headline{font-size:17.5px}
  .hero-stats{flex-wrap:nowrap!important;gap:4px!important;margin-top:9px!important;overflow-x:auto!important}
  .stat-pill{padding:4px 8px!important;font-size:10.5px!important;gap:4px!important;letter-spacing:-.02em!important;flex-shrink:0!important}
  .top-disclosure{font-size:10.5px;padding:6px 8px}
  .st-key-filter_bar [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:1fr 1fr!important;gap:7px!important;width:100%!important;margin:0!important}
  .st-key-filter_bar [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child,
  .st-key-filter_bar [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child{grid-column:1 / -1!important;width:100%!important;min-width:0!important}
  .st-key-filter_bar [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  .st-key-filter_bar [data-testid="stHorizontalBlock"] > [data-testid="column"]{width:100%!important;min-width:0!important}
  .st-key-product_grid > div > [data-testid="stHorizontalBlock"],
  .st-key-related_grid > div > [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:11px!important;width:100%!important;margin:0!important}
  .st-key-product_grid > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  .st-key-product_grid > div > [data-testid="stHorizontalBlock"] > [data-testid="column"],
  .st-key-related_grid > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  .st-key-related_grid > div > [data-testid="stHorizontalBlock"] > [data-testid="column"]{width:100%!important;min-width:0!important;max-width:100%!important;flex:none!important;margin:0!important;padding:0!important}
  .product-title{min-height:auto!important}
  .pros-cons-grid{grid-template-columns:minmax(0,1fr)!important}
  .detail-title{font-size:19px}
  .creator-review-card{flex-direction:column;gap:10px}
  .creator-thumb-link{width:100%}
  .danawa-benefit{white-space:normal}
  .st-key-pagination_bar [data-testid="stHorizontalBlock"]{gap:4px!important}
  .st-key-pagination_bar [data-testid="stColumn"],.st-key-pagination_bar [data-testid="column"]{min-width:34px!important}
  .st-key-pagination_bar .stButton>button{min-width:34px!important;min-height:36px!important;padding:0 8px!important;font-size:12.5px!important}
  .site-footer{padding:13px 12px;font-size:11.5px}.site-footer-sub{font-size:10.5px}
}
</style>
""", unsafe_allow_html=True)

import html
import json
from urllib.parse import quote

import requests
import streamlit as st

from ui.scoring import (
    MAX_CURATED_PRODUCTS,
    compute_curation_score,
    has_partner_deal,
    parse_extra_partner_links,
    passes_quality_gate,
    recommendation_summary,
)


def secret(name):
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


SUPABASE_URL = secret("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = secret("SUPABASE_SERVICE_ROLE_KEY")


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


def api_count(table, params=None):
    query = {"select": "*", "limit": "1"}
    query.update(params or {})
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers("count=exact"),
        params=query,
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(f"{table} 개수 조회 실패: HTTP {response.status_code} · {response.text[:250]}")
    content_range = response.headers.get("Content-Range", "")
    if "/" in content_range:
        total_str = content_range.split("/")[-1].strip()
        if total_str.isdigit():
            return int(total_str)
    data = response.json()
    return len(data) if isinstance(data, list) else 0


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


def api_delete(table, params):
    if not params:
        raise ValueError("삭제 조건(params)이 필요합니다.")
    response = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers("return=minimal"),
        params=params,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"{table} 삭제 실패: HTTP {response.status_code} · {response.text[:250]}")


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


def _attach_recommendations(products, recs):
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

    enriched = []
    for product in products:
        item = dict(product)
        p_recs = grouped.get(item["product_id"], [])
        item["recommendations"] = p_recs
        summary = recommendation_summary(p_recs)
        item["_summary"] = summary
        item["_has_partner"] = has_partner_deal(item)
        item["_channel_count"] = len({r.get("channel_id") for r in p_recs if r.get("channel_id")})
        item["_has_quality_copy"] = bool(summary["pros"] or summary["cons"] or summary["reasons"])
        item["_has_self_buy"] = int(summary["purchase_counts"].get("직접 구매", 0)) > 0
        item["_quality_score"] = compute_curation_score(item)
        enriched.append(item)

    enriched.sort(
        key=lambda p: (
            p["_quality_score"],
            p["_channel_count"],
            len(p["recommendations"]),
            1 if p["_has_partner"] else 0,
        ),
        reverse=True,
    )
    return enriched


@st.cache_data(ttl=300, show_spinner=False)
def load_public_catalog():
    """홈 목록 전용 경량 데이터 로더 (자격 필터 + 점수제 상위 500개 압축)."""
    try:
        products = api_get_all(
            "products",
            "product_id,canonical_name,brand,model,category,search_keyword,coupang_url,affiliate_verified,affiliate_note,image_url,image_source,image_verified,identification_score,created_at",
            {"review_status": "eq.approved", "is_visible": "eq.true", "order": "created_at.desc"},
            max_rows=3000,
        )
    except Exception:
        products = api_get_all(
            "products",
            "product_id,canonical_name,brand,model,category,search_keyword,coupang_url,affiliate_verified,affiliate_note,image_url,image_source,image_verified,created_at",
            {"review_status": "eq.approved", "is_visible": "eq.true", "order": "created_at.desc"},
            max_rows=3000,
        )
    recs = api_get_all(
        "recommendations",
        "recommendation_id,product_id,video_id,channel_id,reason,pros,cons,confidence,purchase_type",
        {"order": "created_at.desc"},
        max_rows=10000,
    )
    all_items = _attach_recommendations(products, recs)
    qualified = [p for p in all_items if passes_quality_gate(p)]
    return qualified[:MAX_CURATED_PRODUCTS]


@st.cache_data(ttl=300, show_spinner=False)
def load_product_detail_recs(product_id):
    """상세 페이지 진입 시에만 해당 상품의 원문 근거(evidence) 포함 리뷰 조회."""
    pid = str(product_id or "").strip()
    if not pid:
        return []
    recs = api_get(
        "recommendations",
        "recommendation_id,product_id,video_id,channel_id,reason,pros,cons,evidence,confidence,purchase_type,created_at",
        {"product_id": f"eq.{pid}", "order": "created_at.desc", "limit": "200"},
    )
    video_ids = [r.get("video_id") for r in recs if r.get("video_id")]
    channel_ids = [r.get("channel_id") for r in recs if r.get("channel_id")]
    videos = fetch_by_ids("videos", "video_id,title,view_count,published_at", "video_id", video_ids)
    channels = fetch_by_ids("channels", "channel_id,channel_name,subscriber_count", "channel_id", channel_ids)
    video_map = {row["video_id"]: row for row in videos}
    channel_map = {row["channel_id"]: row for row in channels}
    enriched = []
    for rec in recs:
        item = dict(rec)
        item["video"] = video_map.get(rec.get("video_id"), {})
        item["channel"] = channel_map.get(rec.get("channel_id"), {})
        enriched.append(item)
    return enriched


@st.cache_data(ttl=300, show_spinner=False)
def load_public_data():
    """관리자 화면 호환용 전체 데이터 로더."""
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
    return _attach_recommendations(products, recs)

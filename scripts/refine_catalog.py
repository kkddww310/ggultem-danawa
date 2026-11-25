import argparse
import json
import os
import re
import time
from pathlib import Path

import requests

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


def load_secrets():
    secrets = {}
    secrets_path = Path(".streamlit/secrets.toml")
    if secrets_path.exists() and tomllib is not None:
        with secrets_path.open("rb") as f:
            secrets = tomllib.load(f)
    for key in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "NAVER_CLIENT_ID",
        "NAVER_CLIENT_SECRET",
    ):
        if os.getenv(key):
            secrets[key] = os.getenv(key)
    return {k: str(v).strip() for k, v in secrets.items() if v}


CFG = load_secrets()
SUPABASE_URL = CFG.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = CFG.get("SUPABASE_SERVICE_ROLE_KEY", "")
GEMINI_API_KEY = CFG.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = CFG.get("OPENAI_API_KEY", "")
NAVER_CLIENT_ID = CFG.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = CFG.get("NAVER_CLIENT_SECRET", "")

HOLLOW_REGEX = re.compile(
    r"(에\s*사용된|에서\s*소개된|에서\s*추천한|에서\s*언급된|에서\s*리뷰한|으로\s*구매한|직접\s*구매\s*제품|추천\s*제품|소개\s*제품|언급\s*제품|리뷰\s*제품)$"
)


def sb_headers(prefer=None):
    h = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
    if SUPABASE_KEY.startswith("eyJ"):
        h["Authorization"] = f"Bearer {SUPABASE_KEY}"
    if prefer:
        h["Prefer"] = prefer
    return h


def sb_get_all(table, fields="*", params=None):
    rows = []
    offset = 0
    while True:
        q = {"select": fields, "limit": "1000", "offset": str(offset)}
        q.update(params or {})
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), params=q, timeout=30)
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return rows


def sb_patch(table, values, params):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=sb_headers("return=minimal"),
        params=params,
        json=values,
        timeout=30,
    )
    r.raise_for_status()


def needs_copy_polish(text):
    t = re.sub(r"\s+", " ", str(text or "").strip())
    if not t:
        return False
    return bool(HOLLOW_REGEX.search(t) or len(t) > 42 or t.endswith(("함", "임", "됨", "있음", "없음")))


def polish_with_llm(product_name, reason, pros, cons):
    prompt = (
        "너는 커머스 큐레이션 매거진 에디터다. 아래 리뷰 데이터를 구매자가 매력을 느낄 간결한 한국어 카피로 다듬어라.\n"
        "규칙:\n"
        "1. '~에 사용된 제품', '~영상에서 소개함', '~직접 구매 제품' 같은 상황/맥락 설명은 절대 금지.\n"
        "2. 반드시 제품의 체감 성능, 사용감, 핵심 강점/주의점 위주로 14~24자 이내 명사형 또는 깔끔한 구문으로 작성.\n"
        "3. 근거가 전혀 없는 빈 문장은 빈 문자열/빈 배열로 반환.\n"
        '4. 반드시 JSON으로만 응답: {"reason": "...", "pros": ["..."], "cons": ["..."]}\n\n'
        f"상품명: {product_name}\n"
        f"기존 추천이유: {reason}\n"
        f"기존 장점: {json.dumps(pros, ensure_ascii=False)}\n"
        f"기존 단점: {json.dumps(cons, ensure_ascii=False)}"
    )

    if GEMINI_API_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        resp = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
            },
            timeout=25,
        )
        if resp.ok:
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw)

    if OPENAI_API_KEY:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=25,
        )
        if resp.ok:
            raw = resp.json()["choices"][0]["message"]["content"]
            return json.loads(raw)

    return None


def fetch_naver_product_image(query):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return ""
    resp = requests.get(
        "https://openapi.naver.com/v1/search/shop.json",
        headers={
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        },
        params={"query": query, "display": 3, "sort": "sim"},
        timeout=15,
    )
    if not resp.ok:
        return ""
    for item in resp.json().get("items") or []:
        img = str(item.get("image") or "").strip()
        if img.startswith(("https://", "http://")):
            try:
                head = requests.head(img, timeout=6, allow_redirects=True)
                if head.ok:
                    return img
            except Exception:
                continue
    return ""


def main():
    parser = argparse.ArgumentParser(description="에디션 픽 DB 품질 정제 및 상품 이미지 보강")
    parser.add_argument("--apply", action="store_true", help="실제 DB에 변경사항 반영 (미지정 시 드라이런)")
    parser.add_argument("--limit", type=int, default=100, help="한 번에 처리할 최대 항목 수")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit("SUPABASE_URL 및 SUPABASE_SERVICE_ROLE_KEY가 필요합니다.")

    products = sb_get_all(
        "products",
        "product_id,canonical_name,brand,search_keyword,is_visible,image_url,image_verified",
        {"review_status": "eq.approved"},
    )
    recs = sb_get_all("recommendations", "recommendation_id,product_id,reason,pros,cons")

    recs_by_pid = {}
    for r in recs:
        recs_by_pid.setdefault(r.get("product_id"), []).append(r)

    hidden_count = 0
    polished_count = 0
    image_count = 0

    for p in products:
        pid = p["product_id"]
        p_recs = recs_by_pid.get(pid, [])
        has_any_text = any(
            (r.get("reason") and len(str(r["reason"]).strip()) >= 3)
            or any(len(str(x).strip()) >= 3 for x in (r.get("pros") or []))
            for r in p_recs
        )
        if p.get("is_visible") and (not p_recs or not has_any_text):
            hidden_count += 1
            print(f"[숨김 대상] {p.get('canonical_name')} (근거 텍스트 부재)")
            if args.apply:
                sb_patch("products", {"is_visible": False}, {"product_id": f"eq.{pid}"})

    if GEMINI_API_KEY or OPENAI_API_KEY:
        prod_name_map = {p["product_id"]: p.get("canonical_name") or "" for p in products}
        for r in recs:
            if polished_count >= args.limit:
                break
            reason = str(r.get("reason") or "").strip()
            pros = [str(x).strip() for x in (r.get("pros") or []) if str(x).strip()]
            cons = [str(x).strip() for x in (r.get("cons") or []) if str(x).strip()]
            if needs_copy_polish(reason) or any(needs_copy_polish(x) for x in pros + cons):
                polished = polish_with_llm(prod_name_map.get(r.get("product_id"), ""), reason, pros, cons)
                if polished:
                    polished_count += 1
                    print(f"[문장 교정] {prod_name_map.get(r.get('product_id'), '')} -> {polished}")
                    if args.apply:
                        sb_patch(
                            "recommendations",
                            {
                                "reason": str(polished.get("reason") or "").strip() or None,
                                "pros": [str(x).strip() for x in (polished.get("pros") or []) if str(x).strip()],
                                "cons": [str(x).strip() for x in (polished.get("cons") or []) if str(x).strip()],
                            },
                            {"recommendation_id": f"eq.{r['recommendation_id']}"},
                        )
                    time.sleep(0.2)

    if NAVER_CLIENT_ID and NAVER_CLIENT_SECRET:
        for p in products:
            if image_count >= args.limit:
                break
            if not p.get("is_visible") or p.get("image_verified"):
                continue
            query = str(p.get("search_keyword") or p.get("canonical_name") or "").strip()
            img_url = fetch_naver_product_image(query)
            if img_url:
                image_count += 1
                print(f"[이미지 매칭] {p.get('canonical_name')} -> {img_url}")
                if args.apply:
                    sb_patch(
                        "products",
                        {"image_url": img_url, "image_source": "affiliate", "image_verified": True},
                        {"product_id": f"eq.{p['product_id']}"},
                    )
                time.sleep(0.15)

    mode = "실제 반영 완료" if args.apply else "드라이런 미리보기 (--apply 옵션으로 실제 적용)"
    print(f"\n=== {mode} ===")
    print(f"부실 상품 숨김: {hidden_count}건 | AI 문장 교정: {polished_count}건 | 상품 이미지 매칭: {image_count}건")


if __name__ == "__main__":
    main()

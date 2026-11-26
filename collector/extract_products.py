import json
import os
import re
import time

import requests

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None


SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "").strip()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
BATCH_SIZE = int(os.getenv("EXTRACT_BATCH_SIZE", "25"))
AUTO_APPROVE_SCORE = int(os.getenv("AUTO_APPROVE_SCORE", "80"))

CATEGORIES = [
    "IT·전자",
    "뷰티",
    "패션",
    "생활·살림",
    "주방",
    "여행",
    "자동차",
    "운동·건강",
    "육아",
    "반려동물",
    "기타",
]

VALID_PURCHASE_TYPES = {
    "직접 구매",
    "제품 제공",
    "유료 광고",
    "확인되지 않음",
}

INVALID_POINT_PATTERNS = (
    "원문에",
    "명시됨",
    "명시되어",
    "후기는 없음",
    "후기 없음",
    "언급 없음",
    "언급이 없음",
    "언급되지",
    "정보가 없음",
    "정보 없음",
    "확인되지 않",
    "알 수 없",
    "단점 없음",
    "단점은 없음",
    "장점 없음",
    "장점은 없음",
    "해당 없음",
    "특이사항 없음",
    "별도 언급",
)

HOLLOW_COPY_REGEX = re.compile(
    r"(에\s*사용된|에서\s*소개된|에서\s*추천한|에서\s*언급된|에서\s*리뷰한|으로\s*구매한|직접\s*구매\s*제품|추천\s*제품|소개\s*제품|언급\s*제품|리뷰\s*제품|협찬\s*제품|제공\s*제품)$"
)

GENERIC_BRAND_KEYS = {
    "기타", "없음", "미상", "알수없음", "무명", "브랜드", "제품", "상품",
    "대기업", "중소기업", "가성비", "추천템", "인기템", "꿀템", "필수템", "unknown",
}

GENERIC_ONLY_WORDS = {
    "티셔츠", "반팔티", "맨투맨", "후드티", "청바지", "슬랙스", "가방", "백팩", "운동화", "스니커즈",
    "패딩", "코트", "자켓", "원피스", "선크림", "수분크림", "토너", "세럼", "앰플", "립스틱", "쿠션",
    "파운데이션", "샴푸", "바디워시", "이어폰", "헤드폰", "노트북", "태블릿", "키보드", "마우스",
    "보조배터리", "청소기", "프라이팬", "냄비", "텀블러", "영양제", "유산균", "비타민",
}

CATEGORY_HINTS = {
    "IT·전자": ("노트북", "태블릿", "아이패드", "갤럭시", "애플", "에어팟", "버즈", "이어폰", "헤드폰", "키보드", "마우스", "모니터", "충전기", "보조배터리", "카메라", "스피커", "스마트워치", "ssd"),
    "뷰티": ("크림", "세럼", "앰플", "토너", "로션", "선크림", "쿠션", "파운데이션", "립", "틴트", "섀도우", "마스카라", "클렌징", "샴푸", "트리트먼트", "향수", "올리브영", "마스크팩"),
    "패션": ("자켓", "패딩", "코트", "니트", "가디건", "셔츠", "티셔츠", "팬츠", "데님", "청바지", "스커트", "원피스", "가방", "백팩", "숄더백", "신발", "스니커즈", "로퍼", "부츠", "모자", "무신사"),
    "생활·살림": ("청소기", "세제", "섬유유연제", "수납", "정리함", "행거", "디퓨저", "방향제", "건조기", "세탁", "매트리스", "베개", "이불", "타월", "휴지", "물티슈", "가습기", "제습기"),
    "주방": ("프라이팬", "냄비", "에어프라이어", "커피머신", "원두", "텀블러", "밀폐용기", "식기", "그릇", "칼", "도마", "블렌더", "믹서기", "오븐", "토스터", "전기포트"),
    "여행": ("캐리어", "여권", "파우치", "목베개", "어댑터", "유심", "이심", "트래블", "기내용"),
    "자동차": ("차량용", "블랙박스", "세차", "와이퍼", "방향제", "거치대", "타이어", "하이패스"),
    "운동·건강": ("러닝화", "요가매트", "덤벨", "프로틴", "단백질", "영양제", "비타민", "유산균", "오메가3", "마사지건", "폼롤러", "헬스"),
    "육아": ("기저귀", "분유", "젖병", "유모차", "카시트", "아기", "유아", "장난감", "물티슈"),
    "반려동물": ("강아지", "고양이", "사료", "간식", "배변패드", "모래", "캣타워", "하네스", "펫"),
}


def sb_headers(prefer=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }
    if SUPABASE_KEY.startswith("eyJ"):
        h["Authorization"] = f"Bearer {SUPABASE_KEY}"
    if prefer:
        h["Prefer"] = prefer
    return h


def sb_get(table, params):
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=sb_headers(),
        params=params,
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"{table} 조회 실패: HTTP {resp.status_code} · {resp.text[:250]}")
    return resp.json()


def sb_post(table, payload):
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=sb_headers("return=representation"),
        json=payload,
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"{table} 저장 실패: HTTP {resp.status_code} · {resp.text[:250]}")
    return resp.json() if resp.text else []


def sb_patch(table, values, params):
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=sb_headers("return=minimal"),
        params=params,
        json=values,
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"{table} 수정 실패: HTTP {resp.status_code} · {resp.text[:250]}")


def norm_key(value):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").lower())


def clean_sentence(value, max_len=180):
    text = re.sub(r"https?://\S+", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip(" ·,-/\"'")
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def is_meaningful_point(text):
    cleaned = clean_sentence(text, max_len=240)
    if len(cleaned) < 4:
        return False
    if any(pat in cleaned for pat in INVALID_POINT_PATTERNS):
        return False
    if HOLLOW_COPY_REGEX.search(cleaned):
        return False
    return True


def clean_points_list(items, limit=4):
    result = []
    seen = set()
    for raw in items or []:
        text = clean_sentence(raw, max_len=90)
        if not is_meaningful_point(text):
            continue
        key = norm_key(text)
        if key and key not in seen:
            seen.add(key)
            result.append(text)
        if len(result) >= limit:
            break
    return result


def normalize_category(raw_cat, full_text=""):
    cat = str(raw_cat or "").strip()
    if cat in CATEGORIES:
        return cat
    alias_map = {
        "가전": "IT·전자",
        "디지털": "IT·전자",
        "전자기기": "IT·전자",
        "테크": "IT·전자",
        "화장품": "뷰티",
        "스킨케어": "뷰티",
        "메이크업": "뷰티",
        "의류": "패션",
        "잡화": "패션",
        "생활": "생활·살림",
        "생활용품": "생활·살림",
        "인테리어": "생활·살림",
        "주방용품": "주방",
        "건강": "운동·건강",
        "운동": "운동·건강",
        "유아동": "육아",
        "반려": "반려동물",
    }
    for k, v in alias_map.items():
        if k in cat:
            return v

    haystack = f"{cat} {full_text}".lower()
    for target_cat, keywords in CATEGORY_HINTS.items():
        if any(kw in haystack for kw in keywords):
            return target_cat
    return "기타"


def normalize_purchase_type(raw_type, context_text=""):
    val = str(raw_type or "").strip()
    if val in VALID_PURCHASE_TYPES:
        return val
    merged = f"{val} {context_text}"
    if any(k in merged for k in ("유료광고", "유료 광고", "광고 포함", "브랜디드")):
        return "유료 광고"
    if any(k in merged for k in ("제품제공", "제품 제공", "협찬", "단순제공", "무상제공", "선물")):
        return "제품 제공"
    if any(k in merged for k in ("내돈내산", "직접 구매", "직접구매", "제 돈 주고", "사비")):
        return "직접 구매"
    return "확인되지 않음"


def is_valid_brand(brand):
    b_norm = norm_key(brand)
    return len(b_norm) >= 2 and b_norm not in GENERIC_BRAND_KEYS


def compute_identity_score(brand, model, canonical_name, confidence):
    b_norm = norm_key(brand)
    m_norm = norm_key(model)
    c_norm = norm_key(canonical_name)

    if not c_norm or c_norm in {norm_key(w) for w in GENERIC_ONLY_WORDS}:
        return 15
    if not is_valid_brand(brand):
        return 25

    score = 35
    if len(b_norm) >= 2:
        score += 25
    if len(m_norm) >= 2 and m_norm not in GENERIC_BRAND_KEYS and m_norm != b_norm:
        score += 18
    if len(c_norm) >= 5 and c_norm != b_norm:
        score += 10
    if any(ch.isdigit() for ch in canonical_name):
        score += 5

    conf_bonus = max(0, min(12, round((float(confidence or 0) - 0.5) * 24)))
    score += conf_bonus
    return max(0, min(100, score))


def fetch_youtube_description(video_id):
    if not YOUTUBE_API_KEY or not video_id:
        return ""
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "snippet", "id": video_id, "key": YOUTUBE_API_KEY},
            timeout=15,
        )
        if not resp.ok:
            return ""
        items = resp.json().get("items") or []
        if not items:
            return ""
        snippet = items[0].get("snippet") or {}
        return str(snippet.get("description") or "").strip()
    except Exception:
        return ""


def fetch_youtube_transcript(video_id):
    if not YouTubeTranscriptApi or not video_id:
        return ""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
        joined = " ".join(seg.get("text", "") for seg in transcript_list)
        return re.sub(r"\s+", " ", joined).strip()[:6500]
    except Exception:
        return ""


def parse_json_response(text):
    raw = str(text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            return json.loads(match.group(0))
        raise


def call_gemini_extract(title, description, transcript):
    if not GEMINI_API_KEY and not OPENROUTER_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 또는 OPENROUTER_API_KEY가 설정되지 않았습니다.")

    prompt = f"""
당신은 한국 유튜브 쇼핑·리뷰 영상을 분석해 소비자가 실제로 구매 비교할 수 있는 고품질 상품 리뷰 데이터만 엄선하는 전문 에디터입니다.

[영상 제목]
{title}

[영상 설명란]
{description[:2800] if description else "(없음)"}

[영상 자막/내용]
{transcript[:6000] if transcript else "(없음)"}

[엄격 추출 규칙]
1. 유튜버가 실제로 사용해 보고 구체적인 평가(장점, 단점, 추천 이유)를 남긴 상품만 추출하세요. (최대 6개)
2. 단순 스쳐 지나가는 언급, 화면 배경 노출, 고정 댓글/설명란 단순 쇼핑몰 링크 나열만 있고 영상 내 실사용 평가가 없는 상품은 절대 추출하지 마세요.
3. 브랜드명과 정확한 제품명/모델명이 식별되지 않는 일반명사(예: "수분크림", "흰 반팔티", "프라이팬", "보조배터리")는 절대 추출하지 마세요.
4. 리뷰·추천 영상이 아니거나 추출할 만한 고품질 상품이 없으면 products를 빈 배열 []로 반환하세요.
5. category는 반드시 아래 11개 중 하나만 선택하세요:
   {", ".join(CATEGORIES)}
6. purchase_type은 영상 제목·설명란·자막의 표기를 근거로 아래 4개 중 하나만 선택하세요:
   - "직접 구매" (내돈내산, 직접 결제 언급 시)
   - "제품 제공" (단순 선물, 협찬, 제품 제공 언급 시)
   - "유료 광고" (유료 광고 포함 표기, 브랜디드 광고 시)
   - "확인되지 않음" (명확한 언급이 없을 때)
7. reason: 소비자가 왜 이 제품을 사야 하는지 한 줄 핵심 추천 근거/추천 대상을 구체적으로 작성하세요. ("~에서 소개된 제품" 같은 형식적 문구 금지)
8. pros / cons: 영상에서 실제로 언급된 구체적인 장점과 아쉬운 점만 간결한 구절로 작성하세요. 언급이 없으면 빈 배열 []로 두세요.
9. evidence: 유튜버의 실제 사용 소감이나 핵심 평가가 드러나는 발언 인용 또는 요약 1~2문장(URL 제외).
10. confidence: 상품 식별 및 추천 근거의 명확성 (0.0 ~ 1.0).

반드시 아래 JSON 형식만 출력하세요:
{{
  "is_product_video": true,
  "video_product_score": 85,
  "products": [
    {{
      "brand": "브랜드명",
      "model": "모델명 또는 라인명",
      "canonical_name": "브랜드 + 공식 상품명 (예: 로지텍 MX Master 3S 무선 마우스)",
      "search_keyword": "쇼핑몰 검색용 핵심 키워드",
      "category": "IT·전자",
      "purchase_type": "직접 구매",
      "reason": "손목 피로도가 적고 다중 기기 전환이 빨라 사무용 마우스를 찾는 분께 적합",
      "pros": ["무소음 클릭감이 조용함", "가로 휠 스크롤이 엑셀 작업에 편리함"],
      "cons": ["손이 작은 사용자에게는 다소 크고 무거움"],
      "evidence": "3개월째 내돈내산으로 매일 쓰고 있는데 휠 감도와 손목 각도가 가장 편했습니다.",
      "confidence": 0.92
    }}
  ]
}}
""".strip()

    errors = []

    # 1축: Google Gemini 무료 티어 (할당량이 넉넉한 flash-lite 우선 호출)
    if GEMINI_API_KEY:
        gemini_models = ["gemini-3.1-flash-lite", "gemini-2.5-flash"]
        for model_name in gemini_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json",
                },
            }
            try:
                resp = requests.post(url, json=body, timeout=35)
                if resp.status_code == 429:
                    errors.append(f"{model_name} HTTP 429")
                    continue
                if not resp.ok:
                    errors.append(f"{model_name} HTTP {resp.status_code}: {resp.text[:120]}")
                    continue
                data = resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                return parse_json_response(text)
            except Exception as exc:
                errors.append(f"{model_name}: {exc}")

    # 2축: OpenRouter 무료 모델 순차 호출 (Gemini 한도 소진 시 자동 폴백)
    if OPENROUTER_API_KEY:
        or_models = []
        if OPENROUTER_MODEL:
            or_models.append(OPENROUTER_MODEL)
        for fallback_or in ("openrouter/free", "google/gemma-4-31b-it:free", "google/gemma-4-26b-a4b-it:free"):
            if fallback_or not in or_models:
                or_models.append(fallback_or)

        for or_model in or_models:
            try:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": or_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                    },
                    timeout=35,
                )
                if resp.status_code == 429:
                    errors.append(f"OpenRouter({or_model}) HTTP 429")
                    time.sleep(1.5)
                    continue
                if not resp.ok:
                    errors.append(f"OpenRouter({or_model}) HTTP {resp.status_code}: {resp.text[:120]}")
                    continue
                content = resp.json()["choices"][0]["message"]["content"]
                return parse_json_response(content)
            except Exception as exc:
                errors.append(f"OpenRouter({or_model}): {exc}")

    raise RuntimeError("AI 분석 실패: " + " | ".join(errors))


def load_existing_catalog():
    rows = sb_get(
        "products",
        {
            "select": "product_id,canonical_name,normalized_name,brand,model,category,review_status",
            "review_status": "in.(approved,pending)",
            "limit": "5000",
        },
    )
    by_norm = {}
    by_brand_model = {}
    for row in rows:
        n_key = norm_key(row.get("normalized_name") or row.get("canonical_name"))
        if n_key:
            by_norm[n_key] = row
        b_key = norm_key(row.get("brand"))
        m_key = norm_key(row.get("model"))
        if len(b_key) >= 2 and len(m_key) >= 2:
            by_brand_model[(b_key, m_key)] = row
    return by_norm, by_brand_model


def load_existing_recs(video_ids):
    if not video_ids:
        return {}
    rows = sb_get(
        "recommendations",
        {
            "select": "recommendation_id,product_id,video_id",
            "video_id": f"in.({','.join(video_ids)})",
            "limit": "5000",
        },
    )
    return {
        (str(r.get("product_id")), str(r.get("video_id"))): r.get("recommendation_id")
        for r in rows
        if r.get("recommendation_id")
    }


def sync_existing_product_category(existing_row, new_category):
    current_cat = str(existing_row.get("category") or "").strip()
    if current_cat not in CATEGORIES and new_category in CATEGORIES:
        try:
            sb_patch(
                "products",
                {"category": new_category},
                {"product_id": f"eq.{existing_row['product_id']}"},
            )
            existing_row["category"] = new_category
        except Exception:
            pass


def find_or_create_product(item, by_norm, by_brand_model):
    canonical_name = clean_sentence(item.get("canonical_name"), max_len=120)
    brand = clean_sentence(item.get("brand"), max_len=60)
    model = clean_sentence(item.get("model"), max_len=60)
    search_keyword = clean_sentence(item.get("search_keyword") or canonical_name, max_len=100)
    confidence = float(item.get("confidence") or 0.7)

    if not is_valid_brand(brand):
        return None, False

    if norm_key(brand) not in norm_key(canonical_name):
        canonical_name = f"{brand} {canonical_name}".strip()

    n_key = norm_key(canonical_name)
    b_key = norm_key(brand)
    m_key = norm_key(model)

    category = normalize_category(
        item.get("category"),
        f"{canonical_name} {brand} {model} {item.get('reason') or ''}",
    )

    if n_key in by_norm:
        sync_existing_product_category(by_norm[n_key], category)
        return by_norm[n_key]["product_id"], False
    if len(b_key) >= 2 and len(m_key) >= 2 and (b_key, m_key) in by_brand_model:
        sync_existing_product_category(by_brand_model[(b_key, m_key)], category)
        return by_brand_model[(b_key, m_key)]["product_id"], False

    identity_score = compute_identity_score(brand, model, canonical_name, confidence)
    if identity_score < 45:
        return None, False

    has_model = len(m_key) >= 2 and m_key not in GENERIC_BRAND_KEYS and m_key != str(b_key or "")
    auto_approve = identity_score >= AUTO_APPROVE_SCORE and has_model
    payload = {
        "canonical_name": canonical_name,
        "normalized_name": n_key,
        "brand": brand,
        "model": model,
        "category": category,
        "search_keyword": search_keyword or canonical_name,
        "identity_score": identity_score,
        "review_status": "approved" if auto_approve else "pending",
        "is_visible": bool(auto_approve),
        "review_note": (
            f"AI 자동 승인 (식별점수 {identity_score}/100)"
            if auto_approve
            else f"AI 추출 검수 대기 (식별점수 {identity_score}/100)"
        ),
    }
    created = sb_post("products", [payload])
    if not created:
        return None, False
    new_row = created[0]
    by_norm[n_key] = new_row
    if has_model:
        by_brand_model[(b_key, m_key)] = new_row
    return new_row["product_id"], True


def fetch_target_videos(limit):
    queued = sb_get(
        "videos",
        {
            "select": "*",
            "analysis_status": "eq.queued",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    if len(queued) >= limit:
        return queued[:limit]
    remain = limit - len(queued)
    pending = sb_get(
        "videos",
        {
            "select": "*",
            "analysis_status": "eq.pending",
            "order": "created_at.desc",
            "limit": str(remain),
        },
    )
    return queued + pending


def process_video(video, by_norm, by_brand_model, existing_recs):
    video_id = str(video.get("video_id") or "").strip()
    channel_id = str(video.get("channel_id") or "").strip()
    title = str(video.get("title") or "").strip()

    description = str(video.get("description") or "").strip()
    if not description:
        description = fetch_youtube_description(video_id)

    transcript = str(video.get("transcript") or "").strip()
    if not transcript:
        transcript = fetch_youtube_transcript(video_id)

    # 설명란과 자막이 모두 없는 영상은 환각 추출 방지를 위해 스킵
    if not description and not transcript:
        sb_patch(
            "videos",
            {
                "analysis_status": "no_product",
                "analysis_error": None,
                "product_score": 0,
            },
            {"video_id": f"eq.{video_id}"},
        )
        return "no_product", 0

    result = call_gemini_extract(title, description, transcript)
    video_score = int(result.get("video_product_score") or 0)
    raw_products = result.get("products") or []

    if not result.get("is_product_video", True) and not raw_products:
        sb_patch(
            "videos",
            {
                "analysis_status": "skipped_non_product",
                "analysis_error": None,
                "product_score": video_score,
            },
            {"video_id": f"eq.{video_id}"},
        )
        return "skipped_non_product", 0

    if not raw_products:
        sb_patch(
            "videos",
            {
                "analysis_status": "no_product",
                "analysis_error": None,
                "product_score": video_score,
            },
            {"video_id": f"eq.{video_id}"},
        )
        return "no_product", 0

    saved_count = 0
    rejected_generic_count = 0

    for item in raw_products:
        if not isinstance(item, dict):
            continue

        reason = clean_sentence(item.get("reason"), max_len=200)
        if not is_meaningful_point(reason):
            reason = ""

        pros = clean_points_list(item.get("pros"), limit=4)
        cons = clean_points_list(item.get("cons"), limit=4)
        evidence = clean_sentence(item.get("evidence"), max_len=260)
        if not is_meaningful_point(evidence):
            evidence = ""

        # 실사용 장단점이나 추천 근거가 전혀 없는 단순 언급 상품 제외
        if not pros and not cons and not reason:
            rejected_generic_count += 1
            continue

        product_id, _ = find_or_create_product(item, by_norm, by_brand_model)
        if not product_id:
            rejected_generic_count += 1
            continue

        purchase_type = normalize_purchase_type(
            item.get("purchase_type"),
            f"{title} {description[:500]} {evidence}",
        )
        confidence = max(0.0, min(1.0, float(item.get("confidence") or 0.75)))

        rec_payload = {
            "product_id": product_id,
            "video_id": video_id,
            "channel_id": channel_id or None,
            "reason": reason or None,
            "pros": pros,
            "cons": cons,
            "evidence": evidence or None,
            "confidence": round(confidence, 3),
            "purchase_type": purchase_type,
        }

        pair_key = (str(product_id), video_id)
        existing_rec_id = existing_recs.get(pair_key)
        if existing_rec_id:
            sb_patch("recommendations", rec_payload, {"recommendation_id": f"eq.{existing_rec_id}"})
        else:
            created_rec = sb_post("recommendations", [rec_payload])
            if created_rec:
                existing_recs[pair_key] = created_rec[0].get("recommendation_id")
        saved_count += 1

    if saved_count > 0:
        final_status = "analyzed"
    elif rejected_generic_count > 0:
        final_status = "rejected_generic"
    else:
        final_status = "no_product"

    sb_patch(
        "videos",
        {
            "analysis_status": final_status,
            "analysis_error": None,
            "product_score": max(video_score, 70 if saved_count > 0 else video_score),
        },
        {"video_id": f"eq.{video_id}"},
    )
    return final_status, saved_count


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY 환경변수가 없습니다.")
    if not GEMINI_API_KEY and not OPENROUTER_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 또는 OPENROUTER_API_KEY 환경변수가 없습니다.")

    videos = fetch_target_videos(BATCH_SIZE)
    print(f"[extract_products] 분석 대상 영상: {len(videos)}개")
    if not videos:
        return

    by_norm, by_brand_model = load_existing_catalog()
    existing_recs = load_existing_recs([str(v.get("video_id")) for v in videos if v.get("video_id")])

    for idx, video in enumerate(videos, start=1):
        vid = str(video.get("video_id") or "")
        title = str(video.get("title") or "")[:50]
        try:
            status, count = process_video(video, by_norm, by_brand_model, existing_recs)
            print(f"[{idx}/{len(videos)}] {vid} ({title}) -> {status} (상품 {count}개)")
        except Exception as exc:
            err_msg = str(exc)[:400]
            print(f"[{idx}/{len(videos)}] {vid} 오류: {err_msg}")
            try:
                sb_patch(
                    "videos",
                    {
                        "analysis_status": "ai_error",
                        "analysis_error": err_msg,
                    },
                    {"video_id": f"eq.{vid}"},
                )
            except Exception:
                pass
        time.sleep(0.5)


if __name__ == "__main__":
    main()

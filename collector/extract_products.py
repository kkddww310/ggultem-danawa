import json
import re
import time
import uuid

import requests

from collector.config import OPENROUTER_API_KEY
from collector.database import select, upsert, update


# =========================================================
# OpenRouter 설정
# =========================================================
MODELS = (
    "openrouter/free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
)

BATCH_LIMIT = 30
MIN_CONFIDENCE = 0.82


# =========================================================
# 일반 품목명 및 비상품 표현 차단
# =========================================================

# 이 목록에 해당하는 표현은 제품명이 아니라 일반 품목명으로 판단한다.
GENERIC_PRODUCT_NAMES = {
    # 운동
    "사레레밴드",
    "운동밴드",
    "저항밴드",
    "고무밴드",
    "루프밴드",
    "요가매트",
    "덤벨",
    "마사지건",
    "폼롤러",
    "운동기구",
    "헬스용품",

    # 생활·가전
    "로봇청소기",
    "무선청소기",
    "물걸레청소기",
    "청소기",
    "음식물처리기",
    "공기청정기",
    "가습기",
    "제습기",
    "선풍기",
    "전기매트",
    "온수매트",
    "카본매트",
    "냉장고",
    "김치냉장고",
    "세탁기",
    "건조기",
    "생활용품",
    "살림용품",
    "수납용품",
    "욕실용품",

    # IT·전자
    "무선이어폰",
    "이어폰",
    "헤드폰",
    "스피커",
    "보조배터리",
    "충전기",
    "고속충전기",
    "케이블",
    "멀티탭",
    "노트북",
    "태블릿",
    "모니터",
    "키보드",
    "마우스",
    "카메라",
    "마이크",
    "스마트폰",
    "스마트워치",
    "전자제품",
    "it제품",

    # 뷰티
    "화장품",
    "스킨케어",
    "기초화장품",
    "쿠션",
    "파운데이션",
    "컨실러",
    "틴트",
    "립",
    "선크림",
    "클렌저",
    "클렌징폼",
    "크림",
    "세럼",
    "토너",
    "향수",
    "드라이기",
    "고데기",
    "뷰티디바이스",

    # 주방
    "주방용품",
    "조리도구",
    "프라이팬",
    "냄비",
    "식칼",
    "에어프라이어",
    "전자레인지",
    "커피머신",
    "토스터기",
    "믹서기",
    "정수기",
    "식기세척기",
    "밀폐용기",

    # 패션
    "운동화",
    "신발",
    "가방",
    "백팩",
    "지갑",
    "선글라스",
    "시계",
    "아우터",
    "옷",
    "패션아이템",

    # 여행·자동차·육아·반려동물
    "여행용품",
    "여행필수템",
    "캐리어",
    "캠핑용품",
    "차량용품",
    "세차용품",
    "육아용품",
    "육아템",
    "아기용품",
    "강아지용품",
    "고양이용품",
    "반려동물용품",

    # 포괄 표현
    "추천템",
    "필수템",
    "꿀템",
    "아이템",
    "제품",
    "상품",
    "가성비제품",
    "내돈내산제품",
}


# 제품명이 아니라 영상 문구·프로모션일 가능성이 높은 단어
NON_PRODUCT_KEYWORDS = {
    "이벤트",
    "쿠폰",
    "할인",
    "할인가",
    "최저가",
    "프로모션",
    "장바구니",
    "챌린지",
    "배송",
    "무료배송",
    "신규회원",
    "구독",
    "좋아요",
    "댓글",
    "공동구매",
    "공구",
    "체험단",
    "라이브",
    "브이로그",
    "루틴",
    "운동법",
    "강좌",
    "튜토리얼",
    "뉴스",
    "사건",
    "정치",
    "예고",
    "티저",
    "다시보기",
    "뮤직비디오",
}


# 모델명이 없어도 비교적 고유 제품명으로 볼 수 있는 표현
# 예: 정샘물 에센셜 스킨 누더 쿠션처럼 모델 번호가 없어도
# 브랜드와 고유 상품명이 명확한 경우
GENERIC_SUFFIXES = (
    "로봇청소기",
    "무선청소기",
    "청소기",
    "음식물처리기",
    "전기매트",
    "카본매트",
    "모니터",
    "태블릿",
    "노트북",
    "키보드",
    "마우스",
    "이어폰",
    "헤드폰",
    "충전기",
    "보조배터리",
    "쿠션",
    "컨실러",
    "크림",
    "세럼",
    "향수",
    "드라이기",
    "고데기",
    "운동화",
    "가방",
    "캐리어",
)


# =========================================================
# 문자열 정규화
# =========================================================
def normalize_text(value):
    """
    비교용 문자열 정규화.
    공백, 괄호, 특수기호를 제거하고 소문자로 변환한다.
    """
    return re.sub(
        r"[^0-9a-z가-힣]+",
        "",
        str(value or "").lower(),
    )


def normalize_name(value):
    """
    상품 중복 판별용 정규화.

    자주 쓰이는 영문 브랜드를 한국어 표기로 통일한다.
    """
    text = str(value or "").lower().strip()

    replacements = {
        "logitech": "로지텍",
        "samsung": "삼성",
        "apple": "애플",
        "anker": "앤커",
        "ugreen": "유그린",
        "dyson": "다이슨",
        "shark": "샤크",
        "lg electronics": "lg",
        "lge": "lg",
        "xiaomi": "샤오미",
        "sony": "소니",
        "bose": "보스",
        "jbl": "제이비엘",
    }

    for source, target in replacements.items():
        text = text.replace(source, target)

    return normalize_text(text)


def meaningful_tokens(value):
    """
    근거 확인에 사용할 의미 있는 토큰을 추출한다.

    지나치게 짧은 토큰과 일반 품목 단어는 제외한다.
    """
    raw_tokens = re.findall(
        r"[0-9A-Za-z가-힣]+",
        str(value or "").lower(),
    )

    ignored = {
        "제품",
        "상품",
        "추천",
        "추천템",
        "리뷰",
        "사용기",
        "비교",
        "내돈내산",
        "필수템",
        "꿀템",
        "신제품",
        "가성비",
        "the",
        "and",
        "for",
    }

    return [
        token
        for token in raw_tokens
        if len(token) >= 2
        and token not in ignored
    ]


# =========================================================
# AI 응답 JSON 처리
# =========================================================
def extract_json(text):
    cleaned = re.sub(
        r"```(?:json)?",
        "",
        str(text or ""),
        flags=re.I,
    ).replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    decoder = json.JSONDecoder()

    for index, char in enumerate(cleaned):
        if char not in "[{":
            continue

        try:
            result, _ = decoder.raw_decode(
                cleaned[index:]
            )
            return result
        except Exception:
            continue

    raise ValueError(
        "OpenRouter 응답에서 JSON을 찾지 못했습니다."
    )


# =========================================================
# 상품 검증
# =========================================================
def contains_non_product_phrase(name):
    """
    명칭에 프로모션·영상 문구가 섞였는지 확인한다.
    """
    normalized = normalize_text(name)

    return any(
        normalize_text(keyword) in normalized
        for keyword in NON_PRODUCT_KEYWORDS
    )


def is_generic_name(name):
    """
    정확한 상품명이 아닌 일반 품목명인지 확인한다.
    """
    normalized = normalize_name(name)

    if not normalized:
        return True

    if normalized in GENERIC_PRODUCT_NAMES:
        return True

    # '추천 로봇청소기', '가성비 충전기'처럼
    # 일반 수식어만 붙은 상품도 차단한다.
    removable_prefixes = (
        "추천",
        "가성비",
        "최고",
        "인기",
        "신상",
        "신제품",
        "내돈내산",
        "필수",
        "프리미엄",
        "무선",
        "휴대용",
        "대용량",
    )

    reduced = normalized

    for prefix in removable_prefixes:
        if reduced.startswith(prefix):
            reduced = reduced[len(prefix):]

    if reduced in GENERIC_PRODUCT_NAMES:
        return True

    return False


def has_model_signal(model, name):
    """
    모델명이 실제 제품 식별 신호를 갖는지 확인한다.

    숫자 또는 영문+숫자 조합이 있으면 강한 모델 신호다.
    고유 모델명이 충분히 긴 경우도 허용한다.
    """
    model = str(model or "").strip()

    if not model:
        return False

    normalized_model = normalize_text(model)

    if len(normalized_model) < 2:
        return False

    # MX Master 3S, T7 Shield, D10, IW4271KRBK 등
    if re.search(
        r"[a-z가-힣]*\d+[a-z0-9가-힣]*",
        normalized_model,
        flags=re.I,
    ):
        return True

    # 숫자가 없어도 고유명사가 충분히 긴 경우
    # 예: 에센셜스킨누더
    if len(normalized_model) >= 5:
        return True

    return False


def product_appears_in_source(
    name,
    brand,
    model,
    video,
):
    """
    AI가 만든 상품 정보가 실제 제목·설명에 존재하는지 확인한다.

    완전 일치가 아니더라도 브랜드와 모델 토큰이
    입력 원문에서 확인되어야 한다.
    """
    source = " ".join(
        [
            str(video.get("title", "")),
            str(video.get("description", "")),
        ]
    ).lower()

    normalized_source = normalize_text(source)
    normalized_name = normalize_text(name)
    normalized_brand = normalize_text(brand)
    normalized_model = normalize_text(model)

    # 정확한 상품명 전체가 입력에 있으면 가장 강한 근거
    if (
        normalized_name
        and normalized_name in normalized_source
    ):
        return True

    brand_found = bool(
        normalized_brand
        and normalized_brand in normalized_source
    )

    model_found = bool(
        normalized_model
        and normalized_model in normalized_source
    )

    if brand_found and model_found:
        return True

    # 상품명 토큰 중 의미 있는 토큰이 얼마나 확인되는지 검사
    tokens = meaningful_tokens(name)

    if not tokens:
        return False

    found_tokens = sum(
        1
        for token in tokens
        if normalize_text(token) in normalized_source
    )

    token_ratio = (
        found_tokens / len(tokens)
        if tokens
        else 0
    )

    # 브랜드가 확인되고 상품명 핵심 토큰 70% 이상 확인
    if brand_found and token_ratio >= 0.70:
        return True

    return False


def validate_product(video, raw):
    """
    AI 출력 상품을 실제 저장 가능한 상품인지 검증한다.

    반환:
    (통과 여부, 정제된 상품 데이터, 제외 이유)
    """
    name = str(
        raw.get("name", "")
    ).strip()

    brand = str(
        raw.get("brand", "")
    ).strip()

    model = str(
        raw.get("model", "")
    ).strip()

    keyword = str(
        raw.get("keyword", "")
    ).strip()

    category = str(
        raw.get("category", "기타")
    ).strip() or "기타"

    evidence = str(
        raw.get("evidence", "")
    ).strip()

    reason = str(
        raw.get("reason", "")
    ).strip()

    try:
        confidence = float(
            raw.get("confidence", 0)
            or 0
        )
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(
        0.0,
        min(1.0, confidence),
    )

    normalized = normalize_name(name)

    if not name:
        return False, None, "상품명 없음"

    if len(normalized) < 5:
        return False, None, "상품명이 너무 짧음"

    if confidence < MIN_CONFIDENCE:
        return (
            False,
            None,
            f"신뢰도 부족: {confidence:.2f}",
        )

    if contains_non_product_phrase(name):
        return (
            False,
            None,
            "프로모션 또는 비상품 표현 포함",
        )

    if is_generic_name(name):
        return (
            False,
            None,
            "일반 품목명",
        )

    # 브랜드 없는 항목은 정확한 상품 식별이 어렵기 때문에 제외
    if not brand:
        return (
            False,
            None,
            "브랜드 없음",
        )

    # 모델 또는 고유 상품명이 있어야 함
    model_signal = has_model_signal(
        model,
        name,
    )

    # 모델명이 비어 있으면 상품명에서
    # 브랜드를 제거한 나머지가 충분히 고유한지 확인
    name_without_brand = normalize_name(
        name
    ).replace(
        normalize_name(brand),
        "",
        1,
    )

    unique_name_signal = (
        len(name_without_brand) >= 5
        and name_without_brand
        not in GENERIC_PRODUCT_NAMES
    )

    if (
        not model_signal
        and not unique_name_signal
    ):
        return (
            False,
            None,
            "모델 또는 고유 상품명 없음",
        )

    if not product_appears_in_source(
        name=name,
        brand=brand,
        model=model,
        video=video,
    ):
        return (
            False,
            None,
            "제목·설명에서 상품 식별 근거 부족",
        )

    # AI evidence 자체도 원문과 너무 동떨어진 경우 제외
    if evidence:
        evidence_tokens = meaningful_tokens(
            evidence
        )

        source_text = normalize_text(
            f"{video.get('title', '')} "
            f"{video.get('description', '')}"
        )

        if evidence_tokens:
            evidence_found = sum(
                1
                for token in evidence_tokens
                if normalize_text(token)
                in source_text
            )

            evidence_ratio = (
                evidence_found
                / len(evidence_tokens)
            )

            if evidence_ratio < 0.35:
                return (
                    False,
                    None,
                    "AI 근거 문장이 원문과 불일치",
                )

    cleaned = {
        "name": name,
        "normalized_name": normalized,
        "brand": brand,
        "model": model,
        "keyword": keyword or name,
        "category": category,
        "reason": reason,
        "pros": [
            str(value).strip()
            for value in raw.get(
                "pros",
                [],
            )
            if str(value).strip()
        ][:4],
        "cons": [
            str(value).strip()
            for value in raw.get(
                "cons",
                [],
            )
            if str(value).strip()
        ][:4],
        "evidence": evidence[:300],
        "confidence": confidence,
        "purchase_type": str(
            raw.get(
                "purchase_type",
                "확인되지 않음",
            )
        ).strip() or "확인되지 않음",
    }

    return True, cleaned, ""


# =========================================================
# OpenRouter 호출
# =========================================================
def call_openrouter(video):
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY가 없습니다."
        )

    prompt = f"""
너는 유튜브 영상에서 실제 판매 제품을 식별하는 상품 데이터 검수자다.

아래 제목과 설명에 직접 명시된 정확한 제품만 추출하라.

중요:
- 일반 품목명은 제품으로 반환하지 마라.
- 브랜드가 없는 항목은 반환하지 마라.
- 모델명 또는 고유 상품명이 없는 항목은 반환하지 마라.
- 운동법, 루틴, 강좌에서 사용한 일반 도구는 반환하지 마라.
- 제목·설명에 없는 제품명을 추측하지 마라.
- 이벤트, 할인, 장소, 앱, 서비스는 상품이 아니다.

반드시 아래 JSON 객체 하나만 반환한다.

{{
  "items": [
    {{
      "name": "브랜드 + 정확한 상품명 또는 모델명",
      "brand": "입력에서 확인된 브랜드",
      "model": "입력에서 확인된 모델명 또는 고유 상품명",
      "keyword": "판매처 검색용 정확한 검색어",
      "category": "IT·전자|뷰티|패션|생활·살림|주방|여행|자동차|운동·건강|육아|반려동물|기타",
      "reason": "영상에서 해당 제품을 소개한 이유",
      "pros": ["입력에서 확인되는 장점"],
      "cons": ["입력에서 확인되는 단점"],
      "evidence": "입력에 실제 존재하는 100자 이하 근거",
      "confidence": 0.0,
      "purchase_type": "직접 구매|제품 제공|유료 광고|확인되지 않음"
    }}
  ]
}}

잘못된 반환 예:
- 사레레 밴드
- 운동 밴드
- 로봇청소기
- 무선 이어폰
- 전기매트
- 주방용품
- 추천템

올바른 반환 예:
- 로지텍 MX Master 3S
- 삼성 포터블 SSD T7 Shield 2TB
- 샤크 젠프로 D10 로봇청소기
- 정샘물 에센셜 스킨 누더 쿠션

규칙:
1. 브랜드가 제목이나 설명에서 확인되어야 한다.
2. 모델 또는 고유 상품명이 제목이나 설명에서 확인되어야 한다.
3. confidence 0.82 이상인 제품만 반환한다.
4. 정확한 제품을 확인할 수 없으면 {{"items": []}}를 반환한다.
5. 동일 제품은 한 번만 반환한다.
6. evidence는 입력 원문에 실제 있는 표현만 사용한다.

[영상 제목]
{video.get("title", "")}

[영상 설명]
{(video.get("description") or "")[:9000]}
""".strip()

    last_error = None

    for model in MODELS:
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": (
                        f"Bearer "
                        f"{OPENROUTER_API_KEY}"
                    ),
                    "Content-Type": (
                        "application/json"
                    ),
                    "HTTP-Referer": (
                        "https://github.com/"
                        "kkddww310/"
                        "ggultem-danawa"
                    ),
                    "X-Title": (
                        "Ggultem Danawa "
                        "Collector"
                    ),
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    "temperature": 0.0,
                },
                timeout=75,
            )

            if response.status_code >= 400:
                raise RuntimeError(
                    f"HTTP "
                    f"{response.status_code}: "
                    f"{response.text[:300]}"
                )

            response_data = response.json()

            content = (
                response_data
                ["choices"][0]
                ["message"]["content"]
            )

            parsed = extract_json(
                content
            )

            if isinstance(parsed, dict):
                items = parsed.get(
                    "items",
                    [],
                )

            elif isinstance(parsed, list):
                items = parsed

            else:
                items = []

            return items

        except Exception as error:
            last_error = error
            time.sleep(1.5)

    raise RuntimeError(
        "OpenRouter 전체 모델 실패: "
        f"{last_error}"
    )


# =========================================================
# Supabase 상품 저장
# =========================================================
def existing_product(normalized):
    rows = select(
        "products",
        (
            "product_id,"
            "normalized_name,"
            "review_status,"
            "is_visible"
        ),
        {
            "normalized_name": (
                f"eq.{normalized}"
            )
        },
        limit=1,
    )

    return rows[0] if rows else None


def save_validated_item(
    video,
    item,
):
    """
    검증을 통과한 정확한 상품만 저장한다.

    새 상품은 pending + 비공개 상태로 저장된다.
    """
    normalized = item[
        "normalized_name"
    ]

    product = existing_product(
        normalized
    )

    if product:
        product_id = product[
            "product_id"
        ]

    else:
        product_id = str(
            uuid.uuid4()
        )

        upsert(
            "products",
            [
                {
                    "product_id": (
                        product_id
                    ),
                    "canonical_name": (
                        item["name"]
                    ),
                    "normalized_name": (
                        normalized
                    ),
                    "brand": (
                        item["brand"]
                    ),
                    "model": (
                        item["model"]
                    ),
                    "category": (
                        item["category"]
                    ),
                    "search_keyword": (
                        item["keyword"]
                    ),

                    # 관리자 승인 전 비공개
                    "review_status": (
                        "pending"
                    ),
                    "is_visible": False,
                    "reviewed_at": None,
                    "review_note": (
                        "자동 수집 후 "
                        "정확한 제품명 검수 대기"
                    ),
                }
            ],
            "normalized_name",
        )

        product = existing_product(
            normalized
        )

        if product:
            product_id = product[
                "product_id"
            ]

    upsert(
        "recommendations",
        [
            {
                "recommendation_id": str(
                    uuid.uuid4()
                ),
                "product_id": (
                    product_id
                ),
                "video_id": (
                    video["video_id"]
                ),
                "channel_id": (
                    video["channel_id"]
                ),
                "reason": (
                    item["reason"]
                ),
                "pros": (
                    item["pros"]
                ),
                "cons": (
                    item["cons"]
                ),
                "evidence": (
                    item["evidence"]
                ),
                "start_sec": 0,
                "confidence": (
                    item["confidence"]
                ),
                "purchase_type": (
                    item[
                        "purchase_type"
                    ]
                ),
            }
        ],
        "product_id,video_id",
    )

    return True


# =========================================================
# 실행
# =========================================================
def main():
    videos = select(
        "videos",
        (
            "video_id,"
            "channel_id,"
            "title,"
            "description,"
            "product_score,"
            "view_count"
        ),
        {
            "analysis_status": (
                "eq.queued"
            )
        },
        limit=BATCH_LIMIT,
        order=(
            "product_score.desc,"
            "view_count.desc"
        ),
    )

    processed = 0
    saved_total = 0
    rejected_total = 0
    failures = 0

    rejection_reasons = {}

    for video in videos:
        try:
            extracted_items = (
                call_openrouter(video)
            )

            if not isinstance(
                extracted_items,
                list,
            ):
                extracted_items = []

            saved = 0
            rejected = 0

            for raw in extracted_items:
                if not isinstance(
                    raw,
                    dict,
                ):
                    rejected += 1
                    continue

                passed, item, reason = (
                    validate_product(
                        video,
                        raw,
                    )
                )

                if not passed:
                    rejected += 1
                    rejection_reasons[
                        reason
                    ] = (
                        rejection_reasons
                        .get(reason, 0)
                        + 1
                    )

                    print(
                        "Rejected product | "
                        f"video="
                        f"{video['video_id']} | "
                        f"name="
                        f"{raw.get('name')} | "
                        f"reason={reason}"
                    )

                    continue

                if save_validated_item(
                    video,
                    item,
                ):
                    saved += 1

            if saved > 0:
                analysis_status = (
                    "analyzed"
                )

                analysis_error = None

            elif rejected > 0:
                analysis_status = (
                    "rejected_generic"
                )

                analysis_error = (
                    "AI가 상품 후보를 "
                    "반환했지만 정확한 "
                    "브랜드·모델 검증에 "
                    "통과하지 못함"
                )

            else:
                analysis_status = (
                    "no_product"
                )

                analysis_error = None

            update(
                "videos",
                {
                    "analysis_status": (
                        analysis_status
                    ),
                    "analysis_error": (
                        analysis_error
                    ),
                },
                {
                    "video_id": (
                        f"eq."
                        f"{video['video_id']}"
                    )
                },
            )

            saved_total += saved
            rejected_total += rejected

        except Exception as error:
            failures += 1

            update(
                "videos",
                {
                    "analysis_status": (
                        "ai_error"
                    ),
                    "analysis_error": str(
                        error
                    )[:1000],
                },
                {
                    "video_id": (
                        f"eq."
                        f"{video['video_id']}"
                    )
                },
            )

            print(
                "AI ERROR | "
                f"video="
                f"{video['video_id']} | "
                f"error={error}"
            )

        processed += 1

    print(
        "Product extraction completed | "
        f"processed={processed} | "
        f"saved={saved_total} | "
        f"rejected={rejected_total} | "
        f"failures={failures}"
    )

    if rejection_reasons:
        print(
            "Rejection reasons:"
        )

        for reason, count in sorted(
            rejection_reasons.items(),
            key=lambda value: (
                value[1]
            ),
            reverse=True,
        ):
            print(
                f"- {reason}: {count}"
            )


if __name__ == "__main__":
    main()

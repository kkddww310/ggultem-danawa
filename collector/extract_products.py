import json
import re
import time
import uuid

import requests

from collector.config import OPENROUTER_API_KEY
from collector.database import select, upsert, update

MODELS = (
    # OpenRouter가 현재 이용 가능한 무료 모델을 자동 선택한다.
    # 개별 :free 모델 ID는 종료되거나 변경될 수 있어 고정하지 않는다.
    "openrouter/free",
)

OPENROUTER_MAX_ATTEMPTS = 3
OPENROUTER_RETRY_SECONDS = (5, 12)

BATCH_LIMIT = 5
MIN_CONFIDENCE = 0.87

GENERIC_TERMS = {
    "사레레밴드", "운동밴드", "저항밴드", "고무밴드", "루프밴드",
    "문틀철봉", "철봉", "수평계", "요가매트", "덤벨", "폼롤러",
    "마사지건", "운동기구", "헬스용품", "로봇청소기", "무선청소기",
    "물걸레청소기", "청소기", "음식물처리기", "공기청정기", "가습기",
    "제습기", "선풍기", "전기매트", "온수매트", "카본매트", "냉장고",
    "김치냉장고", "세탁기", "건조기", "생활용품", "살림용품",
    "수납용품", "욕실용품", "무선이어폰", "이어폰", "헤드폰", "스피커",
    "보조배터리", "충전기", "고속충전기", "케이블", "멀티탭", "노트북",
    "태블릿", "모니터", "키보드", "마우스", "카메라", "마이크",
    "스마트폰", "스마트워치", "전자제품", "it제품", "화장품", "스킨케어",
    "기초화장품", "쿠션", "파운데이션", "컨실러", "틴트", "립", "선크림",
    "클렌저", "클렌징폼", "크림", "세럼", "토너", "향수", "드라이기",
    "고데기", "뷰티디바이스", "주방용품", "조리도구", "프라이팬", "냄비",
    "식칼", "에어프라이어", "전자레인지", "커피머신", "토스터기", "믹서기",
    "정수기", "식기세척기", "밀폐용기", "운동화", "신발", "가방", "백팩",
    "지갑", "선글라스", "시계", "아우터", "옷", "패션아이템", "여행용품",
    "여행필수템", "캐리어", "캠핑용품", "차량용품", "세차용품", "육아용품",
    "육아템", "아기용품", "강아지용품", "고양이용품", "반려동물용품",
    "추천템", "필수템", "꿀템", "아이템", "제품", "상품", "가성비제품",
}

NON_PRODUCT_WORDS = {
    "이벤트", "쿠폰", "할인", "최저가", "프로모션", "장바구니", "챌린지",
    "배송", "신규회원", "구독", "좋아요", "댓글", "공동구매", "체험단",
    "라이브", "브이로그", "루틴", "운동법", "강좌", "튜토리얼", "뉴스",
    "사건", "정치", "예고", "티저", "다시보기", "뮤직비디오",
}

COMPOSITE_MARKERS = ("+", "/", "&", " 세트", " 패키지", " 외 ", " 등 ")


def normalize_text(value):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").lower())


def normalize_name(value):
    text = str(value or "").lower().strip()
    replacements = {
        "logitech": "로지텍", "samsung": "삼성", "apple": "애플",
        "anker": "앤커", "ugreen": "유그린", "dyson": "다이슨",
        "shark": "샤크", "lg electronics": "lg", "lge": "lg",
        "xiaomi": "샤오미", "sony": "소니", "bose": "보스",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return normalize_text(text)


def extract_json(text):
    cleaned = re.sub(r"```(?:json)?", "", str(text or ""), flags=re.I)
    cleaned = cleaned.replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char in "[{":
            try:
                return decoder.raw_decode(cleaned[index:])[0]
            except Exception:
                continue
    raise ValueError("OpenRouter 응답에서 JSON을 찾지 못했습니다.")


def is_generic(value):
    normalized = normalize_text(value)
    if not normalized:
        return True
    if normalized in GENERIC_TERMS:
        return True
    prefixes = ("추천", "가성비", "인기", "신상", "신제품", "내돈내산", "필수", "휴대용", "대용량")
    reduced = normalized
    for prefix in prefixes:
        if reduced.startswith(prefix):
            reduced = reduced[len(prefix):]
    return reduced in GENERIC_TERMS


def contains_composite_marker(name):
    lowered = str(name or "").lower()
    return any(marker in lowered for marker in COMPOSITE_MARKERS)


def contains_non_product_word(name):
    normalized = normalize_text(name)
    return any(normalize_text(word) in normalized for word in NON_PRODUCT_WORDS)


def model_is_specific(model):
    normalized = normalize_text(model)
    if len(normalized) < 2 or is_generic(model):
        return False
    # D10, MX Master 3S, IW4271KRBK처럼 숫자가 있는 모델을 우선 신뢰한다.
    if re.search(r"[a-z가-힣]*\d+[a-z0-9가-힣]*", normalized, flags=re.I):
        return True
    # 숫자가 없는 고유 라인명은 6자 이상이어야 한다.
    return len(normalized) >= 6


def source_contains_identity(video, name, brand, model):
    source = normalize_text(f"{video.get('title', '')} {video.get('description', '')}")
    normalized_name = normalize_text(name)
    normalized_brand = normalize_text(brand)
    normalized_model = normalize_text(model)
    if normalized_name and normalized_name in source:
        return True
    return bool(
        normalized_brand and normalized_model
        and normalized_brand in source and normalized_model in source
    )


def validate_product(video, raw):
    name = str(raw.get("name", "")).strip()
    brand = str(raw.get("brand", "")).strip()
    model = str(raw.get("model", "")).strip()
    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0) or 0)))
    except (TypeError, ValueError):
        confidence = 0.0

    normalized = normalize_name(name)
    if len(normalized) < 5:
        return False, None, "상품명이 너무 짧음"
    if confidence < MIN_CONFIDENCE:
        return False, None, f"신뢰도 부족: {confidence:.2f}"
    if contains_composite_marker(name):
        return False, None, "복합 품목 표현"
    if contains_non_product_word(name):
        return False, None, "비상품 표현 포함"
    if is_generic(name):
        return False, None, "일반 품목명"
    if not brand or is_generic(brand):
        return False, None, "유효한 브랜드 없음"
    if not model_is_specific(model):
        return False, None, "정확한 모델명 없음"
    if not source_contains_identity(video, name, brand, model):
        return False, None, "제목·설명에서 브랜드와 모델 확인 불가"

    evidence = str(raw.get("evidence", "")).strip()
    cleaned = {
        "name": name,
        "normalized_name": normalized,
        "brand": brand,
        "model": model,
        "keyword": str(raw.get("keyword", "")).strip() or name,
        "category": str(raw.get("category", "기타")).strip() or "기타",
        "reason": str(raw.get("reason", "")).strip(),
        "pros": [str(x).strip() for x in raw.get("pros", []) if str(x).strip()][:4],
        "cons": [str(x).strip() for x in raw.get("cons", []) if str(x).strip()][:4],
        "evidence": evidence[:300],
        "confidence": confidence,
        "purchase_type": str(raw.get("purchase_type", "확인되지 않음")).strip() or "확인되지 않음",
    }
    return True, cleaned, ""


def call_openrouter(video):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY가 없습니다.")

    prompt = f'''너는 유튜브 영상에서 실제 판매 제품을 식별하는 상품 데이터 검수자다.
제목과 설명에 직접 명시된 브랜드와 정확한 모델이 있는 단일 제품만 추출하라.
일반 품목명, 운동 도구의 통칭, 여러 물건을 + 또는 /로 묶은 표현은 반환하지 마라.
브랜드 또는 모델을 추측하지 마라.

반드시 JSON 객체 하나만 반환한다.
{{"items":[{{"name":"브랜드 + 정확한 단일 제품명","brand":"브랜드","model":"정확한 모델명","keyword":"판매처 검색용 정확한 상품명","category":"IT·전자|뷰티|패션|생활·살림|주방|여행|자동차|운동·건강|육아|반려동물|기타","reason":"소개 이유","pros":["장점"],"cons":["단점"],"evidence":"원문 근거","confidence":0.0,"purchase_type":"직접 구매|제품 제공|유료 광고|확인되지 않음"}}]}}

차단 예: 사레레 밴드, ironvic 수평계+문틀철봉, 운동 밴드, 로봇청소기, 무선 이어폰.
허용 예: 로지텍 MX Master 3S, 샤크 젠프로 D10, 삼성 T7 Shield 2TB.
confidence 0.87 이상이며 브랜드와 모델이 원문에 직접 확인될 때만 반환한다.
확정할 수 없으면 {{"items":[]}}만 반환한다.

[제목]
{video.get("title", "")}

[설명]
{(video.get("description") or "")[:9000]}'''

    errors = []

    for model in MODELS:
        for attempt in range(1, OPENROUTER_MAX_ATTEMPTS + 1):
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/kkddww310/ggultem-danawa",
                        "X-Title": "Ggultem Danawa Collector",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                    },
                    timeout=40,
                )

                if response.status_code >= 400:
                    body = response.text[:500]
                    error_text = (
                        f"model={model} attempt={attempt} "
                        f"HTTP {response.status_code}: {body}"
                    )
                    errors.append(error_text)
                    print(f"OpenRouter request failed | {error_text}")

                    # 인증·결제 오류는 반복해도 해결되지 않으므로 즉시 중단한다.
                    if response.status_code in {401, 402, 403}:
                        raise RuntimeError(error_text)

                    # 404는 개별 모델 고정 ID에서 주로 발생한다. 다음 모델로 이동한다.
                    if response.status_code == 404:
                        break

                    # 429·5xx는 같은 라우터로 잠시 후 재시도한다.
                    if (
                        response.status_code == 429
                        or response.status_code >= 500
                    ) and attempt < OPENROUTER_MAX_ATTEMPTS:
                        wait_seconds = OPENROUTER_RETRY_SECONDS[attempt - 1]
                        print(
                            "OpenRouter retry scheduled | "
                            f"model={model} wait={wait_seconds}s"
                        )
                        time.sleep(wait_seconds)
                        continue

                    raise RuntimeError(error_text)

                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    raise ValueError(
                        f"model={model} attempt={attempt} choices가 없습니다: "
                        f"{str(data)[:500]}"
                    )

                content = choices[0].get("message", {}).get("content", "")
                parsed = extract_json(content)
                items = parsed.get("items", []) if isinstance(parsed, dict) else parsed

                if not isinstance(items, list):
                    raise ValueError("items가 배열이 아닙니다.")

                print(
                    "OpenRouter request succeeded | "
                    f"model={model} attempt={attempt} items={len(items)}"
                )
                return items

            except requests.Timeout as error:
                error_text = f"model={model} attempt={attempt} timeout: {error}"
                errors.append(error_text)
                print(f"OpenRouter request failed | {error_text}")
                if attempt < OPENROUTER_MAX_ATTEMPTS:
                    wait_seconds = OPENROUTER_RETRY_SECONDS[attempt - 1]
                    time.sleep(wait_seconds)
                    continue

            except (ValueError, KeyError, json.JSONDecodeError) as error:
                error_text = (
                    f"model={model} attempt={attempt} response_error: {error}"
                )
                errors.append(error_text)
                print(f"OpenRouter response invalid | {error_text}")
                if attempt < OPENROUTER_MAX_ATTEMPTS:
                    wait_seconds = OPENROUTER_RETRY_SECONDS[attempt - 1]
                    time.sleep(wait_seconds)
                    continue

            except RuntimeError:
                raise

            except Exception as error:
                error_text = f"model={model} attempt={attempt} error: {error}"
                errors.append(error_text)
                print(f"OpenRouter request failed | {error_text}")
                if attempt < OPENROUTER_MAX_ATTEMPTS:
                    wait_seconds = OPENROUTER_RETRY_SECONDS[attempt - 1]
                    time.sleep(wait_seconds)
                    continue

    error_summary = " || ".join(errors[-8:])
    raise RuntimeError(f"OpenRouter 전체 시도 실패: {error_summary}")


def normalize_brand_key(value):
    text = str(value or "").lower().strip()
    replacements = {
        "dyson": "다이슨", "shark": "샤크", "logitech": "로지텍",
        "samsung": "삼성", "apple": "애플", "anker": "앤커",
        "ugreen": "유그린", "lg electronics": "lg", "lge": "lg",
        "xiaomi": "샤오미", "sony": "소니", "bose": "보스",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return normalize_text(text)


def normalize_model_key(value):
    return normalize_text(value)


def existing_product(normalized):
    rows = select(
        "products",
        (
            "product_id,normalized_name,brand_key,model_key,review_status,"
            "is_visible,merge_status,merged_into"
        ),
        {"normalized_name": f"eq.{normalized}"},
        limit=1,
    )
    return rows[0] if rows else None


def find_product_by_identity(brand_key, model_key):
    if not brand_key or not model_key:
        return None
    rows = select(
        "products",
        (
            "product_id,canonical_name,normalized_name,brand_key,model_key,"
            "review_status,is_visible,merge_status,merged_into,created_at"
        ),
        {
            "brand_key": f"eq.{brand_key}",
            "model_key": f"eq.{model_key}",
            "review_status": "neq.merged",
        },
        limit=20,
        order="is_visible.desc,created_at.asc",
    )
    return rows[0] if rows else None


def calculate_identity_score(video, item):
    score = int(round(float(item["confidence"]) * 40))
    source = normalize_text(f"{video.get('title', '')} {video.get('description', '')}")
    brand_key = normalize_brand_key(item["brand"])
    model_key = normalize_model_key(item["model"])
    name_key = normalize_text(item["name"])
    if brand_key and brand_key in source:
        score += 20
    if model_key and model_key in source:
        score += 25
    if name_key and name_key in source:
        score += 10
    if re.search(r"https?://", str(video.get("description", ""))):
        score += 5
    return min(100, score)


def save_validated_item(video, item):
    brand_key = normalize_brand_key(item["brand"])
    model_key = normalize_model_key(item["model"])
    identity_score = calculate_identity_score(video, item)

    # 1순위: 정규화 상품명이 완전히 같은 기존 상품
    product = existing_product(item["normalized_name"])

    # 2순위: 브랜드와 모델 키가 정확히 같은 기존 대표 상품
    if not product:
        product = find_product_by_identity(brand_key, model_key)

    if product:
        product_id = product["product_id"]
        print(
            "Merged recommendation into existing product | "
            f"product_id={product_id} | brand_key={brand_key} | "
            f"model_key={model_key} | name={item['name']}"
        )
    else:
        product_id = str(uuid.uuid4())

        # 자체 검증점수 93점 이상은 자동 승인, 그 외는 관리자 검수 대기
        auto_approved = identity_score >= 93
        upsert(
            "products",
            [{
                "product_id": product_id,
                "canonical_name": item["name"],
                "normalized_name": item["normalized_name"],
                "brand": item["brand"],
                "model": item["model"],
                "brand_key": brand_key,
                "model_key": model_key,
                "identity_score": identity_score,
                "merge_status": "unique",
                "merged_into": None,
                "category": item["category"],
                "search_keyword": item["keyword"],
                "review_status": "approved" if auto_approved else "pending",
                "is_visible": auto_approved,
                "reviewed_at": None,
                "review_note": (
                    "자동 검증 93점 이상 공개"
                    if auto_approved
                    else "정확한 브랜드·모델 관리자 검수 대기"
                ),
            }],
            "normalized_name",
        )
        refreshed = existing_product(item["normalized_name"])
        if refreshed:
            product_id = refreshed["product_id"]

    upsert(
        "recommendations",
        [{
            "recommendation_id": str(uuid.uuid4()),
            "product_id": product_id,
            "video_id": video["video_id"],
            "channel_id": video["channel_id"],
            "reason": item["reason"],
            "pros": item["pros"],
            "cons": item["cons"],
            "evidence": item["evidence"],
            "start_sec": 0,
            "confidence": item["confidence"],
            "purchase_type": item["purchase_type"],
        }],
        "product_id,video_id",
    )
    return True


def main():
    videos = select(
        "videos",
        "video_id,channel_id,title,description,product_score,view_count",
        {"analysis_status": "eq.queued"},
        limit=BATCH_LIMIT,
        order="product_score.desc,view_count.desc",
    )

    processed = saved_total = rejected_total = failures = 0
    for video in videos:
        try:
            extracted = call_openrouter(video)
            saved = rejected = 0
            for raw in extracted if isinstance(extracted, list) else []:
                if not isinstance(raw, dict):
                    rejected += 1
                    continue
                passed, item, reason = validate_product(video, raw)
                if not passed:
                    rejected += 1
                    print(
                        f"Rejected product | video={video['video_id']} | "
                        f"name={raw.get('name')} | reason={reason}"
                    )
                    continue
                if save_validated_item(video, item):
                    saved += 1

            if saved:
                status, error = "analyzed", None
            elif rejected:
                status, error = "rejected_generic", "정확한 단일 브랜드·모델 검증 실패"
            else:
                status, error = "no_product", None

            update(
                "videos",
                {"analysis_status": status, "analysis_error": error},
                {"video_id": f"eq.{video['video_id']}"},
            )
            saved_total += saved
            rejected_total += rejected
        except Exception as error:
            failures += 1
            update(
                "videos",
                {"analysis_status": "ai_error", "analysis_error": str(error)[:1000]},
                {"video_id": f"eq.{video['video_id']}"},
            )
        processed += 1

    print(
        f"Product extraction completed | processed={processed} | "
        f"saved={saved_total} | rejected={rejected_total} | failures={failures}"
    )


if __name__ == "__main__":
    main()

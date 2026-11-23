import json
import re
import time
import uuid

import requests

from collector.config import OPENROUTER_API_KEY
from collector.database import select, upsert, update
from collector.youtube_api import get_creator_comments

MODELS = ("openrouter/free",)
BATCH_LIMIT = 12
MIN_CONFIDENCE = 0.87
MAX_ATTEMPTS = 2
RETRY_SECONDS = (5,)

GENERIC_TERMS = {
    "사레레밴드", "운동밴드", "저항밴드", "고무밴드", "문틀철봉", "철봉",
    "수평계", "요가매트", "덤벨", "폼롤러", "운동기구", "로봇청소기",
    "무선청소기", "청소기", "음식물처리기", "공기청정기", "가습기",
    "제습기", "선풍기", "전기매트", "생활용품", "살림용품", "무선이어폰",
    "이어폰", "헤드폰", "스피커", "보조배터리", "충전기", "케이블",
    "노트북", "태블릿", "모니터", "키보드", "마우스", "카메라", "마이크",
    "화장품", "스킨케어", "쿠션", "파운데이션", "컨실러", "틴트", "립",
    "선크림", "크림", "세럼", "토너", "향수", "드라이기", "고데기",
    "주방용품", "조리도구", "프라이팬", "냄비", "에어프라이어", "커피머신",
    "믹서기", "정수기", "식기세척기", "운동화", "신발", "가방", "캐리어",
    "패딩", "경량패딩", "자켓", "코트", "니트", "맨투맨", "후드티",
    "셔츠", "바지", "슬랙스", "청바지", "데님", "치마", "스커트",
    "원피스", "양말", "모자", "벨트", "안경", "선글라스", "아우터", "상의", "하의",
    "캠핑용품", "차량용품", "육아용품", "강아지용품", "고양이용품",
    "추천템", "필수템", "꿀템", "아이템", "제품", "상품",
}
UNKNOWN_MODELS = {"", "확인되지않음", "미확인", "unknown", "없음", "미상"}
COMPOSITE_MARKERS = ("+", "/", "&", " 세트", " 패키지", " 외 ", " 등 ")
INVALID_POINT_PATTERNS = (
    "원문에", "명시됨", "후기는 없음", "후기 없음", "언급 없음",
    "정보가 없음", "정보 없음", "정보 부족", "확인되지 않", "알 수 없",
    "단점 없음", "장점 없음", "가격 정보", "가격 미공개", "가격이 공개", "가격 알 수",
)

STANDARD_CATEGORIES = {
    "IT·전자", "뷰티", "패션", "생활·살림", "주방", "여행",
    "자동차", "운동·건강", "육아", "반려동물", "기타",
}
CATEGORY_ALIASES = {
    "it": "IT·전자", "it전자": "IT·전자", "전자": "IT·전자",
    "전자기기": "IT·전자", "디지털": "IT·전자",
    "기타뷰티": "뷰티", "뷰티기타": "뷰티", "화장품": "뷰티",
    "코스메틱": "뷰티", "beauty": "뷰티",
    "의류": "패션", "잡화": "패션", "코디": "패션", "fashion": "패션",
    "주방생활살림": "생활·살림", "생활살림주방": "생활·살림",
    "가전": "생활·살림", "생활가전": "생활·살림", "살림": "생활·살림",
    "생활": "생활·살림", "주방가전": "주방", "조리": "주방",
    "스포츠": "운동·건강", "헬스": "운동·건강", "운동": "운동·건강",
    "펫": "반려동물", "반려견": "반려동물", "반려묘": "반려동물",
    "아동": "육아", "유아": "육아", "차량": "자동차",
}

SPECIFIC_OPTION_PATTERN = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s?(?:ml|l|g|kg|mg|tb|gb|w|mah|hz|인치|매|개|호|번|세대)\b"
    r"|\b[A-Za-z]{1,15}[- ]?\d+[A-Za-z0-9-]*\b"
    r"|(?:핑크골드|베이지|브라운|뉴트럴|피치|로즈|블랙|화이트|레드|블루|그린|퍼플|코랄|네이비|차콜|카키|아이보리))",
    re.I,
)


class OpenRouterDailyLimitReached(RuntimeError):
    """OpenRouter 무료 일일 한도가 소진된 상태."""


def normalize_text(value):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").lower())


def normalize_brand(value):
    text = str(value or "").lower().strip()
    replacements = {
        "dyson": "다이슨", "shark": "샤크", "logitech": "로지텍",
        "samsung": "삼성", "apple": "애플", "anker": "앤커",
        "ugreen": "유그린", "lg electronics": "lg", "lge": "lg",
        "xiaomi": "샤오미", "sony": "소니", "bose": "보스",
        "uniqlo": "유니클로", "zara": "자라", "musinsa": "무신사",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return normalize_text(text)


def build_video_source_text(video):
    desc = str(video.get("description") or "").strip()
    comments = video.get("creator_comments") or []
    if comments:
        joined_comments = "\n\n".join(comments)
        return f"{desc}\n\n[채널 주인 고정/작성 댓글]\n{joined_comments}".strip()
    return desc


def extract_json(text):
    cleaned = re.sub(r"```(?:json)?", "", str(text or ""), flags=re.I)
    cleaned = cleaned.replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    decoder = json.JSONDecoder()
    for index, character in enumerate(cleaned):
        if character in "[{":
            try:
                return decoder.raw_decode(cleaned[index:])[0]
            except Exception:
                continue
    raise ValueError("OpenRouter 응답에서 JSON을 찾지 못했습니다.")


def is_generic(value):
    normalized = normalize_text(value)
    return not normalized or normalized in GENERIC_TERMS


def clean_points(values):
    cleaned_list = []
    for raw in values or []:
        text = re.sub(r"\s+", " ", str(raw or "").strip())
        if len(text) < 2:
            continue
        if any(pattern in text for pattern in INVALID_POINT_PATTERNS):
            continue
        cleaned_list.append(text)
    return cleaned_list[:4]


def has_specific_model(model, category=""):
    normalized = normalize_text(model)
    if normalized in UNKNOWN_MODELS or len(normalized) < 2:
        return False
    if re.search(r"[a-z가-힣]*\d+[a-z0-9가-힣]*", normalized, flags=re.I):
        return True
    # 패션·뷰티·생활 카테고리는 브랜드와 함께 쓰인 4자 이상 구체 품목/라인명을 허용한다.
    if category in {"패션", "뷰티", "생활·살림", "주방", "운동·건강", "육아", "반려동물"}:
        return len(normalized) >= 4
    return len(normalized) >= 5


def source_contains_identity(video, name, brand, model):
    full_source = f"{video.get('title', '')} {build_video_source_text(video)}"
    source = normalize_text(full_source)
    name_key = normalize_text(name)
    brand_key = normalize_brand(brand)
    model_key = normalize_text(model)
    return bool(
        (name_key and name_key in source)
        or (brand_key and model_key and brand_key in source and model_key in source)
    )


def standardize_category(value, name=""):
    raw = str(value or "기타").strip()
    if raw in STANDARD_CATEGORIES:
        return raw
    key = normalize_text(raw)
    if key in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[key]
    product_name = str(name or "").lower()
    if any(word in product_name for word in ("토너", "세럼", "쿠션", "크림", "마스크", "선크림", "틴트", "파운데이션", "고데기", "향수")):
        return "뷰티"
    if any(word in product_name for word in ("패딩", "자켓", "코트", "니트", "팬츠", "슬랙스", "데님", "부츠", "스니커즈", "백팩", "가방")):
        return "패션"
    if any(word in product_name for word in ("냄비", "프라이팬", "식기", "블렌더", "믹서기", "커피머신", "토스터", "에어프라이어")):
        return "주방"
    if any(word in product_name for word in ("청소기", "냉장고", "세탁기", "건조기", "가습기", "제습기", "매트")):
        return "생활·살림"
    return "기타"


def has_specific_option(name, model):
    return bool(SPECIFIC_OPTION_PATTERN.search(f"{name} {model}"))


def concrete_searchable_product(video, item):
    """모델 번호가 없어도 브랜드+고유명+옵션이 원문에 있으면 검색 가능한 상품으로 인정한다."""
    if item["confidence"] < 0.90:
        return False
    if not item["brand_key"] or is_generic(item["brand"]):
        return False
    if is_generic(item["name"]):
        return False
    if any(marker in item["name"].lower() for marker in COMPOSITE_MARKERS):
        return False
    if not source_contains_identity(video, item["name"], item["brand"], item["model"]):
        return False
    if len(item["model_key"]) < 4:
        return False
    return has_specific_option(item["name"], item["model"]) or item["category"] in {"패션", "뷰티"}


def validate_product(video, raw):
    name = str(raw.get("name", "")).strip()
    brand = str(raw.get("brand", "")).strip()
    model = str(raw.get("model", "")).strip()
    category = standardize_category(raw.get("category", "기타"), name)
    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0) or 0)))
    except (TypeError, ValueError):
        confidence = 0.0

    if len(normalize_text(name)) < 5:
        return False, None, "상품명이 너무 짧음"
    if confidence < MIN_CONFIDENCE:
        return False, None, f"신뢰도 부족: {confidence:.2f}"
    if any(marker in name.lower() for marker in COMPOSITE_MARKERS):
        return False, None, "복합 품목 표현"
    if is_generic(name):
        return False, None, "일반 품목명"
    if not brand or is_generic(brand):
        return False, None, "유효한 브랜드 없음"
    if not has_specific_model(model, category):
        return False, None, "정확한 모델/제품명 없음"
    if not source_contains_identity(video, name, brand, model):
        return False, None, "원문에서 브랜드와 제품명 확인 불가"

    item = {
        "name": name,
        "normalized_name": normalize_text(name),
        "brand": brand,
        "model": model,
        "brand_key": normalize_brand(brand),
        "model_key": normalize_text(model),
        "keyword": str(raw.get("keyword", "")).strip() or name,
        "category": category,
        "reason": str(raw.get("reason", "")).strip(),
        "pros": clean_points(raw.get("pros", [])),
        "cons": clean_points(raw.get("cons", [])),
        "evidence": str(raw.get("evidence", "")).strip()[:300],
        "confidence": confidence,
        "purchase_type": str(raw.get("purchase_type", "확인되지 않음")).strip() or "확인되지 않음",
    }
    return True, item, ""


def build_prompt(video):
    source_text = build_video_source_text(video)[:11000]
    return f'''너는 유튜브 영상에서 실제 판매 제품을 식별하는 상품 데이터 검수자다.
제목, 설명, 채널 주인 댓글에 직접 명시된 브랜드와 구체적인 제품명(또는 모델명)이 있는 단일 제품만 추출하라.
하울·모음전·룩북·추천템 리스트 영상처럼 여러 제품이 나열된 경우, 일부만 뽑지 말고 언급된 모든 개별 제품을 빠짐없이 추출하라(최대 15개).
브랜드 없는 일반 품목명이나 여러 물건을 + 또는 /로 묶은 표현은 반환하지 마라.
브랜드나 제품명을 추측하지 마라.
pros와 cons에는 실제 제품의 특징·효능·착용감·사용감·가격적 아쉬움만 적고, "원문에 명시됨", "상세 후기 없음", "가격 정보 미공개" 같은 정보 부재 메모는 절대 넣지 마라. 근거가 없으면 빈 배열 []로 두어라.

반드시 JSON 객체 하나만 반환한다.
{{"items":[{{"name":"브랜드 + 정확한 단일 제품명","brand":"브랜드","model":"모델명 또는 구체 제품명","keyword":"정확한 상품 검색어","category":"IT·전자|뷰티|패션|생활·살림|주방|여행|자동차|운동·건강|육아|반려동물|기타","reason":"소개 이유","pros":["장점"],"cons":["단점"],"evidence":"원문 근거","confidence":0.0,"purchase_type":"직접 구매|제품 제공|유료 광고|확인되지 않음"}}]}}

confidence 0.87 이상이며 브랜드와 제품명이 원문에 직접 있을 때만 반환한다.
확정할 수 없으면 {{"items":[]}}만 반환한다.

[제목]
{video.get("title", "")}

[설명 및 채널 주인 댓글]
{source_text}'''


def call_openrouter(video):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY가 없습니다.")

    prompt = build_prompt(video)
    errors = []

    for model in MODELS:
        for attempt in range(1, MAX_ATTEMPTS + 1):
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
                    timeout=45,
                )

                if response.status_code >= 400:
                    body = response.text[:700]
                    error_text = f"model={model} attempt={attempt} HTTP {response.status_code}: {body}"
                    errors.append(error_text)
                    print(f"OpenRouter request failed | {error_text}")

                    body_lower = body.lower()
                    if response.status_code == 429 and any(
                        marker in body_lower
                        for marker in (
                            "free-models-per-day",
                            "free model requests per day",
                            "free-model daily limit",
                        )
                    ):
                        raise OpenRouterDailyLimitReached(error_text)

                    if response.status_code in {401, 402, 403}:
                        raise RuntimeError(error_text)
                    if response.status_code == 404:
                        break
                    if (response.status_code == 429 or response.status_code >= 500) and attempt < MAX_ATTEMPTS:
                        wait_seconds = RETRY_SECONDS[attempt - 1]
                        print(f"OpenRouter retry scheduled | model={model} wait={wait_seconds}s")
                        time.sleep(wait_seconds)
                        continue
                    raise RuntimeError(error_text)

                payload = response.json()
                choices = payload.get("choices") or []
                if not choices:
                    raise ValueError(f"choices가 없습니다: {str(payload)[:500]}")
                content = choices[0].get("message", {}).get("content", "")
                parsed = extract_json(content)
                items = parsed.get("items", []) if isinstance(parsed, dict) else parsed
                if not isinstance(items, list):
                    raise ValueError("items가 배열이 아닙니다.")
                print(f"OpenRouter request succeeded | model={model} attempt={attempt} items={len(items)}")
                return items[:15]

            except OpenRouterDailyLimitReached:
                raise
            except (requests.Timeout, ValueError, KeyError, json.JSONDecodeError) as error:
                error_text = f"model={model} attempt={attempt} response_error: {error}"
                errors.append(error_text)
                print(f"OpenRouter response failed | {error_text}")
                if attempt < MAX_ATTEMPTS:
                    time.sleep(RETRY_SECONDS[attempt - 1])
                    continue
            except RuntimeError:
                raise
            except Exception as error:
                error_text = f"model={model} attempt={attempt} error: {error}"
                errors.append(error_text)
                print(f"OpenRouter request failed | {error_text}")
                if attempt < MAX_ATTEMPTS:
                    time.sleep(RETRY_SECONDS[attempt - 1])
                    continue

    raise RuntimeError("OpenRouter 전체 시도 실패: " + " || ".join(errors[-8:]))


def find_existing_product(item):
    rows = select(
        "products",
        "product_id,canonical_name,review_status,is_visible,merged_into",
        {
            "brand_key": f"eq.{item['brand_key']}",
            "model_key": f"eq.{item['model_key']}",
            "review_status": "neq.merged",
        },
        limit=1,
        order="is_visible.desc,created_at.asc",
    )
    if rows:
        return rows[0]
    rows = select(
        "products",
        "product_id,canonical_name,review_status,is_visible,merged_into",
        {"normalized_name": f"eq.{item['normalized_name']}"},
        limit=1,
    )
    return rows[0] if rows else None


def identity_score(video, item):
    full_source = f"{video.get('title', '')} {build_video_source_text(video)}"
    source = normalize_text(full_source)
    score = int(round(item["confidence"] * 40))
    if item["brand_key"] in source:
        score += 20
    if item["model_key"] in source:
        score += 25
    if item["normalized_name"] in source:
        score += 10
    if re.search(r"https?://", full_source):
        score += 5
    return min(100, score)


def save_item(video, item):
    product = find_existing_product(item)
    score = identity_score(video, item)

    if product:
        product_id = product["product_id"]
        print(f"Merged recommendation into existing product | product_id={product_id} | name={item['name']}")
    else:
        product_id = str(uuid.uuid4())
        searchable_approved = concrete_searchable_product(video, item)
        auto_approved = score >= 93 or searchable_approved
        upsert(
            "products",
            [{
                "product_id": product_id,
                "canonical_name": item["name"],
                "normalized_name": item["normalized_name"],
                "brand": item["brand"],
                "model": item["model"],
                "brand_key": item["brand_key"],
                "model_key": item["model_key"],
                "identity_score": score,
                "merge_status": "unique",
                "merged_into": None,
                "category": item["category"],
                "search_keyword": item["keyword"],
                "review_status": "approved" if auto_approved else "pending",
                "is_visible": auto_approved,
                "reviewed_at": None,
                "review_note": (
                    "자동 검증 93점 이상 공개"
                    if score >= 93
                    else "브랜드·고유 제품명·옵션 확인 자동 공개"
                    if searchable_approved
                    else "관리자 검수 대기"
                ),
            }],
            "normalized_name",
        )

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
            video["creator_comments"] = get_creator_comments(video["video_id"], video["channel_id"])
            extracted = call_openrouter(video)
            saved = rejected = 0

            for raw in extracted if isinstance(extracted, list) else []:
                if not isinstance(raw, dict):
                    rejected += 1
                    continue
                passed, item, reason = validate_product(video, raw)
                if not passed:
                    rejected += 1
                    print(f"Rejected product | video={video['video_id']} | name={raw.get('name')} | reason={reason}")
                    continue
                if save_item(video, item):
                    saved += 1

            if saved:
                status, error = "analyzed", None
            elif rejected:
                status, error = "rejected_generic", "정확한 브랜드·제품명 검증 실패"
            else:
                status, error = "no_product", None

            update(
                "videos",
                {"analysis_status": status, "analysis_error": error},
                {"video_id": f"eq.{video['video_id']}"},
            )
            processed += 1
            saved_total += saved
            rejected_total += rejected

        except OpenRouterDailyLimitReached as error:
            print(
                "OpenRouter daily free limit reached | "
                f"video={video['video_id']} | batch_stopped=true | "
                "current_and_remaining_videos=queued"
            )
            print(f"OpenRouter limit detail | {str(error)[:700]}")
            break

        except Exception as error:
            failures += 1
            processed += 1
            update(
                "videos",
                {"analysis_status": "ai_error", "analysis_error": str(error)[:1000]},
                {"video_id": f"eq.{video['video_id']}"},
            )

    print(
        f"Product extraction completed | processed={processed} | "
        f"saved={saved_total} | rejected={rejected_total} | failures={failures}"
    )


if __name__ == "__main__":
    main()

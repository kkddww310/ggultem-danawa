import json
import os
import re
import time
import uuid

import requests

from collector.config import OPENROUTER_API_KEY
from collector.database import select, upsert, update
from collector.youtube_api import get_creator_comments

TOTAL_FETCH_LIMIT = 35
BATCH_SIZE = 5
MIN_CONFIDENCE = 0.70
MAX_ATTEMPTS = 2
GEMINI_MIN_INTERVAL_SEC = 13.0

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
COMPOSITE_MARKERS = ("+", "/", "&", " 외 ", " 등 ")
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
BRAND_ALIASES = {
    "dyson": "다이슨", "shark": "샤크", "logitech": "로지텍",
    "samsung": "삼성", "apple": "애플", "anker": "앤커",
    "ugreen": "유그린", "lg electronics": "lg", "lge": "lg",
    "xiaomi": "샤오미", "sony": "소니", "bose": "보스",
    "uniqlo": "유니클로", "zara": "자라", "musinsa": "무신사",
    "insilence": "인사일런스", "spao": "스파오", "cos": "코스",
    "nike": "나이키", "adidas": "아디다스", "newbalance": "뉴발란스",
}

SPECIFIC_OPTION_PATTERN = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s?(?:ml|l|g|kg|mg|tb|gb|w|mah|hz|인치|매|개|호|번|세대)\b"
    r"|\b[A-Za-z]{1,15}[- ]?\d+[A-Za-z0-9-]*\b"
    r"|(?:핑크골드|베이지|브라운|뉴트럴|피치|로즈|블랙|화이트|레드|블루|그린|퍼플|코랄|네이비|차콜|카키|아이보리))",
    re.I,
)
COMPARISON_TITLE_PATTERN = re.compile(
    r"(?:비교|실험|테스트|전부|싹\s?다|다\s?사봤|순위|랭킹|대결|\bvs\b|계급도)",
    re.I,
)
TOP_PICK_EVIDENCE_PATTERN = re.compile(
    r"(?:[123]\s?[위등]|종합\s?(?:1위|우승|추천)|최종\s?(?:추천|선택|픽)|우승|대상|가성비\s?(?:1위|추천|픽)|베스트|best|top\s?[123]|추천\s?픽)",
    re.I,
)
NOISY_KEYWORD_TERMS_PATTERN = re.compile(
    r"\b(?:mastrotrotto|마스트로또|이태리가죽|이탈리아가죽|천연소가죽|소가죽|양가죽|단독특가|공식몰|정품|리뉴얼|기획세트|증정|단품|본품)\b",
    re.I,
)


class AllProvidersRateLimited(RuntimeError):
    """설정된 모든 무료 LLM 제공자의 일일 한도가 소진된 상태."""


class TemporaryProviderUnavailable(RuntimeError):
    """무료 LLM 서버의 일시적 과부하(503) 또는 분당 요청 제한으로 잠시 대기해야 하는 상태."""


def get_providers():
    providers = []
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        providers.append({
            "name": "gemini",
            "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "api_key": gemini_key,
            "model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash",
            "min_interval": GEMINI_MIN_INTERVAL_SEC,
            "extra_headers": {},
        })

    or_key = str(OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY", "")).strip()
    if or_key:
        providers.append({
            "name": "openrouter",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "api_key": or_key,
            "model": os.getenv("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free",
            "min_interval": 1.0,
            "extra_headers": {
                "HTTP-Referer": "https://github.com/kkddww310/ggultem-danawa",
                "X-Title": "Ggultem Danawa Collector",
            },
        })

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        providers.append({
            "name": "groq",
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "api_key": groq_key,
            "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b",
            "min_interval": 2.0,
            "extra_headers": {},
        })
    return providers


def normalize_text(value):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").lower())


def apply_brand_aliases(value):
    text = str(value or "").lower()
    for source, target in BRAND_ALIASES.items():
        text = text.replace(source, target)
    return normalize_text(text)


def normalize_brand(value):
    return apply_brand_aliases(str(value or "").strip())


def clean_search_keyword(keyword, brand="", name=""):
    """쇼핑몰 검색 0건을 유발하는 언더바, 특수기호, 원산지·프로모션 표기를 정제한다."""
    raw = str(keyword or "").strip() or str(name or "").strip()
    text = re.sub(r"[\[\]【】<>]", " ", raw)
    text = re.sub(r"\(([^)]{1,12})\)", r" \1 ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[_/|\\•·*#~\"']+", " ", text)
    text = re.sub(r"(?<=[A-Za-z0-9가-힣])\.(?=\s|$)", " ", text)
    text = NOISY_KEYWORD_TERMS_PATTERN.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()

    deduped = []
    for token in text.split():
        if not deduped or deduped[-1].lower() != token.lower():
            deduped.append(token)
    cleaned = " ".join(deduped).strip()

    if len(normalize_text(cleaned)) < 2:
        fallback = re.sub(r"[_/|\\•·.]+", " ", f"{brand} {name}")
        cleaned = re.sub(r"\s+", " ", fallback).strip()
    return cleaned


def build_video_source_text(video):
    desc = str(video.get("description") or "").strip()
    comments = video.get("creator_comments") or []
    if comments:
        joined_comments = "\n\n".join(comments)
        return f"{desc}\n\n[채널 주인 고정/작성 댓글]\n{joined_comments}".strip()
    return desc


def compact_source_for_batch(video, max_head=750, max_extra_lines=25):
    """배치 호출 시 토큰 한도를 넘기지 않도록 핵심 줄만 압축한다."""
    full_text = build_video_source_text(video)
    head = full_text[:max_head]
    extra = []
    for line in full_text[max_head:].splitlines():
        s = line.strip()
        if not s:
            continue
        has_time = bool(re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", s))
        has_link_or_brand = any(
            k in s.lower()
            for k in ("http://", "https://", "쿠팡", "네이버", "스마트스토어", "무신사", "올리브영", "댓글", "제품", "착용", "리뷰")
        )
        if has_time or has_link_or_brand or len(s) <= 90:
            extra.append(s[:160])
        if len(extra) >= max_extra_lines:
            break
    combined = head + ("\n" + "\n".join(extra) if extra else "")
    return combined[:2000]


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
    raise ValueError("LLM 응답에서 JSON을 찾지 못했습니다.")


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
    if category in {"패션", "뷰티", "생활·살림", "주방", "운동·건강", "육아", "반려동물"}:
        return len(normalized) >= 4
    return len(normalized) >= 5


def source_contains_identity(video, name, brand, model):
    full_source = f"{video.get('title', '')} {build_video_source_text(video)}"
    source_norm = normalize_text(full_source)
    source_alias = apply_brand_aliases(full_source)
    name_key = normalize_text(name)
    name_alias = apply_brand_aliases(name)
    brand_key = normalize_brand(brand)
    model_key = normalize_text(model)
    return bool(
        (name_key and (name_key in source_norm or name_alias in source_alias))
        or (brand_key and model_key and brand_key in source_alias and model_key in source_norm)
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


def needs_comparison_review(video, item):
    """비교·실험 영상인데 상위권/우승 근거가 명확하지 않으면 관리자 검수 탭으로 보류한다."""
    title = str(video.get("title") or "")
    if not COMPARISON_TITLE_PATTERN.search(title):
        return False
    reason_and_evidence = f"{item.get('reason', '')} {item.get('evidence', '')}"
    return not bool(TOP_PICK_EVIDENCE_PATTERN.search(reason_and_evidence))


def validate_product(video, raw):
    if raw.get("is_recommended") is False:
        return False, None, "비교군/하위권 또는 단순 착장(OOTD)"

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

    raw_keyword = str(raw.get("keyword", "")).strip() or name
    cleaned_keyword = clean_search_keyword(raw_keyword, brand=brand, name=name)

    item = {
        "name": name,
        "normalized_name": normalize_text(name),
        "brand": brand,
        "model": model,
        "brand_key": normalize_brand(brand),
        "model_key": normalize_text(model),
        "keyword": cleaned_keyword,
        "category": category,
        "reason": str(raw.get("reason", "")).strip(),
        "pros": clean_points(raw.get("pros", [])),
        "cons": clean_points(raw.get("cons", [])),
        "evidence": str(raw.get("evidence", "")).strip()[:300],
        "confidence": confidence,
        "purchase_type": str(raw.get("purchase_type", "확인되지 않음")).strip() or "확인되지 않음",
    }
    return True, item, ""


def build_batch_prompt(videos):
    payload = [
        {
            "video_id": v["video_id"],
            "title": str(v.get("title") or "")[:180],
            "text": compact_source_for_batch(v),
        }
        for v in videos
    ]
    return f'''너는 유튜브 영상 목록에서 유튜버가 실제로 추천하는 판매 제품을 식별하는 상품 데이터 검수자다.
각 영상의 title과 text에 직접 명시된 브랜드와 구체적인 제품명(또는 모델명)이 있는 단일 제품만 추출하라.

[필터링 규칙]
1. 비교·순위 영상: 유튜버가 최종 추천하거나 상위권(1~3위, 종합 우승, 가성비 추천, 상황별 베스트)으로 꼽은 제품만 추출하라. 4위 이하 하위권 제품, 성능이 떨어져 탈락한 비교 대조군, 비추천 제품은 절대 포함하지 마라.
2. 패션·뷰티 영상: 영상 주제와 무관한 유튜버 본인의 단순 촬영 착장(OOTD 코디용 상하의·신발 등)은 제외하고, 실제로 리뷰·추천하는 메인 제품만 추출하라(영상당 최대 15개).
3. 브랜드 없는 일반 품목명이나 여러 물건을 + 또는 /로 묶은 표현은 반환하지 마라. 브랜드나 제품명을 추측하지 마라.
4. pros와 cons에는 실제 제품의 특징·효능·착용감·사용감·가격적 아쉬움만 적고, "원문에 명시됨", "상세 후기 없음", "가격 정보 미공개" 같은 정보 부재 메모는 절대 넣지 마라. 근거가 없으면 빈 배열 []로 두어라.
5. keyword 필드에는 반드시 쇼핑몰 검색이 바로 되도록 언더바(_)·슬래시(/)·괄호·가죽 원산지 표기(예: MASTROTROTTO, 이태리가죽)를 제거하고 '브랜드 + 핵심 제품명 + 한글 대표 품목명'(예: 올도큐브 iPlay 70 Ultra Pad 태블릿, 다이슨 V15 무선청소기, 어바웃톤 블러 파우더 팩트) 형태로 깔끔하게 적어라.

반드시 아래 JSON 객체 하나만 반환하라. 추천 상품이 없는 영상은 items를 []로 반환하라.
{{"results":[{{"video_id":"영상ID","items":[{{"is_recommended":true,"name":"브랜드 + 정확한 단일 제품명","brand":"브랜드","model":"모델명 또는 구체 제품명","keyword":"브랜드 핵심제품명 한글품목명","category":"IT·전자|뷰티|패션|생활·살림|주방|여행|자동차|운동·건강|육아|반려동물|기타","reason":"추천 이유 또는 선정 근거","pros":["장점"],"cons":["단점"],"evidence":"원문 근거","confidence":0.0,"purchase_type":"직접 구매|제품 제공|유료 광고|확인되지 않음"}}]}}]}}

[입력 영상 목록]
{json.dumps(payload, ensure_ascii=False)}'''


def call_llm_with_fallback(prompt, providers, exhausted_providers, last_call_ts):
    available = [p for p in providers if p["name"] not in exhausted_providers]
    if not available:
        raise AllProvidersRateLimited("모든 무료 LLM 제공자의 일일 한도가 소진되었습니다.")

    errors = []
    transient_failures = 0

    for provider in available:
        name = provider["name"]
        min_interval = float(provider.get("min_interval") or 0.0)

        for attempt in range(1, MAX_ATTEMPTS + 1):
            elapsed = time.time() - last_call_ts.get(name, 0.0)
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)

            last_call_ts[name] = time.time()
            try:
                headers = {
                    "Authorization": f"Bearer {provider['api_key']}",
                    "Content-Type": "application/json",
                }
                headers.update(provider.get("extra_headers") or {})
                response = requests.post(
                    provider["url"],
                    headers=headers,
                    json={
                        "model": provider["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                    },
                    timeout=50,
                )

                if response.status_code >= 400:
                    body = response.text[:500]
                    error_text = f"provider={name} model={provider['model']} attempt={attempt} HTTP {response.status_code}: {body}"
                    errors.append(error_text)
                    print(f"LLM request failed | {error_text}")

                    if response.status_code == 429:
                        transient_failures += 1
                        body_lower = body.lower()
                        is_daily = any(
                            m in body_lower
                            for m in ("per-day", "per day", "daily", "free-models-per-day", "openrouter_free_tier_daily")
                        )
                        if is_daily:
                            exhausted_providers.add(name)
                            break
                        if attempt < MAX_ATTEMPTS:
                            time.sleep(20)
                            continue
                        break

                    if response.status_code in {401, 402, 403, 404}:
                        exhausted_providers.add(name)
                        break

                    if response.status_code == 503:
                        transient_failures += 1
                        break

                    if response.status_code >= 500:
                        transient_failures += 1
                        if attempt < MAX_ATTEMPTS:
                            time.sleep(3)
                            continue
                        break
                    break

                payload = response.json()
                choices = payload.get("choices") or []
                if not choices:
                    raise ValueError(f"choices가 없습니다: {str(payload)[:300]}")
                content = choices[0].get("message", {}).get("content", "")
                parsed = extract_json(content)
                print(f"LLM request succeeded | provider={name} model={provider['model']} attempt={attempt}")
                return parsed

            except requests.Timeout as error:
                transient_failures += 1
                error_text = f"provider={name} model={provider['model']} attempt={attempt} timeout: {error}"
                errors.append(error_text)
                print(f"LLM response failed | {error_text}")
                break
            except (ValueError, KeyError, json.JSONDecodeError) as error:
                transient_failures += 1
                error_text = f"provider={name} model={provider['model']} attempt={attempt} parse_error: {error}"
                errors.append(error_text)
                print(f"LLM response failed | {error_text}")
                if attempt < MAX_ATTEMPTS:
                    time.sleep(3)
                    continue
                break
            except Exception as error:
                error_text = f"provider={name} model={provider['model']} attempt={attempt} error: {error}"
                errors.append(error_text)
                print(f"LLM unexpected error | {error_text}")
                break

    if all(p["name"] in exhausted_providers for p in providers):
        raise AllProvidersRateLimited("모든 무료 LLM 제공자의 일일 한도가 소진되었습니다.")
    if transient_failures > 0:
        raise TemporaryProviderUnavailable("무료 LLM 서버 일시 과부하 또는 분당 한도: " + " || ".join(errors[-4:]))
    raise RuntimeError("LLM 호출 실패: " + " || ".join(errors[-6:]))


def extract_for_chunk(videos, providers, exhausted_providers, last_call_ts):
    """영상 묶음을 한 번에 호출하고, 누락된 video_id만 단건으로 보완한다."""
    prompt = build_batch_prompt(videos)
    parsed = call_llm_with_fallback(prompt, providers, exhausted_providers, last_call_ts)

    results_by_id = {}
    if isinstance(parsed, dict) and isinstance(parsed.get("results"), list):
        for entry in parsed["results"]:
            if not isinstance(entry, dict):
                continue
            vid = str(entry.get("video_id") or "").strip()
            items = entry.get("items")
            if vid and isinstance(items, list):
                results_by_id[vid] = items[:15]

    missing = [v for v in videos if v["video_id"] not in results_by_id]
    for video in missing:
        single_parsed = call_llm_with_fallback(build_batch_prompt([video]), providers, exhausted_providers, last_call_ts)
        items = []
        if isinstance(single_parsed, dict) and isinstance(single_parsed.get("results"), list):
            for entry in single_parsed["results"]:
                if isinstance(entry, dict) and isinstance(entry.get("items"), list):
                    items = entry["items"][:15]
                    break
        results_by_id[video["video_id"]] = items

    return results_by_id


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
    source_norm = normalize_text(full_source)
    source_alias = apply_brand_aliases(full_source)
    score = int(round(item["confidence"] * 40))
    if item["brand_key"] in source_alias:
        score += 20
    if item["model_key"] in source_norm:
        score += 25
    if item["normalized_name"] in source_norm:
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
        comparison_hold = needs_comparison_review(video, item)
        searchable_approved = concrete_searchable_product(video, item)
        auto_approved = (not comparison_hold) and (score >= 93 or searchable_approved)

        if comparison_hold:
            review_note = "비교·테스트 영상 순위 검수 대기"
        elif score >= 93:
            review_note = "자동 검증 93점 이상 공개"
        elif searchable_approved:
            review_note = "브랜드·고유 제품명·옵션 확인 자동 공개"
        else:
            review_note = "관리자 검수 대기"

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
                "review_note": review_note,
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
    providers = get_providers()
    if not providers:
        raise RuntimeError("사용 가능한 LLM API 키(OPENROUTER_API_KEY, GROQ_API_KEY, GEMINI_API_KEY)가 없습니다.")

    videos = select(
        "videos",
        "video_id,channel_id,title,description,product_score,view_count",
        {"analysis_status": "eq.queued"},
        limit=TOTAL_FETCH_LIMIT,
        order="product_score.desc,view_count.desc",
    )

    exhausted_providers = set()
    last_call_ts = {}
    processed = saved_total = rejected_total = failures = 0

    for start in range(0, len(videos), BATCH_SIZE):
        chunk = videos[start:start + BATCH_SIZE]
        for video in chunk:
            video["creator_comments"] = get_creator_comments(video["video_id"], video["channel_id"])

        try:
            extracted_map = extract_for_chunk(chunk, providers, exhausted_providers, last_call_ts)
        except (AllProvidersRateLimited, TemporaryProviderUnavailable) as error:
            print(f"Batch paused (remaining videos kept queued) | detail={str(error)[:400]}")
            break
        except Exception as error:
            for video in chunk:
                failures += 1
                processed += 1
                update(
                    "videos",
                    {"analysis_status": "ai_error", "analysis_error": str(error)[:1000]},
                    {"video_id": f"eq.{video['video_id']}"},
                )
            continue

        for video in chunk:
            extracted = extracted_map.get(video["video_id"], [])
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

    print(
        f"Product extraction completed | processed={processed} | "
        f"saved={saved_total} | rejected={rejected_total} | failures={failures}"
    )


if __name__ == "__main__":
    main()

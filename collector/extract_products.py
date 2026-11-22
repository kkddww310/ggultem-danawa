import json
import re
import time
import uuid

import requests

from collector.config import OPENROUTER_API_KEY
from collector.database import select, upsert, update


MODELS = (
    "openrouter/free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
)

BATCH_LIMIT = 20


def normalize_name(value):
    text = (value or "").lower().strip()

    replacements = {
        "logitech": "로지텍",
        "samsung": "삼성",
        "apple": "애플",
        "anker": "앤커",
        "lg electronics": "lg",
    }

    for source, target in replacements.items():
        text = text.replace(source, target)

    return re.sub(r"[^0-9a-z가-힣]+", "", text)


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
        if char in "[{":
            try:
                result, _ = decoder.raw_decode(cleaned[index:])
                return result
            except Exception:
                pass

    raise ValueError(
        "OpenRouter 응답에서 JSON을 찾지 못했습니다."
    )


def call_openrouter(video):
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY가 없습니다."
        )

    prompt = f"""
너는 유튜브 상품 데이터 검수자다.

아래 영상 제목과 설명에 명시적으로 등장하는
실제 구매 가능한 제품만 추출하라.

브랜드나 모델명이 입력에 없으면 추측하지 마라.
할인, 이벤트, 장소, 서비스, 앱 기능, 뉴스 주제는
상품으로 만들지 마라.

반드시 다음 형식의 JSON 객체 하나만 반환한다.

{{
  "items": [
    {{
      "name": "브랜드 + 정확한 제품명",
      "brand": "브랜드",
      "model": "모델명",
      "keyword": "일반 품목",
      "category": "IT·전자|뷰티|패션|생활·살림|주방|여행|자동차|운동·건강|육아|반려동물|기타",
      "reason": "추천 이유 한 줄",
      "pros": ["장점"],
      "cons": ["단점"],
      "evidence": "입력에 실제 있는 100자 이하 근거",
      "confidence": 0.0,
      "purchase_type": "직접 구매|제품 제공|유료 광고|확인되지 않음"
    }}
  ]
}}

규칙:
1. 제품명이 제목이나 설명에서 직접 확인되어야 한다.
2. confidence가 0.75 이상인 제품만 반환한다.
3. 브랜드 또는 모델을 확인할 수 없으면 추측하지 않는다.
4. 장점과 단점은 입력에 실제로 언급된 내용만 작성한다.
5. 광고나 제품 제공이 명시된 경우에만 해당 상태를 작성한다.
6. 제품을 확정할 수 없으면 {{"items": []}}를 반환한다.
7. 동일한 제품은 한 번만 반환한다.

[영상 제목]
{video.get("title", "")}

[영상 설명]
{(video.get("description") or "")[:7000]}
""".strip()

    last_error = None

    for model in MODELS:
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": (
                        f"Bearer {OPENROUTER_API_KEY}"
                    ),
                    "Content-Type": "application/json",
                    "HTTP-Referer": (
                        "https://github.com/"
                        "kkddww310/ggultem-danawa"
                    ),
                    "X-Title": "Ggultem Danawa Collector",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    "temperature": 0.05,
                },
                timeout=60,
            )

            if response.status_code >= 400:
                raise RuntimeError(
                    f"HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )

            response_data = response.json()

            content = (
                response_data["choices"][0]
                ["message"]["content"]
            )

            parsed = extract_json(content)

            if isinstance(parsed, dict):
                items = parsed.get("items", [])
            elif isinstance(parsed, list):
                items = parsed
            else:
                items = []

            return items

        except Exception as error:
            last_error = error
            time.sleep(1)

    raise RuntimeError(
        f"OpenRouter 전체 모델 실패: {last_error}"
    )


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
            "normalized_name": f"eq.{normalized}",
        },
        limit=1,
    )

    return rows[0] if rows else None


def save_item(video, raw):
    name = str(
        raw.get("name", "")
    ).strip()

    normalized = normalize_name(name)

    try:
        confidence = float(
            raw.get("confidence", 0) or 0
        )
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(
        0.0,
        min(1.0, confidence),
    )

    if len(normalized) < 4:
        return False

    if confidence < 0.75:
        return False

    product = existing_product(normalized)

    if product:
        product_id = product["product_id"]
    else:
        product_id = str(uuid.uuid4())

        upsert(
            "products",
            [
                {
                    "product_id": product_id,
                    "canonical_name": name,
                    "normalized_name": normalized,
                    "brand": str(
                        raw.get("brand", "")
                    ).strip(),
                    "model": str(
                        raw.get("model", "")
                    ).strip(),
                    "category": str(
                        raw.get("category", "기타")
                    ).strip() or "기타",
                    "search_keyword": str(
                        raw.get("keyword", "")
                    ).strip() or name,

                    # 신규 자동 수집 상품은
                    # 관리자 승인 전까지 공개하지 않는다.
                    "review_status": "pending",
                    "is_visible": False,
                    "reviewed_at": None,
                    "review_note": (
                        "자동 수집 후 검수 대기"
                    ),
                }
            ],
            "normalized_name",
        )

        product = existing_product(normalized)

        if product:
            product_id = product["product_id"]

    pros = [
        str(value).strip()
        for value in raw.get("pros", [])
        if str(value).strip()
    ][:4]

    cons = [
        str(value).strip()
        for value in raw.get("cons", [])
        if str(value).strip()
    ][:4]

    purchase_type = str(
        raw.get(
            "purchase_type",
            "확인되지 않음",
        )
    ).strip() or "확인되지 않음"

    upsert(
        "recommendations",
        [
            {
                "recommendation_id": str(
                    uuid.uuid4()
                ),
                "product_id": product_id,
                "video_id": video["video_id"],
                "channel_id": video["channel_id"],
                "reason": str(
                    raw.get("reason", "")
                ).strip(),
                "pros": pros,
                "cons": cons,
                "evidence": str(
                    raw.get("evidence", "")
                ).strip()[:300],
                "start_sec": 0,
                "confidence": confidence,
                "purchase_type": purchase_type,
            }
        ],
        "product_id,video_id",
    )

    return True


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
            "analysis_status": "eq.queued",
        },
        limit=BATCH_LIMIT,
        order="product_score.desc,view_count.desc",
    )

    processed = 0
    saved_total = 0
    failures = 0

    for video in videos:
        try:
            extracted_items = call_openrouter(video)

            saved = 0

            if not isinstance(extracted_items, list):
                extracted_items = []

            for item in extracted_items:
                if not isinstance(item, dict):
                    continue

                if save_item(video, item):
                    saved += 1

            update(
                "videos",
                {
                    "analysis_status": (
                        "analyzed"
                        if saved
                        else "no_product"
                    ),
                    "analysis_error": None,
                },
                {
                    "video_id": (
                        f"eq.{video['video_id']}"
                    )
                },
            )

            saved_total += saved

        except Exception as error:
            failures += 1

            update(
                "videos",
                {
                    "analysis_status": "ai_error",
                    "analysis_error": str(error)[:1000],
                },
                {
                    "video_id": (
                        f"eq.{video['video_id']}"
                    )
                },
            )

        processed += 1

    print(
        f"AI processed {processed} videos; "
        f"saved recommendations: {saved_total}; "
        f"failures: {failures}"
    )


if __name__ == "__main__":
    main()

import re
from collections import defaultdict

from collector.database import select, update

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
    "스마트폰", "스마트워치", "전자제품", "화장품", "스킨케어",
    "기초화장품", "쿠션", "파운데이션", "컨실러", "틴트", "립",
    "선크림", "클렌저", "크림", "세럼", "토너", "향수", "드라이기",
    "고데기", "주방용품", "조리도구", "프라이팬", "냄비", "식칼",
    "에어프라이어", "전자레인지", "커피머신", "토스터기", "믹서기",
    "정수기", "식기세척기", "밀폐용기", "운동화", "신발", "가방",
    "백팩", "지갑", "선글라스", "시계", "아우터", "여행용품",
    "여행필수템", "캐리어", "캠핑용품", "차량용품", "세차용품",
    "육아용품", "육아템", "아기용품", "강아지용품", "고양이용품",
    "추천템", "필수템", "꿀템", "아이템", "제품", "상품",
}

UNKNOWN_MODELS = {
    "", "확인되지않음", "확인되지않은", "미확인", "unknown", "없음", "미상"
}

COMPOSITE_MARKERS = ("+", "/", "&", " 세트", " 패키지", " 외 ", " 등 ")
AUTO_APPROVE_SCORE = 93
CONCRETE_APPROVE_SCORE = 82
SPECIFIC_OPTION_PATTERN = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s?(?:ml|l|g|kg|mg|tb|gb|w|mah|hz|인치|매|개|호|번|세대)\b"
    r"|\b[A-Za-z]{1,15}[- ]?\d+[A-Za-z0-9-]*\b"
    r"|(?:핑크골드|베이지|브라운|뉴트럴|피치|로즈|블랙|화이트|레드|블루|그린|퍼플|코랄))",
    re.I,
)


def normalize(value):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").lower())


def is_generic(value):
    normalized = normalize(value)
    return not normalized or normalized in GENERIC_TERMS


def has_composite_marker(value):
    lowered = str(value or "").lower()
    return any(marker in lowered for marker in COMPOSITE_MARKERS)


def identity_key(product):
    brand_key = normalize(product.get("brand_key") or product.get("brand"))
    model_key = normalize(product.get("model_key") or product.get("model"))
    return brand_key, model_key


def video_ids_for_product(recommendations, product_id):
    return {
        row.get("video_id")
        for row in recommendations
        if row.get("product_id") == product_id and row.get("video_id")
    }


def choose_representative(products):
    """승인·공개·고점수·오래된 상품을 대표로 선택한다."""
    return sorted(
        products,
        key=lambda row: (
            0 if row.get("review_status") == "approved" else 1,
            0 if row.get("is_visible") else 1,
            -int(row.get("identity_score") or 0),
            row.get("created_at") or "",
        ),
    )[0]


def hide_product(product, reason):
    update(
        "products",
        {
            "review_status": "hidden",
            "is_visible": False,
            "merge_status": "review",
            "review_note": reason,
        },
        {"product_id": f"eq.{product['product_id']}"},
    )


def approve_product(product):
    update(
        "products",
        {
            "review_status": "approved",
            "is_visible": True,
            "merge_status": "unique",
            "review_note": "자동 식별점수 93점 이상 공개",
        },
        {"product_id": f"eq.{product['product_id']}"},
    )


def merge_product(duplicate, representative):
    # 추천 영상 중복이 없는 경우에만 안전하게 product_id를 이동한다.
    update(
        "recommendations",
        {"product_id": representative["product_id"]},
        {"product_id": f"eq.{duplicate['product_id']}"},
    )
    update(
        "products",
        {
            "review_status": "merged",
            "is_visible": False,
            "merge_status": "matched",
            "merged_into": representative["product_id"],
            "review_note": "브랜드·모델 키 정확히 일치하여 자동 병합",
        },
        {"product_id": f"eq.{duplicate['product_id']}"},
    )


def is_concrete_searchable(product, recommendation):
    """과거 pending 상품도 브랜드+고유명+옵션+신뢰도가 충분하면 자동 승인한다."""
    name = str(product.get("canonical_name") or "")
    brand = str(product.get("brand") or "")
    model = str(product.get("model") or "")
    score = int(product.get("identity_score") or 0)
    confidence = float((recommendation or {}).get("confidence") or 0)

    if score < CONCRETE_APPROVE_SCORE or confidence < 0.90:
        return False
    if not normalize(brand) or is_generic(brand):
        return False
    if not normalize(model) or is_generic(model):
        return False
    if is_generic(name) or has_composite_marker(name):
        return False
    if len(normalize(model)) < 6:
        return False
    return bool(SPECIFIC_OPTION_PATTERN.search(f"{name} {model}"))


def main():
    products = select(
        "products",
        (
            "product_id,canonical_name,brand,model,brand_key,model_key,"
            "identity_score,review_status,is_visible,merge_status,created_at"
        ),
        {"review_status": "eq.pending"},
        limit=5000,
        order="created_at.asc",
    )
    recommendations = select(
        "recommendations",
        "recommendation_id,product_id,video_id,confidence",
        limit=10000,
    )

    best_recommendation = {}
    for recommendation in recommendations:
        product_id = recommendation.get("product_id")
        current = best_recommendation.get(product_id)
        if current is None or float(recommendation.get("confidence") or 0) > float(current.get("confidence") or 0):
            best_recommendation[product_id] = recommendation

    hidden = approved = merged = review_kept = 0

    # 1. 명백히 부정확한 대기 상품 자동 숨김
    survivors = []
    for product in products:
        name = product.get("canonical_name") or ""
        brand = product.get("brand") or ""
        model = product.get("model") or ""
        normalized_model = normalize(model)

        if has_composite_marker(name):
            hide_product(product, "복합 품목 표현 자동 숨김")
            hidden += 1
            continue
        if is_generic(name):
            hide_product(product, "일반 품목명 자동 숨김")
            hidden += 1
            continue
        if not normalize(brand) or is_generic(brand):
            hide_product(product, "유효한 브랜드 없음 자동 숨김")
            hidden += 1
            continue
        if normalized_model in UNKNOWN_MODELS or is_generic(model):
            hide_product(product, "정확한 모델명 없음 자동 숨김")
            hidden += 1
            continue
        survivors.append(product)

    # 2. 기존 승인 상품을 포함해 브랜드+모델 동일 그룹 구성
    all_products = select(
        "products",
        (
            "product_id,canonical_name,brand,model,brand_key,model_key,"
            "identity_score,review_status,is_visible,merge_status,created_at"
        ),
        {"review_status": "neq.merged"},
        limit=10000,
        order="created_at.asc",
    )
    groups = defaultdict(list)
    for product in all_products:
        key = identity_key(product)
        if key[0] and key[1] and key[1] not in UNKNOWN_MODELS:
            groups[key].append(product)

    survivor_ids = {row["product_id"] for row in survivors}

    for product in survivors:
        # 앞선 병합에서 이미 처리된 경우 건너뜀
        if product["product_id"] not in survivor_ids:
            continue

        group = groups.get(identity_key(product), [])
        representative = choose_representative(group) if group else product

        if representative["product_id"] != product["product_id"]:
            duplicate_videos = video_ids_for_product(recommendations, product["product_id"])
            keeper_videos = video_ids_for_product(recommendations, representative["product_id"])

            if duplicate_videos & keeper_videos:
                # UNIQUE(product_id, video_id) 충돌 위험이 있어 자동 병합하지 않는다.
                update(
                    "products",
                    {
                        "merge_status": "review",
                        "review_note": "동일 브랜드·모델이나 추천 영상 중복으로 수동 병합 필요",
                    },
                    {"product_id": f"eq.{product['product_id']}"},
                )
                review_kept += 1
                continue

            merge_product(product, representative)
            merged += 1
            survivor_ids.discard(product["product_id"])
            continue

        score = int(product.get("identity_score") or 0)
        concrete = is_concrete_searchable(
            product,
            best_recommendation.get(product["product_id"]),
        )
        if score >= AUTO_APPROVE_SCORE or concrete:
            update(
                "products",
                {
                    "review_status": "approved",
                    "is_visible": True,
                    "merge_status": "unique",
                    "review_note": (
                        "자동 식별점수 93점 이상 공개"
                        if score >= AUTO_APPROVE_SCORE
                        else "브랜드·고유 제품명·옵션 확인 자동 공개"
                    ),
                },
                {"product_id": f"eq.{product['product_id']}"},
            )
            approved += 1
        else:
            update(
                "products",
                {
                    "merge_status": "review",
                    "review_note": "자동 승인 기준 미달로 관리자 검수 유지",
                },
                {"product_id": f"eq.{product['product_id']}"},
            )
            review_kept += 1

    print(
        "Product cleanup completed | "
        f"pending_scanned={len(products)} | hidden={hidden} | "
        f"merged={merged} | approved={approved} | review_kept={review_kept}"
    )


if __name__ == "__main__":
    main()

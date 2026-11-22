def save_item(video, raw):
    name = str(raw.get("name", "")).strip()
    normalized = normalize_name(name)

    confidence = max(
        0.0,
        min(
            1.0,
            float(raw.get("confidence", 0) or 0)
        )
    )

    if len(normalized) < 4 or confidence < 0.75:
        return False

    product = existing_product(normalized)

    product_id = (
        product["product_id"]
        if product
        else str(uuid.uuid4())
    )

    # 새 상품은 관리자 검수 전까지 공개하지 않음
    if not product:
        upsert(
            "products",
            [{
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

                # 관리자 검수 필드
                "review_status": "pending",
                "is_visible": False,
                "reviewed_at": None,
                "review_note": "자동 수집 후 검수 대기"
            }],
            "normalized_name"
        )

        product = existing_product(normalized)

        if product:
            product_id = product["product_id"]

    # 추천 기록은 상품 공개 여부와 관계없이 저장
    upsert(
        "recommendations",
        [{
            "recommendation_id": str(uuid.uuid4()),
            "product_id": product_id,
            "video_id": video["video_id"],
            "channel_id": video["channel_id"],
            "reason": str(
                raw.get("reason", "")
            ).strip(),
            "pros": [
                str(value).strip()
                for value in raw.get("pros", [])
                if str(value).strip()
            ][:4],
            "cons": [
                str(value).strip()
                for value in raw.get("cons", [])
                if str(value).strip()
            ][:4],
            "evidence": str(
                raw.get("evidence", "")
            ).strip()[:300],
            "start_sec": 0,
            "confidence": confidence,
            "purchase_type": str(
                raw.get(
                    "purchase_type",
                    "확인되지 않음"
                )
            ).strip() or "확인되지 않음"
        }],
        "product_id,video_id"
    )

    return True

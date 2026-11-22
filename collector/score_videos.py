import re
from urllib.parse import urlparse

from collector.database import select, update

# 제품 구매·리뷰 의도가 강한 표현
PRODUCT_INTENT = {
    "내돈내산": 7, "찐추천": 6, "추천템": 6, "필수템": 6,
    "인생템": 6, "하울": 6, "언박싱": 6, "구매 후기": 6,
    "한달 사용": 6, "한 달 사용": 6, "실사용": 5,
    "사용기": 5, "리뷰": 5, "비교": 5, "써봤": 4,
    "사봤": 4, "구매": 4, "신제품": 4, "가성비": 3,
    "추천": 2, "베스트": 3, "top": 3,
}

COMMERCE_SIGNALS = {
    "유료 광고": 6, "유료광고": 6, "제품 제공": 6, "제품제공": 6,
    "협찬": 5, "광고 포함": 5, "광고포함": 5, "파트너스": 6,
    "구매 링크": 5, "구매링크": 5, "제품 링크": 5, "제품링크": 5,
    "공식몰": 4, "스마트스토어": 4, "올리브영": 3,
    "쿠팡": 3, "네이버쇼핑": 3, "오늘의집": 3,
}

# 요리·일상 콘텐츠 표현. 제품 중심 신호가 없으면 강하게 제외한다.
RECIPE_LIFESTYLE = {
    "cook with me": -12, "meal prep": -12, "요리 모음": -12,
    "집밥": -9, "레시피": -10, "도시락": -9, "반찬": -9,
    "아침밥": -8, "저녁밥": -8, "야식": -7, "먹는": -5,
    "만들기": -5, "요리법": -9, "요리 방법": -9, "한끼": -6,
    "한 끼": -6, "주방 브이로그": -10, "살림 브이로그": -8,
    "새벽 5시": -6, "새벽 5시 기상": -8, "냉장고 털기": -8,
}

# 청소법·정리법·관리법·메이크업 방법 등 제품보다 방법이 중심인 영상
METHOD_LIFESTYLE = {
    "청소법": -12, "청소 방법": -12, "세탁법": -12, "세탁 방법": -12,
    "정리법": -12, "정리 방법": -12, "수납법": -10, "관리법": -10,
    "관리 방법": -10, "집안일": -9, "살림 루틴": -10, "청소 루틴": -10,
    "세탁 루틴": -10, "정리 루틴": -10, "봄맞이 청소": -10,
    "대청소": -8, "옷장 정리": -9, "냉장고 정리": -9, "욕실 청소": -9,
    "주방 청소": -9, "메이크업 방법": -12, "메이크업 튜토리얼": -12,
    "메이크업 룩": -8, "눈 커지는": -10, "얼굴 작아지는": -10,
    "피부 관리법": -10, "바디 관리": -8, "헤어 관리": -8,
    "꿀팁": -5, "노하우": -5, "방법": -4, "활용법": -7,
}

STRONG_NEGATIVE = {
    "뮤직비디오": -18, "music video": -18, "official mv": -18,
    "티저": -12, "예고편": -12, "다시보기": -12,
    "하이라이트": -10, "경기": -10, "야구": -10, "축구": -10,
    "농구": -10, "뉴스": -12, "속보": -14, "정치": -12,
    "국회": -12, "선거": -12, "사건": -10, "사고": -10,
    "먹방": -10, "브이로그": -6, "vlog": -6, "라이브": -8,
    "챌린지": -8, "웹예능": -9, "몰아보기": -12,
    "운동 루틴": -10, "홈트 루틴": -10, "운동법": -10,
    "자세 교정": -9, "강의": -9, "강좌": -9, "튜토리얼": -9,
}

SHOPPING_DOMAINS = {
    "coupang.com", "link.coupang.com", "shopping.naver.com",
    "smartstore.naver.com", "brand.naver.com", "oliveyoung.co.kr",
    "ohou.se", "11st.co.kr", "gmarket.co.kr", "auction.co.kr",
    "ssg.com", "lotteon.com", "musinsa.com", "29cm.co.kr", "kurly.com",
}

# 제목이 제품 자체를 중심으로 한다는 신호
PRODUCT_TITLE_PATTERNS = (
    re.compile(r"(?:추천|리뷰|비교|사용기|언박싱|내돈내산|사봤|써봤)"),
    re.compile(r"(?:냄비|블렌더|청소기|모니터|노트북|이어폰|키보드|마우스|충전기|화장품|쿠션|선크림|가방|신발)\s*(?:추천|리뷰|비교)"),
    re.compile(r"\b[A-Za-z]{2,15}[- ]?[A-Za-z]*\d+[A-Za-z0-9-]*\b", re.I),
)

MODEL_PATTERNS = (
    re.compile(r"\b[A-Za-z]{1,15}[- ]?\d{1,5}[A-Za-z0-9-]*\b", re.I),
    re.compile(
        r"\b(?=[A-Za-z0-9-]{5,20}\b)(?=[A-Za-z0-9-]*[A-Za-z])"
        r"(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]+\b",
        re.I,
    ),
)


def normalize(value):
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def keyword_score(text, rules):
    total = 0
    matches = []
    for keyword, points in rules.items():
        if keyword in text:
            total += points
            matches.append(keyword)
    return total, matches


def shopping_links(description):
    domains = set()
    for url in re.findall(r'https?://[^\s<>\"]+', str(description or ""), flags=re.I):
        try:
            hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
            for domain in SHOPPING_DOMAINS:
                if hostname == domain or hostname.endswith(f".{domain}"):
                    domains.add(domain)
                    break
        except Exception:
            continue
    return sorted(domains)


def model_signals(text):
    found = set()
    for pattern in MODEL_PATTERNS:
        for token in pattern.findall(text):
            normalized = re.sub(r"[^0-9a-z가-힣]+", "", token.lower())
            if normalized and normalized not in {"top10", "top5", "2024", "2025", "2026", "2027"}:
                found.add(token)
    return sorted(found)


def has_product_title_signal(title):
    return any(pattern.search(title) for pattern in PRODUCT_TITLE_PATTERNS)


def score_video(video):
    title = normalize(video.get("title"))
    description = normalize(video.get("description"))
    combined = f"{title} {description}"

    title_intent, title_matches = keyword_score(title, PRODUCT_INTENT)
    description_intent, _ = keyword_score(description, PRODUCT_INTENT)
    commerce, commerce_matches = keyword_score(combined, COMMERCE_SIGNALS)
    recipe_penalty, recipe_matches = keyword_score(title, RECIPE_LIFESTYLE)
    method_penalty, method_matches = keyword_score(title, METHOD_LIFESTYLE)
    negative, negative_matches = keyword_score(combined, STRONG_NEGATIVE)
    domains = shopping_links(video.get("description"))
    models = model_signals(combined)
    product_title = has_product_title_signal(title)

    score = 0
    reasons = []

    if title_intent:
        points = min(14, int(title_intent * 1.35))
        score += points
        reasons.append(f"제목 제품 의도 +{points}")

    if description_intent:
        points = min(6, description_intent)
        score += points
        reasons.append(f"설명 제품 의도 +{points}")

    if commerce:
        points = min(9, commerce)
        score += points
        reasons.append(f"상거래 신호 +{points}")

    if domains:
        points = min(6, len(domains) * 2)
        score += points
        reasons.append(f"쇼핑 링크 +{points}")

    if models:
        points = min(6, len(models) * 2)
        score += points
        reasons.append(f"모델 신호 +{points}")

    if product_title:
        score += 3
        reasons.append("제품 중심 제목 +3")

    # 레시피·집밥 영상은 제품 중심 제목이거나 강한 상거래 증거가 있어야 살린다.
    if recipe_matches:
        rescue = (
            product_title
            or title_intent >= 4
            or (commerce >= 5 and bool(domains))
            or (bool(models) and title_intent >= 2)
        )
        if rescue:
            applied = max(-4, recipe_penalty // 3)
            score += applied
            reasons.append(f"레시피지만 제품 중심 {applied}")
        else:
            score += recipe_penalty
            reasons.append(f"레시피·일상 {recipe_penalty}")

    # 청소법·정리법·관리법은 제품 중심 제목이나 구체적 모델이 있을 때만 살린다.
    if method_matches:
        method_rescue = (
            title_intent >= 5
            or (product_title and bool(models))
            or (bool(models) and commerce >= 5 and bool(domains))
        )
        if method_rescue:
            applied = max(-4, method_penalty // 3)
            score += applied
            reasons.append(f"생활방법이지만 제품 중심 {applied}")
        else:
            score += method_penalty
            reasons.append(f"청소·정리·관리 방법 {method_penalty}")

    if negative:
        score += negative
        reasons.append(f"비상품 영상 {negative}")

    # 명확한 제품 신호가 전혀 없으면 쇼핑 링크만으로 후보가 되지 않도록 한다.
    if not product_title and title_intent == 0 and not models:
        score -= 5
        reasons.append("제목 제품 식별 신호 없음 -5")

    # 요리·일상 제목인데 구체적인 브랜드/모델과 제품 의도가 없으면 강제 제외권.
    hard_recipe_block = bool(recipe_matches) and not (
        product_title or title_intent >= 4 or (commerce >= 5 and domains) or (models and title_intent >= 2)
    )
    hard_method_block = bool(method_matches) and not (
        title_intent >= 5
        or (product_title and bool(models))
        or (models and commerce >= 5 and domains)
    )

    # 설명란의 쇼핑 링크만으로 후보가 되는 것을 막는다.
    # 제목에 제품 의도가 있거나 구체적 모델 신호가 있어야 한다.
    identity_gate = bool(models) or title_intent >= 4 or product_title

    score = max(-40, min(30, score))
    return {
        "score": score,
        "hard_recipe_block": hard_recipe_block,
        "hard_method_block": hard_method_block,
        "identity_gate": identity_gate,
        "reasons": reasons,
        "domains": domains,
        "models": models[:10],
        "recipe_matches": recipe_matches,
        "method_matches": method_matches,
        "negative_matches": negative_matches,
        "commerce_matches": commerce_matches,
        "title_matches": title_matches,
    }


def main():
    videos = select(
        "videos",
        "video_id,title,description,view_count,analysis_status",
        {"analysis_status": "eq.pending"},
        limit=5000,
        order="published_at.desc",
    )

    threshold = 6
    queued = skipped = 0

    for video in videos:
        result = score_video(video)
        if (
            result["score"] >= threshold
            and result["identity_gate"]
            and not result["hard_recipe_block"]
            and not result["hard_method_block"]
        ):
            status = "queued"
            queued += 1
        else:
            status = "skipped_non_product"
            skipped += 1

        diagnostic_parts = list(result["reasons"])
        if result["models"]:
            diagnostic_parts.append("모델=" + ", ".join(result["models"]))
        if result["domains"]:
            diagnostic_parts.append("쇼핑도메인=" + ", ".join(result["domains"]))
        if result["recipe_matches"]:
            diagnostic_parts.append("레시피표현=" + ", ".join(result["recipe_matches"]))
        if result["method_matches"]:
            diagnostic_parts.append("생활방법표현=" + ", ".join(result["method_matches"]))

        update(
            "videos",
            {
                "product_score": result["score"],
                "analysis_status": status,
                "analysis_error": " | ".join(diagnostic_parts)[:1000] or None,
            },
            {"video_id": f"eq.{video['video_id']}"},
        )

        print(
            f"Scored video | id={video['video_id']} | score={result['score']} | "
            f"status={status} | recipe_block={result['hard_recipe_block']} | "
            f"method_block={result['hard_method_block']} | "
            f"identity_gate={result['identity_gate']} | "
            f"title={video.get('title', '')[:90]}"
        )

    print(
        "Video scoring completed | "
        f"scored={len(videos)} | queued={queued} | skipped={skipped} | "
        f"threshold={threshold}"
    )


if __name__ == "__main__":
    main()

import re
from urllib.parse import urlparse

from collector.database import select, update

# 제목에 이 표현이 있으면 '제품 검토 목적'으로 인정
STRONG_REVIEW_TERMS = (
    "내돈내산", "리뷰", "비교", "사용기", "실사용", "한달 사용",
    "한 달 사용", "언박싱", "써봤", "사봤", "구매 후기", "추천템",
    "필수템", "인생템", "하울", "재구매", "살까", "사라면",
)

# 여러 제품을 소개하는 영상으로 인정할 제목 표현
MULTI_PRODUCT_TERMS = (
    "추천템", "필수템", "하울", "내돈내산", "잘 산", "잘산",
    "베스트", "best", "top", "추천 리스트", "꿀템",
)

# 제목에서 제품 품목과 검토 의도가 같이 있어야 통과시키는 품목
PRODUCT_NOUNS = (
    "로봇청소기", "무선청소기", "청소기", "냉장고", "김치냉장고",
    "음식물처리기", "세탁기", "건조기", "공기청정기", "제습기",
    "가습기", "전기매트", "냄비", "프라이팬", "블렌더", "믹서기",
    "에어프라이어", "커피머신", "식기세척기", "밀폐용기", "모니터",
    "노트북", "태블릿", "스마트폰", "이어폰", "헤드폰", "스피커",
    "키보드", "마우스", "충전기", "보조배터리", "카메라", "마이크",
    "선크림", "세럼", "쿠션", "파운데이션", "컨실러", "틴트",
    "향수", "드라이기", "고데기", "뷰티 디바이스", "운동화",
    "신발", "가방", "캐리어", "차량용품", "육아용품", "반려동물용품",
)

# 제목 중심이 방법·일상·정보일 때 제외
METHOD_OR_NON_PRODUCT = (
    "청소법", "청소 방법", "세탁법", "세탁 방법", "정리법", "정리 방법",
    "관리법", "관리 방법", "활용법", "사용법", "집안일", "살림 루틴",
    "청소 루틴", "세탁 루틴", "봄맞이 청소", "대청소", "메이크업 방법",
    "메이크업 튜토리얼", "메이크업 룩", "눈 커지는", "얼굴 작아지는",
    "피부 관리법", "바디 관리", "헤어 관리", "스타일링", "운동법",
    "운동 루틴", "자세 교정", "집밥", "레시피", "요리 모음",
    "도시락", "반찬", "cook with me", "meal prep", "브이로그", "vlog",
    "뉴스", "속보", "정치", "국회", "선거", "경기", "야구", "축구",
    "뮤직비디오", "티저", "예고편", "다시보기", "하이라이트", "먹방",
)

SHOPPING_DOMAINS = {
    "coupang.com", "link.coupang.com", "shopping.naver.com",
    "smartstore.naver.com", "brand.naver.com", "oliveyoung.co.kr",
    "ohou.se", "11st.co.kr", "gmarket.co.kr", "auction.co.kr",
    "ssg.com", "lotteon.com", "musinsa.com", "29cm.co.kr", "kurly.com",
}

# 제목에 있는 구체 모델만 인정. 설명란 숫자·가격·연도는 모델로 보지 않음.
TITLE_MODEL_PATTERNS = (
    re.compile(r"\b[A-Za-z가-힣]{1,20}[- ]?[A-Za-z가-힣]*\d+[A-Za-z0-9가-힣-]*\b", re.I),
    re.compile(
        r"\b(?=[A-Za-z0-9-]{4,20}\b)(?=[A-Za-z0-9-]*[A-Za-z])"
        r"(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]+\b",
        re.I,
    ),
)

FALSE_MODEL_TOKENS = {
    "2024", "2025", "2026", "2027", "top3", "top5", "top10",
    "4k", "8k", "1080p", "24시간", "30일", "100일",
}


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def find_title_models(title):
    found = set()
    for pattern in TITLE_MODEL_PATTERNS:
        for token in pattern.findall(title):
            key = re.sub(r"[^0-9a-z가-힣]+", "", token.lower())
            if len(key) >= 3 and key not in FALSE_MODEL_TOKENS:
                found.add(token.strip())
    return sorted(found)


def find_shopping_domains(description):
    result = set()
    for url in re.findall(r'https?://[^\s<>\"]+', str(description or ""), re.I):
        try:
            host = (urlparse(url).hostname or "").lower().removeprefix("www.")
            for domain in SHOPPING_DOMAINS:
                if host == domain or host.endswith(f".{domain}"):
                    result.add(domain)
                    break
        except Exception:
            continue
    return sorted(result)


def contains_any(text, terms):
    return [term for term in terms if term in text]


def product_nouns_in_title(title):
    return [term for term in PRODUCT_NOUNS if term in title]


def classify(video):
    title = norm(video.get("title"))
    description = norm(video.get("description"))

    review_terms = contains_any(title, STRONG_REVIEW_TERMS)
    multi_terms = contains_any(title, MULTI_PRODUCT_TERMS)
    method_terms = contains_any(title, METHOD_OR_NON_PRODUCT)
    product_nouns = product_nouns_in_title(title)
    title_models = find_title_models(title)
    shopping_domains = find_shopping_domains(description)

    # 필수 통과 경로 A: 제목에 구체 모델이 있고 제품 품목/리뷰 표현 중 하나 존재
    model_path = bool(title_models) and bool(product_nouns or review_terms)

    # 필수 통과 경로 B: 제목에 제품 품목 + 강한 리뷰/비교/사용 의도
    review_path = bool(product_nouns) and bool(review_terms)

    # 필수 통과 경로 C: 다제품 추천 형식. 설명에 실제 쇼핑 링크가 있어야 함
    multi_path = bool(multi_terms) and bool(shopping_domains)

    # 방법/일상 콘텐츠는 모델+강한 리뷰 표현이 함께 있을 때만 예외 허용
    hard_block = bool(method_terms) and not (
        bool(title_models) and bool(review_terms) and bool(product_nouns)
    )

    passed = (model_path or review_path or multi_path) and not hard_block

    score = 0
    reasons = []
    if model_path:
        score += 10
        reasons.append("제목 모델+제품 신호 +10")
    if review_path:
        score += 8
        reasons.append("제목 품목+검토 의도 +8")
    if multi_path:
        score += 7
        reasons.append("다제품 추천+쇼핑 링크 +7")
    if title_models:
        score += min(4, len(title_models) * 2)
    if shopping_domains:
        score += min(3, len(shopping_domains))
    if hard_block:
        score = -20
        reasons.append("방법·일상 콘텐츠 강제 제외")
    if not passed and not hard_block:
        score = min(score, 4)
        reasons.append("제목 필수 게이트 미통과")

    return {
        "passed": passed,
        "score": score,
        "title_models": title_models,
        "product_nouns": product_nouns,
        "review_terms": review_terms,
        "multi_terms": multi_terms,
        "method_terms": method_terms,
        "shopping_domains": shopping_domains,
        "reasons": reasons,
    }


def main():
    videos = select(
        "videos",
        "video_id,title,description,analysis_status,published_at",
        {"analysis_status": "eq.pending"},
        limit=5000,
        order="published_at.desc",
    )

    queued = 0
    skipped = 0

    for video in videos:
        result = classify(video)
        status = "queued" if result["passed"] else "skipped_non_product"
        queued += int(result["passed"])
        skipped += int(not result["passed"])

        diagnostics = list(result["reasons"])
        if result["title_models"]:
            diagnostics.append("제목모델=" + ", ".join(result["title_models"]))
        if result["product_nouns"]:
            diagnostics.append("제품품목=" + ", ".join(result["product_nouns"]))
        if result["review_terms"]:
            diagnostics.append("검토표현=" + ", ".join(result["review_terms"]))
        if result["method_terms"]:
            diagnostics.append("차단표현=" + ", ".join(result["method_terms"]))
        if result["shopping_domains"]:
            diagnostics.append("쇼핑도메인=" + ", ".join(result["shopping_domains"]))

        update(
            "videos",
            {
                "product_score": result["score"],
                "analysis_status": status,
                "analysis_error": " | ".join(diagnostics)[:1000] or None,
            },
            {"video_id": f"eq.{video['video_id']}"},
        )

        print(
            f"Scored video | id={video['video_id']} | score={result['score']} | "
            f"status={status} | title_models={bool(result['title_models'])} | "
            f"review_path={bool(result['product_nouns'] and result['review_terms'])} | "
            f"multi_path={bool(result['multi_terms'] and result['shopping_domains'])} | "
            f"title={video.get('title', '')[:100]}"
        )

    print(
        "Video scoring completed | "
        f"scored={len(videos)} | queued={queued} | skipped={skipped} | "
        "gate=title_required"
    )


if __name__ == "__main__":
    main()

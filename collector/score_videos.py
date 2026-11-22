import re
from urllib.parse import urlparse

from collector.database import select, update


# =========================================================
# 후보 점수 기준
# =========================================================

# 구매 의도가 강한 표현
STRONG_POSITIVE = {
    "내돈내산": 6,
    "찐추천": 5,
    "추천템": 5,
    "필수템": 5,
    "잘 산": 5,
    "잘산": 5,
    "인생템": 5,
    "하울": 5,
    "언박싱": 5,
    "구매 후기": 5,
    "한달 사용": 5,
    "한 달 사용": 5,
    "실사용": 4,
    "사용기": 4,
    "리뷰": 4,
    "비교": 4,
    "써봤": 4,
    "사봤": 4,
    "구매": 3,
    "신제품": 3,
    "가성비": 3,
    "베스트": 3,
    "top": 3,
}

# 설명란에 있으면 상품 소개 가능성이 높은 표현
COMMERCE_SIGNALS = {
    "유료 광고": 5,
    "유료광고": 5,
    "제품 제공": 5,
    "제품제공": 5,
    "협찬": 4,
    "광고 포함": 4,
    "광고포함": 4,
    "파트너스": 5,
    "구매 링크": 4,
    "구매링크": 4,
    "제품 링크": 4,
    "제품링크": 4,
    "최저가 링크": 3,
    "공식몰": 3,
    "스마트스토어": 3,
    "올리브영": 2,
    "쿠팡": 2,
    "네이버쇼핑": 2,
    "오늘의집": 2,
}

# 판매처나 쇼핑 도메인
SHOPPING_DOMAINS = {
    "coupang.com",
    "link.coupang.com",
    "shopping.naver.com",
    "smartstore.naver.com",
    "brand.naver.com",
    "oliveyoung.co.kr",
    "ohou.se",
    "11st.co.kr",
    "gmarket.co.kr",
    "auction.co.kr",
    "ssg.com",
    "lotteon.com",
    "musinsa.com",
    "29cm.co.kr",
    "kurly.com",
    "aliexpress.com",
    "amazon.com",
}

# 영상 성격상 상품 추출 대상이 아닐 가능성이 큰 표현
STRONG_NEGATIVE = {
    "뮤직비디오": -15,
    "music video": -15,
    "official mv": -15,
    "티저": -10,
    "예고편": -10,
    "다시보기": -10,
    "하이라이트": -8,
    "경기": -8,
    "야구": -8,
    "축구": -8,
    "농구": -8,
    "골 모음": -10,
    "뉴스": -10,
    "속보": -12,
    "정치": -10,
    "국회": -10,
    "선거": -10,
    "사건": -8,
    "사고": -8,
    "먹방": -7,
    "브이로그": -5,
    "vlog": -5,
    "라이브": -7,
    "live": -4,
    "챌린지": -6,
    "토크": -4,
    "인터뷰": -4,
    "웹예능": -7,
    "몰아보기": -10,
}

# 운동·강좌 영상에서 일반 도구 한 번 언급되는 일을 줄임
TUTORIAL_NEGATIVE = {
    "운동 루틴": -8,
    "홈트 루틴": -8,
    "헬스 루틴": -8,
    "운동법": -8,
    "사용법": -3,
    "자세 교정": -7,
    "근육 키우기": -7,
    "어깨 운동": -7,
    "가슴 운동": -7,
    "하체 운동": -7,
    "등 운동": -7,
    "강의": -7,
    "강좌": -7,
    "튜토리얼": -7,
    "레시피": -5,
    "요리 방법": -5,
}

# 브랜드·모델 후보 패턴
MODEL_PATTERNS = (
    # MX Master 3S, T7 Shield, R2, D10
    re.compile(
        r"\b[A-Za-z]{1,15}[- ]?\d{1,5}[A-Za-z0-9-]*\b",
        re.I,
    ),

    # IW4271KRBK, B95AWBH 등 긴 영숫자 모델
    re.compile(
        r"\b(?=[A-Za-z0-9-]{5,20}\b)"
        r"(?=[A-Za-z0-9-]*[A-Za-z])"
        r"(?=[A-Za-z0-9-]*\d)"
        r"[A-Za-z0-9-]+\b",
        re.I,
    ),

    # 2TB, 100W, 27인치, 4K 등 상세 사양
    re.compile(
        r"\b\d+(?:\.\d+)?"
        r"(?:tb|gb|w|mah|hz|인치|세대|k)\b",
        re.I,
    ),
)

# 너무 흔해 모델 신호로 쓰면 안 되는 표현
FALSE_MODEL_TOKENS = {
    "top10",
    "top5",
    "top3",
    "2024",
    "2025",
    "2026",
    "2027",
    "4k",
    "1080p",
    "shorts",
}


# =========================================================
# 유틸
# =========================================================
def normalize_text(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or "").lower(),
    ).strip()


def count_keyword_score(text, rules):
    score = 0
    matched = []

    for keyword, points in rules.items():
        if keyword in text:
            score += points
            matched.append(
                {
                    "keyword": keyword,
                    "points": points,
                }
            )

    return score, matched


def extract_urls(text):
    return re.findall(
        r"https?://[^\s<>\"]+",
        str(text or ""),
        flags=re.I,
    )


def count_shopping_links(description):
    count = 0
    domains = set()

    for url in extract_urls(description):
        try:
            hostname = (
                urlparse(url).hostname
                or ""
            ).lower()

            hostname = hostname.removeprefix(
                "www."
            )

            for domain in SHOPPING_DOMAINS:
                if (
                    hostname == domain
                    or hostname.endswith(
                        f".{domain}"
                    )
                ):
                    count += 1
                    domains.add(domain)
                    break

        except Exception:
            continue

    return count, sorted(domains)


def find_model_signals(text):
    found = set()

    for pattern in MODEL_PATTERNS:
        for match in pattern.findall(text):
            token = str(match).strip()

            normalized = re.sub(
                r"[^0-9a-z가-힣]+",
                "",
                token.lower(),
            )

            if not normalized:
                continue

            if normalized in FALSE_MODEL_TOKENS:
                continue

            found.add(token)

    return sorted(found)


# =========================================================
# 영상 점수 계산
# =========================================================
def score_video(video):
    title = normalize_text(
        video.get("title", "")
    )

    description = normalize_text(
        video.get("description", "")
    )

    combined = f"{title} {description}"

    score = 0
    reasons = []

    # 제목은 구매 의도가 강하므로 더 높은 비중
    title_score, title_matches = (
        count_keyword_score(
            title,
            STRONG_POSITIVE,
        )
    )

    if title_score:
        weighted_title_score = int(
            title_score * 1.4
        )

        score += weighted_title_score

        reasons.append(
            f"제목 상품 의도 "
            f"+{weighted_title_score}"
        )

    # 설명란의 추천·리뷰 표현
    description_score, _ = (
        count_keyword_score(
            description,
            STRONG_POSITIVE,
        )
    )

    if description_score:
        # 설명란은 반복 키워드가 많으므로 최대 8점
        applied = min(
            description_score,
            8,
        )

        score += applied

        reasons.append(
            f"설명 상품 의도 +{applied}"
        )

    # 광고·제품 제공·구매 링크 설명
    commerce_score, _ = (
        count_keyword_score(
            combined,
            COMMERCE_SIGNALS,
        )
    )

    if commerce_score:
        applied = min(
            commerce_score,
            10,
        )

        score += applied

        reasons.append(
            f"상거래 신호 +{applied}"
        )

    # 실제 쇼핑 링크
    shopping_link_count, domains = (
        count_shopping_links(
            video.get(
                "description",
                "",
            )
        )
    )

    if shopping_link_count:
        link_score = min(
            9,
            shopping_link_count * 3,
        )

        score += link_score

        reasons.append(
            f"쇼핑 링크 {shopping_link_count}개 "
            f"+{link_score}"
        )

    # 모델 번호나 구체적 사양
    model_signals = find_model_signals(
        combined
    )

    if model_signals:
        model_score = min(
            8,
            len(model_signals) * 2,
        )

        score += model_score

        reasons.append(
            f"모델·사양 신호 "
            f"{len(model_signals)}개 "
            f"+{model_score}"
        )

    # 강한 제외어
    negative_score, negative_matches = (
        count_keyword_score(
            combined,
            STRONG_NEGATIVE,
        )
    )

    if negative_score:
        score += negative_score

        reasons.append(
            f"비상품 영상 {negative_score}"
        )

    # 강좌·운동법 감점
    tutorial_score, tutorial_matches = (
        count_keyword_score(
            combined,
            TUTORIAL_NEGATIVE,
        )
    )

    if tutorial_score:
        score += tutorial_score

        reasons.append(
            f"강좌·루틴 {tutorial_score}"
        )

    # 제목에 상품 의도도 없고 쇼핑 링크도 없으면 추가 감점
    if (
        title_score == 0
        and shopping_link_count == 0
        and commerce_score == 0
    ):
        score -= 3
        reasons.append(
            "구매 근거 부족 -3"
        )

    # 모델 신호만 있고 리뷰·추천·링크가 전혀 없으면
    # 연도·화질·점수 등을 모델로 오인했을 수 있으므로 감점
    if (
        model_signals
        and title_score == 0
        and commerce_score == 0
        and shopping_link_count == 0
    ):
        score -= 2
        reasons.append(
            "모델 단독 신호 -2"
        )

    # 최종 점수를 과도하게 크게 저장하지 않도록 제한
    score = max(
        -30,
        min(30, score),
    )

    return {
        "score": score,
        "reasons": reasons,
        "shopping_links": (
            shopping_link_count
        ),
        "shopping_domains": domains,
        "model_signals": (
            model_signals[:10]
        ),
        "negative_matches": [
            item["keyword"]
            for item
            in negative_matches
        ][:10],
        "tutorial_matches": [
            item["keyword"]
            for item
            in tutorial_matches
        ][:10],
    }


# =========================================================
# 실행
# =========================================================
def main():
    videos = select(
        "videos",
        (
            "video_id,"
            "title,"
            "description,"
            "view_count,"
            "analysis_status"
        ),
        {
            "analysis_status": (
                "eq.pending"
            )
        },
        limit=5000,
        order=(
            "published_at.desc"
        ),
    )

    queued = 0
    skipped = 0

    # 5점 이상을 AI 후보로 전송
    queue_threshold = 5

    for video in videos:
        result = score_video(
            video
        )

        product_score = result[
            "score"
        ]

        if product_score >= (
            queue_threshold
        ):
            status = "queued"
            queued += 1

        else:
            status = (
                "skipped_non_product"
            )
            skipped += 1

        diagnostic = (
            " | ".join(
                result["reasons"]
            )
        )

        if result[
            "model_signals"
        ]:
            diagnostic += (
                " | 모델신호="
                + ", ".join(
                    result[
                        "model_signals"
                    ]
                )
            )

        if result[
            "shopping_domains"
        ]:
            diagnostic += (
                " | 쇼핑도메인="
                + ", ".join(
                    result[
                        "shopping_domains"
                    ]
                )
            )

        update(
            "videos",
            {
                "product_score": (
                    product_score
                ),
                "analysis_status": (
                    status
                ),

                # 후보 점수 근거를 관리용으로 저장한다.
                # errors 컬럼을 진단 로그로도 활용한다.
                "analysis_error": (
                    diagnostic[:1000]
                    if diagnostic
                    else None
                ),
            },
            {
                "video_id": (
                    f"eq."
                    f"{video['video_id']}"
                )
            },
        )

        print(
            f"Scored video | "
            f"id={video['video_id']} | "
            f"score={product_score} | "
            f"status={status} | "
            f"title="
            f"{video.get('title', '')[:80]}"
        )

    print(
        "Video scoring completed | "
        f"scored={len(videos)} | "
        f"queued={queued} | "
        f"skipped={skipped} | "
        f"threshold={queue_threshold}"
    )


if __name__ == "__main__":
    main()

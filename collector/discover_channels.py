from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

from collector.config import (
    DISCOVERY_QUERIES,
    DISCOVERY_QUERY_LIMIT,
    MIN_SUBSCRIBERS,
)
from collector.database import upsert
from collector.youtube_api import (
    search_videos,
    get_channels,
)


KST = timezone(timedelta(hours=9))


def normalize_query_entry(entry):
    """
    config.py의 검색어를 표준 형태로 변환한다.

    새 형식:
    {
        "query": "로봇청소기 사용기",
        "category": "생활·살림"
    }

    구형 문자열 형식도 호환한다.
    """
    if isinstance(entry, dict):
        query = str(
            entry.get("query", "")
        ).strip()

        category = str(
            entry.get("category", "기타")
        ).strip() or "기타"

        return {
            "query": query,
            "category": category,
        }

    return {
        "query": str(entry or "").strip(),
        "category": "기타",
    }


def get_daily_queries():
    """
    현재 날짜를 기준으로 오늘 실행할 검색어 묶음을 선택한다.

    예:
    전체 검색어 140개
    하루 실행 20개

    1일차: 0~19
    2일차: 20~39
    3일차: 40~59
    ...
    7일차: 120~139
    8일차: 다시 0~19
    """
    normalized_queries = [
        normalize_query_entry(entry)
        for entry in DISCOVERY_QUERIES
    ]

    normalized_queries = [
        entry
        for entry in normalized_queries
        if entry["query"]
    ]

    if not normalized_queries:
        return []

    limit = max(
        1,
        min(
            DISCOVERY_QUERY_LIMIT,
            len(normalized_queries),
        ),
    )

    today = datetime.now(KST).date()

    # 2026-01-01을 순환 기준일로 사용한다.
    base_date = datetime(
        2026,
        1,
        1,
        tzinfo=KST,
    ).date()

    elapsed_days = (
        today - base_date
    ).days

    start_index = (
        elapsed_days * limit
    ) % len(normalized_queries)

    selected = []

    for offset in range(limit):
        index = (
            start_index + offset
        ) % len(normalized_queries)

        selected.append(
            normalized_queries[index]
        )

    return selected


def discover_channel_candidates(
    selected_queries,
):
    """
    오늘 선택된 검색어로 YouTube 영상을 검색하고
    실제 업로드 채널 ID를 수집한다.

    채널명 문자열을 추측하지 않고
    YouTube 검색 결과의 snippet.channelId를 사용한다.
    """
    channel_names = {}
    category_votes = defaultdict(Counter)
    query_results = []

    for index, entry in enumerate(
        selected_queries,
        start=1,
    ):
        query = entry["query"]
        category = entry["category"]

        try:
            items = search_videos(
                query,
                max_results=25,
            )

            discovered_in_query = set()

            for item in items:
                snippet = item.get(
                    "snippet",
                    {},
                )

                channel_id = str(
                    snippet.get(
                        "channelId",
                        "",
                    )
                ).strip()

                channel_name = str(
                    snippet.get(
                        "channelTitle",
                        "",
                    )
                ).strip()

                if not channel_id:
                    continue

                discovered_in_query.add(
                    channel_id
                )

                if channel_name:
                    channel_names[
                        channel_id
                    ] = channel_name

                category_votes[
                    channel_id
                ][category] += 1

            query_results.append(
                {
                    "query": query,
                    "category": category,
                    "found": len(
                        discovered_in_query
                    ),
                    "error": "",
                }
            )

            print(
                f"[{index}/"
                f"{len(selected_queries)}] "
                f"{category} | "
                f"{query} | "
                f"channels="
                f"{len(discovered_in_query)}"
            )

        except Exception as error:
            query_results.append(
                {
                    "query": query,
                    "category": category,
                    "found": 0,
                    "error": str(error),
                }
            )

            print(
                f"[{index}/"
                f"{len(selected_queries)}] "
                f"{category} | "
                f"{query} | "
                f"ERROR: {error}"
            )

    return {
        "channel_ids": list(
            channel_names.keys()
        ),
        "channel_names": channel_names,
        "category_votes": category_votes,
        "query_results": query_results,
    }


def choose_primary_category(
    channel_id,
    category_votes,
):
    """
    한 채널이 여러 검색 분야에서 발견된 경우
    가장 많이 발견된 분야를 대표 카테고리로 사용한다.
    """
    votes = category_votes.get(
        channel_id,
    )

    if not votes:
        return "기타"

    return votes.most_common(1)[0][0]


def build_channel_records(
    channel_items,
    candidate_data,
):
    """
    YouTube channels.list 결과를
    Supabase channels 테이블 형식으로 변환한다.
    """
    records = []

    scanned_at = datetime.now(
        timezone.utc
    ).isoformat()

    category_votes = candidate_data[
        "category_votes"
    ]

    fallback_names = candidate_data[
        "channel_names"
    ]

    for item in channel_items:
        channel_id = str(
            item.get("id", "")
        ).strip()

        if not channel_id:
            continue

        snippet = item.get(
            "snippet",
            {},
        )

        statistics = item.get(
            "statistics",
            {},
        )

        content_details = item.get(
            "contentDetails",
            {},
        )

        related_playlists = (
            content_details
            .get(
                "relatedPlaylists",
                {},
            )
        )

        uploads_playlist_id = (
            related_playlists
            .get("uploads")
        )

        hidden_subscribers = bool(
            statistics.get(
                "hiddenSubscriberCount",
                False,
            )
        )

        try:
            subscriber_count = int(
                statistics.get(
                    "subscriberCount",
                    0,
                )
                or 0
            )
        except (TypeError, ValueError):
            subscriber_count = 0

        if hidden_subscribers:
            status = (
                "hidden_subscribers"
            )

        elif subscriber_count >= (
            MIN_SUBSCRIBERS
        ):
            status = "active"

        else:
            status = (
                "below_threshold"
            )

        channel_name = str(
            snippet.get(
                "title",
                "",
            )
            or fallback_names.get(
                channel_id,
                "",
            )
        ).strip()

        primary_category = (
            choose_primary_category(
                channel_id,
                category_votes,
            )
        )

        category_counts = dict(
            category_votes.get(
                channel_id,
                {},
            )
        )

        records.append(
            {
                "channel_id": (
                    channel_id
                ),
                "channel_name": (
                    channel_name
                    or channel_id
                ),
                "subscriber_count": (
                    subscriber_count
                ),
                "subscriber_hidden": (
                    hidden_subscribers
                ),
                "country": (
                    snippet.get(
                        "country"
                    )
                ),
                "description": str(
                    snippet.get(
                        "description",
                        "",
                    )
                    or ""
                )[:5000],
                "primary_category": (
                    primary_category
                ),
                "category_scores": (
                    category_counts
                ),
                "uploads_playlist_id": (
                    uploads_playlist_id
                ),
                "status": status,
                "last_scanned_at": (
                    scanned_at
                ),
            }
        )

    return records


def main():
    """
    날짜에 따라 검색어 일부를 순환 실행하고
    발견된 YouTube 채널을 Supabase에 저장한다.
    """
    selected_queries = (
        get_daily_queries()
    )

    if not selected_queries:
        print(
            "실행할 검색어가 없습니다."
        )
        return

    print(
        "YouTube channel discovery "
        "started"
    )

    print(
        f"Total configured queries: "
        f"{len(DISCOVERY_QUERIES)}"
    )

    print(
        f"Queries selected today: "
        f"{len(selected_queries)}"
    )

    for entry in selected_queries:
        print(
            f"- [{entry['category']}] "
            f"{entry['query']}"
        )

    candidate_data = (
        discover_channel_candidates(
            selected_queries
        )
    )

    channel_ids = candidate_data[
        "channel_ids"
    ]

    if not channel_ids:
        print(
            "검색 결과에서 채널을 "
            "발견하지 못했습니다."
        )
        return

    print(
        f"Unique channel candidates: "
        f"{len(channel_ids)}"
    )

    channel_items = get_channels(
        channel_ids
    )

    records = build_channel_records(
        channel_items,
        candidate_data,
    )

    if records:
        upsert(
            "channels",
            records,
            "channel_id",
        )

    active_count = sum(
        1
        for record in records
        if record["status"] == "active"
    )

    below_count = sum(
        1
        for record in records
        if record["status"]
        == "below_threshold"
    )

    hidden_count = sum(
        1
        for record in records
        if record["status"]
        == "hidden_subscribers"
    )

    query_error_count = sum(
        1
        for result
        in candidate_data[
            "query_results"
        ]
        if result["error"]
    )

    print(
        "Channel discovery completed | "
        f"saved={len(records)} | "
        f"active_1m_plus="
        f"{active_count} | "
        f"below_threshold="
        f"{below_count} | "
        f"hidden_subscribers="
        f"{hidden_count} | "
        f"query_errors="
        f"{query_error_count}"
    )


if __name__ == "__main__":
    main()

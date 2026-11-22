from datetime import datetime, timezone

from collector.config import DISCOVERY_QUERIES
from collector.database import select, upsert


def normalize_entry(entry):
    """config.py의 문자열/딕셔너리 검색어를 DB 저장 형식으로 통일한다."""
    if isinstance(entry, dict):
        query_text = str(entry.get("query", "")).strip()
        category = str(entry.get("category", "기타")).strip() or "기타"
        priority = int(entry.get("priority", 1) or 1)
    else:
        query_text = str(entry or "").strip()
        category = "기타"
        priority = 1

    priority = max(1, min(5, priority))
    return {
        "query_text": query_text,
        "category": category,
        "priority": priority,
    }


def load_existing_queries():
    rows = select(
        "discovery_queries",
        (
            "query_id,query_text,category,priority,enabled,last_run_at,next_run_at,"
            "run_count,channels_found,active_channels_found,consecutive_empty_runs,"
            "error_count,last_error,created_at,updated_at"
        ),
        limit=10000,
    )
    return {row["query_text"]: row for row in rows}


def main():
    existing = load_existing_queries()
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    seen = set()

    for raw_entry in DISCOVERY_QUERIES:
        entry = normalize_entry(raw_entry)
        query_text = entry["query_text"]

        if not query_text or query_text in seen:
            continue

        seen.add(query_text)
        old = existing.get(query_text)

        if old:
            # 실행 통계와 일정은 보존하고, config.py에서 관리하는 분류만 갱신한다.
            rows.append({
                "query_id": old["query_id"],
                "query_text": query_text,
                "category": entry["category"],
                "priority": entry["priority"],
                "enabled": old.get("enabled", True),
                "last_run_at": old.get("last_run_at"),
                "next_run_at": old.get("next_run_at") or now,
                "run_count": int(old.get("run_count", 0) or 0),
                "channels_found": int(old.get("channels_found", 0) or 0),
                "active_channels_found": int(old.get("active_channels_found", 0) or 0),
                "consecutive_empty_runs": int(old.get("consecutive_empty_runs", 0) or 0),
                "error_count": int(old.get("error_count", 0) or 0),
                "last_error": old.get("last_error"),
                "created_at": old.get("created_at") or now,
                "updated_at": now,
            })
        else:
            rows.append({
                "query_text": query_text,
                "category": entry["category"],
                "priority": entry["priority"],
                "enabled": True,
                "next_run_at": now,
                "run_count": 0,
                "channels_found": 0,
                "active_channels_found": 0,
                "consecutive_empty_runs": 0,
                "error_count": 0,
                "last_error": None,
                "updated_at": now,
            })

    upsert("discovery_queries", rows, "query_text")

    new_count = sum(1 for row in rows if row["query_text"] not in existing)
    updated_count = len(rows) - new_count
    print(
        "Discovery query seed completed | "
        f"configured={len(seen)} | new={new_count} | updated={updated_count}"
    )


if __name__ == "__main__":
    main()

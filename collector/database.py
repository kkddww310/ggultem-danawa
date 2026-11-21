import json
import requests
from collector.config import SUPABASE_URL, SUPABASE_KEY

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation,resolution=merge-duplicates",
}


def _url(table):
    return f"{SUPABASE_URL}/rest/v1/{table}"


def upsert(table, rows, on_conflict):
    if not rows:
        return []
    response = requests.post(
        _url(table),
        params={"on_conflict": on_conflict},
        headers=HEADERS,
        data=json.dumps(rows, ensure_ascii=False),
        timeout=45,
    )
    response.raise_for_status()
    return response.json() if response.text else []


def select(table, columns="*", filters=None, limit=1000, order=None):
    params = {"select": columns, "limit": limit}
    if filters:
        params.update(filters)
    if order:
        params["order"] = order
    response = requests.get(_url(table), params=params, headers=HEADERS, timeout=45)
    response.raise_for_status()
    return response.json()


def update(table, values, filters):
    response = requests.patch(
        _url(table), params=filters, headers=HEADERS,
        data=json.dumps(values, ensure_ascii=False), timeout=45,
    )
    response.raise_for_status()
    return response.json() if response.text else []

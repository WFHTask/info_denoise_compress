import re


def select_event_candidates(events: list[dict], query: str, limit: int = 5) -> list[dict]:
    query_lower = (query or "").lower()
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", query_lower)
    if not tokens:
        tokens = [query_lower]

    scored = []
    for item in events:
        title = item.get("title", "")
        if not title:
            continue
        summary = item.get("summary", "")
        haystack = " ".join(
            [title.lower(), summary.lower(), (item.get("url") or "").lower()]
        )
        score = 0
        if query_lower and query_lower in title.lower():
            score += 4
        for token in tokens:
            if token and token in haystack:
                score += 2
        if score:
            scored.append((score, item))

    if not scored:
        return []

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]

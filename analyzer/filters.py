from typing import List, Dict, Any


def top_items(
    items: List[Dict[str, Any]],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Lấy N phần tử có điểm tương tác cao nhất.
    """

    limit = max(1, limit)

    return items[:limit]


def filter_by_min_score(
    items: List[Dict[str, Any]],
    min_score: float = 0,
) -> List[Dict[str, Any]]:
    """
    Chỉ giữ lại các phần tử có điểm tương tác
    lớn hơn hoặc bằng min_score.
    """

    return [
        item
        for item in items
        if item.get("engagement_score", 0) >= min_score
    ]
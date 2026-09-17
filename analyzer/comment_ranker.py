from typing import List, Dict, Any

from .engagement import calculate_comment_score


def rank_comments(
    comments: List[Dict[str, Any]],
    reaction_weight: float = 1.0,
    reply_weight: float = 2.0,
) -> List[Dict[str, Any]]:
    """
    Tính điểm và xếp hạng bình luận.
    """

    ranked_comments = []

    for comment in comments:
        comment = comment.copy()

        score = calculate_comment_score(
            reactions=comment.get("reactions", 0),
            replies=comment.get("replies", 0),
            reaction_weight=reaction_weight,
            reply_weight=reply_weight,
        )

        comment["engagement_score"] = score

        ranked_comments.append(comment)

    ranked_comments.sort(
        key=lambda x: x["engagement_score"],
        reverse=True,
    )

    for index, comment in enumerate(ranked_comments, start=1):
        comment["rank"] = index

    return ranked_comments
from typing import List, Dict, Any

from .engagement import calculate_post_score


def rank_posts(
    posts: List[Dict[str, Any]],
    like_weight: float = 1.0,
    comment_weight: float = 2.0,
    share_weight: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    Tính điểm và xếp hạng bài viết theo mức độ tương tác.
    """

    ranked_posts = []

    for post in posts:
        post = post.copy()

        score = calculate_post_score(
            likes=post.get("likes", 0),
            comments=post.get("comments", 0),
            shares=post.get("shares", 0),
            like_weight=like_weight,
            comment_weight=comment_weight,
            share_weight=share_weight,
        )

        post["engagement_score"] = score

        ranked_posts.append(post)

    ranked_posts.sort(
        key=lambda x: x["engagement_score"],
        reverse=True,
    )

    for index, post in enumerate(ranked_posts, start=1):
        post["rank"] = index

    return ranked_posts
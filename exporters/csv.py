from typing import Any

import pandas as pd


def posts_to_csv(
    posts: list[dict[str, Any]],
) -> bytes:
    rows = []

    for post in posts:
        rows.append({
            "Rank": post.get("rank", ""),
            "Post ID": post.get("post_id", ""),
            "Group ID": post.get("group_id", ""),
            "Post URL": post.get("post_url", ""),
            "Author": post.get("author_name", ""),
            "Content": post.get("content", ""),
            "Created Time": post.get("created_time", ""),
            "Likes": post.get("likes", 0),
            "Comments": post.get("comments", 0),
            "Shares": post.get("shares", 0),
            "Engagement Score": post.get(
                "engagement_score",
                0,
            ),
            "Collected At": post.get(
                "collected_at",
                "",
            ),
        })

    df = pd.DataFrame(rows)

    return df.to_csv(
        index=False,
        encoding="utf-8-sig",
    ).encode("utf-8-sig")


def comments_to_csv(
    comments: list[dict[str, Any]],
) -> bytes:
    rows = []

    for comment in comments:
        rows.append({
            "Rank": comment.get("rank", ""),
            "Comment ID": comment.get(
                "comment_id",
                "",
            ),
            "Post ID": comment.get(
                "post_id",
                "",
            ),
            "Comment URL": comment.get(
                "comment_url",
                "",
            ),
            "Author": comment.get(
                "author_name",
                "",
            ),
            "Content": comment.get(
                "content",
                "",
            ),
            "Created Time": comment.get(
                "created_time",
                "",
            ),
            "Reactions": comment.get(
                "reactions",
                0,
            ),
            "Replies": comment.get(
                "replies",
                0,
            ),
            "Engagement Score": comment.get(
                "engagement_score",
                0,
            ),
            "Collected At": comment.get(
                "collected_at",
                "",
            ),
        })

    df = pd.DataFrame(rows)

    return df.to_csv(
        index=False,
        encoding="utf-8-sig",
    ).encode("utf-8-sig")
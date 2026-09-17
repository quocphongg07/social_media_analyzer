from io import BytesIO
from typing import Any

import pandas as pd


def posts_to_excel(
    posts: list[dict[str, Any]],
) -> bytes:
    """
    Chuyển danh sách bài viết thành file Excel.
    """

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

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:
        df.to_excel(
            writer,
            index=False,
            sheet_name="Top Posts",
        )

    return output.getvalue()


def comments_to_excel(
    comments: list[dict[str, Any]],
) -> bytes:
    """
    Chuyển danh sách bình luận thành file Excel.
    """

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

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:
        df.to_excel(
            writer,
            index=False,
            sheet_name="Top Comments",
        )

    return output.getvalue()


def analysis_to_excel(
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> bytes:
    """
    Tạo một file Excel chứa cả bài viết và bình luận.
    """

    post_rows = []

    for post in posts:
        post_rows.append({
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

    comment_rows = []

    for comment in comments:
        comment_rows.append({
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

    posts_df = pd.DataFrame(post_rows)
    comments_df = pd.DataFrame(comment_rows)

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        posts_df.to_excel(
            writer,
            index=False,
            sheet_name="Top Posts",
        )

        comments_df.to_excel(
            writer,
            index=False,
            sheet_name="Top Comments",
        )

    return output.getvalue()
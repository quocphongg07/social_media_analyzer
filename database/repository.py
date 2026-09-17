from datetime import datetime, timezone
from typing import Any

from .database import get_connection


def now_iso() -> str:
    """
    Thời gian UTC hiện tại theo ISO 8601.
    """

    return datetime.now(timezone.utc).isoformat()


class GroupRepository:

    def save_group(
        self,
        group_id: str,
        name: str,
        url: str,
    ) -> None:

        connection = get_connection()

        connection.execute(
            """
            INSERT INTO groups (
                group_id,
                name,
                url,
                last_scanned
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(group_id)
            DO UPDATE SET
                name = excluded.name,
                url = excluded.url,
                last_scanned = excluded.last_scanned
            """,
            (
                group_id,
                name,
                url,
                now_iso(),
            ),
        )

        connection.commit()
        connection.close()


class PostRepository:

    def save_posts(
        self,
        posts: list[dict[str, Any]],
    ) -> None:

        if not posts:
            return

        connection = get_connection()

        collected_at = now_iso()

        for post in posts:

            connection.execute(
                """
                INSERT INTO posts (
                    post_id,
                    group_id,
                    post_url,
                    author_name,
                    content,
                    created_time,
                    likes,
                    comments,
                    shares,
                    engagement_score,
                    rank,
                    collected_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )

                ON CONFLICT(post_id)
                DO UPDATE SET
                    group_id = excluded.group_id,
                    post_url = excluded.post_url,
                    author_name = excluded.author_name,
                    content = excluded.content,
                    created_time = excluded.created_time,
                    likes = excluded.likes,
                    comments = excluded.comments,
                    shares = excluded.shares,
                    engagement_score = excluded.engagement_score,
                    rank = excluded.rank,
                    collected_at = excluded.collected_at
                """,
                (
                    post.get("post_id", ""),
                    post.get("group_id", ""),
                    post.get("post_url", ""),
                    post.get("author_name", ""),
                    post.get("content", ""),
                    post.get("created_time", ""),

                    post.get("likes", 0),
                    post.get("comments", 0),
                    post.get("shares", 0),

                    post.get("engagement_score", 0),
                    post.get("rank", 0),

                    collected_at,
                ),
            )

        connection.commit()
        connection.close()

    def get_group_posts(
        self,
        group_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:

        connection = get_connection()

        rows = connection.execute(
            """
            SELECT *
            FROM posts
            WHERE group_id = ?
            ORDER BY engagement_score DESC
            LIMIT ?
            """,
            (
                group_id,
                limit,
            ),
        ).fetchall()

        connection.close()

        return [
            dict(row)
            for row in rows
        ]


class CommentRepository:

    def save_comments(
        self,
        comments: list[dict[str, Any]],
    ) -> None:

        if not comments:
            return

        connection = get_connection()

        collected_at = now_iso()

        for comment in comments:

            connection.execute(
                """
                INSERT INTO comments (
                    comment_id,
                    post_id,
                    comment_url,
                    author_name,
                    content,
                    created_time,
                    reactions,
                    replies,
                    engagement_score,
                    rank,
                    collected_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )

                ON CONFLICT(comment_id)
                DO UPDATE SET
                    post_id = excluded.post_id,
                    comment_url = excluded.comment_url,
                    author_name = excluded.author_name,
                    content = excluded.content,
                    created_time = excluded.created_time,
                    reactions = excluded.reactions,
                    replies = excluded.replies,
                    engagement_score = excluded.engagement_score,
                    rank = excluded.rank,
                    collected_at = excluded.collected_at
                """,
                (
                    comment.get("comment_id", ""),
                    comment.get("post_id", ""),
                    comment.get("comment_url", ""),
                    comment.get("author_name", ""),
                    comment.get("content", ""),
                    comment.get("created_time", ""),

                    comment.get("reactions", 0),
                    comment.get("replies", 0),

                    comment.get("engagement_score", 0),
                    comment.get("rank", 0),

                    collected_at,
                ),
            )

        connection.commit()
        connection.close()

    def get_post_comments(
        self,
        post_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:

        connection = get_connection()

        rows = connection.execute(
            """
            SELECT *
            FROM comments
            WHERE post_id = ?
            ORDER BY engagement_score DESC
            LIMIT ?
            """,
            (
                post_id,
                limit,
            ),
        ).fetchall()

        connection.close()

        return [
            dict(row)
            for row in rows
        ]
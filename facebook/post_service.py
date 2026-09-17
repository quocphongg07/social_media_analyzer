from typing import Any

from analyzer.comment_ranker import rank_comments
from database.repository import CommentRepository

from .client import FacebookClient
from .parser import parse_post


class PostService:

    def __init__(
        self,
        client: FacebookClient,
        comment_repository: CommentRepository | None = None,
    ):
        self.client = client

        self.comment_repository = (
            comment_repository
            or CommentRepository()
        )

    def get_post(
        self,
        post_id: str,
        post_url: str | None = None,
    ):
        # Browser client cần biết Group ID khi người dùng nhập trực tiếp
        # một Post URL thay vì đi từ tab Phân tích Group.
        if post_url and hasattr(self.client, "set_post_url_context"):
            self.client.set_post_url_context(post_url)

        data = self.client.get_post(
            post_id
        )

        return parse_post(data)

    def get_ranked_comments(
        self,
        post_id: str,
        limit: int = 100,
        reaction_weight: float = 1.0,
        reply_weight: float = 2.0,
        post_url: str | None = None,
    ) -> list[dict[str, Any]]:

        if post_url and hasattr(self.client, "set_post_url_context"):
            self.client.set_post_url_context(post_url)

        raw_comments = (
            self.client.get_post_comments(
                post_id=post_id,
                limit=limit,
            )
        )

        comments = []

        for comment in raw_comments:

            comments.append({
                "comment_id": comment.get(
                    "comment_id",
                    "",
                ),
                "post_id": comment.get(
                    "post_id",
                    post_id,
                ),
                "comment_url": comment.get(
                    "comment_url",
                    "",
                ),
                "author_name": comment.get(
                    "author_name",
                    "",
                ),
                "content": comment.get(
                    "content",
                    "",
                ),
                "created_time": comment.get(
                    "created_time",
                    "",
                ),
                "reactions": comment.get(
                    "reactions",
                    0,
                ),
                "replies": comment.get(
                    "replies",
                    0,
                ),
            })

        # Tính điểm + xếp hạng
        ranked_comments = rank_comments(
            comments,
            reaction_weight=reaction_weight,
            reply_weight=reply_weight,
        )

        # Tự động lưu SQLite
        self.comment_repository.save_comments(
            ranked_comments
        )

        return ranked_comments
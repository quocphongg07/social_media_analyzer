from typing import Any

from analyzer.post_ranker import rank_posts
from database.repository import GroupRepository, PostRepository

from .client import FacebookClient
from .models import FacebookGroup
from .parser import parse_group


class GroupService:

    def __init__(
        self,
        client: FacebookClient,
        group_repository: GroupRepository | None = None,
        post_repository: PostRepository | None = None,
    ):
        self.client = client

        self.group_repository = (
            group_repository
            or GroupRepository()
        )

        self.post_repository = (
            post_repository
            or PostRepository()
        )

    def get_group(
        self,
        group_id: str,
    ) -> FacebookGroup:

        data = self.client.get_group(group_id)

        group = parse_group(data)

        # Tự động lưu Group
        self.group_repository.save_group(
            group_id=group.group_id,
            name=group.name,
            url=group.url,
        )

        return group

    def get_ranked_posts(
        self,
        group_id: str,
        limit: int = 100,
        like_weight: float = 1.0,
        comment_weight: float = 2.0,
        share_weight: float = 3.0,
    ) -> list[dict[str, Any]]:

        raw_posts = self.client.get_group_posts(
            group_id=group_id,
            limit=limit,
        )

        posts = []

        for post in raw_posts:

            posts.append({
                "post_id": post.get(
                    "post_id",
                    "",
                ),
                "group_id": post.get(
                    "group_id",
                    group_id,
                ),
                "post_url": post.get(
                    "post_url",
                    "",
                ),
                "author_name": post.get(
                    "author_name",
                    "",
                ),
                "content": post.get(
                    "content",
                    "",
                ),
                "created_time": post.get(
                    "created_time",
                    "",
                ),
                "likes": post.get(
                    "likes",
                    0,
                ),
                "comments": post.get(
                    "comments",
                    0,
                ),
                "shares": post.get(
                    "shares",
                    0,
                ),
            })

        # Tính điểm + xếp hạng
        ranked_posts = rank_posts(
            posts,
            like_weight=like_weight,
            comment_weight=comment_weight,
            share_weight=share_weight,
        )

        # Tự động lưu kết quả vào SQLite
        self.post_repository.save_posts(
            ranked_posts
        )

        return ranked_posts
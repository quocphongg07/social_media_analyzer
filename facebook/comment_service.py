from .client import FacebookClient
from .parser import parse_comment


class CommentService:

    def __init__(self, client: FacebookClient):
        self.client = client

    def get_comments(
        self,
        post_id: str,
        limit: int = 100,
    ):
        raw_comments = self.client.get_post_comments(
            post_id=post_id,
            limit=limit,
        )

        return [
            parse_comment(comment)
            for comment in raw_comments
        ]
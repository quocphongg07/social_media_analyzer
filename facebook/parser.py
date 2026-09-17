from typing import Any

from .models import (
    FacebookGroup,
    FacebookPost,
    FacebookComment,
)


def _to_int(value: Any) -> int:
    """
    Chuyển một giá trị về integer an toàn.
    """

    if value is None:
        return 0

    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        return 0


def parse_group(data: dict[str, Any]) -> FacebookGroup:
    return FacebookGroup(
        group_id=str(data.get("group_id", "")),
        name=str(data.get("name", "")),
        url=str(data.get("url", "")),
    )


def parse_post(data: dict[str, Any]) -> FacebookPost:
    return FacebookPost(
        post_id=str(data.get("post_id", "")),
        group_id=data.get("group_id"),
        post_url=str(data.get("post_url", "")),
        author_name=str(data.get("author_name", "")),
        content=str(data.get("content", "")),
        created_time=str(data.get("created_time", "")),

        likes=_to_int(data.get("likes")),
        comments=_to_int(data.get("comments")),
        shares=_to_int(data.get("shares")),
    )


def parse_comment(data: dict[str, Any]) -> FacebookComment:
    return FacebookComment(
        comment_id=str(data.get("comment_id", "")),
        post_id=str(data.get("post_id", "")),
        comment_url=str(data.get("comment_url", "")),
        author_name=str(data.get("author_name", "")),
        content=str(data.get("content", "")),
        created_time=str(data.get("created_time", "")),

        reactions=_to_int(data.get("reactions")),
        replies=_to_int(data.get("replies")),
    )
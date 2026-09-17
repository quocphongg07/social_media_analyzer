from dataclasses import dataclass
from typing import Optional


@dataclass
class FacebookGroup:
    group_id: str
    name: str = ""
    url: str = ""


@dataclass
class FacebookPost:
    post_id: str
    group_id: Optional[str] = None
    post_url: str = ""
    author_name: str = ""
    content: str = ""
    created_time: str = ""

    likes: int = 0
    comments: int = 0
    shares: int = 0

    engagement_score: float = 0.0
    rank: int = 0


@dataclass
class FacebookComment:
    comment_id: str
    post_id: str
    comment_url: str = ""
    author_name: str = ""
    content: str = ""
    created_time: str = ""

    reactions: int = 0
    replies: int = 0

    engagement_score: float = 0.0
    rank: int = 0
from dataclasses import dataclass
from typing import Optional


@dataclass
class GroupRecord:
    group_id: str
    name: str
    url: str
    last_scanned: Optional[str] = None


@dataclass
class PostRecord:
    post_id: str
    group_id: str
    post_url: str
    author_name: str
    content: str
    created_time: str

    likes: int
    comments: int
    shares: int

    engagement_score: float
    rank: int

    collected_at: str


@dataclass
class CommentRecord:
    comment_id: str
    post_id: str
    comment_url: str
    author_name: str
    content: str
    created_time: str

    reactions: int
    replies: int

    engagement_score: float
    rank: int

    collected_at: str
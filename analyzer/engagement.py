def calculate_post_score(
    likes: int,
    comments: int,
    shares: int,
    like_weight: float = 1.0,
    comment_weight: float = 2.0,
    share_weight: float = 3.0,
) -> float:
    """
    Tính điểm tương tác cho bài viết.

    Công thức:

    Score =
        Likes × LikeWeight
        + Comments × CommentWeight
        + Shares × ShareWeight
    """

    likes = max(0, likes)
    comments = max(0, comments)
    shares = max(0, shares)

    return (
        likes * like_weight
        + comments * comment_weight
        + shares * share_weight
    )


def calculate_comment_score(
    reactions: int,
    replies: int,
    reaction_weight: float = 1.0,
    reply_weight: float = 2.0,
) -> float:
    """
    Tính điểm tương tác cho bình luận.

    Công thức:

    Score =
        Reactions × ReactionWeight
        + Replies × ReplyWeight
    """

    reactions = max(0, reactions)
    replies = max(0, replies)

    return (
        reactions * reaction_weight
        + replies * reply_weight
    )
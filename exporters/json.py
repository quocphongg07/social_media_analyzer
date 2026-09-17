import json
from typing import Any


def data_to_json(
    data: list[dict[str, Any]],
) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def analysis_to_json(
    posts: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> bytes:

    data = {
        "posts": posts,
        "comments": comments,
    }

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
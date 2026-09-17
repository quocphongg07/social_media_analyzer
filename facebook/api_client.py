from typing import Any

import requests

from config.settings import settings

from .client import FacebookClient


class FacebookApiError(Exception):
    """Lỗi khi giao tiếp với Facebook Graph API."""


class FacebookApiClient(FacebookClient):

    def __init__(
        self,
        access_token: str | None = None,
        timeout: int = 30,
    ):
        self.access_token = (
            access_token
            or settings.FACEBOOK_ACCESS_TOKEN
        )

        self.timeout = timeout

        self.base_url = (
            f"{settings.FACEBOOK_API_BASE_URL}/"
            f"{settings.FACEBOOK_GRAPH_API_VERSION}"
        )

        if not self.access_token:
            raise ValueError(
                "FACEBOOK_ACCESS_TOKEN chưa được cấu hình."
            )

    # ========================================================
    # REQUEST
    # ========================================================

    def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        request_params = dict(
            params or {}
        )

        request_params["access_token"] = (
            self.access_token
        )

        try:

            response = requests.get(
                url,
                params=request_params,
                timeout=self.timeout,
            )

        except requests.RequestException as exc:

            raise FacebookApiError(
                f"Không thể kết nối Facebook Graph API: {exc}"
            ) from exc

        try:
            data = response.json()

        except ValueError as exc:

            raise FacebookApiError(
                "Facebook Graph API trả về dữ liệu "
                "không phải JSON."
            ) from exc

        if response.status_code >= 400:

            error = data.get(
                "error",
                {},
            )

            message = error.get(
                "message",
                "Facebook Graph API trả về lỗi.",
            )

            code = error.get(
                "code",
                "unknown",
            )

            raise FacebookApiError(
                f"Facebook API error "
                f"[{code}]: {message}"
            )

        if "error" in data:

            error = data["error"]

            raise FacebookApiError(
                f"Facebook API error: "
                f"{error.get('message', 'Unknown error')}"
            )

        return data

    # ========================================================
    # GROUP
    # ========================================================

    def get_group(
        self,
        group_id: str,
    ) -> dict[str, Any]:

        data = self._get(
            group_id,
            params={
                "fields": (
                    "id,name,link,"
                    "description"
                ),
            },
        )

        return {
            "group_id": str(
                data.get(
                    "id",
                    group_id,
                )
            ),
            "name": data.get(
                "name",
                "",
            ),
            "url": data.get(
                "link",
                f"https://www.facebook.com/groups/{group_id}",
            ),
        }

    # ========================================================
    # GROUP POSTS
    # ========================================================

    def get_group_posts(
        self,
        group_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:

        fields = (
            "id,"
            "message,"
            "created_time,"
            "permalink_url,"
            "from,"
            "reactions.summary(true),"
            "comments.summary(true),"
            "shares"
        )

        data = self._get(
            f"{group_id}/feed",
            params={
                "fields": fields,
                "limit": min(
                    max(1, limit),
                    100,
                ),
            },
        )

        posts = []

        for item in data.get(
            "data",
            [],
        ):

            reactions = item.get(
                "reactions",
                {},
            )

            comments = item.get(
                "comments",
                {},
            )

            shares = item.get(
                "shares",
                {},
            )

            reaction_summary = (
                reactions.get(
                    "summary",
                    {},
                )
            )

            comment_summary = (
                comments.get(
                    "summary",
                    {},
                )
            )

            from_data = item.get(
                "from",
                {},
            )

            posts.append({
                "post_id": str(
                    item.get(
                        "id",
                        "",
                    )
                ),
                "group_id": group_id,
                "post_url": item.get(
                    "permalink_url",
                    "",
                ),
                "author_name": from_data.get(
                    "name",
                    "",
                ),
                "content": item.get(
                    "message",
                    "",
                ),
                "created_time": item.get(
                    "created_time",
                    "",
                ),
                "likes": int(
                    reaction_summary.get(
                        "total_count",
                        0,
                    )
                ),
                "comments": int(
                    comment_summary.get(
                        "total_count",
                        0,
                    )
                ),
                "shares": int(
                    shares.get(
                        "count",
                        0,
                    )
                ),
            })

        return posts

    # ========================================================
    # POST
    # ========================================================

    def get_post(
        self,
        post_id: str,
    ) -> dict[str, Any]:

        data = self._get(
            post_id,
            params={
                "fields": (
                    "id,"
                    "message,"
                    "created_time,"
                    "permalink_url,"
                    "from,"
                    "reactions.summary(true),"
                    "comments.summary(true),"
                    "shares"
                ),
            },
        )

        reactions = data.get(
            "reactions",
            {},
        )

        comments = data.get(
            "comments",
            {},
        )

        shares = data.get(
            "shares",
            {},
        )

        reaction_summary = reactions.get(
            "summary",
            {},
        )

        comment_summary = comments.get(
            "summary",
            {},
        )

        from_data = data.get(
            "from",
            {},
        )

        return {
            "post_id": str(
                data.get(
                    "id",
                    post_id,
                )
            ),
            "group_id": None,
            "post_url": data.get(
                "permalink_url",
                "",
            ),
            "author_name": from_data.get(
                "name",
                "",
            ),
            "content": data.get(
                "message",
                "",
            ),
            "created_time": data.get(
                "created_time",
                "",
            ),
            "likes": int(
                reaction_summary.get(
                    "total_count",
                    0,
                )
            ),
            "comments": int(
                comment_summary.get(
                    "total_count",
                    0,
                )
            ),
            "shares": int(
                shares.get(
                    "count",
                    0,
                )
            ),
        }

    # ========================================================
    # POST COMMENTS
    # ========================================================

    def get_post_comments(
        self,
        post_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:

        fields = (
            "id,"
            "message,"
            "created_time,"
            "from,"
            "permalink_url,"
            "like_count,"
            "comments.summary(true)"
        )

        data = self._get(
            f"{post_id}/comments",
            params={
                "fields": fields,
                "limit": min(
                    max(1, limit),
                    100,
                ),
            },
        )

        comments = []

        for item in data.get(
            "data",
            [],
        ):

            from_data = item.get(
                "from",
                {},
            )

            replies = item.get(
                "comments",
                {},
            )

            reply_summary = replies.get(
                "summary",
                {},
            )

            comments.append({
                "comment_id": str(
                    item.get(
                        "id",
                        "",
                    )
                ),
                "post_id": post_id,
                "comment_url": item.get(
                    "permalink_url",
                    "",
                ),
                "author_name": from_data.get(
                    "name",
                    "",
                ),
                "content": item.get(
                    "message",
                    "",
                ),
                "created_time": item.get(
                    "created_time",
                    "",
                ),
                "reactions": int(
                    item.get(
                        "like_count",
                        0,
                    )
                ),
                "replies": int(
                    reply_summary.get(
                        "total_count",
                        0,
                    )
                ),
            })

        return comments
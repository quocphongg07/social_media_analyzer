from .url_parser import (
    detect_url_type,
    is_facebook_url,
)


def validate_facebook_url(url: str) -> tuple[bool, str]:
    """
    Kiểm tra Facebook URL.

    Returns:
        (True, message) nếu hợp lệ
        (False, message) nếu không hợp lệ
    """

    if not url or not url.strip():
        return False, "URL không được để trống."

    if not is_facebook_url(url):
        return False, "URL không phải Facebook."

    url_type = detect_url_type(url)

    if url_type == "invalid":
        return False, "URL Facebook không hợp lệ."

    if url_type == "facebook":
        return (
            False,
            "Không xác định được đây là URL Group hay Post.",
        )

    return True, url_type
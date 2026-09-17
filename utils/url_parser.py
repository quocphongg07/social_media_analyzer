import re
from urllib.parse import urlparse


def normalize_facebook_url(url: str) -> str:
    """
    Chuẩn hóa Facebook URL.
    """
    url = url.strip()

    if not url:
        return ""

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def is_facebook_url(url: str) -> bool:
    """
    Kiểm tra URL có thuộc Facebook hay không.
    """

    try:
        parsed = urlparse(normalize_facebook_url(url))
        hostname = parsed.hostname or ""

        return (
            hostname == "facebook.com"
            or hostname.endswith(".facebook.com")
        )

    except Exception:
        return False


def extract_group_id(url: str) -> str | None:
    """
    Lấy Group ID từ Facebook Group URL.

    Ví dụ:
    https://www.facebook.com/groups/123456789
    -> 123456789
    """

    url = normalize_facebook_url(url)

    pattern = r"facebook\.com/groups/([^/?#]+)"

    match = re.search(pattern, url, re.IGNORECASE)

    if not match:
        return None

    group_id = match.group(1)

    # Không coi các đường dẫn đặc biệt là Group ID
    if group_id.lower() in {
        "join",
        "create",
        "discover",
        "feed",
    }:
        return None

    return group_id


def extract_post_id(url: str) -> str | None:
    """
    Cố gắng lấy Post ID từ Facebook Post URL.
    """

    url = normalize_facebook_url(url)

    patterns = [
        # Group post: /groups/123/posts/456 hoặc /groups/123/permalink/456
        r"/groups/\d+/(?:posts|permalink)/(\d+)",

        # /posts/123456789
        r"/posts/(\d+)",

        # /permalink/123456789
        r"/permalink/(\d+)",

        # story_fbid=123456789
        r"story_fbid=(\d+)",

        # fbid=123456789
        r"fbid=(\d+)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            url,
            re.IGNORECASE,
        )

        if match:
            return match.group(1)

    return None


def detect_url_type(url: str) -> str:
    """
    Xác định loại Facebook URL.

    Kết quả:
    - group
    - post
    - facebook
    - invalid
    """

    url = normalize_facebook_url(url)

    if not url:
        return "invalid"

    if not is_facebook_url(url):
        return "invalid"

    if extract_post_id(url):
        return "post"

    if extract_group_id(url):
        return "group"

    return "facebook"
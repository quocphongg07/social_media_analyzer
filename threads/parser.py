from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

METRICS = ('likes', 'comments', 'reposts', 'quotes', 'shares')
HOSTS = {'threads.net', 'www.threads.net', 'threads.com', 'www.threads.com'}


def parse_profile(value: str) -> str:
    value = value.strip()
    if '://' in value:
        url = urlparse(value)
        if (url.scheme not in {'http', 'https'} or url.hostname not in HOSTS
                or url.username or url.password or url.port):
            raise ValueError('Chỉ chấp nhận link tài khoản threads.com hoặc threads.net.')
        value = url.path.strip('/')
        if not value.startswith('@'):
            raise ValueError('Link tài khoản phải có dạng https://www.threads.com/@username.')
    value = value.removeprefix('@')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.]{0,29}', value):
        raise ValueError('Username không hợp lệ; hãy nhập link tài khoản, không phải link bài viết.')
    return value.lower()


def count(value):
    # Only exact structured counts. Never turn hidden/abbreviated values into zero.
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r'\d+', value):
        return int(value)
    return None


def decode_payload(text):
    text = text.strip()
    if text.startswith('for (;;);'):
        text = text[9:].lstrip()
    try:
        return [json.loads(text)]
    except (ValueError, RecursionError):
        result = []
        for line in text.splitlines():
            try:
                result.append(json.loads(line))
            except (ValueError, RecursionError):
                pass
        return result


def extract_posts(payload, username, include_replies=False):
    """Read post objects from page JSON; exclude embedded quotes/reposts."""
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(item)
            continue
        if not isinstance(item, dict):
            continue
        user = item.get('user') or item.get('owner') or {}
        info = item.get('text_post_app_info') or {}
        if not isinstance(user, dict):
            user = {}
        if not isinstance(info, dict):
            info = {}
        code = item.get('code')
        if (isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_-]+', code)
                and str(user.get('username', '')).lower() == username):
            is_reply = bool(info.get('reply_to_author') or info.get('reply_to_id')
                            or item.get('is_reply') or info.get('is_reply'))
            if include_replies or not is_reply:
                caption = item.get('caption') or {}
                content = caption.get('text', '') if isinstance(caption, dict) else str(caption)
                timestamp = item.get('taken_at')
                try:
                    created = datetime.fromtimestamp(float(timestamp), timezone.utc).isoformat()
                except (TypeError, ValueError, OverflowError, OSError):
                    created = ''
                def metric(*keys):
                    for source in (item, info):
                        for key in keys:
                            v = count(source.get(key))
                            if v is not None:
                                return v
                    return None
                yield dict(post_id=code, post_url=f'https://www.threads.com/@{username}/post/{code}',
                           author_name=username, content=content, created_time=created,
                           likes=metric('like_count'), comments=metric('direct_reply_count', 'reply_count'),
                           reposts=metric('repost_count'), quotes=metric('quote_count'),
                           shares=metric('share_count'), is_reply=is_reply,
                           collected_at=datetime.now(timezone.utc).isoformat(), source='threads_page_json')
        for key, value in item.items():
            if key not in {'quoted_post', 'reposted_post', 'quoted_post_data', 'reposted_post_data', 'reply_to_post'}:
                if isinstance(value, (list, dict)):
                    stack.append(value)


def merge_post(previous, incoming):
    if previous is None:
        return dict(incoming)
    merged = dict(previous)
    for key, value in incoming.items():
        if value is not None and value != '':
            merged[key] = value
    return merged
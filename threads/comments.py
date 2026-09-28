"""Read replies only when page JSON establishes their parent post relationship."""
import re
from urllib.parse import urlparse
from .parser import HOSTS, count, decode_payload, extract_posts


def parse_post_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port:
        raise ValueError('Link bài phải thuộc Threads.')
    match = re.fullmatch(r'/@([A-Za-z0-9_.]+)/post/([A-Za-z0-9_-]+)/?', parsed.path)
    if not match:
        raise ValueError('Cần link Threads dạng /@username/post/mã_bài.')
    return match.group(2)


def identities(item):
    if not isinstance(item, dict):
        return {str(item)} if isinstance(item, (str, int)) and not isinstance(item, bool) and str(item) else set()
    values = set()
    for key in ('pk', 'id', 'code'):
        value = item.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = str(value)
            values.add(text)
            if re.fullmatch(r'\d+_\d+', text):
                values.add(text.split('_')[0])
    return values


class ReplyParser:
    def __init__(self, root_code):
        self.root_code = root_code
        self.items = {}

    def ingest(self, payload):
        stack = [payload]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                code = item.get('code')
                user = item.get('user') or item.get('owner') or {}
                if isinstance(code, str) and isinstance(user, dict) and user.get('username'):
                    # Merge partial deliveries without losing the parent linkage.
                    previous = self.items.get(code, {})
                    combined = {**previous, **item}
                    combined['text_post_app_info'] = {
                        **(previous.get('text_post_app_info') or {}), **(item.get('text_post_app_info') or {})}
                    self.items[code] = combined
                for key, value in item.items():
                    if key not in {'quoted_post', 'reposted_post', 'quoted_post_data', 'reposted_post_data'} and isinstance(value, (dict, list)):
                        stack.append(value)

    def rows(self):
        root_item = self.items.get(self.root_code, {})
        root_user = str(
            (root_item.get('user') or root_item.get('owner') or {}).get('username', '')
        ).lower()
        root_ids = {self.root_code} | identities(root_item)
        parents = {i: (self.root_code, 0) for i in root_ids}
        found = {}
        changed = True
        while changed:
            changed = False
            for code, item in self.items.items():
                if code == self.root_code or code in found:
                    continue
                info = item.get('text_post_app_info') or {}
                candidates = set()
                for source in (item, info):
                    for key in (
                        'reply_to_id', 'reply_to_pk', 'reply_to_media_id',
                        'reply_to_post_id', 'reply_to_post', 'replied_to_post',
                        'parent_id', 'parent_post_id', 'root_post_id', 'thread_id',
                    ):
                        candidates |= identities(source.get(key))
                matches = sorted(candidates & parents.keys())
                if not matches:
                    continue
                parent_code, depth = parents[matches[0]]
                username = (item.get('user') or item.get('owner') or {}).get('username', '').lower()
                posts = list(extract_posts(item, username, include_replies=True))
                post = next((p for p in posts if p['post_id'] == code), None)
                if not post:
                    continue
                found[code] = dict(comment_id=code, post_id=self.root_code, parent_comment_id='' if depth == 0 else parent_code,
                    depth=depth + 1, comment_url=post['post_url'], author_name=post['author_name'], content=post['content'],
                    created_time=post['created_time'], collected_at=post['collected_at'], reactions=post['likes'], replies=post['comments'])
                for alias in identities(item) | {code}:
                    parents[alias] = (code, depth + 1)
                changed = True

        # Some Threads responses expose reply_to_author/is_reply but omit the
        # numeric parent id.  On a single-post page, a reply explicitly aimed
        # at the root author is still safely attributable to that root post.
        if root_user:
            for code, item in self.items.items():
                if code == self.root_code or code in found:
                    continue
                info = item.get('text_post_app_info') or {}
                reply_author = info.get('reply_to_author') or item.get('reply_to_author')
                if isinstance(reply_author, dict):
                    reply_author = reply_author.get('username') or reply_author.get('name')
                is_reply = bool(
                    reply_author or info.get('is_reply') or item.get('is_reply')
                )
                if not is_reply or str(reply_author or '').lower().lstrip('@') != root_user.lstrip('@'):
                    continue
                username = str(
                    (item.get('user') or item.get('owner') or {}).get('username', '')
                ).lower()
                posts = list(extract_posts(item, username, include_replies=True))
                post = next((row for row in posts if row['post_id'] == code), None)
                if post:
                    found[code] = dict(
                        comment_id=code,
                        post_id=self.root_code,
                        parent_comment_id='',
                        depth=1,
                        comment_url=post['post_url'],
                        author_name=post['author_name'],
                        content=post['content'],
                        created_time=post['created_time'],
                        collected_at=post['collected_at'],
                        reactions=post['likes'],
                        replies=post['comments'],
                    )
        return list(found.values())


def expand_reply_controls(page):
    """Click visible controls that request another reply batch."""
    patterns = (
        re.compile(r"(?:view|see|show)\s+(?:all\s+)?(?:\d+[\s,.]*)?(?:more\s+)?repl(?:y|ies)", re.I),
        re.compile(r"(?:view|see|show)\s+hidden\s+repl(?:y|ies)", re.I),
        re.compile(r"xem\s+(?:tất\s+cả\s+)?(?:thêm\s+)?(?:\d+[\s,.]*)?(?:câu\s+)?trả\s+lời", re.I),
        re.compile(r"xem\s+(?:thêm\s+)?(?:\d+[\s,.]*)?phản\s+hồi", re.I),
    )
    clicked = 0
    seen = set()
    for selector in ('[role="button"]', 'button', 'div[tabindex="0"]'):
        try:
            controls = page.locator(selector)
            count = min(controls.count(), 150)
        except Exception:
            continue
        for index in range(count):
            try:
                control = controls.nth(index)
                if not control.is_visible():
                    continue
                label = ' '.join((
                    control.get_attribute('aria-label') or '',
                    control.inner_text() or '',
                )).strip()
                normalized = ' '.join(label.split()).casefold()
                if not normalized or normalized in seen:
                    continue
                if not any(pattern.search(label) for pattern in patterns):
                    continue
                seen.add(normalized)
                control.scroll_into_view_if_needed(timeout=1500)
                control.click(timeout=3000)
                clicked += 1
                page.wait_for_timeout(500)
                if clicked >= 20:
                    return clicked
            except Exception:
                continue
    return clicked


def collect_comments(url, limit=100, progress=print):
    from playwright.sync_api import sync_playwright
    from utils.browser_session import profile_path, restore_session
    code = parse_post_url(url)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
        raise ValueError('Số bình luận phải từ 1 đến 500.')
    parser = ReplyParser(code)
    denied = set()
    def response_received(response):
        try:
            host = urlparse(response.url).hostname or ''
            if (host not in HOSTS and not host.endswith('.threads.com')
                    and not host.endswith('.threads.net')):
                return
            if response.request.resource_type not in {'xhr', 'fetch', 'document'}:
                return
            if response.status in {401, 403, 429}:
                denied.add(response.status)
                return
            if 'json' in response.headers.get('content-type', ''):
                for payload in decode_payload(response.text()):
                    parser.ingest(payload)
        except Exception:
            pass
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(str(profile_path('threads')), headless=False, locale='en-US')
        try:
            restore_session(context, profile_path('threads'))
            page = context.pages[0] if context.pages else context.new_page()
            page.on('response', response_received)
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            previous, idle = 0, 0
            reason = 'max_scrolls'
            for step in range(100):
                page.wait_for_timeout(2500)
                if denied:
                    reason = 'rate_limited' if 429 in denied else 'access_denied'
                    break
                if any(part in urlparse(page.url).path.lower() for part in ('/login', '/checkpoint', '/challenge')):
                    reason = 'login_required'
                    break
                for script in page.locator('script[type="application/json"]').all_text_contents():
                    for payload in decode_payload(script):
                        parser.ingest(payload)
                rows = parser.rows()
                progress(f'Đọc được {min(len(rows), limit)}/{limit} bình luận có liên kết với bài đã chọn.')
                if len(rows) >= limit:
                    reason = 'limit'
                    break
                idle = idle + 1 if len(rows) == previous else 0
                previous = len(rows)
                if idle >= 12:
                    reason = 'no_new_comments'
                    break
                # Only click controls rendered by Threads; no private request replay.
                clicked = expand_reply_controls(page)
                if clicked:
                    progress(f'Đã bấm {clicked} nút tải thêm bình luận Threads.')
                page.mouse.wheel(0, 1500)
            return dict(comments=parser.rows()[:limit], post_url=url, requested_limit=limit, stop_reason=reason,
                warnings=['Chỉ gồm bình luận đọc được và xác định được bài cha; không khẳng định đã lấy toàn bộ.'])
        finally:
            context.close()
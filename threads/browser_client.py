from __future__ import annotations

from pathlib import Path
from utils.browser_session import profile_path, manual_login, restore_session
from urllib.parse import urlparse
from .parser import HOSTS, decode_payload, extract_posts, merge_post, parse_profile
from utils.feed_loading import decode_feed, is_feed_response, advance_feed, FeedProgress

ROOT = Path(__file__).resolve().parents[1]


class ThreadsBrowserClient:
    """Observe JSON delivered to the browser; no private API replay or credentials in code."""

    def __init__(self, profile_dir=None, headless=False):
        self.profile_dir = Path(profile_dir or profile_path('threads')).resolve()
        self.headless = headless

    def collect(self, profile, limit=100, max_scrolls=40, wait_seconds=3,
                login_wait=0, include_replies=False, progress=None):
        from playwright.sync_api import sync_playwright
        username = parse_profile(profile)
        if not 1 <= limit <= 500 or not 1 <= max_scrolls <= 200 or not 1 <= wait_seconds <= 15 or not 0 <= login_wait <= 300:
            raise ValueError('Thông số thu thập ngoài phạm vi cho phép.')
        found, errors = {}, []
        def ingest(payload):
            for post in extract_posts(payload, username, include_replies):
                found[post['post_id']] = merge_post(found.get(post['post_id']), post)
        def on_response(response):
            try:
                host = urlparse(response.url).hostname or ''
                if host not in HOSTS and not host.endswith('.threads.com') and not host.endswith('.threads.net'):
                    return
                if not is_feed_response(response):
                    return
                if response.status in (401, 403, 429):
                    errors.append(response.status)
                    return
                for payload in decode_feed(response.text()):
                    ingest(payload)
            except Exception:
                # A cancelled/unrelated response must not abort the scan.
                return
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(str(self.profile_dir), headless=self.headless,
                        viewport={'width': 1440, 'height': 1000}, locale='en-US')
            try:
                restore_session(context, self.profile_dir)
                page = context.pages[0] if context.pages else context.new_page()
                page.on('response', on_response)
                page.goto(f'https://www.threads.com/@{username}', wait_until='domcontentloaded', timeout=60000)
                if login_wait:
                    if progress:
                        progress(f'Bạn có {login_wait} giây để đăng nhập thủ công trong cửa sổ trình duyệt.')
                    page.wait_for_timeout(login_wait * 1000)
                    page.goto(f'https://www.threads.com/@{username}', wait_until='domcontentloaded', timeout=60000)
                tracker = FeedProgress()
                selector = f'a[href*="/@{username}/post/" i]'
                reason = 'max_scrolls'
                for step in range(max_scrolls):
                    page.wait_for_timeout(wait_seconds * 1000)
                    for script in page.locator('script[type="application/json"]').all_text_contents():
                        for payload in decode_payload(script):
                            ingest(payload)
                    if progress:
                        progress(f'Lượt {step + 1}/{max_scrolls}: đọc được {len(found)} bài của @{username}.')
                    if 429 in errors:
                        reason = 'rate_limited'
                        break
                    if 401 in errors or 403 in errors:
                        reason = 'access_denied'
                        break
                    if len(found) >= limit:
                        reason = 'limit'
                        break
                    position = advance_feed(page, selector)
                    if tracker.stalled(len(found), position):
                        reason = 'no_new_posts'
                        break
                if not found:
                    raise RuntimeError('Không đọc được bài viết. Có thể cần đăng nhập, tài khoản riêng tư, '
                                       'bị giới hạn truy cập hoặc Threads đã đổi cấu trúc dữ liệu. '
                                       'Nếu cần đăng nhập lại, bấm nút đăng nhập Threads trên web. ')
                warnings = ['Kết quả chỉ gồm bài đọc được trong phiên quét; không khẳng định toàn bộ tài khoản.']
                if errors:
                    warnings.append('Trang có phản hồi hạn chế truy cập (HTTP ' + ', '.join(map(str, sorted(set(errors)))) + ').')
                if reason == 'no_new_posts':
                    warnings.append('Dừng sau 12 lượt không có bài mới và vị trí cuộn không đổi; chưa xác nhận đã hết bài.')
                return {'username': username, 'posts': list(found.values())[:limit], 'stop_reason': reason,
                        'warnings': warnings, 'requested_limit': limit, 'source': 'threads_browser'}
            finally:
                context.close()

    def login(self):
        return manual_login('threads')
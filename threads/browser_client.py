from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from .parser import HOSTS, decode_payload, extract_posts, merge_post, parse_profile

ROOT = Path(__file__).resolve().parents[1]


class ThreadsBrowserClient:
    """Observe JSON delivered to the browser; no private API replay or credentials in code."""

    def __init__(self, profile_dir=None, headless=False):
        self.profile_dir = Path(profile_dir or ROOT / 'data' / 'threads_browser_profile').resolve()
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
                if response.status in (401, 403, 429):
                    errors.append(response.status)
                if response.request.resource_type not in {'xhr', 'fetch'}:
                    return
                if 'json' in response.headers.get('content-type', ''):
                    for payload in decode_payload(response.text()):
                        ingest(payload)
            except Exception:
                # A cancelled/unrelated response must not abort the scan.
                return
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(str(self.profile_dir), headless=self.headless,
                        viewport={'width': 1440, 'height': 1000}, locale='en-US')
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.on('response', on_response)
                page.goto(f'https://www.threads.com/@{username}', wait_until='domcontentloaded', timeout=60000)
                if login_wait:
                    if progress:
                        progress(f'Bạn có {login_wait} giây để đăng nhập thủ công trong cửa sổ trình duyệt.')
                    page.wait_for_timeout(login_wait * 1000)
                    page.goto(f'https://www.threads.com/@{username}', wait_until='domcontentloaded', timeout=60000)
                idle, previous = 0, 0
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
                    idle = idle + 1 if len(found) == previous else 0
                    previous = len(found)
                    if idle >= 5:
                        reason = 'no_new_posts'
                        break
                    # Wheel events also scroll a feed held in an overflow container.
                    page.mouse.move(700, 700)
                    page.mouse.wheel(0, 2200)
                if not found:
                    raise RuntimeError('Không đọc được bài viết. Có thể cần đăng nhập, tài khoản riêng tư, '
                                       'bị giới hạn truy cập hoặc Threads đã đổi cấu trúc dữ liệu. '
                                       'Nếu cần đăng nhập lại, chạy: python -m threads.cli --login. ')
                warnings = ['Kết quả chỉ gồm bài đọc được trong phiên quét; không khẳng định toàn bộ tài khoản.']
                if errors:
                    warnings.append('Trang có phản hồi hạn chế truy cập (HTTP ' + ', '.join(map(str, sorted(set(errors)))) + ').')
                if reason == 'no_new_posts':
                    warnings.append('Dừng sau 5 lượt không có bài mới; chưa xác nhận đã đến cuối tài khoản.')
                return {'username': username, 'posts': list(found.values())[:limit], 'stop_reason': reason,
                        'warnings': warnings, 'requested_limit': limit, 'source': 'threads_browser'}
            finally:
                context.close()

    def login(self):
        """Let the user sign in manually, then retain the dedicated profile."""
        from playwright.sync_api import sync_playwright
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(str(self.profile_dir), headless=False,
                        viewport={'width': 1440, 'height': 1000}, locale='en-US')
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto('https://www.threads.com/', wait_until='domcontentloaded', timeout=60000)
                input('Đăng nhập trong cửa sổ trình duyệt; sau khi xong quay lại terminal và nhấn Enter để lưu phiên: ')
            finally:
                context.close()
from pathlib import Path
from urllib.parse import urlparse
from .profile_parser import HOSTS, ProfileParser, decode, parse_profile

ROOT = Path(__file__).resolve().parents[1]


class FacebookProfileClient:
    def __init__(self, profile_dir=None):
        self.profile_dir = Path(profile_dir or ROOT / 'data' / 'facebook_profile_browser').resolve()

    def login(self):
        from playwright.sync_api import sync_playwright
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(str(self.profile_dir), headless=False)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=60000)
                input('Đăng nhập Facebook trong Chromium. Khi xong quay lại terminal và nhấn Enter để lưu phiên: ')
            finally:
                context.close()

    def collect(self, profile, limit=100, max_scrolls=200, progress=None):
        from playwright.sync_api import sync_playwright
        target = parse_profile(profile)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError('Số bài phải từ 1 đến 500.')
        if not 1 <= max_scrolls <= 200:
            raise ValueError('Số lượt cuộn ngoài phạm vi.')
        parser = ProfileParser(target)
        denied = set()
        def response_received(response):
            try:
                host = urlparse(response.url).hostname or ''
                if host not in HOSTS and not host.endswith('.facebook.com'):
                    return
                if response.request.resource_type not in {'xhr', 'fetch', 'document'}:
                    return
                if response.status in {401, 403, 429}:
                    denied.add(response.status)
                    return
                if response.request.resource_type != 'document' and 'json' in response.headers.get('content-type', ''):
                    for payload in decode(response.text()):
                        parser.ingest(payload)
            except Exception:
                # An unrelated cancelled response must not crash the browser session.
                pass
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(str(self.profile_dir), headless=False,
                        viewport={'width': 1440, 'height': 1000}, locale='vi-VN')
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.on('response', response_received)
                page.goto(target['url'], wait_until='domcontentloaded', timeout=60000)
                previous, idle = 0, 0
                reason = 'max_scrolls'
                for step in range(max_scrolls):
                    page.wait_for_timeout(3000)
                    if any(s in urlparse(page.url).path.lower() for s in ('/login', '/checkpoint', '/two_step_verification')):
                        raise RuntimeError('Facebook yêu cầu đăng nhập/xác minh. Chạy python -m facebook.profile_cli --login '
                                           'và hoàn tất thủ công trước khi thu thập.')
                    for text in page.locator('script[type="application/json"]').all_text_contents():
                        for payload in decode(text):
                            parser.ingest(payload)
                    posts = parser.posts()
                    if progress:
                        progress(f'Lượt {step + 1}/{max_scrolls}: đọc được {min(len(posts), limit)}/{limit} bài đúng tác giả.')
                    if denied:
                        reason = 'rate_limited' if 429 in denied else 'access_denied'
                        break
                    if len(posts) >= limit:
                        reason = 'limit'
                        break
                    idle = idle + 1 if len(posts) == previous else 0
                    previous = len(posts)
                    if idle >= 8:
                        reason = 'no_new_posts'
                        break
                    page.mouse.move(700, 700)
                    page.mouse.wheel(0, 1800)
                posts = parser.posts()[:limit]
                if not posts:
                    raise RuntimeError('Không đọc được bài đúng tác giả. Có thể chưa đăng nhập, nội dung không truy cập được '
                                       'hoặc Facebook đã đổi cấu trúc. Đăng nhập bằng python -m facebook.profile_cli --login. '
                                       'Không có dữ liệu mẫu thay thế.')
                warnings = []
                if denied:
                    warnings.append('Facebook trả giới hạn/từ chối truy cập; đã dừng, không thử vượt hạn chế.')
                if reason == 'no_new_posts':
                    warnings.append('Không có bài mới sau 8 lượt cuộn; chưa xác nhận đã hết bài của tài khoản.')
                return dict(profile=target, posts=posts, requested_limit=limit, stop_reason=reason,
                            warnings=warnings, source='facebook_profile_browser')
            finally:
                context.close()
from pathlib import Path
from utils.browser_session import profile_path, manual_login, restore_session
from urllib.parse import urlparse
from .profile_parser import HOSTS, ProfileParser, decode, parse_profile
from utils.feed_loading import decode_feed, is_feed_response, advance_feed, FeedProgress

ROOT = Path(__file__).resolve().parents[1]


class FacebookProfileClient:
    def __init__(self, profile_dir=None):
        self.profile_dir = Path(profile_dir or profile_path('facebook')).resolve()

    def login(self):
        return manual_login('facebook')

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
                if not is_feed_response(response):
                    return
                if response.status in {401, 403, 429}:
                    denied.add(response.status)
                    return
                parser.ingest_response(decode_feed(response.text()))
            except Exception:
                # An unrelated cancelled response must not crash the browser session.
                pass
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(str(self.profile_dir), channel='chrome', headless=False,
                        viewport={'width': 1440, 'height': 1000}, locale='vi-VN')
            try:
                restore_session(context, self.profile_dir)
                page = context.pages[0] if context.pages else context.new_page()
                page.on('response', response_received)
                page.goto(target['url'], wait_until='domcontentloaded', timeout=60000)
                tracker = FeedProgress()
                selector = ('[role="main"] a[href*="/posts/"], '
                            '[role="main"] a[href*="story_fbid="], '
                            '[role="main"] a[href*="/videos/"], '
                            '[role="main"] a[href*="/permalink/"]')
                reason = 'max_scrolls'
                for step in range(max_scrolls):
                    page.wait_for_timeout(3000)
                    if any(s in urlparse(page.url).path.lower() for s in ('/login', '/checkpoint', '/two_step_verification')):
                        raise RuntimeError('Facebook yêu cầu đăng nhập/xác minh. Bấm Đăng nhập / đổi tài khoản Facebook trên web '
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
                    position = advance_feed(page, selector)
                    if tracker.stalled(len(posts), position):
                        reason = 'no_new_posts'
                        break
                posts = parser.posts()[:limit]
                if not posts:
                    raise RuntimeError('Không đọc được bài đúng tác giả. Có thể chưa đăng nhập, nội dung không truy cập được '
                                       'hoặc Facebook đã đổi cấu trúc. Bấm nút đăng nhập Facebook trên web. '
                                       'Không có dữ liệu mẫu thay thế.')
                warnings = []
                if denied:
                    warnings.append('Facebook trả giới hạn/từ chối truy cập; đã dừng, không thử vượt hạn chế.')
                if reason == 'no_new_posts':
                    warnings.append('Không có bài mới và vị trí cuộn không đổi sau 12 lượt; chưa xác nhận đã hết bài.')
                return dict(profile=target, posts=posts, requested_limit=limit, stop_reason=reason,
                            warnings=warnings, source='facebook_profile_browser')
            finally:
                context.close()
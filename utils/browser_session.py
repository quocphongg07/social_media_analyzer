"""Dedicated, shared Facebook session for group/profile; separate Threads session."""
import json
import os
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'data' / 'browser_sessions.json'
DEFAULTS = {'facebook': 'facebook_group_account_2', 'threads': 'threads_browser_profile'}


def profile_path(platform):
    if platform not in DEFAULTS:
        raise ValueError('Nền tảng không hợp lệ.')
    try:
        name = json.loads(CONFIG.read_text(encoding='utf-8')).get(platform, DEFAULTS[platform])
        if not isinstance(name, str) or Path(name).name != name or name in {'.', '..'}:
            raise ValueError('Tên phiên không hợp lệ.')
    except FileNotFoundError:
        name = DEFAULTS[platform]
    return ROOT / 'data' / name


def manual_login(platform):
    """Fresh profile; retain old active session if manual sign-in is cancelled."""
    from playwright.sync_api import sync_playwright
    name = platform + '_session_' + uuid.uuid4().hex
    directory = ROOT / 'data' / name
    directory.mkdir(parents=True, exist_ok=True)
    authenticated = False
    closed = False
    with sync_playwright() as pw:
        options = dict(headless=False, locale='vi-VN')
        if platform == 'facebook':
            options['channel'] = 'chrome'
        context = pw.chromium.launch_persistent_context(str(directory), **options)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            url = 'https://www.facebook.com/login/' if platform == 'facebook' else 'https://www.threads.com/login'
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            print('Đăng nhập thủ công trong trình duyệt. Chờ thông báo nhận phiên, rồi đóng cửa sổ trình duyệt để tiếp tục.', flush=True)
            deadline = time.monotonic() + 600
            notified = False
            while time.monotonic() < deadline:
                try:
                    cookies = context.cookies()
                    cookie_name = 'c_user' if platform == 'facebook' else 'sessionid'
                    domains = ('facebook.com',) if platform == 'facebook' else ('threads.com', 'threads.net')
                    authenticated = any(c['name'] == cookie_name and c.get('value') and
                        any(c.get('domain', '').lstrip('.') == d or c.get('domain', '').endswith('.' + d) for d in domains)
                        for c in cookies)
                    if authenticated:
                        # Preserve session cookies for the next browser process after normal window close.
                        state_path = directory / 'login_cookies.json'
                        state_path.write_text(json.dumps(cookies), encoding='utf-8')
                        storage_path = directory / 'login_storage_state.json'
                        context.storage_state(path=str(storage_path))
                    if authenticated and not notified:
                        print('Đã nhận cookie phiên đăng nhập. Bạn hãy đóng cửa sổ trình duyệt này để lưu và tiếp tục trên web.', flush=True)
                        notified = True
                    pages = context.pages
                    if not pages:
                        closed = True
                        break
                    pages[0].wait_for_timeout(500)
                except Exception:
                    if not context.pages:
                        closed = True
                        break
                    raise
        finally:
            context.close()
    if not closed:
        raise RuntimeError('Hết thời gian đăng nhập. Phiên cũ vẫn được giữ nguyên.')
    if not authenticated:
        raise RuntimeError('Chưa nhận được cookie phiên đăng nhập. Phiên cũ vẫn được giữ nguyên; hãy đăng nhập và chờ thông báo trước khi đóng cửa sổ.')
    try:
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
    except FileNotFoundError:
        config = {}
    config[platform] = name
    temp = CONFIG.with_suffix('.tmp')
    temp.write_text(json.dumps(config), encoding='utf-8')
    os.replace(temp, CONFIG)
    return {'logged_in': True, 'platform': platform}


def restore_session(context, directory):
    cookie_file = Path(directory) / 'login_cookies.json'
    if cookie_file.exists():
        saved = json.loads(cookie_file.read_text(encoding='utf-8'))
        if saved:
            # add_cookies replaces cookies with the same name/domain/path. This
            # prevents a stale persistent-profile cookie from overriding the
            # session selected with the web login button.
            context.add_cookies(saved)
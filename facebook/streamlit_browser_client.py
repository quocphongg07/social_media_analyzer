import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import streamlit as st
from .client import FacebookClient

ROOT = Path(__file__).resolve().parents[1]


class StreamlitFacebookBrowserClient(FacebookClient):
    """Interface-compatible real data source. No mock/fallback branch."""
    def _run(self, action, **params):
        status = st.empty()
        process = None
        try:
            with tempfile.TemporaryDirectory(prefix='fb_group_') as directory:
                request = Path(directory) / 'request.json'
                output = Path(directory) / 'result.json'
                log = Path(directory) / 'progress.txt'
                request.write_text(json.dumps({'action': action, **params}), encoding='utf-8')
                with log.open('w', encoding='utf-8') as writer:
                    process = subprocess.Popen([sys.executable, '-m', 'facebook.browser_worker',
                        '--request', str(request), '--output', str(output)], cwd=ROOT,
                        stdout=writer, stderr=subprocess.STDOUT,
                        env=dict(os.environ, PYTHONIOENCODING='utf-8'))
                    started = time.monotonic()
                    try:
                        while process.poll() is None:
                            lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
                            status.info(lines[-1] if lines else 'Đang mở Chrome. Đăng nhập trong trình duyệt nếu được yêu cầu; không cần nhấn Enter.')
                            if time.monotonic() - started > 3600:
                                raise TimeoutError('Phiên Facebook quá thời gian. Hãy thử số bài/bình luận ít hơn.')
                            time.sleep(1)
                        if process.returncode != 0 or not output.exists():
                            lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
                            raise RuntimeError('\n'.join(lines[-5:]) or 'Thu thập thất bại; không có dữ liệu demo thay thế.')
                        return json.loads(output.read_text(encoding='utf-8'))
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
        finally:
            status.empty()

    def login(self):
        return self._run('login')

    def get_group(self, group_id):
        value = self._run('get_group', group_id=group_id)
        if not isinstance(value, dict) or not value.get('group_id'):
            raise RuntimeError('Không đọc được thông tin nhóm Facebook.')
        st.session_state['fb_browser_group_id'] = str(value['group_id'])
        st.session_state['fb_browser_group_input'] = str(group_id)
        return value

    def get_group_posts(self, group_id, limit=100):
        # Prefer the resolved numeric id when the user supplied a group slug.
        resolved = group_id
        if str(group_id) == st.session_state.get('fb_browser_group_input'):
            resolved = st.session_state.get('fb_browser_group_id') or group_id
        posts = self._run('get_group_posts', group_id=resolved, limit=limit)
        if not posts:
            raise RuntimeError('Không lấy được bài của nhóm. Kiểm tra quyền xem nhóm/phiên đăng nhập; không dùng dữ liệu demo.')
        for post in posts:
            if post.get('group_id'):
                st.session_state['fb_browser_group_id'] = str(post['group_id'])
            if post.get('post_id') and post.get('post_url'):
                links = st.session_state.setdefault('fb_browser_post_links', {})
                links[str(post['post_id'])] = post['post_url']
        return posts

    def _post_input(self, post_id):
        return st.session_state.get('fb_browser_post_links', {}).get(str(post_id), str(post_id))

    def get_post(self, post_id):
        value = self._run('get_post', post_id=self._post_input(post_id),
                          group_id=st.session_state.get('fb_browser_group_id', ''))
        if not value:
            raise RuntimeError('Không đọc được bài. Hãy phân tích nhóm trước hoặc nhập link bài đầy đủ.')
        return value

    def get_post_comments(self, post_id, limit=100):
        return self._run('get_post_comments', post_id=self._post_input(post_id), limit=limit,
                         group_id=st.session_state.get('fb_browser_group_id', ''))
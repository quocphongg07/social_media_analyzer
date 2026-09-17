"""Read-only official Threads API. Never falls back to browser collection."""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from .parser import METRICS, count, parse_profile

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = 'https://graph.threads.net/v1.0'
FIELDS = 'id,username,text,timestamp,permalink'


def configured_token():
    load_dotenv(ROOT / '.env', override=False)
    return os.getenv('THREADS_ACCESS_TOKEN', '').strip()


class ThreadsAPIError(RuntimeError):
    def __init__(self, message, kind='api', code=None):
        super().__init__(message)
        self.kind = kind
        self.code = code


class ThreadsAPIClient:
    def __init__(self, access_token=None, session=None):
        self._token = configured_token() if access_token is None else access_token.strip()
        if not self._token:
            raise ThreadsAPIError('Chưa cấu hình THREADS_ACCESS_TOKEN. Xem README_THREADS.md; '
                                  'phiên đăng nhập trình duyệt không thay thế token API.', 'auth')
        self._session = session or requests.Session()
        self._owns_session = session is None
        self._deadline = 0

    def close(self):
        if self._owns_session:
            self._session.close()

    def _get(self, path, params):
        if not re.fullmatch(r'(me|me/threads|profile_posts|[0-9]+/insights)', path):
            raise ThreadsAPIError('Endpoint không được phép trong bộ đọc này.')
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise ThreadsAPIError('Đã hết thời gian của phiên đọc API.', 'timeout')
        try:
            # Never print params, request URLs, raw API messages or the token.
            response = self._session.get(BASE_URL + '/' + path,
                params={**params, 'access_token': self._token},
                timeout=min(30, remaining), allow_redirects=False)
        except requests.RequestException:
            raise ThreadsAPIError('Không kết nối được Threads API. Phiên đọc đã dừng.', 'network') from None
        if 300 <= response.status_code < 400:
            raise ThreadsAPIError('API trả chuyển hướng; đã dừng, không chuyển token sang địa chỉ khác.')
        try:
            data = response.json()
        except ValueError:
            raise ThreadsAPIError('API trả dữ liệu không phải JSON.', 'response') from None
        if not isinstance(data, dict):
            raise ThreadsAPIError('Cấu trúc phản hồi API không hợp lệ.', 'response')
        error = data.get('error') or {}
        code = error.get('code') if isinstance(error, dict) else None
        if response.status_code >= 400 or error:
            if response.status_code == 429 or code in {4, 17, 32, 613}:
                raise ThreadsAPIError('Threads API giới hạn tốc độ. Đã dừng toàn bộ yêu cầu; '
                                      'hãy tuân thủ thời gian chờ/quota trên Meta Dashboard.', 'rate_limited', code)
            if response.status_code == 401 or code == 190:
                raise ThreadsAPIError('Token API hết hạn, bị thu hồi hoặc không hợp lệ. Cần cấp quyền lại.', 'auth', code)
            if response.status_code == 403 or code in {10, 200}:
                raise ThreadsAPIError('API từ chối quyền truy cập. Kiểm tra quyền và App Review; '
                                      'chương trình không chuyển sang scraping.', 'permission', code)
            raise ThreadsAPIError(f'API không chấp nhận yêu cầu (HTTP {response.status_code}, mã {code}). '
                                  'Kiểm tra tài liệu và cấu hình quyền.', 'api', code)
        return data

    def collect(self, profile, limit=100, progress=None):
        username = parse_profile(profile)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError('Số bài cần lấy phải từ 1 đến 500.')
        self._deadline = time.monotonic() + 600
        me = self._get('me', {'fields': 'id,username'})
        if not isinstance(me.get('username'), str) or not me.get('id'):
            raise ThreadsAPIError('API chưa xác định được tài khoản cấp quyền.', 'response')
        own = me['username'].lower() == username
        path = 'me/threads' if own else 'profile_posts'
        params = {'fields': FIELDS}
        if not own:
            params['username'] = username
        posts, seen, cursors, warnings = [], set(), set(), []
        reason, stopped = 'api_end', False
        for _ in range(100):
            params['limit'] = min(50, limit - len(posts))
            try:
                page = self._get(path, params)
                if not isinstance(page.get('data'), list):
                    raise ThreadsAPIError('API không trả danh sách bài hợp lệ.', 'response')
            except ThreadsAPIError as exc:
                if not posts or exc.kind in {'auth', 'permission'}:
                    raise
                warnings.append(str(exc))
                reason, stopped = exc.kind, True
                break
            for raw in page['data']:
                if not isinstance(raw, dict):
                    continue
                ident = str(raw.get('id', ''))
                if (not re.fullmatch(r'[0-9]+', ident) or ident in seen
                        or str(raw.get('username', '')).lower() != username):
                    continue
                seen.add(ident)
                url = raw.get('permalink') or ''
                parsed = urlparse(url)
                if parsed.scheme != 'https' or parsed.hostname not in {'threads.net', 'www.threads.net', 'threads.com', 'www.threads.com'}:
                    url = ''
                posts.append(dict(post_id=ident, author_name=username, post_url=url,
                    content=raw.get('text') or '', created_time=raw.get('timestamp') or '',
                    **{metric: None for metric in METRICS},
                    collected_at=datetime.now(timezone.utc).isoformat(), source='threads_official_api'))
                if len(posts) == limit:
                    break
            if progress:
                progress(f'Đã nhận {len(posts)}/{limit} bài qua Threads API.')
            if len(posts) == limit:
                reason = 'limit'
                break
            paging = page.get('paging') or {}
            if not paging.get('next'):
                break
            after = (paging.get('cursors') or {}).get('after')
            if not isinstance(after, str) or not after or after in cursors:
                reason = 'pagination_stopped'
                warnings.append('Đã dừng vì API không cung cấp con trỏ trang mới hợp lệ.')
                break
            cursors.add(after)
            # Never follow the supplied next URL; reuse only its cursor at the fixed endpoint.
            params['after'] = after
        else:
            reason = 'page_budget'
            warnings.append('Đã đạt giới hạn số trang của một phiên đọc.')

        if not own:
            warnings.append('Đây là danh sách công khai qua Profile Discovery. Bản này không gọi Insights '
                            'cho tài khoản khác và không có số liệu để xếp hạng tương tác của tài khoản đó.')
        elif not stopped:
            share_supported = True
            for index, post in enumerate(posts, 1):
                try:
                    data = self._get(post['post_id'] + '/insights', {'metric': 'likes,replies,reposts,quotes'})
                    self._apply_insights(post, data)
                    if share_supported:
                        try:
                            self._apply_insights(post, self._get(post['post_id'] + '/insights', {'metric': 'shares'}))
                        except ThreadsAPIError as exc:
                            if exc.kind == 'api' and exc.code == 100:
                                # Optional metric unavailable; no repeated requests for it in this run.
                                share_supported = False
                                warnings.append('API không cung cấp chỉ số shares trong phiên này; để trống.')
                            else:
                                raise
                except ThreadsAPIError as exc:
                    if exc.kind in {'auth', 'permission'}:
                        raise
                    warnings.append(str(exc))
                    reason = 'insights_' + exc.kind
                    break  # No more requests after auth, permission or quota failures.
                if progress:
                    progress(f'Đã đọc số liệu tương tác {index}/{len(posts)} bài.')
        return dict(username=username, posts=posts, requested_limit=limit,
                    stop_reason=reason, warnings=warnings, source='threads_official_api',
                    access_mode='authorized_account' if own else 'public_profile_discovery')

    @staticmethod
    def _apply_insights(post, payload):
        if not isinstance(payload.get('data'), list):
            raise ThreadsAPIError('API không trả danh sách Insights hợp lệ.', 'response')
        mapping = {'likes': 'likes', 'replies': 'comments', 'reposts': 'reposts', 'quotes': 'quotes', 'shares': 'shares'}
        for metric in payload['data']:
            if not isinstance(metric, dict) or metric.get('name') not in mapping:
                continue
            values = metric.get('values')
            if isinstance(values, list) and len(values) == 1 and isinstance(values[0], dict):
                post[mapping[metric['name']]] = count(values[0].get('value'))
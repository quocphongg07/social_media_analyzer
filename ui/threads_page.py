import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from ui.table_components import display_ranked_table
from ui.comments_panel import render_comments_panel
from ui.browser_runner import run_browser_action
import streamlit as st
from threads.parser import METRICS, parse_profile
from threads.service import rank_posts
from threads.repository import save_run
from threads.exports import to_csv, to_excel, to_json

ROOT = Path(__file__).resolve().parents[1]


def collect_in_worker(profile, limit, scrolls, login_wait, include_replies, status):
    # A separate process avoids Playwright's subprocess/event-loop restrictions on Windows.
    with tempfile.TemporaryDirectory(prefix='threads_scan_') as temp:
        output = Path(temp) / 'result.json'
        log_path = Path(temp) / 'progress.log'
        cmd = [sys.executable, '-m', 'threads.cli', profile, '--limit', str(limit),
               '--max-scrolls', str(scrolls), '--login-wait', str(login_wait), '--output', str(output)]
        if include_replies:
            cmd.append('--include-replies')
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        with log_path.open('w', encoding='utf-8') as log:
            process = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
            started = time.monotonic()
            try:
                while process.poll() is None:
                    lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
                    status.info(lines[-1] if lines else 'Đang mở trình duyệt Threads…')
                    if time.monotonic() - started > 120 + login_wait + scrolls * 10:
                        raise TimeoutError('Phiên quét quá thời gian. Hãy thử lại với số bài ít hơn.')
                    time.sleep(1)
                if process.returncode or not output.exists():
                    lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
                    raise RuntimeError('\n'.join(lines[-6:]) or 'Không nhận được kết quả từ trình duyệt.')
                return json.loads(output.read_text(encoding='utf-8'))
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                status.empty()


def rank_collected_posts(posts, weights):
    ranked = rank_posts(posts, weights, include_incomplete=True)
    known, unknown = [], []
    for row in ranked:
        if not any(weights.values()) or any(row.get(k) is not None and weights.get(k, 0) > 0 for k in METRICS):
            known.append(row)
        else:
            row.update(engagement_score=None, rank=None, score_status='unavailable')
            unknown.append(row)
    for index, row in enumerate(known, 1):
        row['rank'] = index
    return known + unknown


def render_threads_page(like_weight, comment_weight, share_weight, browser_client, reaction_weight=1.0, reply_weight=2.0):
    st.header('Phân tích tài khoản Threads')
    if st.button('Đăng nhập / đổi tài khoản Threads', key='threads_login_in_tab'):
        try:
            run_browser_action('login', platform='threads')
            for state_key in ('threads_result', 'threads_comment_result', 'threads_selected_post'):
                st.session_state.pop(state_key, None)
            st.success('Đã lưu phiên Threads mới. Bây giờ bạn có thể thu thập dữ liệu.')
        except Exception as exc:
            st.error(str(exc))
    st.caption('Nhập link và số bài cần lấy. Chương trình dùng lại phiên đăng nhập trình duyệt đã lưu.')
    profile = st.text_input('Link tài khoản Threads', placeholder='https://www.threads.com/@username', key='threads_profile')
    limit = st.number_input('Số bài viết tối đa cần lấy', min_value=1, max_value=500,
                            value=100, step=1, key='threads_limit')
    if st.button('Thu thập và xếp hạng', type='primary', key='threads_scan'):
        try:
            username = parse_profile(profile)
            st.session_state.pop('threads_result', None)
            st.session_state.pop('threads_comment_result', None)
            result = collect_in_worker(username, int(limit), 200, 0, False, st.empty())
            result['requested_limit'] = int(limit)
            st.session_state['threads_result'] = result
            try:
                save_run(result)
            except Exception as exc:
                st.warning(f'Đã thu thập nhưng chưa lưu được kết quả: {exc}. Bạn vẫn có thể tải dữ liệu bên dưới.')
        except Exception as exc:
            st.error(str(exc))

    result = st.session_state.get('threads_result')
    if not result or result.get('source') != 'threads_browser':
        return
    weights = dict(likes=like_weight, comments=comment_weight,
                   reposts=share_weight, quotes=share_weight, shares=share_weight)
    try:
        rows = rank_collected_posts(result['posts'], weights)
    except ValueError as exc:
        st.error(str(exc))
        return

    st.subheader(f'Kết quả: @{result["username"]}')
    requested = result.get('requested_limit', len(rows))
    if len(rows) < requested:
        st.warning(f'Đã lấy được {len(rows)}/{requested} bài yêu cầu. Hiển thị toàn bộ {len(rows)} bài đã lấy được.')
        reasons = {
            'no_new_posts': 'Trang không tải thêm bài sau nhiều lượt cuộn.',
            'max_scrolls': 'Phiên quét đã đạt giới hạn cuộn tự động.',
            'rate_limited': 'Threads đang giới hạn truy cập. Phiên thu thập đã dừng.',
            'access_denied': 'Trang từ chối truy cập. Phiên thu thập đã dừng.',
        }
        reason = reasons.get(result.get('stop_reason'))
        if reason:
            st.caption(reason)
    else:
        st.success(f'Đã lấy và xếp hạng {len(rows)} bài. Bảng và file tải xuống chứa đầy đủ {len(rows)} bài.')
    for warning in result.get('warnings', []):
        if warning != 'Kết quả chỉ gồm bài đọc được trong phiên quét; không khẳng định toàn bộ tài khoản.':
            st.warning(warning)
    st.caption('Xếp hạng trong tập bài đã thu thập. Like và Comment dùng trọng số tương ứng; '
               'Repost, Quote và Share đều dùng trọng số Share ở thanh bên.')
    st.caption('Ô trống là chỉ số chưa đọc được. Điểm partial là điểm tạm tính; '
               'bài chưa có chỉ số nào dùng để tính điểm được để trống điểm và thứ hạng.')
    if not rows:
        st.info('Không có bài viết để hiển thị.')
        return
    columns = ['rank', 'content', 'likes', 'comments', 'reposts', 'quotes', 'shares',
               'engagement_score', 'score_status', 'created_time', 'post_url']
    rows = display_ranked_table(rows, columns, 'threads_table')
    metadata = {k: v for k, v in result.items() if k != 'posts'}
    metadata.update(weights=weights, include_incomplete=True, export_count=len(rows))
    a, b, c = st.columns(3)
    stem = 'threads_' + result['username']
    a.download_button('Tải CSV', to_csv(rows), stem + '.csv', 'text/csv', key='threads_csv')
    b.download_button('Tải Excel', to_excel(rows), stem + '.xlsx',
                      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key='threads_xlsx')
    c.download_button('Tải JSON', to_json(rows, metadata), stem + '.json', 'application/json', key='threads_json')

    def fetch(post, count):
        return run_browser_action(
            'threads_comments',
            url=post['post_url'],
            limit=count,
            timeout=900,
        )
    render_comments_panel(rows, 'threads', fetch, reaction_weight, reply_weight)
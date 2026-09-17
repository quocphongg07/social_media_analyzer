import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import pandas as pd
import streamlit as st
from facebook.profile_parser import parse_profile
from facebook.profile_service import rank_posts, save_run, to_csv, to_excel, to_json

ROOT = Path(__file__).resolve().parents[1]


def collect_in_worker(profile, limit, status):
    # A separate process avoids Playwright's subprocess/event-loop restrictions on Windows.
    with tempfile.TemporaryDirectory(prefix='fb_profile_scan_') as temp:
        output = Path(temp) / 'result.json'
        log_path = Path(temp) / 'progress.log'
        cmd = [sys.executable, '-m', 'facebook.profile_cli', profile, '--limit', str(limit), '--output', str(output)]
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        with log_path.open('w', encoding='utf-8') as log:
            process = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
            started = time.monotonic()
            try:
                while process.poll() is None:
                    lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
                    status.info(lines[-1] if lines else 'Đang mở trình duyệt Facebook…')
                    if time.monotonic() - started > 1500:
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


def render_profile_page(like_weight, comment_weight, share_weight):
    st.header('Phân tích tài khoản Facebook')
    st.caption('Thu thập bài đăng và bài chia sẻ đọc được trên dòng thời gian của tài khoản.')
    url = st.text_input('Link tài khoản Facebook', placeholder='https://www.facebook.com/username', key='fb_profile_url')
    limit = st.number_input('Số bài viết tối đa cần lấy', min_value=1, max_value=500,
                            value=100, step=1, key='fb_profile_limit')
    st.caption('Lần đầu cần đăng nhập Facebook: chạy python -m facebook.profile_cli --login trong terminal.')
    if st.button('Thu thập và xếp hạng', type='primary', key='fb_profile_scan'):
        st.session_state.pop('fb_profile_result', None)
        try:
            target = parse_profile(url)
            result = collect_in_worker(target['url'], int(limit), st.empty())
            st.session_state['fb_profile_result'] = result
            try:
                save_run(result)
            except Exception as exc:
                st.warning(f'Đã thu thập nhưng chưa lưu được SQLite: {exc}. Bạn vẫn có thể tải dữ liệu.')
        except Exception as exc:
            st.error(str(exc))
    result = st.session_state.get('fb_profile_result')
    if not result:
        return
    try:
        rows = rank_posts(result['posts'], like_weight, comment_weight, share_weight)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.subheader(f'Kết quả: {result["profile"]["key"]}')
    count = len(rows)
    requested = result.get('requested_limit', count)
    st.write(f'Đã lấy {count}/{requested} bài. Bảng và file xuất có toàn bộ {count} bài.')
    shared_count = sum(row['post_type'] == 'Bài chia sẻ' for row in rows)
    st.caption(f'{count - shared_count} bài đăng · {shared_count} bài chia sẻ được nhận diện.')
    for warning in result.get('warnings', []):
        st.warning(warning)
    if count < requested:
        st.info('Chưa lấy đủ số yêu cầu. Có thể đã hết nội dung tải được, nội dung bị giới hạn hoặc cấu trúc trang chưa được hỗ trợ.')
    st.caption('Điểm = tổng Reaction × trọng số Like + Comment × trọng số Comment + Share × trọng số Share ở thanh bên. '
               'Reaction gồm các loại cảm xúc, không chỉ nút Thích.')
    st.caption('Bài chia sẻ dùng tương tác của chính bài chia sẻ; không cộng tương tác của bài gốc. '
               'Ô trống là chưa đọc được. Điểm partial là tạm tính; unavailable không có điểm/thứ hạng.')
    if not rows:
        return
    columns = ['rank', 'post_type', 'author_name', 'content', 'shared_content', 'reactions', 'comments',
               'shares', 'engagement_score', 'score_status', 'created_time', 'post_url', 'shared_post_url']
    frame = pd.DataFrame(rows)[columns]
    for key in ['rank', 'reactions', 'comments', 'shares']:
        frame[key] = pd.array(frame[key], dtype='Int64')
    st.dataframe(frame, use_container_width=True, hide_index=True,
        column_config={'post_url': st.column_config.LinkColumn('Link bài'),
                       'shared_post_url': st.column_config.LinkColumn('Link bài gốc')})
    st.caption('Cuộn trong bảng để xem tất cả bài. Nội dung chia sẻ để riêng ở cột shared_content.')
    metadata = {k: v for k, v in result.items() if k != 'posts'}
    metadata.update(weights=dict(reactions=like_weight, comments=comment_weight, shares=share_weight), export_count=count)
    stem = 'facebook_profile_' + result['profile']['key']
    a, b, c = st.columns(3)
    a.download_button('Tải CSV', to_csv(rows), stem + '.csv', 'text/csv', key='fb_profile_csv')
    b.download_button('Tải Excel', to_excel(rows), stem + '.xlsx',
                      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key='fb_profile_excel')
    c.download_button('Tải JSON', to_json(rows, metadata), stem + '.json', 'application/json', key='fb_profile_json')
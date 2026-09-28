import streamlit as st
from analyzer.post_ranker import rank_posts
from utils.url_parser import detect_url_type, extract_group_id
from exporters.csv import posts_to_csv
from exporters.excel import posts_to_excel
from exporters.json import data_to_json
from .table_components import display_post_table
from .comments_panel import render_comments_panel
from .browser_runner import run_browser_action


def render_group_page(group_service, post_service, like_weight, comment_weight, share_weight,
                      reaction_weight, reply_weight):
    st.header('Phân tích nhóm Facebook')
    if st.button('Đăng nhập / đổi tài khoản Facebook', key='facebook_login_group_tab'):
        try:
            run_browser_action('login', platform='facebook')
            for state_key in ('current_group', 'current_posts', 'group_comment_result',
                              'group_selected_post', 'fb_browser_group_id',
                              'fb_browser_group_input', 'fb_browser_post_links'):
                st.session_state.pop(state_key, None)
            st.success('Đã lưu phiên Facebook mới. Phiên này được dùng chung cho cả hai tab Facebook.')
        except Exception as exc:
            st.error(str(exc))
    value = st.text_input('Link nhóm Facebook hoặc Group ID', key='group_input').strip()
    limit = st.number_input('Số bài viết tối đa cần lấy', min_value=1, max_value=500, value=100, key='group_post_limit')
    if st.button('Thu thập và xếp hạng', type='primary', key='analyze_group'):
        if not value:
            st.warning('Vui lòng nhập link nhóm.')
        else:
            try:
                if value.startswith(('https://', 'http://')):
                    if detect_url_type(value) != 'group':
                        raise ValueError('Link không phải nhóm Facebook.')
                    group_id = extract_group_id(value)
                else:
                    group_id = value
                for key in ('current_group', 'current_posts', 'group_comment_result', 'group_selected_post'):
                    st.session_state.pop(key, None)
                group = group_service.get_group(group_id)
                posts = group_service.get_ranked_posts(group_id=group_id, limit=int(limit),
                    like_weight=like_weight, comment_weight=comment_weight, share_weight=share_weight)
                st.session_state.update(current_group=group, current_posts=posts, group_requested_limit=int(limit))
            except Exception as exc:
                st.error(str(exc))
    group = st.session_state.get('current_group')
    posts = st.session_state.get('current_posts', [])
    if not group or not posts:
        return
    st.subheader(group.name)
    rows = rank_posts(posts, like_weight, comment_weight, share_weight)
    requested = st.session_state.get('group_requested_limit', len(rows))
    st.write(f'Đã đọc {len(rows)}/{requested} bài. Hiển thị và xuất toàn bộ bài đã đọc được.')
    if len(rows) < requested:
        st.caption('Chưa lấy đủ số yêu cầu; trang có thể không tải thêm nội dung hoặc phiên quét đã đạt giới hạn.')
    rows = display_post_table(rows, key='group_posts')
    a, b, c = st.columns(3)
    a.download_button('Tải CSV', posts_to_csv(rows), 'facebook_group_posts.csv', 'text/csv', key='group_posts_csv')
    b.download_button('Tải Excel', posts_to_excel(rows), 'facebook_group_posts.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key='group_posts_xlsx')
    c.download_button('Tải JSON', data_to_json(rows), 'facebook_group_posts.json', 'application/json', key='group_posts_json')
    def fetch(post, count):
        return post_service.get_ranked_comments(post_id=post.get('post_url') or post['post_id'], limit=count,
            reaction_weight=reaction_weight, reply_weight=reply_weight)
    render_comments_panel(rows, 'group', fetch, reaction_weight, reply_weight)
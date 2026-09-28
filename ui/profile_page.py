from ui.table_components import display_ranked_table
from ui.comments_panel import render_comments_panel
from ui.browser_runner import run_browser_action
import streamlit as st
from facebook.profile_parser import parse_profile
from facebook.profile_service import rank_posts, save_run, to_csv, to_excel, to_json

def collect_in_worker(profile, limit, status):
    return run_browser_action(
        'facebook_profile',
        profile=profile,
        limit=limit,
        timeout=1500,
        status=status,
    )


def render_profile_page(like_weight, comment_weight, share_weight, post_service, reaction_weight=1.0, reply_weight=2.0):
    st.header('Phân tích tài khoản Facebook')
    if st.button('Đăng nhập / đổi tài khoản Facebook', key='facebook_login_profile_tab'):
        try:
            run_browser_action('login', platform='facebook')
            for state_key in ('fb_profile_result', 'profile_comment_result',
                              'profile_selected_post', 'current_group', 'current_posts',
                              'group_comment_result', 'group_selected_post',
                              'fb_browser_group_id', 'fb_browser_group_input',
                              'fb_browser_post_links'):
                st.session_state.pop(state_key, None)
            st.success('Đã lưu phiên Facebook mới. Tab nhóm và tab tài khoản sẽ dùng chung phiên này.')
        except Exception as exc:
            st.error(str(exc))
    st.caption('Thu thập bài đăng và bài chia sẻ đọc được trên dòng thời gian của tài khoản.')
    url = st.text_input('Link tài khoản Facebook', placeholder='https://www.facebook.com/username', key='fb_profile_url')
    limit = st.number_input('Số bài viết tối đa cần lấy', min_value=1, max_value=500,
                            value=100, step=1, key='fb_profile_limit')
    st.caption('Dùng chung tài khoản với tab nhóm. Bấm nút đăng nhập Facebook ở thanh bên để thay tài khoản.')
    if st.button('Thu thập và xếp hạng', type='primary', key='fb_profile_scan'):
        st.session_state.pop('fb_profile_result', None)
        st.session_state.pop('profile_comment_result', None)
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
    rows = display_ranked_table(rows, columns, 'profile_table')
    metadata = {k: v for k, v in result.items() if k != 'posts'}
    metadata.update(weights=dict(reactions=like_weight, comments=comment_weight, shares=share_weight), export_count=count)
    stem = 'facebook_profile_' + result['profile']['key']
    a, b, c = st.columns(3)
    a.download_button('Tải CSV', to_csv(rows), stem + '.csv', 'text/csv', key='fb_profile_csv')
    b.download_button('Tải Excel', to_excel(rows), stem + '.xlsx',
                      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key='fb_profile_excel')
    c.download_button('Tải JSON', to_json(rows, metadata), stem + '.json', 'application/json', key='fb_profile_json')

    def fetch(post, count):
        return run_browser_action(
            'facebook_profile_comments',
            post_url=post['post_url'],
            post_id=post['post_id'],
            limit=count,
            timeout=900,
        )
    render_comments_panel(rows, 'profile', fetch, reaction_weight, reply_weight)
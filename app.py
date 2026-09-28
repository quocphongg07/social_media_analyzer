import streamlit as st
from config.settings import settings
from database.database import initialize_database
from facebook.streamlit_browser_client import StreamlitFacebookBrowserClient
from facebook.group_service import GroupService
from facebook.post_service import PostService
from ui.group_page import render_group_page
from ui.profile_page import render_profile_page
from ui.threads_page import render_threads_page
from ui.browser_runner import run_browser_action

st.set_page_config(page_title=settings.APP_NAME, page_icon='📊', layout='wide')
initialize_database()
client = StreamlitFacebookBrowserClient()
group_service = GroupService(client=client)
post_service = PostService(client=client)

FACEBOOK_RESULTS = ('current_group', 'current_group_id', 'current_posts', 'current_post', 'current_comments',
    'selected_post_comments', 'selected_post_for_comments', 'selected_post_id',
    'fb_profile_result', 'fb_browser_group_id', 'fb_browser_group_input', 'fb_browser_post_links',
    'group_comment_result', 'profile_comment_result', 'group_selected_post', 'profile_selected_post')
if st.session_state.get('facebook_data_source') != 'browser_worker_v3_shared_session':
    for key in FACEBOOK_RESULTS:
        st.session_state.pop(key, None)
    st.session_state['facebook_data_source'] = 'browser_worker_v3_shared_session'

st.title('📊 Facebook & Threads Engagement Analyzer')
st.caption('Thu thập bài viết, phân tích bình luận và xếp hạng tương tác. Ngày giờ hiển thị và xuất file theo Việt Nam (UTC+7).')
with st.sidebar:
    st.header('Tài khoản đăng nhập')
    st.caption('Facebook dùng chung phiên cho nhóm và trang cá nhân. Threads dùng phiên riêng.')
    st.caption('Bấm nút bên dưới, đăng nhập thủ công; chờ thông báo nhận phiên rồi đóng cửa sổ trình duyệt đó để tiếp tục.')
    if st.button('Đăng nhập / đổi tài khoản Facebook', key='facebook_login'):
        try:
            run_browser_action('login', platform='facebook')
            for key in FACEBOOK_RESULTS:
                st.session_state.pop(key, None)
            st.success('Đã lưu phiên Facebook mới.')
        except Exception as exc:
            st.error(str(exc))
    if st.button('Đăng nhập / đổi tài khoản Threads', key='threads_login'):
        try:
            run_browser_action('login', platform='threads')
            for key in ('threads_result', 'threads_comment_result', 'threads_selected_post'):
                st.session_state.pop(key, None)
            st.success('Đã lưu phiên Threads mới.')
        except Exception as exc:
            st.error(str(exc))
    st.divider()
    st.subheader('Trọng số bài viết')
    like_weight = st.number_input('Like / Reaction', min_value=0.0, value=float(settings.LIKE_WEIGHT), step=0.5, key='like_weight')
    comment_weight = st.number_input('Comment', min_value=0.0, value=float(settings.COMMENT_WEIGHT), step=0.5, key='comment_weight')
    share_weight = st.number_input('Share', min_value=0.0, value=float(settings.SHARE_WEIGHT), step=0.5, key='share_weight')
    st.subheader('Trọng số bình luận')
    reaction_weight = st.number_input('Reaction bình luận', min_value=0.0, value=float(settings.REACTION_WEIGHT), step=0.5, key='reaction_weight')
    reply_weight = st.number_input('Reply', min_value=0.0, value=float(settings.REPLY_WEIGHT), step=0.5, key='reply_weight')
    st.caption('Nguồn dữ liệu: trình duyệt Facebook / Threads. Thay trọng số sẽ tính lại điểm của dữ liệu đang hiển thị.')

tab_group, tab_profile, tab_threads = st.tabs(['📊 Nhóm Facebook', '👤 Trang cá nhân Facebook', '🧵 Trang cá nhân Threads'])
with tab_group:
    render_group_page(group_service, post_service, like_weight, comment_weight, share_weight, reaction_weight, reply_weight)
with tab_profile:
    render_profile_page(like_weight, comment_weight, share_weight, post_service, reaction_weight, reply_weight)
with tab_threads:
    render_threads_page(like_weight, comment_weight, share_weight, client, reaction_weight, reply_weight)
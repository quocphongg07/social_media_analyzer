import streamlit as st

from config.settings import settings
from database.database import initialize_database

from facebook.streamlit_browser_client import StreamlitFacebookBrowserClient
from facebook.group_service import GroupService
from facebook.post_service import PostService

from ui.group_page import render_group_page
from ui.post_page import render_post_page
from ui.threads_page import render_threads_page
try:
    from ui.profile_page import render_profile_page
except ModuleNotFoundError as exc:
    if exc.name != "ui.profile_page":
        raise
    render_profile_page = None


# ============================================================
# STREAMLIT CONFIG
# ============================================================

st.set_page_config(
    page_title=settings.APP_NAME,
    page_icon="📊",
    layout="wide",
)


# ============================================================
# DATABASE
# ============================================================

initialize_database()


# ============================================================
# FACEBOOK CLIENT
# ============================================================

client = StreamlitFacebookBrowserClient()

# Remove old demo results from this session when switching to the real source.
if st.session_state.get("facebook_data_source") != "browser_worker_v1":
    for key in ("current_group", "current_group_id", "current_posts", "selected_post_id",
                "selected_post_comments", "selected_post_for_comments", "current_post", "current_comments",
                "fb_browser_group_id", "fb_browser_post_links"):
        st.session_state.pop(key, None)
    st.session_state["facebook_data_source"] = "browser_worker_v1"


# ============================================================
# SERVICES
# ============================================================

group_service = GroupService(
    client=client
)

post_service = PostService(
    client=client
)


# ============================================================
# HEADER
# ============================================================

st.title(
    "📊 Facebook & Threads Engagement Analyzer"
)

st.caption(
    "Phân tích, xếp hạng và lưu trữ "
    "nội dung Facebook và Threads theo mức độ tương tác."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Cấu hình")
    if st.button("Đăng nhập / đổi tài khoản Facebook quét nhóm", key="fb_group_login"):
        try:
            client.login()
            for key in ("current_group", "current_group_id", "current_posts", "selected_post_id",
                        "selected_post_comments", "selected_post_for_comments", "current_post", "current_comments",
                        "fb_browser_group_id", "fb_browser_post_links"):
                st.session_state.pop(key, None)
            st.success("Đã nhận phiên Facebook. Nhập link nhóm trên web để phân tích.")
        except Exception as exc:
            st.error(str(exc))

    # --------------------------------------------------------
    # Trọng số bài viết
    # --------------------------------------------------------

    st.subheader(
        "📊 Trọng số bài viết"
    )

    like_weight = st.number_input(
        "Like",
        min_value=0.0,
        value=settings.LIKE_WEIGHT,
        step=0.5,
        key="like_weight",
    )

    comment_weight = st.number_input(
        "Comment",
        min_value=0.0,
        value=settings.COMMENT_WEIGHT,
        step=0.5,
        key="comment_weight",
    )

    share_weight = st.number_input(
        "Share",
        min_value=0.0,
        value=settings.SHARE_WEIGHT,
        step=0.5,
        key="share_weight",
    )

    st.divider()

    # --------------------------------------------------------
    # Trọng số bình luận
    # --------------------------------------------------------

    st.subheader(
        "💬 Trọng số bình luận"
    )

    reaction_weight = st.number_input(
        "Reaction",
        min_value=0.0,
        value=settings.REACTION_WEIGHT,
        step=0.5,
        key="reaction_weight",
    )

    reply_weight = st.number_input(
        "Reply",
        min_value=0.0,
        value=settings.REPLY_WEIGHT,
        step=0.5,
        key="reply_weight",
    )

    st.divider()

    # --------------------------------------------------------
    # Thông tin hệ thống
    # --------------------------------------------------------

    st.subheader(
        "ℹ️ Thông tin hệ thống"
    )

    st.caption(
        "Nguồn dữ liệu hiện tại:"
    )

    st.code(
        "Facebook Group/Bài viết: Chrome — dữ liệu thật\nThreads/Tài khoản Facebook: Chromium",
        language="text",
    )

    st.caption(
        "Dữ liệu phân tích được lưu vào SQLite."
    )


# ============================================================
# TABS
# ============================================================

labels = ["📊 Phân tích Group", "💬 Phân tích bài viết", "🧵 Phân tích Threads"]
if render_profile_page is not None:
    labels.append("👤 Tài khoản Facebook")
tabs = st.tabs(labels)
tab_group, tab_post, tab_threads = tabs[:3]


# ============================================================
# TAB 1 — GROUP
# ============================================================

with tab_group:

    render_group_page(
        group_service=group_service,
        post_service=post_service,

        like_weight=like_weight,
        comment_weight=comment_weight,
        share_weight=share_weight,

        reaction_weight=reaction_weight,
        reply_weight=reply_weight,
    )


# ============================================================
# TAB 2 — POST
# ============================================================

with tab_post:

    render_post_page(
        post_service=post_service,

        reaction_weight=reaction_weight,
        reply_weight=reply_weight,
    )

with tab_threads:
    render_threads_page(like_weight, comment_weight, share_weight)


if render_profile_page is not None:
    with tabs[3]:
        render_profile_page(like_weight, comment_weight, share_weight)
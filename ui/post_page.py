import streamlit as st

from analyzer.comment_ranker import rank_comments
from utils.datetime_utils import format_vietnam
from facebook.post_service import PostService
from utils.url_parser import (
    detect_url_type,
    extract_post_id,
)
from exporters.excel import comments_to_excel
from exporters.csv import comments_to_csv
from exporters.json import data_to_json
from .table_components import display_comment_table


def render_post_page(
    post_service: PostService,
    reaction_weight: float,
    reply_weight: float,
):
    st.header("💬 Phân tích bình luận bài viết")

    post_input = st.text_input(
        "Facebook Post URL hoặc Post ID",
        placeholder=(
            "https://www.facebook.com/.../posts/..."
        ),
        key="post_input",
    )

    limit = st.number_input('Số bình luận tối đa cần lấy', min_value=1, max_value=500,
                            value=100, key='comment_limit')

    if st.button(
        "🔎 Phân tích bình luận",
        type="primary",
        key="analyze_comments",
    ):

        if not post_input.strip():
            st.warning(
                "Vui lòng nhập Post URL hoặc Post ID."
            )
            return

        value = post_input.strip()

        if value.startswith(("http://", "https://")):

            if detect_url_type(value) != "post":
                st.error(
                    "URL không phải Facebook Post hợp lệ."
                )
                return

            post_id = value  # Preserve full group/permalink context for the browser.

        else:
            post_id = value

        if not post_id:
            st.error("Không xác định được Post ID.")
            return

        with st.spinner(
            "Đang phân tích bình luận..."
        ):

            try:
                post = post_service.get_post(
                    post_id
                )

                comments = (
                    post_service.get_ranked_comments(
                        post_id=post_id,
                        limit=int(limit),
                        reaction_weight=reaction_weight,
                        reply_weight=reply_weight,
                    )
                )

            except Exception as exc:
                st.error(
                    f"Lỗi khi phân tích bài viết: {exc}"
                )
                return

        st.session_state[
            "current_post"
        ] = post

        st.session_state[
            "current_comments"
        ] = comments

        st.success(
            "Đã phân tích bài viết thành công."
        )

    comments = st.session_state.get(
        "current_comments",
        [],
    )

    if not comments:
        return

    post = st.session_state.get('current_post')
    if post:
        st.write(getattr(post, 'content', '') or '')
        st.caption('Ngày đăng: ' + (format_vietnam(getattr(post, 'created_time', None)) or 'Chưa đọc được') + ' (UTC+7)')
    filtered_comments = rank_comments(comments, reaction_weight, reply_weight)

    st.subheader(
        f"🔥 Kết quả: {len(filtered_comments)} bình luận"
    )

    filtered_comments = display_comment_table(filtered_comments, key='post_comments')

    st.divider()

    st.subheader("📥 Xuất dữ liệu")

    export_col1, export_col2, export_col3 = st.columns(3)

    with export_col1:
        st.download_button(
            label="📊 Excel",
            data=comments_to_excel(
                filtered_comments
            ),
            file_name="facebook_comments.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            key="export_post_comments_excel",
        )

    with export_col2:
        st.download_button(
            label="📄 CSV",
            data=comments_to_csv(
                filtered_comments
            ),
            file_name="facebook_comments.csv",
            mime="text/csv",
            key="export_post_comments_csv",
        )

    with export_col3:
        st.download_button(
            label="🧾 JSON",
            data=data_to_json(
                filtered_comments
            ),
            file_name="facebook_comments.json",
            mime="application/json",
            key="export_post_comments_json",
        )
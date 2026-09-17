import streamlit as st

from facebook.post_service import PostService
from utils.url_parser import (
    detect_url_type,
    extract_post_id,
)
from exporters.excel import comments_to_excel
from exporters.csv import comments_to_csv
from exporters.json import data_to_json
from .components import display_comment_table


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

    col1, col2 = st.columns(2)

    with col1:
        limit = st.number_input(
            "Số bình luận lấy về",
            min_value=1,
            max_value=500,
            value=100,
            step=1,
            key="comment_limit",
        )

    with col2:
        st.caption(
            "Kết quả hiển thị = toàn bộ số bình luận thực tế lấy được."
        )

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

            post_id = extract_post_id(value)

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
                    post_id,
                    post_url=value if value.startswith(("http://", "https://")) else None,
                )

                comments = (
                    post_service.get_ranked_comments(
                        post_id=post_id,
                        limit=int(limit),
                        reaction_weight=reaction_weight,
                        reply_weight=reply_weight,
                        post_url=value if value.startswith(("http://", "https://")) else None,
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

    # Không cắt số lượng hiển thị: toàn bộ comments đã lấy được
    # sẽ được xếp hạng và hiển thị.
    ranked_comments = comments

    st.subheader(
        f"🔥 {len(ranked_comments)} bình luận — xếp hạng theo điểm"
    )

    display_comment_table(
        ranked_comments
    )

    st.divider()

    st.subheader("📥 Xuất dữ liệu")

    export_col1, export_col2, export_col3 = st.columns(3)

    with export_col1:
        st.download_button(
            label="📊 Excel",
            data=comments_to_excel(
                ranked_comments
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
                ranked_comments
            ),
            file_name="facebook_comments.csv",
            mime="text/csv",
            key="export_post_comments_csv",
        )

    with export_col3:
        st.download_button(
            label="🧾 JSON",
            data=data_to_json(
                ranked_comments
            ),
            file_name="facebook_comments.json",
            mime="application/json",
            key="export_post_comments_json",
        )
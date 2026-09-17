import streamlit as st

from facebook.group_service import GroupService
from facebook.post_service import PostService
from utils.url_parser import detect_url_type, extract_group_id

from exporters.excel import analysis_to_excel
from exporters.csv import (
    posts_to_csv,
    comments_to_csv,
)

from exporters.json import data_to_json

from .components import (
    display_post_table,
    display_post_summary,
    display_comment_table,
)


def render_group_page(
    group_service: GroupService,
    post_service: PostService,
    like_weight: float,
    comment_weight: float,
    share_weight: float,
    reaction_weight: float,
    reply_weight: float,
):
    st.header("📊 Phân tích Facebook Group")

    # =========================================================
    # 1. NHẬP GROUP
    # =========================================================

    group_input = st.text_input(
        "Facebook Group URL hoặc Group ID",
        placeholder=(
            "https://www.facebook.com/groups/ten-group"
        ),
        key="group_input",
    )

    # =========================================================
    # 2. CẤU HÌNH PHÂN TÍCH
    # =========================================================

    col1, col2 = st.columns(2)

    with col1:
        limit = st.number_input(
            "Số bài viết quét",
            min_value=1,
            max_value=500,
            value=20,
            step=1,
            key="group_post_limit",
            help="Số bài viết được lấy từ Facebook. Kết quả sẽ hiển thị đúng số bài đã quét nếu Facebook trả đủ dữ liệu.",
        )

    with col2:
        st.info(
            "Các bài viết được xếp hạng theo Engagement Score giảm dần. "
            "Không cắt Top N sau khi quét."
        )

    st.divider()

    # =========================================================
    # 3. NÚT PHÂN TÍCH GROUP
    # =========================================================

    if st.button(
        "🔎 Phân tích Group",
        type="primary",
        key="analyze_group",
    ):
        if not group_input.strip():
            st.warning(
                "Vui lòng nhập Facebook Group URL hoặc Group ID."
            )
            return

        value = group_input.strip()

        # -----------------------------------------------------
        # Xác định Group ID
        # -----------------------------------------------------

        if value.startswith(("http://", "https://")):

            if detect_url_type(value) != "group":
                st.error(
                    "URL không phải Facebook Group hợp lệ."
                )
                return

            group_id = extract_group_id(value)

        else:
            group_id = value

        if not group_id:
            st.error(
                "Không xác định được Group ID."
            )
            return

        # -----------------------------------------------------
        # Phân tích Group
        # -----------------------------------------------------

        with st.spinner(
            "Đang lấy thông tin Group và phân tích bài viết..."
        ):
            try:
                group = group_service.get_group(
                    group_id
                )

                posts = group_service.get_ranked_posts(
                    group_id=group_id,
                    limit=int(limit),
                    like_weight=like_weight,
                    comment_weight=comment_weight,
                    share_weight=share_weight,
                )

            except Exception as exc:
                st.error(
                    f"Lỗi khi phân tích Group: {exc}"
                )
                return

        # -----------------------------------------------------
        # Lưu vào Session State
        # -----------------------------------------------------

        st.session_state["current_group"] = group
        st.session_state["current_group_id"] = group_id
        st.session_state["current_posts"] = posts

        # Khi phân tích Group mới thì xóa bài viết đang chọn
        st.session_state.pop(
            "selected_post_id",
            None,
        )

        st.session_state.pop(
            "selected_post_comments",
            None,
        )

        st.session_state.pop(
            "selected_post_for_comments",
            None,
        )

        st.success(
            f"Đã phân tích Group: {group.name}"
        )

    # =========================================================
    # 4. HIỂN THỊ GROUP
    # =========================================================

    group = st.session_state.get(
        "current_group"
    )

    posts = st.session_state.get(
        "current_posts",
        [],
    )

    if not group or not posts:
        return

    st.divider()

    st.subheader(
        f"👥 {group.name}"
    )

    st.write(
        f"**Group ID:** `{group.group_id}`"
    )

    if group.url:
        st.write(
            f"**URL:** {group.url}"
        )

    st.divider()

    # =========================================================
    # 5. HIỂN THỊ TOÀN BỘ BÀI ĐÃ QUÉT
    # =========================================================

    # get_ranked_posts() đã tính điểm và sắp xếp giảm dần.
    # Không lọc/cắt thêm ở UI để số bài hiển thị phản ánh đúng số bài đã quét.
    display_posts = list(posts)

    st.subheader(
        f"🔥 Kết quả: {len(display_posts)} bài viết"
    )

    if not display_posts:
        st.info(
            "Facebook không trả về bài viết nào trong lần quét này."
        )
        return

    # =========================================================
    # 6. HIỂN THỊ BẢNG BÀI VIẾT
    # =========================================================

    display_post_table(
        display_posts
    )

    # =========================================================
    # EXPORT BÀI VIẾT
    # =========================================================

    st.subheader("📥 Xuất dữ liệu bài viết")

    export_col1, export_col2, export_col3 = st.columns(3)

    with export_col1:
        st.download_button(
            label="📊 Excel",
            data=analysis_to_excel(
                posts=display_posts,
                comments=[],
            ),
            file_name="facebook_posts.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            key="export_group_posts_excel",
        )

    with export_col2:
        st.download_button(
            label="📄 CSV",
            data=posts_to_csv(
                display_posts
            ),
            file_name="facebook_posts.csv",
            mime="text/csv",
            key="export_group_posts_csv",
        )

    with export_col3:
        st.download_button(
            label="🧾 JSON",
            data=data_to_json(
                display_posts
            ),
            file_name="facebook_posts.json",
            mime="application/json",
            key="export_group_posts_json",
        )

    st.divider()

    # =========================================================
    # 7. CHỌN BÀI VIẾT ĐỂ XEM CHI TIẾT / BÌNH LUẬN
    # =========================================================

    post_options = {
        (
            f"#{post.get('rank', '')} | "
            f"{post.get('author_name', '')} | "
            f"{post.get('content', '')[:80]}"
        ): post.get("post_id", "")
        for post in display_posts
    }

    selected_label = st.selectbox(
        "📌 Chọn bài viết để xem chi tiết hoặc phân tích bình luận",
        options=list(post_options.keys()),
        key="selected_post_label",
    )

    selected_post_id = post_options.get(
        selected_label
    )

    previous_selected_post_id = st.session_state.get(
        "selected_post_id"
    )

    if (
        previous_selected_post_id
        and previous_selected_post_id != selected_post_id
    ):
        st.session_state.pop("selected_post_comments", None)
        st.session_state.pop("selected_post_for_comments", None)

    st.session_state["selected_post_id"] = selected_post_id

    selected_post = next(
        (
            post
            for post in display_posts
            if post.get("post_id") == selected_post_id
        ),
        None,
    )

    if not selected_post:
        return

    # =========================================================
    # 10. HIỂN THỊ CHI TIẾT BÀI VIẾT
    # =========================================================

    st.divider()

    st.subheader(
        "📝 Chi tiết bài viết"
    )

    content = selected_post.get(
        "content",
        "",
    )

    if content:
        st.markdown(
            f"### {content}"
        )
    else:
        st.info(
            "Bài viết không có nội dung văn bản."
        )

    st.write(
        f"**Tác giả:** "
        f"{selected_post.get('author_name', '')}"
    )

    st.write(
        f"**Thời gian:** "
        f"{selected_post.get('created_time', '')}"
    )

    post_url = selected_post.get(
        "post_url",
        "",
    )

    if post_url:
        st.write(
            f"**Post URL:** {post_url}"
        )

    display_post_summary(
        selected_post
    )

    # =========================================================
    # 11. PHÂN TÍCH BÌNH LUẬN
    # =========================================================

    st.divider()

    st.subheader(
        "💬 Phân tích bình luận"
    )

    if st.button(
        "💬 Phân tích bình luận bài viết này",
        type="primary",
        key="analyze_selected_post_comments",
    ):

        with st.spinner(
            "Đang lấy và xếp hạng bình luận..."
        ):
            try:

                comments = (
                    post_service.get_ranked_comments(
                        post_id=selected_post_id,
                        limit=100,
                        reaction_weight=reaction_weight,
                        reply_weight=reply_weight,
                    )
                )

            except Exception as exc:
                st.error(
                    f"Lỗi khi phân tích bình luận: {exc}"
                )
                return

        st.session_state[
            "selected_post_for_comments"
        ] = selected_post_id

        st.session_state[
            "selected_post_comments"
        ] = comments

        st.success(
            f"Đã tìm thấy {len(comments)} bình luận."
        )

    # =========================================================
    # 12. HIỂN THỊ BÌNH LUẬN
    # =========================================================

    selected_comments = st.session_state.get(
        "selected_post_comments",
        [],
    )

    selected_comments_post_id = (
        st.session_state.get(
            "selected_post_for_comments"
        )
    )

    # Chỉ hiển thị comment nếu đúng bài viết đang được chọn
    if (
        selected_comments
        and selected_comments_post_id
        == selected_post_id
    ):
        st.divider()

        st.subheader(
            f"🔥 Top {len(selected_comments)} bình luận"
        )

        display_comment_table(
            selected_comments
        )

        # =========================================================
        # EXPORT BÌNH LUẬN
        # =========================================================

        st.subheader("📥 Xuất dữ liệu bình luận")

        comment_export_col1, comment_export_col2, comment_export_col3 = (
            st.columns(3)
        )

        with comment_export_col1:
            st.download_button(
                label="📊 Excel",
                data=analysis_to_excel(
                    posts=[],
                    comments=selected_comments,
                ),
                file_name="facebook_comments.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                key="export_group_comments_excel",
            )

        with comment_export_col2:
            from exporters.csv import comments_to_csv

            st.download_button(
                label="📄 CSV",
                data=comments_to_csv(
                    selected_comments
                ),
                file_name="facebook_comments.csv",
                mime="text/csv",
                key="export_group_comments_csv",
            )

        with comment_export_col3:
            st.download_button(
                label="🧾 JSON",
                data=data_to_json(
                    selected_comments
                ),
                file_name="facebook_comments.json",
                mime="application/json",
                key="export_group_comments_json",
            )
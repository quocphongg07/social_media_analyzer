"""Shared sortable tables used by all three tabs.

This module has a distinct name so an older ui/components.py left on a user's
machine cannot be imported accidentally with the newer pages.
"""
import pandas as pd
import streamlit as st

from utils.datetime_utils import vietnam_datetime


LABELS = {
    'parent_comment_id': 'Bình luận cha',
    'depth': 'Cấp trả lời',
    'rank': 'Hạng',
    'post_id': 'Bài viết',
    'comment_id': 'Bình luận',
    'author_name': 'Tác giả',
    'content': 'Nội dung',
    'likes': 'Like / Reaction',
    'reactions': 'Reaction',
    'comments': 'Comment',
    'shares': 'Share',
    'replies': 'Reply',
    'reposts': 'Repost',
    'quotes': 'Quote',
    'engagement_score': 'Điểm',
    'score_status': 'Trạng thái điểm',
    'created_time': 'Ngày đăng',
    'collected_at': 'Ngày thu thập',
    'post_url': 'Link bài',
    'comment_url': 'Link bình luận',
    'post_type': 'Loại bài',
    'shared_content': 'Nội dung chia sẻ',
    'shared_post_url': 'Link bài gốc',
}

NUMERIC = {
    'depth', 'rank', 'likes', 'reactions', 'comments', 'shares',
    'replies', 'reposts', 'quotes', 'engagement_score',
}

POST_COLUMNS = [
    'rank', 'post_id', 'author_name', 'content', 'likes', 'comments',
    'shares', 'engagement_score', 'created_time', 'post_url',
]

COMMENT_COLUMNS = [
    'rank', 'comment_id', 'author_name', 'content', 'reactions',
    'replies', 'engagement_score', 'created_time', 'comment_url',
]


def table_frame(rows, columns):
    frame = pd.DataFrame(
        [{column: row.get(column) for column in columns} for row in rows],
        columns=columns,
    )
    for column in columns:
        if column in NUMERIC:
            frame[column] = pd.to_numeric(frame[column], errors='coerce')
        elif column in ('created_time', 'collected_at'):
            frame[column] = pd.to_datetime(
                frame[column].map(vietnam_datetime), errors='coerce'
            )
        else:
            frame[column] = frame[column].map(
                lambda value: '' if value is None else str(value)
            )
    return frame


def sort_rows(rows, columns, column, ascending):
    frame = table_frame(rows, columns).sort_values(
        column,
        ascending=ascending,
        na_position='last',
        kind='stable',
    )
    return [rows[index] for index in frame.index], frame


def display_ranked_table(rows, columns, key):
    if not rows:
        st.info('Không có dữ liệu.')
        return []

    left, right = st.columns([2, 1])
    default_index = columns.index('engagement_score') if 'engagement_score' in columns else 0
    sort_column = left.selectbox(
        'Sắp xếp theo',
        columns,
        index=default_index,
        format_func=lambda column: LABELS.get(column, column),
        key=key + '_sort_column',
    )
    ascending = right.selectbox(
        'Thứ tự',
        ['Giảm dần', 'Tăng dần'],
        key=key + '_sort_order',
    ) == 'Tăng dần'

    ordered, frame = sort_rows(rows, columns, sort_column, ascending)
    column_config = {}
    for column in columns:
        label = LABELS.get(column, column)
        if column in ('created_time', 'collected_at'):
            column_config[column] = st.column_config.DatetimeColumn(
                label,
                format='DD/MM/YYYY HH:mm:ss',
                help='Giờ Việt Nam (UTC+7)',
            )
        elif column.endswith('_url'):
            column_config[column] = st.column_config.LinkColumn(
                label, display_text='Xem'
            )
        else:
            column_config[column] = label

    st.dataframe(
        frame,
        hide_index=True,
        use_container_width=True,
        column_config=column_config,
    )
    st.caption(
        f'{len(rows)} dòng · Giờ Việt Nam (UTC+7). Lựa chọn sắp xếp phía trên '
        'áp dụng cho bảng và file xuất. Hạng luôn là hạng theo điểm tương tác.'
    )
    return ordered


def post_table_frame(posts):
    return table_frame(posts, POST_COLUMNS).rename(columns=LABELS)


def display_post_table(posts, key='facebook_post_table'):
    return display_ranked_table(posts, POST_COLUMNS, key)


def display_comment_table(comments, key='facebook_comment_table'):
    return display_ranked_table(comments, COMMENT_COLUMNS, key)


def display_post_summary(post):
    first, second, third, fourth = st.columns(4)
    first.metric('❤️ Reactions', post.get('likes', post.get('reactions', 0)))
    second.metric('💬 Comments', post.get('comments', 0))
    third.metric('↗️ Shares', post.get('shares', 0))
    fourth.metric('🔥 Engagement Score', post.get('engagement_score', 0))
from datetime import timedelta, timezone
import math
import re

import pandas as pd
import streamlit as st

VIETNAM = timezone(timedelta(hours=7))


def vietnam_datetime(value):
    """Convert UTC epochs (s/ms/us/ns), ISO strings or datetimes to Vietnam wall time.

    Return datetime values, not formatted strings, so column sorting stays chronological.
    Naive input dates are interpreted as UTC; blank/invalid/zero timestamps stay blank.
    """
    if value is None or isinstance(value, bool):
        return pd.NaT
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return pd.NaT
        if re.fullmatch(r'[+-]?\d+(?:\.\d+)?', value):
            value = float(value) if '.' in value else int(value)
    try:
        if isinstance(value, (int, float)):
            if not math.isfinite(value) or value == 0:
                return pd.NaT
            size = abs(value)
            unit = 'ns' if size >= 10**17 else 'us' if size >= 10**14 else 'ms' if size >= 10**11 else 's'
            parsed = pd.to_datetime(value, unit=unit, utc=True, errors='coerce')
        else:
            parsed = pd.to_datetime(value, utc=True, errors='coerce')
        if pd.isna(parsed):
            return pd.NaT
        # Strip timezone only after converting, preventing browser timezone changes.
        return parsed.tz_convert(VIETNAM).tz_localize(None)
    except (ValueError, TypeError, OverflowError):
        return pd.NaT


def post_table_frame(posts):
    rows = []
    for post in posts:
        rows.append({
            'Hạng': post.get('rank'),
            'Bài viết': str(post.get('post_id') or ''),
            'Tác giả': post.get('author_name') or '',
            'Nội dung': post.get('content') or '',
            'Reaction': post.get('likes', post.get('reactions')),
            'Comment': post.get('comments'),
            'Share': post.get('shares'),
            'Điểm': post.get('engagement_score'),
            'Ngày đăng': vietnam_datetime(post.get('created_time')),
            'Link': post.get('post_url') or '',
        })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for column in ['Hạng', 'Reaction', 'Comment', 'Share', 'Điểm']:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    frame['Ngày đăng'] = pd.to_datetime(frame['Ngày đăng'], errors='coerce')
    return frame


def display_post_table(posts: list[dict], key='facebook_post_table') -> None:
    if not posts:
        st.info('Không có bài viết nào.')
        return
    frame = post_table_frame(posts)
    left, right = st.columns([2, 1])
    sort_column = left.selectbox('Sắp xếp theo', list(frame.columns),
                                 index=list(frame.columns).index('Điểm'), key=key + '_sort_column')
    order = right.selectbox('Thứ tự', ['Giảm dần', 'Tăng dần'], key=key + '_sort_order')
    # Stable sort retains input order for equal values; missing values always go last.
    frame = frame.sort_values(sort_column, ascending=(order == 'Tăng dần'),
                              na_position='last', kind='stable')
    st.dataframe(frame, use_container_width=True, hide_index=True,
        column_config={
            'Ngày đăng': st.column_config.DatetimeColumn('Ngày đăng', format='DD/MM/YYYY HH:mm:ss',
                          help='Giờ Việt Nam (UTC+7). Ô trống nghĩa là chưa có ngày đăng hợp lệ.'),
            'Link': st.column_config.LinkColumn('Link', display_text='Xem bài'),
            'Bài viết': st.column_config.TextColumn('Bài viết'),
            'Điểm': st.column_config.NumberColumn('Điểm'),
        })
    st.caption('Ngày đăng theo giờ Việt Nam (UTC+7). Chọn cách sắp xếp phía trên hoặc nhấn tiêu đề cột để đổi thứ tự. '
               'Cột Hạng vẫn là hạng theo điểm tương tác; bảng hiển thị toàn bộ bài được truyền vào.')


def display_comment_table(comments: list[dict]) -> None:
    if not comments:
        st.info('Không có bình luận nào.')
        return
    rows = []
    for comment in comments:
        rows.append({
            'Hạng': comment.get('rank'),
            'Bình luận': str(comment.get('comment_id') or ''),
            'Tác giả': comment.get('author_name') or '',
            'Nội dung': comment.get('content') or '',
            'Reaction': comment.get('reactions'),
            'Reply': comment.get('replies'),
            'Điểm': comment.get('engagement_score'),
            'Thời gian': vietnam_datetime(comment.get('created_time')),
        })
    frame = pd.DataFrame(rows)
    for column in ['Hạng', 'Reaction', 'Reply', 'Điểm']:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    frame['Thời gian'] = pd.to_datetime(frame['Thời gian'], errors='coerce')
    st.dataframe(frame, use_container_width=True, hide_index=True,
        column_config={'Thời gian': st.column_config.DatetimeColumn('Thời gian', format='DD/MM/YYYY HH:mm:ss')})


def display_post_summary(post: dict) -> None:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric('❤️ Reactions', post.get('likes', post.get('reactions', 0)))
    with col2:
        st.metric('💬 Comments', post.get('comments', 0))
    with col3:
        st.metric('↗️ Shares', post.get('shares', 0))
    with col4:
        st.metric('🔥 Engagement Score', post.get('engagement_score', 0))
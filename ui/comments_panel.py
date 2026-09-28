import streamlit as st
from utils.datetime_utils import format_vietnam
from exporters.common import COMMENT_FIELDS, csv_bytes, excel_bytes, json_bytes
from .table_components import display_ranked_table, COMMENT_COLUMNS


def rank_comment_rows(comments, reaction_weight, reply_weight):
    known, unknown = [], []
    weights = dict(reactions=reaction_weight, replies=reply_weight)
    for source in comments:
        row = dict(source)
        available = [k for k, w in weights.items() if w > 0 and row.get(k) is not None]
        missing = [k for k, w in weights.items() if w > 0 and row.get(k) is None]
        if available or not any(weights.values()):
            row['engagement_score'] = sum((row.get(k) or 0) * w for k, w in weights.items())
            row['score_status'] = 'partial' if missing else 'complete'
            known.append(row)
        else:
            row.update(engagement_score=None, rank=None, score_status='unavailable')
            unknown.append(row)
    known.sort(key=lambda row: -row['engagement_score'])
    for rank, row in enumerate(known, 1):
        row['rank'] = rank
    return known + unknown


def render_comments_panel(posts, key, fetch_comments, reaction_weight, reply_weight):
    if not posts:
        return
    st.divider()
    st.subheader('Chi tiết bài viết và bình luận')
    lookup = {str(row.get('post_id') or row.get('post_url')): row for row in posts}
    selection_key = key + '_selected_post'
    if st.session_state.get(selection_key) not in lookup:
        st.session_state.pop(selection_key, None)
    def label(post_id):
        row = lookup[post_id]
        return f"{row.get('author_name', '')} | {(row.get('content') or '')[:90]} | {post_id}"
    selected_id = st.selectbox('Chọn bài viết', list(lookup), format_func=label, key=selection_key)
    post = lookup[selected_id]
    st.write(post.get('content') or 'Bài viết không có nội dung văn bản.')
    st.caption('Ngày đăng: ' + (format_vietnam(post.get('created_time')) or 'Chưa đọc được') + ' (UTC+7)')
    if post.get('shared_content'):
        st.write('Nội dung được chia sẻ: ' + post['shared_content'])
    if post.get('post_url'):
        st.link_button('Mở bài viết', post['post_url'])
    limit = st.number_input('Số bình luận tối đa cần lấy', min_value=1, max_value=500, value=100, key=key + '_comment_limit')
    cache_key = key + '_comment_result'
    if st.button('Thu thập và phân tích bình luận', key=key + '_scan_comments'):
        st.session_state.pop(cache_key, None)
        try:
            result = fetch_comments(post, int(limit))
            if isinstance(result, list):
                result = dict(comments=result, requested_limit=int(limit))
            st.session_state[cache_key] = dict(result, selected_id=selected_id)
        except Exception as exc:
            st.error(f'Không thu thập được bình luận: {exc}')
    result = st.session_state.get(cache_key)
    if not result or result['selected_id'] != selected_id:
        return
    comments = rank_comment_rows(result.get('comments', []), reaction_weight, reply_weight)
    st.write(f"Đã đọc {len(comments)}/{result['requested_limit']} bình luận yêu cầu.")
    if len(comments) < result['requested_limit']:
        st.caption('Chưa lấy đủ giới hạn yêu cầu. Trang có thể đã hết bình luận có thể truy cập, '
                   'không tải thêm dữ liệu hoặc đang giới hạn phiên truy cập.')
    for warning in result.get('warnings', []):
        st.caption(warning)
    if result.get('stop_reason') in {'login_required', 'access_denied', 'rate_limited'}:
        st.warning('Phiên quét dừng vì trang yêu cầu đăng nhập hoặc hạn chế truy cập.')
    if not comments:
        st.info('Không đọc được bình luận phù hợp. Kết quả này không xác nhận bài viết không có bình luận.')
        return
    st.caption('Điểm bình luận = Reaction × trọng số Reaction + Reply × trọng số Reply. Ô trống là chỉ số chưa đọc được.')
    columns = COMMENT_COLUMNS + ['score_status']
    if any('parent_comment_id' in row for row in comments):
        columns += ['parent_comment_id', 'depth']
    ordered = display_ranked_table(comments, columns, key + '_comments')
    a, b, c = st.columns(3)
    stem = key + '_comments'
    a.download_button('Tải CSV bình luận', csv_bytes(ordered, COMMENT_FIELDS), stem + '.csv', 'text/csv', key=stem + '_csv')
    b.download_button('Tải Excel bình luận', excel_bytes([('Comments', ordered, COMMENT_FIELDS)]), stem + '.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key=stem + '_xlsx')
    c.download_button('Tải JSON bình luận', json_bytes(dict(comments=ordered, metadata=dict(
        post_url=post.get('post_url'), timezone='Asia/Ho_Chi_Minh', date_format='DD/MM/YYYY HH:mm:ss',
        reaction_weight=reaction_weight, reply_weight=reply_weight))), stem + '.json', 'application/json', key=stem + '_json')
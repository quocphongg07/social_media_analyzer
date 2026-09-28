from .common import excel_bytes, POST_FIELDS, COMMENT_FIELDS

def posts_to_excel(posts):
    return excel_bytes([("Posts", posts, POST_FIELDS)])

def comments_to_excel(comments):
    return excel_bytes([("Comments", comments, COMMENT_FIELDS)])

def analysis_to_excel(posts, comments):
    return excel_bytes([("Posts", posts, POST_FIELDS), ("Comments", comments, COMMENT_FIELDS)])

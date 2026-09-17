"""Execute the user's Facebook browser collector outside the Streamlit thread."""
import argparse
import json
import os
from pathlib import Path


def perform(client, request):
    action = request['action']
    if action not in {'login', 'get_group', 'get_group_posts', 'get_post', 'get_post_comments'}:
        raise ValueError('Thao tác không hợp lệ.')
    if action == 'login':
        # The explicit web button requests replacing this dedicated session.
        client._ensure_browser()
        client._context.clear_cookies()
    if not client.ensure_login():
        raise RuntimeError('Chưa đăng nhập Facebook. Không sử dụng dữ liệu demo.')
    if action == 'login':
        return {'logged_in': True}
    group_id = str(request.get('group_id') or '')
    if group_id.isdigit():
        type(client)._global_last_group_id = group_id
    if action == 'get_group':
        return client.get_group(group_id)
    if action == 'get_group_posts':
        return client.get_group_posts(group_id, limit=int(request['limit']))
    post_id = str(request.get('post_id') or '')
    if group_id.isdigit() and post_id.isdigit():
        post_input = f'https://www.facebook.com/groups/{group_id}/posts/{post_id}/'
    else:
        post_input = post_id
    if action == 'get_post':
        return client.get_post(post_input)
    # Restore the selected post's page/context across Streamlit reruns/processes.
    post = client.get_post(post_input)
    if not post:
        raise RuntimeError('Không mở được bài viết để đọc bình luận. Hãy phân tích nhóm hoặc nhập link bài đầy đủ.')
    return client.get_post_comments(post.get('post_id') or post_id, limit=int(request['limit']))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    client = None
    try:
        request = json.loads(Path(args.request).read_text(encoding='utf-8'))
        from .browser_client import FacebookBrowserClient
        client = FacebookBrowserClient(headless=False)
        value = perform(client, request)
        path = Path(args.output)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, path)
    except Exception as exc:
        print(f'Lỗi Facebook: {exc}', flush=True)
        raise SystemExit(1)
    finally:
        if client is not None:
            client.close()


if __name__ == '__main__':
    main()
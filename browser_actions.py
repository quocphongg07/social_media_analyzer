"""Small subprocess entry point for browser actions initiated on the web UI."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        request = json.loads(Path(args.request).read_text(encoding='utf-8'))
        if request['action'] == 'login' and request.get('platform') in {'facebook', 'threads'}:
            from utils.browser_session import manual_login
            result = manual_login(request['platform'])
        elif request['action'] == 'facebook_profile':
            from facebook.profile_client import FacebookProfileClient
            from utils.browser_session import profile_path
            client = FacebookProfileClient(profile_dir=profile_path('facebook'))
            result = client.collect(
                request['profile'],
                limit=int(request['limit']),
                progress=lambda msg: print(msg, flush=True),
            )
        elif request['action'] == 'facebook_profile_comments':
            from facebook.browser_client import FacebookBrowserClient
            from utils.browser_session import profile_path
            client = FacebookBrowserClient(
                headless=False,
                user_data_dir=str(profile_path('facebook')),
            )
            try:
                limit = int(request['limit'])
                result = client._collect_post_comments(
                    str(request['post_url']),
                    max_comments=limit,
                    max_rounds=min(100, max(30, limit)),
                    expected_post_id=str(request.get('post_id') or ''),
                )
            finally:
                client.close()
        elif request['action'] == 'threads_comments':
            from threads.comments import collect_comments
            result = collect_comments(request['url'], int(request['limit']), progress=lambda msg: print(msg, flush=True))
        else:
            raise ValueError('Thao tác không hợp lệ.')
        path = Path(args.output)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, path)
    except Exception as exc:
        print(str(exc), flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
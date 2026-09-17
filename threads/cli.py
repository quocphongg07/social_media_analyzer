"""Run collection outside Streamlit's thread/event loop (including Windows)."""
import argparse
import json
import os
from pathlib import Path
from .browser_client import ThreadsBrowserClient


def main():
    p = argparse.ArgumentParser(description='Thu thập tài khoản Threads bằng trình duyệt')
    p.add_argument('profile', nargs='?')
    p.add_argument('--login', action='store_true', help='Mở trình duyệt để đăng nhập thủ công và lưu phiên')
    p.add_argument('--limit', type=int, default=100)
    p.add_argument('--max-scrolls', type=int, default=40)
    p.add_argument('--wait-seconds', type=int, default=3)
    p.add_argument('--login-wait', type=int, default=0)
    p.add_argument('--include-replies', action='store_true')
    p.add_argument('--output', default='data/threads_result.json')
    args = p.parse_args()
    try:
        if args.login:
            ThreadsBrowserClient().login()
            print('Đã đóng trình duyệt và lưu phiên. Quay lại Streamlit để thu thập.', flush=True)
            return
        if not args.profile:
            p.error('Cần nhập link tài khoản, hoặc dùng --login.')
        result = ThreadsBrowserClient().collect(args.profile, limit=args.limit,
            max_scrolls=args.max_scrolls, wait_seconds=args.wait_seconds,
            login_wait=args.login_wait, include_replies=args.include_replies,
            progress=lambda s: print(s, flush=True))
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, path)
        print(f'Đã lưu {len(result["posts"])} bài.', flush=True)
    except Exception as exc:
        print(f'Thu thập thất bại: {exc}', flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
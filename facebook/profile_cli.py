import argparse
import json
import os
from pathlib import Path
from .profile_client import FacebookProfileClient


def main():
    p = argparse.ArgumentParser(description='Thu thập dòng thời gian tài khoản Facebook')
    p.add_argument('profile', nargs='?')
    p.add_argument('--login', action='store_true')
    p.add_argument('--limit', type=int, default=100)
    p.add_argument('--output', default='data/facebook_profile_result.json')
    args = p.parse_args()
    try:
        client = FacebookProfileClient()
        if args.login:
            client.login()
            print('Đã lưu phiên Facebook. Quay lại Streamlit để thu thập.', flush=True)
            return
        if not args.profile:
            p.error('Cần link tài khoản hoặc --login.')
        result = client.collect(args.profile, args.limit, progress=lambda s: print(s, flush=True))
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, path)
        print(f'Đã thu thập {len(result["posts"])} bài.', flush=True)
    except Exception as exc:
        print(f'Thu thập thất bại: {exc}', flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
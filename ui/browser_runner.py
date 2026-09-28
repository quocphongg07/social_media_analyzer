"""Run manual browser jobs outside Streamlit's script thread on Windows."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import streamlit as st


ROOT = Path(__file__).resolve().parents[1]


def run_browser_action(action, *, timeout=3600, status=None, **params):
    status = status or st.empty()
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix='social_browser_') as directory:
            request = Path(directory) / 'request.json'
            output = Path(directory) / 'result.json'
            log_path = Path(directory) / 'progress.log'
            request.write_text(
                json.dumps({'action': action, **params}, ensure_ascii=False),
                encoding='utf-8',
            )
            with log_path.open('w', encoding='utf-8') as log:
                process = subprocess.Popen(
                    [sys.executable, '-m', 'browser_actions',
                     '--request', str(request), '--output', str(output)],
                    cwd=ROOT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=dict(os.environ, PYTHONIOENCODING='utf-8'),
                )
                started = time.monotonic()
                while process.poll() is None:
                    lines = log_path.read_text(
                        encoding='utf-8', errors='replace'
                    ).splitlines()
                    status.info(
                        lines[-1] if lines
                        else 'Đang mở trình duyệt…'
                    )
                    if time.monotonic() - started > timeout:
                        raise TimeoutError(
                            'Phiên trình duyệt quá thời gian. '
                            'Hãy thử lại với giới hạn nhỏ hơn.'
                        )
                    time.sleep(1)

                if process.returncode != 0 or not output.exists():
                    lines = log_path.read_text(
                        encoding='utf-8', errors='replace'
                    ).splitlines()
                    raise RuntimeError(
                        '\n'.join(lines[-8:])
                        or 'Tiến trình trình duyệt không trả về kết quả.'
                    )
                return json.loads(output.read_text(encoding='utf-8'))
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        status.empty()

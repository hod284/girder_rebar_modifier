#!/bin/bash
cd "$(dirname "$0")"
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
command -v "$PY" >/dev/null 2>&1 || [ -x "$PY" ] || { echo "실행 중인 프로그램이 없습니다."; exit 0; }
"$PY" launcher.py --stop

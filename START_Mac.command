#!/bin/bash
# 보 주근 배근 변경 시스템 - Mac 실행 (켜져 있으면 재시작)
#  1) 컴퓨터의 Python(3.10+)에 필요한 라이브러리가 이미 있으면 → 설치 없이 바로 실행
#  2) Python 만 있으면 → 그 Python 으로 이 폴더 안(.venv)에 라이브러리만 설치
#  3) Python 이 없으면 → 이 폴더 안(.uv, .venv)에 전용 Python 과 라이브러리 자동 설치
cd "$(dirname "$0")"
DIR="$PWD"
echo "=================================================="
echo "  보 주근 배근 변경 시스템 시작 (켜져 있으면 재시작)"
echo "=================================================="

fail() {
  echo ""; echo "[오류] $1"
  echo "       인터넷 연결을 확인한 뒤 다시 실행하세요. 계속 실패하면 이 창을 캡처해 주세요."
  read -n 1 -s -r -p "아무 키나 누르면 닫힙니다..."; exit 1
}
is_py310() { "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; }
has_deps() { "$1" -c 'import ifcopenshell, plotly, pandas, matplotlib, numpy, streamlit as s, sys
sys.exit(0 if tuple(int(x) for x in s.__version__.split(".")[:2]) >= (1,50) else 1)' >/dev/null 2>&1; }

VPY="$DIR/.venv/bin/python"
RUN_PY=""
if [ -x "$VPY" ] && has_deps "$VPY"; then
  RUN_PY="$VPY"
else
  # 컴퓨터에 설치된 Python 찾기
  BASE_PY=""
  for c in python3.13 python3.12 python3.11 python3.10 /opt/homebrew/bin/python3 /usr/local/bin/python3 \
           /Library/Frameworks/Python.framework/Versions/Current/bin/python3 python3; do
    command -v "$c" >/dev/null 2>&1 || continue
    is_py310 "$c" || continue
    if has_deps "$c"; then RUN_PY="$c"; break; fi
    [ -z "$BASE_PY" ] && BASE_PY="$c"
  done

  if [ -n "$RUN_PY" ]; then
    echo "[확인] 설치된 Python 과 라이브러리를 그대로 사용합니다. (추가 설치 없음)"
  elif [ -n "$BASE_PY" ]; then
    echo ""; echo "[설치] 설치된 Python($("$BASE_PY" -V 2>&1))을 사용하고, 라이브러리만 이 폴더 안에 설치합니다. (1~3분, 최초 1회)"
    rm -rf "$DIR/.venv"
    "$BASE_PY" -m venv "$DIR/.venv" || fail "가상환경 생성에 실패했습니다."
    "$VPY" -m pip install -q --upgrade pip
    "$VPY" -m pip install -r "$DIR/requirements.txt" || { rm -rf "$DIR/.venv"; fail "라이브러리 설치에 실패했습니다."; }
    echo "[설치] 완료"; RUN_PY="$VPY"
  else
    echo ""; echo "[설치] Python 이 없어 전용 Python 과 라이브러리를 이 폴더 안에 자동 설치합니다. (2~5분, 최초 1회)"
    export UV_INSTALL_DIR="$DIR/.uv" UV_NO_MODIFY_PATH=1 INSTALLER_NO_MODIFY_PATH=1
    export UV_PYTHON_INSTALL_DIR="$DIR/.uv/python" UV_CACHE_DIR="$DIR/.uv/cache"
    UV=""
    for c in "$DIR/.uv/uv" "$DIR/.uv/bin/uv"; do [ -x "$c" ] && UV="$c" && break; done
    if [ -z "$UV" ]; then
      echo "[설치] 1/3 설치 도구(uv) 내려받는 중..."
      curl -LsSf https://astral.sh/uv/install.sh | sh > "$DIR/.uv_install.log" 2>&1
      for c in "$DIR/.uv/uv" "$DIR/.uv/bin/uv"; do [ -x "$c" ] && UV="$c" && break; done
    fi
    if [ -z "$UV" ]; then
      ARCH=$(uname -m); [ "$ARCH" = "arm64" ] && T=aarch64-apple-darwin || T=x86_64-apple-darwin
      mkdir -p "$DIR/.uv" && curl -LsSf "https://github.com/astral-sh/uv/releases/latest/download/uv-$T.tar.gz" \
        | tar -xz -C "$DIR/.uv" --strip-components 1
      [ -x "$DIR/.uv/uv" ] && UV="$DIR/.uv/uv"
    fi
    [ -z "$UV" ] && fail "설치 도구(uv)를 내려받지 못했습니다."
    echo "[설치] 2/3 전용 Python 3.12 설치 중..."
    rm -rf "$DIR/.venv"
    "$UV" venv "$DIR/.venv" --python 3.12 --managed-python --seed -q || fail "Python 설치에 실패했습니다."
    echo "[설치] 3/3 라이브러리 설치 중... (가장 오래 걸립니다)"
    "$UV" pip install --python "$VPY" -r "$DIR/requirements.txt" || { rm -rf "$DIR/.venv"; fail "라이브러리 설치에 실패했습니다."; }
    echo "[설치] 완료"; RUN_PY="$VPY"
  fi
fi

"$RUN_PY" launcher.py "$@" || fail "프로그램을 시작하지 못했습니다. 이 폴더의 app.log 를 확인하세요."
echo ""; echo "브라우저에서 열렸습니다. 이 창은 닫아도 됩니다."

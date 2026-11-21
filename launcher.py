"""
실행기: START_Mac.command / START_Windows.bat 에서 호출

  - 실행한 Python 에 라이브러리가 있으면 그대로 사용, 없으면 폴더 안에 전용 환경(.venv)을 만들어 설치
               → 프로그램 시작 → 브라우저 자동 열기
  - 이미 켜져 있을 때 실행: 기존 프로그램 종료 → 다시 시작 (재시작)
  - python launcher.py --stop : 종료
"""
from __future__ import annotations

import os
import platform
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "src" / "app.py"
VENV = ROOT / ".venv"
PID_FILE = ROOT / ".app.pid"
PORT_FILE = ROOT / ".app.port"
LOG_FILE = ROOT / "app.log"
PORT = 8501
URL = f"http://localhost:{PORT}"
IS_WIN = platform.system() == "Windows"


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")


def in_venv() -> bool:
    try:
        return Path(sys.prefix).resolve() == VENV.resolve()
    except OSError:
        return False


def bootstrap():
    """전용 환경(.venv)이 없으면 만들고 라이브러리를 설치한 뒤, 그 환경의 파이썬으로 다시 실행한다."""
    if sys.version_info < (3, 10):
        print(f"[오류] Python 3.10 이상이 필요합니다. 현재: {platform.python_version()}")
        print("       https://www.python.org/downloads/ 에서 설치 후 다시 실행하세요.")
        sys.exit(1)
    if not venv_python().exists():
        print("[설치] 처음 실행입니다. 전용 환경을 만들고 라이브러리를 설치합니다. (1~3분, 최초 1회)")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
        subprocess.check_call([str(venv_python()), "-m", "pip", "install", "--upgrade", "pip", "-q"])
        subprocess.check_call([str(venv_python()), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
        print("[설치] 완료")
    sys.exit(subprocess.call([str(venv_python()), str(Path(__file__).resolve()), *sys.argv[1:]]))


def deps_ok() -> bool:
    try:
        import ifcopenshell, plotly, pandas, matplotlib, numpy  # noqa: F401,E401
        import streamlit
        return tuple(int(x) for x in streamlit.__version__.split(".")[:2]) >= (1, 50)
    except Exception:  # noqa: BLE001
        return False


def ensure_deps():
    try:
        import ifcopenshell, streamlit, plotly, pandas, matplotlib, numpy  # noqa: F401,E401
    except ImportError:
        print("[설치] 빠진 라이브러리를 설치합니다.")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])


def port_in_use(port: int | None = None) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port or PORT)) == 0


def _run(cmd) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
    except Exception:  # noqa: BLE001
        return ""


def port_pids(port: int) -> list[int]:
    """해당 포트에서 대기 중인 프로세스 PID 목록."""
    pids = set()
    if IS_WIN:
        for line in _run(["netstat", "-ano", "-p", "TCP"]).splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3].upper() == "LISTENING":
                pids.add(int(parts[4]))
    else:
        for tok in _run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"]).split():
            if tok.isdigit():
                pids.add(int(tok))
    return sorted(pids)


def is_streamlit(pid: int) -> bool:
    """이 프로그램(Streamlit)이 띄운 프로세스인지 확인 - 다른 프로그램은 절대 끄지 않는다."""
    if IS_WIN:
        cmd = _run(["powershell", "-NoProfile", "-Command",
                    f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"])
    else:
        cmd = _run(["ps", "-o", "command=", "-p", str(pid)])
    return "streamlit" in cmd.lower()


def kill_pid(pid: int):
    if IS_WIN:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        return
    for fn in (lambda: os.killpg(pid, signal.SIGTERM), lambda: os.kill(pid, signal.SIGTERM)):
        try:
            fn()
            return
        except (ProcessLookupError, PermissionError, OSError):
            continue


def wait_port_free(port: int, sec: float = 10.0):
    for _ in range(int(sec / 0.2)):
        if not port_in_use(port):
            return True
        time.sleep(0.2)
    return not port_in_use(port)


def free_port(start: int = 8501) -> int:
    for p in range(start, start + 100):
        if not port_in_use(p):
            return p
    return start


def stop() -> bool:
    """실행 중인 이 프로그램 종료 (pid 파일 + 포트 검사). 종료한 게 있으면 True.
    예전 폴더에서 켜 두고 잊은 프로그램(pid 파일 없음)도 포트로 찾아서 끈다."""
    killed = False
    ports = {8501}
    if PORT_FILE.exists():
        try:
            ports.add(int(PORT_FILE.read_text().strip()))
        except ValueError:
            pass
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if any(port_in_use(p) for p in ports):
                kill_pid(pid)
                killed = True
        except ValueError:
            pass
    for p in ports:
        for pid in port_pids(p):
            if is_streamlit(pid):
                kill_pid(pid)
                killed = True
        if killed:
            wait_port_free(p)
    PID_FILE.unlink(missing_ok=True)
    PORT_FILE.unlink(missing_ok=True)
    return killed


def start() -> bool:
    global PORT, URL
    PORT = free_port(8501)
    URL = f"http://localhost:{PORT}"
    PORT_FILE.write_text(str(PORT))
    cmd = [sys.executable, "-m", "streamlit", "run", str(APP), "--server.port", str(PORT),
           "--server.headless", "true", "--browser.gatherUsageStats", "false",
           "--client.toolbarMode", "minimal"]
    log = open(LOG_FILE, "w", encoding="utf-8")
    kw = dict(cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    if IS_WIN:
        kw["creationflags"] = 0x00000200 | 0x08000000  # CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen(cmd, **kw)
    PID_FILE.write_text(str(p.pid))
    for _ in range(300):  # 최대 60초
        if port_in_use():
            return True
        if p.poll() is not None:
            break
        time.sleep(0.2)
    print(f"[오류] 프로그램이 시작되지 않았습니다. 로그를 확인하세요: {LOG_FILE}")
    return False


def main():
    if "--stop" in sys.argv:
        print("[종료] 프로그램을 종료했습니다." if stop() else "[종료] 실행 중인 프로그램이 없습니다.")
        return
    if not in_venv() and not deps_ok():
        bootstrap()  # 라이브러리가 없으면 전용 환경(.venv)을 만들어 다시 실행 (여기서 끝남)
    ensure_deps()
    if stop():
        print("[재시작] 실행 중이던 프로그램을 종료하고 다시 시작합니다.")
    print("[시작] 보 주근 배근 변경 시스템을 시작합니다...")
    if start():
        if PORT != 8501:
            print(f"[알림] 8501 포트를 다른 프로그램이 사용 중이라 {PORT} 포트로 열었습니다.")
        print(f"[완료] 브라우저에서 열립니다: {URL}")
        webbrowser.open(URL)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

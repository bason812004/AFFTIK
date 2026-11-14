import os
import sys
import time
import asyncio
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

# CRITICAL FOR WINDOWS + PLAYWRIGHT:
# Always set WindowsProactorEventLoopPolicy so that Playwright subprocesses
# never throw NotImplementedError on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def _free_port_8000():
    """Terminates any stale backend process occupying port 8000 before starting."""
    try:
        import psutil
        my_pid = os.getpid()
        parent_pid = os.getppid()
        pids_to_kill = set()

        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == 8000 and conn.pid:
                if conn.pid not in (0, my_pid, parent_pid):
                    pids_to_kill.add(conn.pid)

        for pid in pids_to_kill:
            try:
                proc = psutil.Process(pid)
                for child in proc.children(recursive=True):
                    try:
                        child.kill()
                    except Exception:
                        pass
                proc.kill()
            except Exception:
                pass

        if pids_to_kill:
            time.sleep(0.5)
    except Exception:
        pass


import uvicorn

if __name__ == "__main__":
    _free_port_8000()
    if sys.platform == "win32":
        uvicorn.run(
            "backend.app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
            loop="asyncio"
        )
    else:
        uvicorn.run(
            "backend.app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=False
        )

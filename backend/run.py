import sys
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

import uvicorn

if __name__ == "__main__":
    if sys.platform == "win32":
        uvicorn.run(
            "backend.app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
            loop="asyncio.windows_events:ProactorEventLoop"
        )
    else:
        uvicorn.run(
            "backend.app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=False
        )

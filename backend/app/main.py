import os
import sys
import asyncio

# CRITICAL FOR WINDOWS + PLAYWRIGHT:
# Always ensure WindowsProactorEventLoopPolicy is active so Playwright subprocesses
# do not raise NotImplementedError on Windows.
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.database import init_db
from backend.app.config import DATA_DIR
from backend.app.services.browser_manager import browser_manager
from backend.app.routers import projects, gemini, flow, muse, ffmpeg_router, prompts, quality, settings, logs

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize SQLite DB and seed default prompts
    init_db()
    try:
        from backend.app.database import _get_raw_conn, get_setting
        from backend.app.services.pipeline_runner import pipeline_runner

        # Clean up any tasks left in 'running' state from an interrupted previous process
        conn = _get_raw_conn()
        conn.execute("""
            UPDATE automation_tasks
            SET status = 'paused',
                step_name = 'Đã tạm dừng (Chờ chạy tiếp)',
                message = 'Bấm Tiếp tục ngoài thẻ dự án hoặc đăng nhập tài khoản để chạy tiếp.'
            WHERE status = 'running' AND step_name NOT LIKE 'Đang chờ tới lượt%'
        """)
        conn.commit()
        conn.close()

        state = pipeline_runner.get_batch_state()
        if state.get("current_project_id") and not pipeline_runner.current_running_project_id:
            state["current_project_id"] = None
            pipeline_runner.save_batch_state(state)

        # Only auto-start batch worker if accounts are already logged in and not paused
        gemini_ok = get_setting("gemini_logged_in") == "true"
        if state.get("active") and not state.get("paused_by_user") and not state.get("paused_for_login") and gemini_ok:
            pipeline_runner.start_batch_worker()
    except Exception:
        pass
    yield
    # Shutdown: Cancel background tasks and cleanly close Playwright browser instances
    try:
        from backend.app.services.pipeline_runner import pipeline_runner
        if pipeline_runner._batch_task and not pipeline_runner._batch_task.done():
            pipeline_runner._batch_task.cancel()
        if pipeline_runner._watcher_task and not pipeline_runner._watcher_task.done():
            pipeline_runner._watcher_task.cancel()
    except Exception:
        pass
    if browser_manager.playwright is not None:
        try:
            await asyncio.wait_for(browser_manager.close_all(), timeout=3.0)
        except Exception:
            pass

app = FastAPI(
    title="TikTok Affiliate AI Studio PRO",
    description="Backend API for Local TikTok Video Automation Suite",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for local web interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount /data directory for direct local media access
os.makedirs(DATA_DIR, exist_ok=True)
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

# Register API routers
app.include_router(projects.router)
app.include_router(gemini.router)
app.include_router(flow.router)
app.include_router(muse.router)
app.include_router(ffmpeg_router.router)
app.include_router(prompts.router)
app.include_router(quality.router)
app.include_router(settings.router)
app.include_router(logs.router)

@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "app": "TikTok Affiliate AI Studio PRO",
        "version": "1.0.0"
    }

# Mount Frontend production build if available
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

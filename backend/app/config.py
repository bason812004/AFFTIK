import os
import shutil
from pathlib import Path
import imageio_ffmpeg

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
PROFILES_DIR = DATA_DIR / "browser_profiles"
GEMINI_PROFILE_DIR = PROFILES_DIR / "gemini"
FLOW_PROFILE_DIR = PROFILES_DIR / "flow"
MUSE_PROFILE_DIR = PROFILES_DIR / "muse"
DB_PATH = DATA_DIR / "studio.db"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
GEMINI_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
FLOW_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
MUSE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# Port & Network Settings (Local only)
HOST = "127.0.0.1"
PORT = 8000
FRONTEND_PORT = 5173

# FFmpeg Path Resolution
def get_ffmpeg_path() -> str:
    # 1. Custom environment variable
    custom_path = os.environ.get("FFMPEG_PATH")
    if custom_path and os.path.isfile(custom_path):
        return custom_path
    
    # 2. System PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
        
    # 3. imageio-ffmpeg bundled binary
    try:
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and os.path.isfile(bundled):
            return bundled
    except Exception:
        pass
        
    # 4. Check Playwright ffmpeg download directory if any
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        pw_ffmpeg_dir = Path(local_app_data) / "ms-playwright"
        if pw_ffmpeg_dir.exists():
            for exe_file in pw_ffmpeg_dir.glob("**/ffmpeg*.exe"):
                if exe_file.is_file():
                    return str(exe_file)
                    
    return "ffmpeg"

FFMPEG_PATH = get_ffmpeg_path()


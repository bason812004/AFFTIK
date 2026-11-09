@echo off
cd /d "%~dp0"
chcp 65001 >nul
title TIKTOK AFFILIATE AI STUDIO PRO
cls

echo =====================================================================
echo           TIKTOK AFFILIATE AI STUDIO PRO - KHỞI ĐỘNG HỆ THỐNG
echo =====================================================================
echo.

:: 1. Kiểm tra Python
echo [1/5] Kiểm tra môi trường Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LỖI] Không tìm thấy Python trên máy tính. Vui lòng cài đặt Python 3.10 trở lên!
    pause
    exit /b
)
python -c "import sys; print('   Python ' + sys.version.split()[0] + ' - OK')"

:: 2. Kiểm tra Node.js & npm
echo [2/5] Kiểm tra môi trường Node.js...
node -v >nul 2>&1
if %errorlevel% neq 0 (
    echo [LỖI] Không tìm thấy Node.js trên máy tính. Vui lòng cài đặt Node.js LTS!
    pause
    exit /b
)
node -e "console.log('   Node.js ' + process.version + ' - OK')"

:: 3. Kiểm tra môi trường ảo Python & Dependencies
echo [3/5] Kiểm tra thư viện Backend & FFmpeg...
if not exist "venv" (
    echo    Tạo môi trường ảo venv...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

:: Kiểm tra FFmpeg
python -c "from backend.app.config import FFMPEG_PATH; import os; print('   FFmpeg Engine: ' + ('OK (' + FFMPEG_PATH + ')' if os.path.exists(FFMPEG_PATH) or FFMPEG_PATH=='ffmpeg' else 'Chưa có'))"

:: 4. Kiểm tra Frontend
echo [4/5] Kiểm tra Frontend dependencies...
if not exist "frontend\node_modules" (
    echo    Cài đặt npm packages cho Frontend...
    cd frontend && npm install && cd ..
)

:: 5. Khởi động Backend và Frontend
echo [5/5] Khởi động máy chủ Local (127.0.0.1)...

:: Dọn dẹp tiến trình cũ nếu còn chạy ngầm trên port 8000, 5173, 9231, 9232
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :9231 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :9232 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1

:: Start Backend (FastAPI on 8000)
start "TikTok Affiliate Studio - Backend" /min cmd /c "if exist venv\Scripts\python.exe (venv\Scripts\python.exe backend/run.py) else (python backend/run.py)"

:: Start Frontend (Vite on 5173)
start "TikTok Affiliate Studio - Frontend" /min cmd /c "cd frontend && npm run dev"

echo.
echo =====================================================================
echo   HỆ THỐNG ĐÃ SẴN SÀNG!
echo   - Backend API:  http://127.0.0.1:8000
echo   - Giao diện Web: http://127.0.0.1:5173
echo =====================================================================
echo.
echo Đang mở trình duyệt giao diện...
timeout /t 3 >nul
start http://127.0.0.1:5173

echo.
echo Nhấn phím bất kỳ hoặc chạy stop.bat để đóng ứng dụng.
pause >nul


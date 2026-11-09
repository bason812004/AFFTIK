@echo off
cd /d "%~dp0"
chcp 65001 >nul
title TIKTOK AFFILIATE AI STUDIO PRO - DỪNG HỆ THỐNG
cls

echo =====================================================================
echo           TIKTOK AFFILIATE AI STUDIO PRO - DỪNG HỆ THỐNG
echo =====================================================================
echo.

echo Đang đóng các tiến trình Backend (8000) và Frontend (5173)...

:: Dừng tiến trình chạy trên cổng 8000 (Backend)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: Dừng tiến trình chạy trên cổng 5173 (Frontend)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo Đã dừng tất cả dịch vụ TikTok Affiliate AI Studio PRO an toàn.
echo.
pause


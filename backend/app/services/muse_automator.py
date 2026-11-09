import os
import json
import time
import shutil
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from backend.app.config import PROJECTS_DIR
from backend.app.database import _get_raw_conn, get_setting, set_setting
from backend.app.services.browser_manager import browser_manager
from backend.app.services.ffmpeg_service import ffmpeg_service

logger = logging.getLogger(__name__)

class MuseAutomator:
    """
    Automates video creation using Muse AI (muse.ai / musevideo.ai):
    - Multi-modal reference: Uses character/product image as reference input.
    - Automates prompt entry (Hook & CTA for 10s 60fps scenes).
    - Downloads completed video and standardizes with FFmpeg (1080x1920 @ 60 FPS).
    """

    def __init__(self):
        self.default_url = "https://muse.ai/create"

    def _get_muse_url(self) -> str:
        return get_setting("muse_url", self.default_url)

    async def generate_scene_video(
        self,
        project_id: str,
        scene_number: int,
        prompt: Optional[str] = None,
        character_image_path: Optional[str] = None,
        reference_image_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Automates creating a scene video (Scene 1 or Scene 2) on Muse AI.
        """
        async def log_fn(msg: str, pct: int):
            logger.info(f"[{project_id} | Muse Scene {scene_number}] {msg} ({pct}%)")
            if progress_callback:
                try:
                    res = progress_callback(msg, pct)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass

        await log_fn("Khởi động trình duyệt tự động kết nối Muse AI...", 10)

        # 1. Fetch project data from DB
        conn = _get_raw_conn()
        cur = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        proj = cur.fetchone()
        if not proj:
            conn.close()
            return {"success": False, "error": f"Không tìm thấy dự án {project_id}"}

        # Determine prompt
        cur = conn.execute("SELECT * FROM scripts WHERE project_id = ? AND is_selected = 1", (project_id,))
        selected_script = cur.fetchone()
        conn.close()

        scene_prompt = prompt or ""
        if not scene_prompt and selected_script:
            try:
                keys = selected_script.keys() if hasattr(selected_script, "keys") else []
                if scene_number == 1:
                    if "scene1_prompt_veo" in keys and selected_script["scene1_prompt_veo"]:
                        scene_prompt = selected_script["scene1_prompt_veo"]
                    elif "scene1_dialogue" in keys:
                        scene_prompt = selected_script["scene1_dialogue"] or ""
                else:
                    if "scene2_prompt_veo" in keys and selected_script["scene2_prompt_veo"]:
                        scene_prompt = selected_script["scene2_prompt_veo"]
                    elif "scene2_dialogue" in keys:
                        scene_prompt = selected_script["scene2_dialogue"] or ""
            except Exception:
                pass

        if not scene_prompt:
            pname = proj["name"] or "Sản phẩm tiện ích"
            scene_prompt = f"Video dọc 9:16 (1080x1920, 10s, 60fps). Giữ nguyên hình ảnh nhân vật và sản phẩm {pname}. Cử động mượt mà, ánh sáng điện ảnh, sắc nét."

        # Target file
        target_dir = PROJECTS_DIR / project_id / "videos"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"scene{scene_number}.mp4"

        # Reference image
        ref_image: Optional[Path] = None
        if reference_image_path and Path(reference_image_path).exists():
            ref_image = Path(reference_image_path)
        elif character_image_path and Path(character_image_path).exists():
            ref_image = Path(character_image_path)
        else:
            char_primary = PROJECTS_DIR / project_id / "character" / "character_primary.png"
            prod_orig = PROJECTS_DIR / project_id / "product" / "product_original.jpg"
            if char_primary.exists():
                ref_image = char_primary
            elif prod_orig.exists():
                ref_image = prod_orig

        # 2. Check Muse AI Login
        muse_url = self._get_muse_url()
        login_st = await browser_manager.check_muse_login(muse_url, force_open=False)
        if not login_st.get("logged_in"):
            await log_fn("Chưa đăng nhập Muse AI! Vui lòng đăng nhập trên cửa sổ Chrome...", 15)
            # Open headed Chrome to login page
            await browser_manager.check_muse_login(muse_url, force_open=True)
            return {
                "success": False,
                "needs_login": True,
                "message": "Chưa đăng nhập Muse AI. Cửa sổ Chrome đã được mở để bạn đăng nhập."
            }

        await log_fn("Đã kết nối tài khoản Muse AI. Đang chuẩn bị tạo video...", 25)

        # 3. Automation on Muse AI Page
        try:
            page = await browser_manager.get_muse_page(headed=False)
            current_url = (page.url or "").lower()
            if "muse.ai" not in current_url:
                await page.goto(muse_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

            await log_fn(f"Đang nhập Prompt Cảnh {scene_number} vào Muse AI...", 40)

            # Locate input prompt textarea or contenteditable element
            prompt_input = await page.query_selector(
                "textarea[placeholder*='prompt' i], textarea[placeholder*='describe' i], " +
                "input[placeholder*='prompt' i], div[contenteditable='true'], textarea"
            )

            if prompt_input:
                try:
                    await prompt_input.click()
                    await prompt_input.fill("")
                    await prompt_input.type(scene_prompt, delay=10)
                except Exception:
                    pass

            # Upload reference image if available
            if ref_image and ref_image.exists():
                await log_fn(f"Đang đính kèm ảnh tham chiếu Cảnh {scene_number}...", 50)
                file_input = await page.query_selector("input[type='file']")
                if file_input:
                    try:
                        await file_input.set_input_files(str(ref_image.resolve()))
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.warning(f"Failed to set reference image: {e}")

            # Locate and click Generate button
            await log_fn("Đang bấm nút Tạo Video trên Muse AI...", 60)
            gen_btn = await page.query_selector(
                "button:has-text('Generate'), button:has-text('Create'), button:has-text('Tạo'), " +
                "button[aria-label*='generate' i], button.btn-generate"
            )
            if gen_btn:
                try:
                    await gen_btn.click()
                except Exception:
                    pass

            await log_fn("Đang chờ Muse AI kết xuất video (Tiến trình Veo/Muse)...", 75)

            # Wait for video generation and download
            # Poll for video element or download button
            downloaded = False
            temp_down = PROJECTS_DIR / project_id / "videos" / f"temp_muse_s{scene_number}.mp4"

            # Check for immediate or completed video download
            for attempt in range(12):
                await asyncio.sleep(5)
                # Check if download link/button appeared
                dl_btn = await page.query_selector(
                    "a[download], button[aria-label*='download' i], button:has-text('Download'), a:has-text('Download')"
                )
                if dl_btn:
                    try:
                        async with page.expect_download(timeout=10000) as dl_info:
                            await dl_btn.click()
                        dl = await dl_info.value
                        await dl.save_as(str(temp_down))
                        downloaded = True
                        break
                    except Exception:
                        pass

                # Check if video src blob/mp4 is visible on page
                video_el = await page.query_selector("video[src]")
                if video_el:
                    v_src = await video_el.get_attribute("src")
                    if v_src and v_src.startswith("http"):
                        # Download directly
                        import urllib.request
                        try:
                            urllib.request.urlretrieve(v_src, str(temp_down))
                            if temp_down.exists() and temp_down.stat().st_size > 100000:
                                downloaded = True
                                break
                        except Exception:
                            pass

                await log_fn(f"Đang kết xuất video Muse AI... ({75 + attempt * 2}%)", 75 + attempt * 2)

            if downloaded and temp_down.exists() and temp_down.stat().st_size > 50000:
                await log_fn(f"Đã tải xong video từ Muse AI! Đang chuẩn hóa 1080x1920 @ 60 FPS...", 92)
                std_res = await ffmpeg_service.standardize_scene_video(
                    input_video_path=str(temp_down),
                    output_video_path=str(target_file),
                    target_width=1080,
                    target_height=1920,
                    target_fps=60
                )
                if not std_res.get("success"):
                    shutil.copyfile(str(temp_down), str(target_file))
                try:
                    temp_down.unlink(missing_ok=True)
                except Exception:
                    pass
                await log_fn(f"Hoàn thành xuất sắc video Cảnh {scene_number} chuẩn TikTok Affiliate!", 100)
                return {
                    "success": True,
                    "video_path": str(target_file),
                    "scene_number": scene_number,
                    "engine": "muse_ai"
                }

            # If generation is queued or taking longer on platform, guide user
            return {
                "success": False,
                "message": "Video đang được tạo trên Muse AI. Bạn có thể xem trên trình duyệt hoặc dán video tải về vào studio."
            }

        except Exception as e:
            logger.error(f"Error automating Muse AI scene {scene_number}: {e}")
            return {"success": False, "error": str(e)}


muse_automator = MuseAutomator()

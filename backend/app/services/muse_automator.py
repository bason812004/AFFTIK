import os
import json
import time
import shutil
import asyncio
import logging
import re
import unicodedata
import base64
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from backend.app.config import PROJECTS_DIR
from backend.app.database import _get_raw_conn, get_setting, set_setting
from backend.app.services.browser_manager import browser_manager
from backend.app.services.ffmpeg_service import ffmpeg_service

logger = logging.getLogger(__name__)

def _slugify(text: str) -> str:
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)

def _get_project_tokens(name: str) -> List[str]:
    slug = _slugify(name)
    tokens = [t for t in slug.split('-') if len(t) >= 2]
    # Add common aliases if applicable
    low = name.lower()
    if "bơm" in low and "ugreen" not in tokens:
        tokens.append("ugreen")
    if "muỗng" in low or "thìa" in low:
        tokens.extend(["muong", "inox", "inox304"])
    if "kệ" in low:
        tokens.extend(["ke", "tang"])
    if "hanbio" in low:
        tokens.extend(["ops", "hanbio"])
    return list(set(tokens))

class MuseAutomator:
    """
    Automates video creation using Muse AI (muse.ai / musevideo.ai):
    - Multi-modal reference: Uses character/product image as reference input.
    - Automates prompt entry (Hook & CTA for 10s 60fps scenes).
    - Detects and extracts blob video bytes directly from browser page context.
    - Standardizes with FFmpeg (1080x1920 @ 60 FPS).
    """

    def __init__(self):
        self.default_url = "https://muse.ai"

    def _get_muse_url(self) -> str:
        return get_setting("muse_url", self.default_url)

    async def download_blob_or_url(self, page: Page, url: str, target_file: Path) -> bool:
        """Downloads a video from either blob: URL (in page memory) or http/https URL."""
        target_file.parent.mkdir(parents=True, exist_ok=True)
        if url.startswith("blob:"):
            try:
                b64_data = await page.evaluate("""async (u) => {
                    const res = await fetch(u);
                    const b = await res.blob();
                    return new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result.split(',')[1]);
                        reader.onerror = reject;
                        reader.readAsDataURL(b);
                    });
                }""", url)
                raw_bytes = base64.b64decode(b64_data)
                target_file.write_bytes(raw_bytes)
                return target_file.exists() and len(raw_bytes) > 20000
            except Exception as e:
                logger.warning(f"Error fetching blob from page: {e}")
                return False
        elif url.startswith("http"):
            import urllib.request
            try:
                urllib.request.urlretrieve(url, str(target_file))
                return target_file.exists() and target_file.stat().st_size > 20000
            except Exception as e:
                logger.warning(f"Error downloading http video: {e}")
                return False
        return False

    async def scan_chat_for_project_videos(
        self,
        page: Page,
        project_name: str
    ) -> Dict[str, Any]:
        """
        Scans all messages in Muse AI chat for videos matching project_name.
        Returns dict with keys 'scene1' and 'scene2' containing { 'src': ..., 'aria': ..., 'text': ... }.
        """
        slug = _slugify(project_name)
        tokens = _get_project_tokens(project_name)

        try:
            await page.wait_for_selector('[data-message-role]', timeout=15000)
            await asyncio.sleep(1)
        except Exception:
            pass

        match_data = await page.evaluate("""async (args) => {
            const { slug, tokens, rawName } = args;
            const results = { scene1: null, scene2: null };

            // Find all messages
            const msgs = Array.from(document.querySelectorAll('[data-message-role="assistant"], [data-message-item="true"]'));
            if (!msgs.length) return results;

            for (let i = 0; i < msgs.length; i++) {
                const m = msgs[i];
                const text = (m.innerText || '').toLowerCase();
                const aria = (m.getAttribute('aria-label') || '').toLowerCase();
                const hasPres = m.getAttribute('data-message-has-presentation') === 'true';

                // Context from neighboring messages
                const prevText = i > 0 ? (msgs[i - 1].innerText || '').toLowerCase() : '';
                const nextText = i < msgs.length - 1 ? (msgs[i + 1].innerText || '').toLowerCase() : '';
                const combinedText = prevText + ' ' + text + ' ' + nextText;

                const textMatches = tokens.some(t => combinedText.includes(t)) || combinedText.includes(rawName.toLowerCase());
                const mHtml = (m.innerHTML || '').toLowerCase();
                const htmlMatches = tokens.some(t => mHtml.includes(t)) || (slug && mHtml.includes(slug));

                if (textMatches || htmlMatches) {
                    m.scrollIntoView({ behavior: 'instant', block: 'center' });
                    await new Promise(r => setTimeout(r, 300));

                    for (let t = 0; t < 6; t++) {
                        const wrappers = m.querySelectorAll('[data-hatch-video-wrapper="true"], [data-testid="hatch-chat-attachment-presentation-video"], video');
                        let foundWrapper = false;
                        for (const w of wrappers) {
                            const video = w.tagName.toLowerCase() === 'video' ? w : w.querySelector('video');
                            const src = w.getAttribute('data-hatch-video-src') || (video ? video.src : null);
                            const wAria = (w.getAttribute('aria-label') || '').toLowerCase();

                            if (src && (src.startsWith('blob:') || src.startsWith('http'))) {
                                foundWrapper = true;
                                const isS1 = wAria.includes('canh1') || wAria.includes('cảnh 1') || text.includes('cảnh 1');
                                const isS2 = wAria.includes('canh2') || wAria.includes('cảnh 2') || text.includes('cảnh 2');

                                if (isS1 && !results.scene1) {
                                    results.scene1 = { src, aria: wAria, text: text.substring(0, 100) };
                                }
                                if (isS2 && !results.scene2) {
                                    results.scene2 = { src, aria: wAria, text: text.substring(0, 100) };
                                }
                            }
                        }
                        if (foundWrapper) break;
                        await new Promise(r => setTimeout(r, 250));
                    }
                }
                if (results.scene1 && results.scene2) break;
            }

            // Fallback: If only 1 video was found or both were in a single assistant message
            if (!results.scene1 || !results.scene2) {
                for (let i = 0; i < msgs.length; i++) {
                    const m = msgs[i];
                    const combined = (m.innerText || '').toLowerCase();
                    if (tokens.some(t => combined.includes(t)) || combined.includes(rawName.toLowerCase())) {
                        m.scrollIntoView({ behavior: 'instant', block: 'center' });
                        await new Promise(r => setTimeout(r, 300));
                        const allV = Array.from(m.querySelectorAll('[data-hatch-video-wrapper="true"], video'));
                        if (allV.length >= 2) {
                            const v1 = allV[0].tagName.toLowerCase() === 'video' ? allV[0] : allV[0].querySelector('video');
                            const v2 = allV[1].tagName.toLowerCase() === 'video' ? allV[1] : allV[1].querySelector('video');
                            const s1 = allV[0].getAttribute('data-hatch-video-src') || (v1 ? v1.src : null);
                            const s2 = allV[1].getAttribute('data-hatch-video-src') || (v2 ? v2.src : null);
                            if (s1 && !results.scene1) results.scene1 = { src: s1, aria: allV[0].getAttribute('aria-label') || '' };
                            if (s2 && !results.scene2) results.scene2 = { src: s2, aria: allV[1].getAttribute('aria-label') || '' };
                        }
                    }
                }
            }

            // Restore scroll to bottom
            const scroller = Array.from(document.querySelectorAll('*')).find(e => e.scrollHeight > e.clientHeight + 50 && e.clientHeight > 200);
            if (scroller) scroller.scrollTop = scroller.scrollHeight;
            return results;
        }""", {"slug": slug, "tokens": tokens, "rawName": project_name})

        return match_data or {}

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
        Directly extracts and standardizes high-resolution video into 1080x1920 @ 60 FPS.
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

        pname = proj["name"] or "Sản phẩm tiện ích"

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
            scene_prompt = f"Video dọc 9:16 (1080x1920, 10s, 60fps). Giữ nguyên hình ảnh nhân vật và sản phẩm {pname}. Cử động mượt mà, sắc nét."

        # Target file
        target_dir = PROJECTS_DIR / project_id / "videos"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"scene{scene_number}.mp4"
        temp_down = target_dir / f"temp_muse_s{scene_number}.mp4"

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

            # Step 3a: Check if video for this scene already exists in chat!
            await log_fn("Kiểm tra video đã hoàn thành trên Muse AI...", 30)
            existing_videos = await self.scan_chat_for_project_videos(page, pname)
            target_scene_key = f"scene{scene_number}"
            existing_match = existing_videos.get(target_scene_key)

            if existing_match and existing_match.get("src"):
                await log_fn(f"Đã tìm thấy video Cảnh {scene_number} từ Muse AI! Đang trích xuất blob...", 50)
                if await self.download_blob_or_url(page, existing_match["src"], temp_down):
                    await log_fn(f"Đang chuẩn hóa video Cảnh {scene_number} (1080x1920 @ 60 FPS)...", 85)
                    await ffmpeg_service.standardize_scene_video(
                        input_video_path=str(temp_down),
                        output_video_path=str(target_file),
                        target_width=1080,
                        target_height=1920,
                        target_fps=60
                    )
                    temp_down.unlink(missing_ok=True)
                    await log_fn(f"Hoàn thành video Cảnh {scene_number} chuẩn TikTok Affiliate!", 100)
                    return {
                        "success": True,
                        "video_path": str(target_file),
                        "scene_number": scene_number,
                        "engine": "muse_ai"
                    }

            # Step 3b: Send prompt into Muse AI Chat
            await log_fn(f"Đang nhập Prompt Cảnh {scene_number} vào Muse AI...", 40)

            prompt_input = await page.query_selector(
                "textarea[placeholder*='Nhắn tin' i], textarea[aria-label*='Nhắn tin' i], " +
                "textarea[placeholder*='prompt' i], textarea[placeholder*='describe' i], " +
                "div[contenteditable='true'], textarea"
            )

            # Format formatted instruction for Muse AI
            formatted_prompt = f"[Cảnh {scene_number} - {pname} | 9:16, 10s, 60fps] {scene_prompt}"

            if prompt_input:
                try:
                    await prompt_input.click(timeout=3000)
                    await prompt_input.fill("")
                    await prompt_input.type(formatted_prompt, delay=1)
                except Exception:
                    pass

            # Upload reference image if available
            if ref_image and ref_image.exists():
                await log_fn(f"Đang đính kèm ảnh tham chiếu {pname}...", 50)
                file_input = await page.query_selector("input[type='file']")
                if file_input:
                    try:
                        await file_input.set_input_files(str(ref_image.resolve()), timeout=3000)
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.warning(f"Failed to set reference image: {e}")

            # Send prompt
            await log_fn("Đang gửi yêu cầu tạo video trên Muse AI...", 55)
            send_btn = await page.query_selector(
                "button[aria-label*='Gửi' i], button:has-text('Gửi'), button:has-text('Send'), " +
                "button:has-text('Generate'), button:has-text('Create'), button:has-text('Tạo'), " +
                "button[aria-label*='generate' i]"
            )
            if send_btn:
                try:
                    await send_btn.click(timeout=3000)
                except Exception:
                    await page.keyboard.press("Enter")
            else:
                await page.keyboard.press("Enter")

            await asyncio.sleep(2)

            # Step 3c: Wait for video generation (up to 90 seconds)
            await log_fn("Đang chờ Muse AI kết xuất video (Tiến trình Muse/Veo)...", 60)

            downloaded = False
            for attempt in range(30):
                await asyncio.sleep(3)
                elapsed = (attempt + 1) * 3
                current_pct = min(60 + int(attempt * 0.9), 90)

                # Keep bottom scrolled into view
                await page.evaluate("""() => {
                    const scroller = Array.from(document.querySelectorAll('*')).find(e => e.scrollHeight > e.clientHeight + 50 && e.clientHeight > 200);
                    if (scroller) scroller.scrollTop = scroller.scrollHeight;
                    window.scrollTo(0, document.body.scrollHeight);
                }""")

                # Look for newest presentation video wrapper
                newest_video = await page.evaluate("""async () => {
                    const wrappers = Array.from(document.querySelectorAll('[data-hatch-video-wrapper="true"], [data-testid="hatch-chat-attachment-presentation-video"], video'));
                    if (!wrappers.length) return null;
                    
                    // Check the last 3 wrappers
                    for (let i = wrappers.length - 1; i >= Math.max(0, wrappers.length - 3); i--) {
                        const w = wrappers[i];
                        w.scrollIntoView({ behavior: 'instant', block: 'center' });
                        await new Promise(r => setTimeout(r, 200));

                        const v = w.tagName.toLowerCase() === 'video' ? w : w.querySelector('video');
                        const src = w.getAttribute('data-hatch-video-src') || (v ? v.src : null);
                        const aria = w.getAttribute('aria-label') || '';

                        if (src && (src.startsWith('blob:') || src.startsWith('http'))) {
                            return { src, aria };
                        }
                    }
                    return null;
                }""")

                if newest_video and newest_video.get("src"):
                    await log_fn(f"Đã tạo xong video trên Muse AI! Đang tải về máy...", 90)
                    if await self.download_blob_or_url(page, newest_video["src"], temp_down):
                        downloaded = True
                        break

                await log_fn(f"Muse AI đang dựng video Cảnh {scene_number} ({elapsed}s)...", current_pct)

            if downloaded and temp_down.exists() and temp_down.stat().st_size > 20000:
                await log_fn(f"Đang chuẩn hóa video Cảnh {scene_number} (1080x1920 @ 60 FPS)...", 94)
                await ffmpeg_service.standardize_scene_video(
                    input_video_path=str(temp_down),
                    output_video_path=str(target_file),
                    target_width=1080,
                    target_height=1920,
                    target_fps=60
                )
                temp_down.unlink(missing_ok=True)
                await log_fn(f"Hoàn thành xuất sắc video Cảnh {scene_number} chuẩn TikTok Affiliate!", 100)
                return {
                    "success": True,
                    "video_path": str(target_file),
                    "scene_number": scene_number,
                    "engine": "muse_ai"
                }

            # If still not ready after timeout, check chat scan one final time
            final_scan = await self.scan_chat_for_project_videos(page, pname)
            if final_scan.get(target_scene_key) and final_scan[target_scene_key].get("src"):
                src = final_scan[target_scene_key]["src"]
                if await self.download_blob_or_url(page, src, temp_down):
                    await ffmpeg_service.standardize_scene_video(
                        input_video_path=str(temp_down),
                        output_video_path=str(target_file),
                        target_width=1080,
                        target_height=1920,
                        target_fps=60
                    )
                    temp_down.unlink(missing_ok=True)
                    return {
                        "success": True,
                        "video_path": str(target_file),
                        "scene_number": scene_number,
                        "engine": "muse_ai"
                    }

            return {
                "success": False,
                "message": f"Muse AI chưa trả video trực tiếp sau 90s. Hệ thống tự động chuyển sang bộ kết xuất video chuyển động 60 FPS để hoàn tất dự án."
            }

        except Exception as e:
            logger.error(f"Error automating Muse AI scene {scene_number}: {e}")
            return {"success": False, "error": str(e)}

    async def pull_project_videos(self, project_id: str) -> Dict[str, Any]:
        """
        Pulls Scene 1 & Scene 2 videos directly from Muse AI chat for this project,
        standardizes them to 1080x1920 @ 60 FPS, stitches them into the final video,
        and saves everything to the database.
        """
        conn = _get_raw_conn()
        proj = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        conn.close()
        if not proj:
            return {"success": False, "error": f"Không tìm thấy dự án {project_id}"}

        pname = proj["name"]
        page = await browser_manager.get_muse_page(headed=False)
        current_url = (page.url or "").lower()
        if "muse.ai" not in current_url:
            await page.goto(self._get_muse_url(), wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

        try:
            await page.wait_for_selector('textarea', timeout=8000)
            await asyncio.sleep(1.5)
        except Exception:
            pass

        videos = await self.scan_chat_for_project_videos(page, pname)
        if not videos.get("scene1") and not videos.get("scene2"):
            return {
                "success": False,
                "message": f"Không tìm thấy video nào của '{pname}' trong lịch sử chat Muse AI."
            }

        v_dir = PROJECTS_DIR / project_id / "videos"
        v_dir.mkdir(parents=True, exist_ok=True)
        s1_file = v_dir / "scene1.mp4"
        s2_file = v_dir / "scene2.mp4"

        s1_ok = False
        s2_ok = False

        if videos.get("scene1") and videos["scene1"].get("src"):
            temp_s1 = v_dir / "temp_pull_s1.mp4"
            if await self.download_blob_or_url(page, videos["scene1"]["src"], temp_s1):
                await ffmpeg_service.standardize_scene_video(
                    input_video_path=str(temp_s1),
                    output_video_path=str(s1_file),
                    target_width=1080,
                    target_height=1920,
                    target_fps=60
                )
                temp_s1.unlink(missing_ok=True)
                s1_ok = True

        if videos.get("scene2") and videos["scene2"].get("src"):
            temp_s2 = v_dir / "temp_pull_s2.mp4"
            if await self.download_blob_or_url(page, videos["scene2"]["src"], temp_s2):
                await ffmpeg_service.standardize_scene_video(
                    input_video_path=str(temp_s2),
                    output_video_path=str(s2_file),
                    target_width=1080,
                    target_height=1920,
                    target_fps=60
                )
                temp_s2.unlink(missing_ok=True)
                s2_ok = True

        # Check existing scene files on disk if only one was in chat
        if not s1_ok and s1_file.exists() and s1_file.stat().st_size > 50000:
            s1_ok = True
        if not s2_ok and s2_file.exists() and s2_file.stat().st_size > 50000:
            s2_ok = True

        # Update DB videos table
        conn = _get_raw_conn()
        if s1_ok:
            p1 = await ffmpeg_service.probe_video(str(s1_file))
            conn.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = 1", (project_id,))
            conn.execute("""
                INSERT INTO videos (id, project_id, scene_number, video_path, duration, resolution, fps, status)
                VALUES (?, ?, 1, ?, ?, ?, ?, 'ready')
            """, (f"v1_{project_id[:4]}", project_id, str(s1_file), p1.get("duration", 10.0), "1080x1920", 60.0))

        if s2_ok:
            p2 = await ffmpeg_service.probe_video(str(s2_file))
            conn.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = 2", (project_id,))
            conn.execute("""
                INSERT INTO videos (id, project_id, scene_number, video_path, duration, resolution, fps, status)
                VALUES (?, ?, 2, ?, ?, ?, ?, 'ready')
            """, (f"v2_{project_id[:4]}", project_id, str(s2_file), p2.get("duration", 10.0), "1080x1920", 60.0))

        conn.commit()

        # If both scenes are ready, stitch them!
        if s1_ok and s2_ok:
            slug = _slugify(pname)
            stitch_res = await ffmpeg_service.stitch_scenes(
                project_id=project_id,
                video1_path=str(s1_file),
                video2_path=str(s2_file),
                product_slug=slug
            )
            if stitch_res.get("success"):
                final_path = stitch_res["final_video_path"]
                fname = stitch_res["file_name"]
                dur = stitch_res.get("duration", 20.0)
                fsize = stitch_res.get("file_size", 0)

                conn.execute("DELETE FROM exports WHERE project_id = ?", (project_id,))
                conn.execute("""
                    INSERT INTO exports (id, project_id, final_video_path, file_name, duration, resolution, fps, file_size, audio_info)
                    VALUES (?, ?, ?, ?, ?, '1080x1920', 60.0, ?, 'AAC 44.1kHz Stereo (Muse AI)')
                """, (f"exp_{project_id[:4]}", project_id, final_path, fname, dur, fsize))
                conn.execute("UPDATE projects SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
                conn.commit()
                conn.close()

                return {
                    "success": True,
                    "s1_ok": True,
                    "s2_ok": True,
                    "stitched": True,
                    "final_video_path": final_path,
                    "final_video_url": stitch_res.get("url"),
                    "message": f"Đã lấy thành công video Cảnh 1 & Cảnh 2 từ Muse AI và ghép video hoàn chỉnh 60 FPS cho {pname}!"
                }

        conn.close()
        return {
            "success": True,
            "s1_ok": s1_ok,
            "s2_ok": s2_ok,
            "stitched": False,
            "message": f"Đã lấy được { 'Cảnh 1' if s1_ok else '' } { 'và Cảnh 2' if s2_ok else '' } từ Muse AI."
        }

    async def pull_all_available_videos(self) -> Dict[str, Any]:
        """Scans all projects in database and pulls any matching completed videos from Muse AI."""
        conn = _get_raw_conn()
        projects = conn.execute("SELECT id, name FROM projects").fetchall()
        conn.close()

        results = []
        for p in projects:
            p_id = p["id"]
            res = await self.pull_project_videos(p_id)
            if res.get("success") and (res.get("s1_ok") or res.get("s2_ok")):
                results.append({"project_id": p_id, "name": p["name"], "res": res})

        return {
            "success": True,
            "total_updated": len(results),
            "updated_projects": results
        }


muse_automator = MuseAutomator()

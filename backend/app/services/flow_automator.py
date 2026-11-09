import os
import re
import time
import shutil
import hashlib
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from playwright.async_api import Page, Download
from backend.app.services.browser_manager import browser_manager
from backend.app.config import PROJECTS_DIR

logger = logging.getLogger(__name__)


class FlowAutomator:
    def __init__(self):
        self.bm = browser_manager

    def _get_video_frame_signature(self, video_path: Path, timestamp_sec: float = 4.0) -> Optional[bytes]:
        """Extracts an 8x8 RGB raw frame (192 bytes) at timestamp_sec to detect duplicate tile downloads."""
        try:
            from backend.app.services.ffmpeg_service import ffmpeg_service
            ffmpeg_exe = ffmpeg_service.ffmpeg_bin or "ffmpeg"
            cmd = [
                ffmpeg_exe, "-y",
                "-ss", str(timestamp_sec),
                "-i", str(video_path),
                "-frames:v", "1",
                "-vf", "scale=8:8",
                "-f", "rawvideo",
                "-pix_fmt", "rgb24",
                "pipe:1"
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=8)
            if res.returncode == 0 and len(res.stdout) == 192:
                return res.stdout
        except Exception as e:
            logger.debug(f"Frame signature extract error: {e}")
        return None

    def _frames_are_identical(self, sig1: Optional[bytes], sig2: Optional[bytes], threshold: float = 3.5) -> bool:
        if not sig1 or not sig2 or len(sig1) != 192 or len(sig2) != 192:
            return False
        diff = sum(abs(a - b) for a, b in zip(sig1, sig2)) / 192.0
        return diff < threshold

    def _is_duplicate_of_existing_video(self, candidate_video: Path, project_id: str, scene_number: int) -> bool:
        """
        Returns True if candidate_video is identical to:
        1) The other scene video in the same project (e.g. Scene 2 downloading Scene 1's tile), OR
        2) Any scene video from a previous project (e.g. Scene 1 downloading an older project's tile).
        """
        cand_sig_4s = self._get_video_frame_signature(candidate_video, 4.0)
        cand_sig_1s = self._get_video_frame_signature(candidate_video, 1.0)
        if not cand_sig_4s:
            return False

        # 1. Check other scene in the same project
        other_scene = 1 if scene_number == 2 else 2
        other_path = PROJECTS_DIR / project_id / "videos" / f"scene{other_scene}.mp4"
        if other_path.exists() and other_path.stat().st_size > 100000:
            other_sig_4s = self._get_video_frame_signature(other_path, 4.0)
            if self._frames_are_identical(cand_sig_4s, other_sig_4s, threshold=2.8):
                logger.warning(f"Candidate video for {project_id} scene {scene_number} matches scene {other_scene}! Rejecting stale tile.")
                return True

        # 2. Check recent other projects' videos
        try:
            for proj_dir in PROJECTS_DIR.iterdir():
                if not proj_dir.is_dir() or proj_dir.name == project_id:
                    continue
                v_dir = proj_dir / "videos"
                if not v_dir.exists():
                    continue
                for old_mp4 in v_dir.glob("scene*.mp4"):
                    if old_mp4.stat().st_size < 100000:
                        continue
                    old_sig_4s = self._get_video_frame_signature(old_mp4, 4.0)
                    if self._frames_are_identical(cand_sig_4s, old_sig_4s, threshold=4.0):
                        old_sig_1s = self._get_video_frame_signature(old_mp4, 1.0)
                        if self._frames_are_identical(cand_sig_1s, old_sig_1s, threshold=4.0):
                            logger.warning(f"Candidate video for {project_id} matches old project {proj_dir.name}/{old_mp4.name}! Rejecting stale tile.")
                            return True
        except Exception as e:
            logger.debug(f"Duplicate check warning: {e}")

        return False

    async def _count_more_option_buttons(self, page: Page) -> int:
        try:
            btns = await page.query_selector_all(
                "button[aria-label='Tuỳ chọn khác'], button[aria-label='Lựa chọn khác'], "
                "button[aria-label='More options'], button[aria-label*='khác'], "
                "button:has(mat-icon:has-text('more_vert'))"
            )
            return len(btns)
        except Exception:
            return 0

    async def _handle_credit_approval_dialog(self, page: Page, log_fn: Optional[Any] = None) -> bool:
        """
        Auto-approves Google Flow's generation cost prompt:
        'Bạn có muốn tôi bắt đầu tạo 1 video này với chi phí là 15 tín dụng không?'
        Flow displays this as div.option-row inside flow-permission-message.
        Prioritizes 'Luôn phê duyệt' (Always approve) so Flow never asks again.
        """
        try:
            # 1. Fast Playwright locator for 'Luôn phê duyệt'
            always_loc = page.locator(".option-row", has_text="Luôn phê duyệt").last
            if await always_loc.count() > 0 and await always_loc.is_visible():
                await always_loc.click(timeout=2500)
                if log_fn:
                    await log_fn("Đã tự động chọn 'Luôn phê duyệt' (15 tín dụng) trên Google Flow!", 68)
                logger.info("[Flow Approval] Clicked .option-row 'Luôn phê duyệt'")
                await asyncio.sleep(1.0)
                return True
        except Exception:
            pass

        try:
            # 2. Fast Playwright locator for 'Phê duyệt'
            approve_loc = page.locator(".option-row", has_text="Phê duyệt").last
            if await approve_loc.count() > 0 and await approve_loc.is_visible():
                await approve_loc.click(timeout=2500)
                if log_fn:
                    await log_fn("Đã tự động chọn 'Phê duyệt' (15 tín dụng) trên Google Flow!", 68)
                logger.info("[Flow Approval] Clicked .option-row 'Phê duyệt'")
                await asyncio.sleep(1.0)
                return True
        except Exception:
            pass

        try:
            # 3. Direct DOM query & click for option-row / option-label / button
            clicked = await page.evaluate('''() => {
                const rows = Array.from(document.querySelectorAll(
                    ".option-row, .option-label, flow-permission-message div, .choice-container div, button"
                ));
                for (const r of rows) {
                    const txt = (r.innerText || '').trim();
                    if (txt.includes('Luôn phê duyệt') || txt.includes('Always approve')) {
                        if (typeof r.click === 'function') { r.click(); return 'Luôn phê duyệt'; }
                    }
                }
                for (const r of rows) {
                    const txt = (r.innerText || '').trim();
                    if (txt.includes('Phê duyệt') || txt.includes('Approve')) {
                        if (typeof r.click === 'function') { r.click(); return 'Phê duyệt'; }
                    }
                }
                return null;
            }''')
            if clicked:
                if log_fn:
                    await log_fn(f"Đã tự động phê duyệt trên Google Flow: '{clicked}'", 68)
                logger.info(f"[Flow Approval] DOM clicked: '{clicked}'")
                await asyncio.sleep(1.0)
                return True
        except Exception:
            pass

        selectors = [
            "button:has-text('Luôn phê duyệt')",
            "[role='button']:has-text('Luôn phê duyệt')",
            "button:has-text('Always approve')",
            "[role='button']:has-text('Always approve')",
            "button:has-text('Phê duyệt')",
            "[role='button']:has-text('Phê duyệt')",
            "button:has-text('Approve')",
            "[role='button']:has-text('Approve')",
        ]
        for sel in selectors:
            try:
                elements = await page.query_selector_all(sel)
                for btn in elements:
                    if await btn.is_visible():
                        txt = (await btn.inner_text()).strip()
                        try:
                            await btn.click(timeout=3000)
                        except Exception:
                            await btn.evaluate("b => b.click()")
                        if log_fn:
                            await log_fn(f"Đã tự động phê duyệt trên Google Flow: '{txt}'", 68)
                        logger.info(f"[Flow Approval] Clicked approval button: '{txt}'")
                        await asyncio.sleep(1.0)
                        return True
            except Exception as e:
                logger.debug(f"Approval check error on {sel}: {e}")
        return False

    async def _check_out_of_credits(self, page: Page) -> Optional[str]:
        """
        Inspects the active Google Flow page for out-of-credit notifications, error toasts,
        or a remaining credit balance below 15 credits.
        """
        try:
            info = await page.evaluate("""() => {
                const bodyText = (document.body && document.body.innerText) ? document.body.innerText : '';
                const alerts = Array.from(document.querySelectorAll(
                    'mat-snack-bar-container, [role="alert"], [role="status"], .cdk-overlay-container, .error-message, .warning-message'
                )).map(el => el.innerText || '').join(' | ');
                return { bodyText, alerts };
            }""")
            combined = f"{info.get('alerts', '')}\n{info.get('bodyText', '')}".lower()

            exhausted_phrases = [
                "không đủ tín dụng",
                "hết tín dụng",
                "không còn tín dụng",
                "đã dùng hết tín dụng",
                "0 tín dụng",
                "not enough credits",
                "insufficient credits",
                "out of credits",
                "no credits left",
                "no credits remaining",
                "0 credits",
                "nạp thêm tín dụng",
                "mua thêm tín dụng",
                "get more credits",
                "top up credits",
                "đã đạt giới hạn tạo",
                "vượt quá giới hạn tín dụng",
                "credit limit reached",
                "daily limit reached",
                "quota exceeded"
            ]
            for phrase in exhausted_phrases:
                if phrase in combined:
                    return f"Phát hiện thông báo trên Google Flow: '{phrase}'"

            # Check explicit remaining credit balance patterns (ignoring 'tốn 15 tín dụng' / 'costs 15 credits')
            lines = [ln.strip() for ln in combined.splitlines() if ln.strip()]
            for ln in lines:
                if "tốn" in ln or "cost" in ln or "will use" in ln or "sẽ dùng" in ln:
                    continue
                m = re.search(r'(?:còn lại|số dư|remaining|balance)\s*[:\-]?\s*(\d{1,2})\s*(?:tín dụng|credits)', ln)
                if not m:
                    m = re.search(r'^(\d{1,2})\s*(?:tín dụng|credits)(?:\s*còn lại)?$', ln)
                if m:
                    rem = int(m.group(1))
                    if rem < 15:
                        return f"Số dư tín dụng Google Flow chỉ còn {rem} tín dụng (cần tối thiểu 15 tín dụng)"
        except Exception as e:
            logger.debug(f"Credit check error: {e}")
        return None

    async def _handle_out_of_credits(self, log_fn: Any, reason: str) -> Dict[str, Any]:
        msg = (
            f"⚠️ TÀI KHOẢN GOOGLE FLOW ĐÃ HẾT TÍN DỤNG ({reason})! "
            f"Hệ thống đang tự động đăng xuất và mở cửa sổ chọn tài khoản Google mới — vui lòng đăng nhập tài khoản khác để tiếp tục."
        )
        await log_fn(msg, 65)
        try:
            await self.bm.clear_flow_session(open_login=True)
        except Exception as e:
            logger.warning(f"Auto switch account on out-of-credits error: {e}")
        return {
            "success": False,
            "out_of_credits": True,
            "needs_login": True,
            "error": msg,
            "message": msg
        }

    async def _download_newest_tile_from_video_tab(
        self,
        page: Page,
        videos_dir: Path,
        target_video_file: Path,
        scene_number: int,
        log_fn: Any,
        project_id: Optional[str] = None,
        max_candidates: int = 1
    ) -> bool:
        """
        Ensures the 'Video' filter tab in the left sidebar is active,
        verifies no video is currently mid-render (showing %),
        hovers over the newest video tile at (250, 250), opens 'Tuỳ chọn khác' -> 'Tải xuống' -> '720p Kích thước gốc',
        verifies the downloaded video is not a stale tile from an earlier project/scene,
        and standardizes it to 1080x1920 @ 60fps.
        """
        try:
            vid_filter = await page.query_selector(
                "button.mat-mdc-list-item:has-text('Cảnh'), "
                "button.mat-mdc-list-item:has-text('movie'), "
                "button.mat-mdc-list-item:has-text('Video'), "
                "button:has-text('Cảnh')"
            )
            if vid_filter and await vid_filter.is_visible():
                await vid_filter.click()
                await asyncio.sleep(1.2)

            # Never click 'Tuỳ chọn khác' if a tile is still rendering (showing %)
            body_txt = await page.evaluate("() => document.body.innerText")
            pct_matches = re.findall(r'(?<!\d)(\d{1,2})\s*%', body_txt)
            if pct_matches:
                logger.info(f"Flow still rendering ({pct_matches[0]}%), skipping premature download.")
                return False

            await page.mouse.move(250, 250)
            await asyncio.sleep(1.0)

            more_btns = await page.query_selector_all(
                "button[aria-label='Tuỳ chọn khác'], button[aria-label='Lựa chọn khác'], "
                "button[aria-label='More options'], button[aria-label*='khác'], "
                "button:has(mat-icon:has-text('more_vert'))"
            )
            # Filter out top navbar buttons (y < 80) and project-level menu buttons
            usable_btns = []
            for b in more_btns:
                try:
                    aria = (await b.get_attribute("aria-label") or "").lower()
                    if "dự án" in aria or "project" in aria:
                        continue
                    box = await b.bounding_box()
                    if box and box["width"] > 0 and box["height"] > 0 and box["y"] >= 75 and box["x"] < 900:
                        usable_btns.append((box, b))
                except Exception:
                    continue

            if not usable_btns:
                return False

            # Pick the top-left-most video card buttons in the active content area
            usable_btns.sort(key=lambda item: round(item[0]["y"] / 50) * 1000 + item[0]["x"])

            for cand_idx, (_, best_btn) in enumerate(usable_btns[:max_candidates]):
                await log_fn(f"Đã phát hiện thẻ Video Cảnh {scene_number} hoàn tất trên Flow! Đang mở menu tải xuống...", 86)
                await best_btn.evaluate("b => b.click()")
                await asyncio.sleep(1.0)

                dl_item = await page.query_selector(
                    ".cdk-overlay-container [role='menuitem']:has-text('Tải xuống'), "
                    ".cdk-overlay-container button:has-text('Tải xuống'), "
                    ".cdk-overlay-container [role='menuitem']:has-text('Download'), "
                    ".cdk-overlay-container button:has-text('Download')"
                )
                if not dl_item:
                    await page.keyboard.press("Escape")
                    continue

                temp_down = videos_dir / f"temp_flow_{scene_number}_{int(time.time())}_{cand_idx}.mp4"
                downloaded_ok = False

                # First click 'Tải xuống' (either triggers download directly or opens resolution submenu)
                try:
                    async with page.expect_download(timeout=3500) as dl_info:
                        await dl_item.click()
                    dl = await dl_info.value
                    await dl.save_as(str(temp_down))
                    downloaded_ok = True
                except Exception:
                    # Resolution submenu opened ('270p', '720p Kích thước gốc', '1080p', '4K')
                    await asyncio.sleep(0.6)
                    res_btn = await page.query_selector(
                        ".cdk-overlay-container [role='menuitem']:has-text('720p'), "
                        ".cdk-overlay-container button:has-text('720p'), "
                        ".cdk-overlay-container [role='menuitem']:has-text('Gốc'), "
                        ".cdk-overlay-container [role='menuitem']:has-text('Original')"
                    )
                    if res_btn:
                        async with page.expect_download(timeout=25000) as dl_info2:
                            await res_btn.click()
                        dl2 = await dl_info2.value
                        await dl2.save_as(str(temp_down))
                        downloaded_ok = True

                if downloaded_ok and temp_down.exists() and temp_down.stat().st_size > 100000:
                    # Check if Google Flow served a stale video from an older project or previous scene
                    proj_id = project_id or videos_dir.parent.name
                    if self._is_duplicate_of_existing_video(temp_down, proj_id, scene_number):
                        await log_fn(f"Video #{cand_idx + 1} là video đã tải ở cảnh khác, đang kiểm tra thẻ tiếp theo...", 80)
                        try:
                            temp_down.unlink(missing_ok=True)
                        except Exception:
                            pass
                        continue

                    await log_fn(f"Đã tải xong video gốc từ Flow. Đang chuẩn hóa 1080x1920 @ 60 FPS...", 92)
                    from backend.app.services.ffmpeg_service import ffmpeg_service
                    std_res = await ffmpeg_service.standardize_scene_video(
                        input_video_path=str(temp_down),
                        output_video_path=str(target_video_file),
                        target_width=1080,
                        target_height=1920,
                        target_fps=60
                    )
                    if not std_res.get("success"):
                        shutil.copyfile(str(temp_down), str(target_video_file))
                    try:
                        temp_down.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return target_video_file.exists() and target_video_file.stat().st_size > 100000
        except Exception as e:
            logger.warning(f"Tile menu download error: {e}")
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
        return False

    async def _get_first_video_tile_signature(self, page: Page) -> str:
        """Returns a signature of the top-left video tile in the Video tab to detect when a new video finishes."""
        try:
            await page.mouse.move(250, 250)
            await asyncio.sleep(0.5)
            sig = await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button[aria-label]'))
                    .map(b => b.getAttribute('aria-label') || '')
                    .filter(a => a && !['Trang chủ', 'Các lựa chọn khác cho dự án', 'Tìm kiếm', 'Các lựa chọn lọc và sắp xếp',
                        'Trình đơn thêm nội dung nghe nhìn', 'Trợ giúp về sản phẩm', 'Cài đặt', 'Lựa chọn khác',
                        'Thông tin về tài khoản', 'Tạo bộ sưu tập', 'Bật/tắt thư viện', 'Yêu thích', 'Sử dụng lại câu lệnh',
                        'Tuỳ chọn khác', 'Thêm thành phần vào ô nhập câu lệnh', 'Điều kiện kích hoạt cài đặt', 'Bắt đầu tạo'].includes(a)
                        && !a.startsWith('Tài khoản Google'));
                return btns.join('|');
            }""")
            return sig or ""
        except Exception:
            return ""

    async def generate_scene_video(
        self,
        project_id: str,
        scene_number: int,
        prompt: str,
        character_image_path: Optional[str] = None,
        reference_image_path: Optional[str] = None,
        flow_url: str = "https://flow.google.com/",
        mode: str = "auto",
        on_log: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Automates Google Flow to generate a 10s 9:16 video from the reference image for Scene 1 or Scene 2.
        Saves downloaded video into data/projects/{project_id}/videos/scene{scene_number}.mp4
        """
        ref_image = character_image_path or reference_image_path

        async def log(msg: str, percent: int = 0):
            if on_log:
                await on_log(msg, percent)
            logger.info(f"[Flow Video Scene {scene_number}] {msg}")

        await log(f"Khởi động trình duyệt Google Flow cho Cảnh {scene_number}...", 10)
        page: Page = await self.bm.get_flow_page(headed=False)

        target_flow = "https://flow.google.com/"
        await log(f"Truy cập Google Flow Studio ({target_flow})...", 18)
        try:
            from urllib.parse import urlparse
            current_url = page.url or ""
            parsed = urlparse(current_url)
            host = (parsed.netloc or "").lower()
            if "accounts.google.com" in host or ("flow.google.com" not in host and "labs.google" not in host):
                await page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(3.0)
        except Exception as e:
            await log(f"Lưu ý truy cập: {str(e)}. Tiếp tục kiểm tra phiên đăng nhập...", 20)

        # Check login
        login_check = await self.bm.check_flow_login(target_flow)
        if not login_check["logged_in"]:
            await log("⚠️ Chưa đăng nhập tài khoản Google trên Flow. Đang mở nút Đăng nhập chính thức trên cửa sổ Chrome...", 25)
            try:
                await self.bm._trigger_flow_sign_in_on_page(page)
            except Exception:
                pass
            return {
                "success": False,
                "needs_login": True,
                "message": "Cần đăng nhập tài khoản Google trên cửa sổ Chrome (Google Flow). Hệ thống đã lưu phiên làm việc và sẽ tự động chạy tiếp ngay sau khi bạn đăng nhập thành công!",
                "error": "Cần đăng nhập tài khoản Google để sử dụng Google Flow."
            }

        videos_dir = PROJECTS_DIR / project_id / "videos"
        videos_dir.mkdir(parents=True, exist_ok=True)
        target_video_file = videos_dir / f"scene{scene_number}.mp4"

        # Navigate into a Flow project workspace if currently on the dashboard/landing page
        if "/project/" not in page.url:
            # First check if another tab in the same context already has /project/ open!
            for p in page.context.pages:
                if "/project/" in (p.url or "") and not p.is_closed():
                    page = p
                    self.bm.flow_page = p
                    break

        if "/project/" not in page.url:
            await log("Đang mở không gian làm việc dự án Google Flow...", 25)
            try:
                proj_trigger = None
                for sel in [
                    "a[href*='/project/']",
                    "button:has-text('Start Creating')",
                    "button:has-text('Dự án mới')",
                    "a[aria-label*='Mở dự án']",
                    "button:has-text('New project')"
                ]:
                    try:
                        proj_trigger = await page.wait_for_selector(sel, timeout=3000)
                        if proj_trigger and await proj_trigger.is_visible():
                            break
                    except Exception:
                        continue
                if proj_trigger:
                    href = await proj_trigger.get_attribute("href")
                    if href and "/project/" in href:
                        if not href.startswith("http"):
                            href = f"https://flow.google.com{href}"
                        await page.goto(href, wait_until="domcontentloaded", timeout=45000)
                    else:
                        await proj_trigger.click()
                    await asyncio.sleep(3.5)
                    # Check again if a new tab was opened by target="_blank"
                    for p in page.context.pages:
                        if "/project/" in (p.url or "") and not p.is_closed():
                            page = p
                            self.bm.flow_page = p
                            break
            except Exception as e_nav:
                logger.warning(f"Navigate to project error: {e_nav}")

        # Dismiss any stray overlays or welcome modals
        try:
            start_modal_btn = await page.query_selector("button:has-text('Bắt đầu')")
            if start_modal_btn and await start_modal_btn.is_visible():
                await start_modal_btn.click(timeout=2000)
                await asyncio.sleep(0.5)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.4)
        except Exception:
            pass

        # 1. Switch left sidebar to 'Cảnh' / 'Video' filter so we can clearly see and download finished videos
        try:
            vid_filter = await page.query_selector(
                "button.mat-mdc-list-item:has-text('Cảnh'), "
                "button.mat-mdc-list-item:has-text('movie'), "
                "button.mat-mdc-list-item:has-text('Video'), "
                "button:has-text('Cảnh')"
            )
            if vid_filter and await vid_filter.is_visible():
                await vid_filter.click()
                await asyncio.sleep(1.2)
        except Exception:
            pass

        initial_tile_sig = await self._get_first_video_tile_signature(page)

        # 2. Clear any old ingredient chips in flow-ingredient-bar so stale images from previous projects are never reused
        try:
            old_chips = await page.query_selector_all(
                "flow-ingredient-bar button.chip-container, "
                "flow-ingredient-chip button.chip-container"
            )
            for chip_btn in old_chips:
                if await chip_btn.is_visible():
                    try:
                        await chip_btn.click(timeout=2000)
                    except Exception:
                        await chip_btn.evaluate("b => b.click()")
                    await asyncio.sleep(0.4)
        except Exception:
            pass

        # Check if account is already out of credits before starting
        early_credit_err = await self._check_out_of_credits(page)
        if early_credit_err:
            return await self._handle_out_of_credits(log, early_credit_err)

        # 3. Configure Settings: Video · Thành phần · 9:16 · Omni 1.1 Flash · 720p · 10 giây · x1 (15 tín dụng)
        await log("Đang thiết lập cài đặt Google Flow (Video · Thành phần · 9:16 · Omni 1.1 Flash · 720p · 10 giây · x1)...", 32)
        try:
            settings_btn = await page.query_selector(
                "button[aria-label*='Điều kiện kích hoạt cài đặt'], "
                "button[aria-label*='Cài đặt'], "
                "button[aria-label*='Settings'], "
                "button:has-text('tune'), "
                "button:has(mat-icon:has-text('tune'))"
            )
            if settings_btn and await settings_btn.is_visible():
                try:
                    await settings_btn.click(timeout=2500)
                except Exception:
                    await settings_btn.evaluate("b => b.click()")
                await asyncio.sleep(0.8)

                # Configure button toggles: Video, Thành phần, 9:16, 720p, 10 giây, x1
                for toggle_label in ["Video", "Thành phần", "9:16", "720p", "10 giây", "x1"]:
                    try:
                        toggle_elem = await page.query_selector(f".cdk-overlay-container mat-button-toggle:has-text('{toggle_label}')")
                        if toggle_elem and await toggle_elem.is_visible():
                            cls = await toggle_elem.get_attribute("class") or ""
                            aria_checked = await toggle_elem.get_attribute("aria-checked")
                            if "mat-button-toggle-checked" not in cls and aria_checked != "true":
                                btn = await toggle_elem.query_selector("button") or toggle_elem
                                try:
                                    await btn.click(timeout=2000)
                                except Exception:
                                    await btn.evaluate("b => b.click()")
                                await asyncio.sleep(0.25)
                        else:
                            btn = await page.query_selector(f".cdk-overlay-container button:has-text('{toggle_label}')")
                            if btn and await btn.is_visible():
                                aria_pressed = await btn.get_attribute("aria-pressed")
                                if aria_pressed != "true":
                                    try:
                                        await btn.click(timeout=2000)
                                    except Exception:
                                        await btn.evaluate("b => b.click()")
                                    await asyncio.sleep(0.25)
                    except Exception as e_tog:
                        logger.debug(f"Toggle {toggle_label} error: {e_tog}")

                # Configure model dropdown: Omni 1.1 Flash
                try:
                    model_trigger = await page.query_selector(
                        ".cdk-overlay-container mat-select, "
                        ".cdk-overlay-container [role='combobox'], "
                        ".cdk-overlay-container .mat-mdc-select-trigger, "
                        ".cdk-overlay-container div[role='button']:has-text('Omni'), "
                        ".cdk-overlay-container button:has-text('Omni'), "
                        ".cdk-overlay-container button:has-text('Veo')"
                    )
                    if model_trigger and await model_trigger.is_visible():
                        cur_text = (await model_trigger.inner_text()).strip()
                        if "Omni 1.1 Flash" not in cur_text:
                            try:
                                await model_trigger.click(timeout=2000)
                            except Exception:
                                await model_trigger.evaluate("b => b.click()")
                            await asyncio.sleep(0.5)
                            omni_opt = await page.query_selector(
                                "mat-option:has-text('Omni 1.1 Flash'), "
                                "[role='option']:has-text('Omni 1.1 Flash'), "
                                ".cdk-overlay-container mat-option:has-text('Omni 1.1 Flash')"
                            )
                            if omni_opt and await omni_opt.is_visible():
                                try:
                                    await omni_opt.click(timeout=2000)
                                except Exception:
                                    await omni_opt.evaluate("b => b.click()")
                                await asyncio.sleep(0.3)
                except Exception as e_model:
                    logger.warning(f"Flow model dropdown selection error: {e_model}")

                # Check if settings overlay warns about insufficient credits
                settings_credit_err = await self._check_out_of_credits(page)
                if settings_credit_err:
                    await page.keyboard.press("Escape")
                    return await self._handle_out_of_credits(log, settings_credit_err)

                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                # Verify overlay closed
                for _ in range(2):
                    still_open = await page.query_selector(".cdk-overlay-container mat-button-toggle:has-text('Video')")
                    if still_open and await still_open.is_visible():
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.4)
                await log("Đã cấu hình Google Flow: Video · Thành phần · 9:16 · Omni 1.1 Flash · 720p · 10 giây · x1 (15 tín dụng)", 38)
        except Exception as e_cfg:
            logger.warning(f"Flow video settings configuration warning: {e_cfg}")
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass

        # 4. Upload Reference Image & Attach to Prompt ('Thêm vào câu lệnh')
        if ref_image and os.path.exists(ref_image):
            try:
                ref_path_obj = Path(ref_image)
                img_hash = hashlib.md5(ref_path_obj.read_bytes()).hexdigest()[:6]
                unique_ref_name = f"ref_{project_id}_{img_hash}.png"
                unique_ref_path = ref_path_obj.parent / unique_ref_name
                if not unique_ref_path.exists() or unique_ref_path.stat().st_size != ref_path_obj.stat().st_size:
                    shutil.copy2(str(ref_path_obj), str(unique_ref_path))

                await log(f"Đang đồng bộ ảnh nhân vật AI ({unique_ref_name}) và gắn vào câu lệnh tạo video Cảnh {scene_number}...", 42)

                # Always clear any existing ingredient chip first so we guarantee the exact current project image is attached
                old_chips = await page.query_selector_all(
                    "flow-ingredient-bar button.chip-container, "
                    "flow-ingredient-chip button.chip-container"
                )
                for chip_btn in old_chips:
                    if await chip_btn.is_visible():
                        try:
                            await chip_btn.click(timeout=2000)
                        except Exception:
                            await chip_btn.evaluate("b => b.click()")
                        await asyncio.sleep(0.4)

                async def ensure_drawer_open() -> bool:
                    search_inp = await page.query_selector(".cdk-overlay-container input[placeholder*='Tìm kiếm thành phần']")
                    if search_inp and await search_inp.is_visible():
                        return True
                    add_btn = await page.query_selector(
                        "button.add-menu-trigger, "
                        "button[aria-label*='Thêm thành phần'], "
                        "button[aria-label*='Add ingredient'], "
                        "button[aria-label*='thành phần']"
                    )
                    if add_btn and await add_btn.is_visible():
                        try:
                            await add_btn.click(timeout=2500)
                        except Exception:
                            await add_btn.evaluate("b => b.click()")
                        await asyncio.sleep(1.5)
                    search_inp = await page.query_selector(".cdk-overlay-container input[placeholder*='Tìm kiếm thành phần']")
                    return bool(search_inp and await search_inp.is_visible())

                await ensure_drawer_open()

                # Check if this exact unique_ref_name is already in the drawer
                exact_asset_sel = f".cdk-overlay-container button.asset-item:has-text('{unique_ref_name}')"
                asset_item = await page.query_selector(exact_asset_sel)

                if not asset_item or not await asset_item.is_visible():
                    # Must upload the current project's reference image
                    upload_btn = await page.query_selector(
                        ".cdk-overlay-container button.sidebar-upload-btn, "
                        ".cdk-overlay-container button:has-text('Tải nội dung nghe nhìn lên'), "
                        ".cdk-overlay-container button:has-text('Tải nội dung'), "
                        "button.sidebar-upload-btn"
                    )
                    if upload_btn and await upload_btn.is_visible():
                        await log(f"Đang tải ảnh nhân vật AI mới ({unique_ref_name}) lên Google Flow...", 46)
                        async with page.expect_file_chooser(timeout=12000) as fc_info:
                            try:
                                await upload_btn.click(timeout=2500)
                            except Exception:
                                await upload_btn.evaluate("b => b.click()")
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(str(unique_ref_path))

                        for _ in range(30):
                            await asyncio.sleep(1.0)
                            asset_item = await page.query_selector(exact_asset_sel)
                            uploading = await page.query_selector(".cdk-overlay-container button.asset-item:has-text('Đang tải lên')")
                            if asset_item and not uploading:
                                break
                        await asyncio.sleep(1.2)

                # Attach the exact unique_ref_name asset and verify flow-ingredient-chip is present
                chip_attached = False
                for attempt in range(3):
                    chip_check = await page.query_selector("flow-ingredient-chip button.chip-container")
                    if chip_check and await chip_check.is_visible():
                        chip_attached = True
                        break

                    await ensure_drawer_open()
                    asset_item = await page.query_selector(exact_asset_sel)
                    if asset_item and await asset_item.is_visible():
                        cls_str = (await asset_item.get_attribute("class") or "")
                        # If not active yet, clicking it either directly attaches it or makes it active
                        if "asset-item-active" not in cls_str or attempt > 0:
                            try:
                                await asset_item.click(timeout=2500)
                            except Exception:
                                await asset_item.evaluate("b => b.click()")
                            await asyncio.sleep(1.2)

                        chip_check = await page.query_selector("flow-ingredient-chip button.chip-container")
                        if chip_check and await chip_check.is_visible():
                            chip_attached = True
                            break

                        # If drawer is still open and 'Thêm vào câu lệnh' button is visible, click it
                        attach_btn = await page.query_selector(
                            ".cdk-overlay-container button.detail-add-to-prompt-btn, "
                            ".cdk-overlay-container button:has-text('Thêm vào câu lệnh'), "
                            ".cdk-overlay-container button:has-text('Add to prompt')"
                        )
                        if attach_btn and await attach_btn.is_visible():
                            try:
                                await attach_btn.click(timeout=2500)
                            except Exception:
                                await attach_btn.evaluate("b => b.click()")
                            await asyncio.sleep(1.2)

                        chip_check = await page.query_selector("flow-ingredient-chip button.chip-container")
                        if chip_check and await chip_check.is_visible():
                            chip_attached = True
                            break

                if chip_attached:
                    await log(f"Đã gắn chính xác ảnh nhân vật AI ({unique_ref_name}) vào câu lệnh Cảnh {scene_number}!", 54)
                else:
                    logger.warning(f"Could not confirm flow-ingredient-chip for {unique_ref_name}")

                # Close drawer if still open so it doesn't block prompt bar
                for _ in range(3):
                    drawer_still_open = await page.query_selector(
                        ".cdk-overlay-container input[placeholder*='Tìm kiếm thành phần'], "
                        ".cdk-overlay-container button.detail-add-to-prompt-btn"
                    )
                    if drawer_still_open and await drawer_still_open.is_visible():
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.4)
                    else:
                        break
            except Exception as e_up:
                logger.warning(f"Flow image upload/attach error: {e_up}")
                try:
                    await page.keyboard.press("Escape")
                except Exception:
                    pass

        # Copy prompt to Windows clipboard for convenience
        try:
            import subprocess
            cmd = f"Set-Clipboard -Value @'\n{prompt}\n'@"
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=False, timeout=5)
        except Exception:
            pass

        # 5. Fill Prompt into Flow ProseMirror editor
        await log(f"Điền Prompt + Lời thoại cho Cảnh {scene_number}...", 58)
        input_selectors = [
            "flow-rich-text-editor div[contenteditable='true']",
            "div.prosemirror-editor div[contenteditable='true']",
            "div[contenteditable='true'][aria-placeholder*='Bạn muốn tạo']",
            "div[contenteditable='true'][data-placeholder*='Bạn muốn tạo']",
            "div[role='textbox'][aria-label*='Bạn muốn tạo']",
            "div[role='textbox']",
            "div[contenteditable='true']",
            "textarea:not([name='g-recaptcha-response'])"
        ]

        prompt_elem = None
        for sel in input_selectors:
            try:
                elements = await page.query_selector_all(sel)
                for elem in elements:
                    if await elem.is_visible():
                        placeholder = (await elem.get_attribute("placeholder") or "").lower()
                        aria_label = (await elem.get_attribute("aria-label") or "").lower()
                        if "tìm kiếm" in placeholder or "tìm kiếm" in aria_label:
                            continue
                        prompt_elem = elem
                        break
                if prompt_elem:
                    break
            except Exception:
                continue

        if prompt_elem:
            try:
                await prompt_elem.click(timeout=3000)
                await asyncio.sleep(0.2)
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await page.keyboard.insert_text(prompt)
                await asyncio.sleep(0.8)
                cur_text = (await prompt_elem.inner_text()).strip()
                if not cur_text:
                    await prompt_elem.evaluate("""(el, text) => {
                        el.innerText = text;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }""", prompt)
                    await asyncio.sleep(0.5)
            except Exception as fill_ex:
                logger.warning(f"Direct click/fill on Flow input: {fill_ex}")

        if mode == "semi":
            await log(f"Chế độ BÁN TỰ ĐỘNG: Ảnh và Prompt Cảnh {scene_number} đã gắn sẵn trên Flow. Vui lòng bấm Tạo video.", 65)
            return {
                "success": True,
                "waiting_user": True,
                "message": f"Nội dung Cảnh {scene_number} đã sẵn sàng trên Flow."
            }

        # 6. Record completed video count in Cảnh / Video tab BEFORE submitting
        try:
            vid_filter = await page.query_selector(
                "button.mat-mdc-list-item:has-text('Cảnh'), "
                "button.mat-mdc-list-item:has-text('movie'), "
                "button.mat-mdc-list-item:has-text('Video'), "
                "button:has-text('Cảnh')"
            )
            if vid_filter and await vid_filter.is_visible():
                await vid_filter.click()
                await asyncio.sleep(1.0)
        except Exception:
            pass
        before_more_count = await self._count_more_option_buttons(page)

        # Click 'Bắt đầu tạo' ('arrow_forward')
        await log(f"Gửi yêu cầu tạo Video Cảnh {scene_number} từ ảnh tham chiếu trên Google Flow...", 65)
        create_btn_selectors = [
            "button[aria-label*='Bắt đầu tạo']",
            "button[aria-label*='Tạo']",
            "button[aria-label*='Generate']",
            "button:has(mat-icon:has-text('arrow_forward'))",
            "button:has-text('arrow_forward')",
            "button:has(mat-icon:has-text('send'))",
            "button:has-text('send')"
        ]
        clicked_submit = False
        found_disabled_submit = False
        for _ in range(12):
            for btn_sel in create_btn_selectors:
                try:
                    elements = await page.query_selector_all(btn_sel)
                    for btn in elements:
                        if await btn.is_visible():
                            aria_dis = await btn.get_attribute("aria-disabled")
                            is_en = await btn.is_enabled()
                            if is_en and aria_dis != "true":
                                try:
                                    await btn.click(timeout=2500)
                                except Exception:
                                    await btn.evaluate("b => b.click()")
                                clicked_submit = True
                                break
                            else:
                                found_disabled_submit = True
                    if clicked_submit:
                        break
                except Exception:
                    continue
            if clicked_submit:
                break
            await asyncio.sleep(0.5)

        await asyncio.sleep(2.0)
        post_submit_credit_err = await self._check_out_of_credits(page)
        if post_submit_credit_err:
            return await self._handle_out_of_credits(log, post_submit_credit_err)

        if not clicked_submit:
            try:
                if prompt_elem:
                    await prompt_elem.press("Enter")
                else:
                    await page.keyboard.press("Enter")
                await asyncio.sleep(2.0)
                retry_credit_err = await self._check_out_of_credits(page)
                if retry_credit_err:
                    return await self._handle_out_of_credits(log, retry_credit_err)
            except Exception:
                pass

        # Auto-approve Google Flow's generation cost prompt:
        # "Bạn có muốn tôi bắt đầu tạo 1 video này với chi phí là 15 tín dụng không?"
        # Buttons: "Luôn phê duyệt", "Phê duyệt"
        await log(f"Đang kiểm tra xác nhận chi phí tạo video trên Google Flow...", 67)
        for _ in range(12):
            approved = await self._handle_credit_approval_dialog(page, log)
            if approved:
                break
            await asyncio.sleep(0.5)

        # Ensure left sidebar stays on 'Cảnh' / 'Video' tab so live % progress & finished video tile appear immediately
        try:
            vid_filter = await page.query_selector(
                "button.mat-mdc-list-item:has-text('Cảnh'), "
                "button.mat-mdc-list-item:has-text('movie'), "
                "button.mat-mdc-list-item:has-text('Video'), "
                "button:has-text('Cảnh')"
            )
            if vid_filter and await vid_filter.is_visible():
                await vid_filter.click(timeout=2500)
                await asyncio.sleep(1.0)
        except Exception:
            pass

        await log(f"Google Flow đang render Video Cảnh {scene_number} (từ ảnh tham chiếu)...", 70)

        download_saved = False
        start_t = asyncio.get_event_loop().time()
        start_wall_time = time.time()
        timeout = 210
        saw_progress_pct = False
        downloads_dir = Path(os.environ.get("USERPROFILE", "C:/Users/LENOVO")) / "Downloads"

        while asyncio.get_event_loop().time() - start_t < timeout:
            await asyncio.sleep(4)
            elapsed = int(asyncio.get_event_loop().time() - start_t)

            # Auto-approve if Flow asks for credit confirmation during rendering
            await self._handle_credit_approval_dialog(page, log)

            # Check if Google Flow displayed an out-of-credits or quota error toast
            loop_credit_err = await self._check_out_of_credits(page)
            if loop_credit_err:
                return await self._handle_out_of_credits(log, loop_credit_err)

            # A. Check if user or Chrome downloaded a new .mp4 into Downloads during this run
            if downloads_dir.exists() and not download_saved:
                candidate_files = []
                for f in downloads_dir.glob("*.mp4"):
                    try:
                        if f.stat().st_mtime >= start_wall_time and f.stat().st_size > 400000:
                            candidate_files.append((f.stat().st_mtime, f))
                    except Exception:
                        pass
                if candidate_files:
                    candidate_files.sort(key=lambda x: x[0], reverse=True)
                    newest_file = candidate_files[0][1]
                    if not self._is_duplicate_of_existing_video(newest_file, project_id, scene_number):
                        await log(f"Phát hiện video mới tải về ({newest_file.name}). Đang chuẩn hóa 1080x1920 @ 60 FPS...", 90)
                        from backend.app.services.ffmpeg_service import ffmpeg_service
                        temp_raw = videos_dir / f"raw_flow_{scene_number}.mp4"
                        shutil.copyfile(str(newest_file), str(temp_raw))
                        std_res = await ffmpeg_service.standardize_scene_video(
                            input_video_path=str(temp_raw),
                            output_video_path=str(target_video_file),
                            target_width=1080,
                            target_height=1920,
                            target_fps=60
                        )
                        try:
                            temp_raw.unlink(missing_ok=True)
                        except Exception:
                            pass
                        if std_res.get("success"):
                            download_saved = True
                            break

            # B. Check live percentage progress on Google Flow page (e.g. '4%', '21%', '68%')
            try:
                body_txt = await page.evaluate("() => document.body.innerText")
                pct_matches = re.findall(r'(?<!\d)(\d{1,2})\s*%', body_txt)
                if pct_matches:
                    saw_progress_pct = True
                    pct_val = int(pct_matches[0])
                    mapped_pct = min(88, 70 + int(pct_val * 0.18))
                    await log(f"Google Flow đang tạo Video Cảnh {scene_number} ({pct_val}%)...", mapped_pct)
                    continue
            except Exception:
                pass

            # C. Only download once progress % has disappeared AND a new video tile is ready!
            after_more_count = await self._count_more_option_buttons(page)
            if (saw_progress_pct and elapsed >= 18) or (after_more_count > before_more_count and elapsed >= 20) or elapsed >= 75:
                await asyncio.sleep(2.0)
                ok = await self._download_newest_tile_from_video_tab(
                    page=page,
                    videos_dir=videos_dir,
                    target_video_file=target_video_file,
                    scene_number=scene_number,
                    log_fn=log,
                    project_id=project_id
                )
                if ok:
                    download_saved = True
                    break
                # Reset saw_progress_pct so we wait before retrying if tile was still finalizing
                saw_progress_pct = False

        if not download_saved:
            return {
                "success": False,
                "manual_required": True,
                "message": f"Google Flow đang hoàn tất Video Cảnh {scene_number}. Bạn có thể bấm 'Lấy Video từ Flow' hoặc dán video sau khi hoàn tất."
            }

        await log(f"Đã tạo và tải thành công Video Cảnh {scene_number} chuẩn 1080x1920 60fps từ Google Flow!", 100)
        return {
            "success": True,
            "video_path": str(target_video_file),
            "file_name": os.path.basename(target_video_file),
            "scene_number": scene_number
        }

    async def pull_latest_video_from_flow(self, project_id: str, scene_number: int) -> Optional[str]:
        """
        Directly downloads the newest video tile from the active Google Flow project workspace.
        """
        try:
            page = await self.bm.get_flow_page(headed=False)
            if "flow.google.com" not in page.url and "labs.google" not in page.url:
                await page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(3)
            if "/project/" not in page.url:
                existing_proj = await page.query_selector("a[href*='/project/'], a[aria-label*='Mở dự án']")
                if existing_proj:
                    await existing_proj.click()
                    await asyncio.sleep(4)
            videos_dir = PROJECTS_DIR / project_id / "videos"
            videos_dir.mkdir(parents=True, exist_ok=True)
            target_video_file = videos_dir / f"scene{scene_number}.mp4"
            async def dummy_log(msg: str, pct: int = 0):
                logger.info(f"[Flow Pull Scene {scene_number}] {msg}")
            ok = await self._download_newest_tile_from_video_tab(
                page=page,
                videos_dir=videos_dir,
                target_video_file=target_video_file,
                scene_number=scene_number,
                log_fn=dummy_log,
                project_id=project_id,
                max_candidates=2
            )
            if ok and target_video_file.exists():
                return str(target_video_file)
        except Exception as e:
            logger.warning(f"pull_latest_video_from_flow error: {e}")
        return None


flow_automator = FlowAutomator()

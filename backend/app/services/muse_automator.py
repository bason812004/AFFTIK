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
from typing import Dict, Any, Optional, Callable, List, Tuple
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from backend.app.config import PROJECTS_DIR
from backend.app.database import _get_raw_conn, get_setting, set_setting
from backend.app.services.browser_manager import browser_manager
from backend.app.services.ffmpeg_service import ffmpeg_service

logger = logging.getLogger(__name__)

def _slugify(text: str) -> str:
    text = (text or "").replace('đ', 'd').replace('Đ', 'd')
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', ' ', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)

ALL_PRODUCT_SPECS = {
    'máy bơm lốp xe hơi': ['may-bom', 'bom-lop', 'ugreen', 'may bom', 'bom lop'],
    'phân bón trung vi lượng': ['phan-bon', 'trung-vi-luong', 'phan bon', 'trung vi luong', 'combi'],
    'phục hồi vàng lá, thối rễ': ['vang-la', 'thoi-re', 'vang la', 'thoi re', 'phuc-hoi', 'phuc hoi'],
    'ngũ cốc gà đá': ['ngu-coc', 'ga-da', 'ngu coc', 'ga da'],
    'muỗng cơm inox 304': ['muong-com', 'inox304', 'inox-304', 'muong com', 'inox 304'],
    'kệ 3 tầng': ['ke-3-tang', 'ke 3 tang'],
    'nhựa đường dầu hắc dạng lỏng': ['nhua-duong', 'dau-hac', 'nhua duong', 'dau hac'],
    'hạt cho mèo': ['hat-cho-meo', 'hat cho meo', 'thuc-an-meo'],
    'ops Hanbio': ['ops-hanbio', 'hanbio', 'ops hanbio'],
    'túi đeo chéo': ['tui-deo', 'deo-cheo', 'tui-deo-cheo', 'tui deo']
}

STOP_WORDS = {
    'cho', 'dang', 'tang', 're', 'la', 'vi', 'cao', 'tot', 'moi', 'cua', 
    'nhieu', 'loai', 'hop', 'chai', 'goi', 'san', 'pham', 'chinh', 'hang', 
    'tien', 'ich', 'chuan', 'sieu', 'dep', 'chat', 'luong', 'ngay', 'hom', 
    'nay', 'them', 'giam', 'gia', 'khuyen', 'mai', 'kem'
}

def _get_distinctive_phrases(product_name: str) -> List[str]:
    slug = _slugify(product_name)
    parts = [p for p in slug.split('-') if p and len(p) >= 2]
    
    phrases = set()
    if slug:
        phrases.add(slug)
    
    # 2-word combinations
    for i in range(len(parts) - 1):
        w1, w2 = parts[i], parts[i+1]
        if w1 not in STOP_WORDS or w2 not in STOP_WORDS:
            phrases.add(f"{w1}-{w2}")
            phrases.add(f"{w1} {w2}")
            
    # 3-word combinations
    for i in range(len(parts) - 2):
        w1, w2, w3 = parts[i], parts[i+1], parts[i+2]
        phrases.add(f"{w1}-{w2}-{w3}")
        phrases.add(f"{w1} {w2} {w3}")
        
    # Long distinctive single tokens (>= 5 chars and not stop word)
    for p in parts:
        if len(p) >= 5 and p not in STOP_WORDS:
            phrases.add(p)
            
    # Product aliases
    low = (product_name or "").lower()
    for cat_name, sigs in ALL_PRODUCT_SPECS.items():
        cat_slug = _slugify(cat_name)
        if cat_slug in slug or slug in cat_slug or cat_name.lower() in low or low in cat_name.lower():
            phrases.update(sigs)
            
    return [p for p in phrases if len(p) >= 3 and p not in STOP_WORDS]

def _get_excluded_signatures(target_name: str) -> List[str]:
    target_slug = _slugify(target_name)
    excluded = set()
    
    for prod_name, spec_sigs in ALL_PRODUCT_SPECS.items():
        p_slug = _slugify(prod_name)
        if p_slug != target_slug and prod_name.lower() not in target_name.lower() and target_name.lower() not in prod_name.lower():
            excluded.update(spec_sigs)
            excluded.add(p_slug)
            
    try:
        conn = _get_raw_conn()
        rows = conn.execute("SELECT name FROM projects").fetchall()
        conn.close()
        for r in rows:
            p_name = r["name"] or ""
            p_slug = _slugify(p_name)
            if p_slug and p_slug != target_slug and p_name.lower() not in target_name.lower() and target_name.lower() not in p_name.lower():
                excluded.add(p_slug)
                for chunk in p_slug.split('-'):
                    if len(chunk) >= 4 and chunk not in STOP_WORDS:
                        excluded.add(chunk)
    except Exception:
        pass
        
    return [s for s in excluded if len(s) >= 3 and s not in STOP_WORDS]

class MuseAutomator:
    """
    Automates video creation using Muse AI (muse.ai / musevideo.ai):
    - Multi-modal reference: Uses character/product image as reference input.
    - Automates prompt entry (Hook & CTA for 10s 60fps scenes).
    - Detects and extracts blob video bytes directly from browser page context.
    - Standardizes with FFmpeg (1080x1920 @ 60 FPS).
    - Strict product signature matching to guarantee zero cross-product contamination.
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
        Scans messages in Muse AI chat strictly for videos matching project_name.
        Uses positive distinctive phrases and negative signature exclusions to prevent cross-contamination.
        Returns dict with keys 'scene1' and 'scene2' containing { 'src': ..., 'aria': ..., 'text': ... }.
        """
        target_slug = _slugify(project_name)
        pos_sigs = _get_distinctive_phrases(project_name)
        neg_sigs = _get_excluded_signatures(project_name)

        try:
            await page.wait_for_selector('[data-message-role]', timeout=15000)
            await asyncio.sleep(1)
        except Exception:
            pass

        match_data = await page.evaluate("""async (args) => {
            const { targetSlug, posSigs, negSigs } = args;
            const results = { scene1: null, scene2: null };

            // Find all assistant messages
            const msgs = Array.from(document.querySelectorAll('[data-message-role="assistant"], [data-message-item="true"]'));
            if (!msgs.length) return results;

            // Scan backwards from newest to oldest
            for (let i = msgs.length - 1; i >= 0; i--) {
                const m = msgs[i];
                const text = (m.innerText || '').toLowerCase();

                // Fast negative check: if message text explicitly belongs to another product, skip
                if (negSigs.some(sig => text.includes(sig))) continue;

                const wrappers = Array.from(m.querySelectorAll('[data-hatch-video-wrapper="true"], [data-testid="hatch-chat-attachment-presentation-video"], video'));
                if (!wrappers.length) continue;

                m.scrollIntoView({ behavior: 'instant', block: 'center' });
                await new Promise(r => setTimeout(r, 200));

                for (let wIdx = 0; wIdx < wrappers.length; wIdx++) {
                    const w = wrappers[wIdx];
                    const wAria = (w.getAttribute('aria-label') || '').toLowerCase();
                    const video = w.tagName.toLowerCase() === 'video' ? w : w.querySelector('video');
                    const src = w.getAttribute('data-hatch-video-src') || (video ? video.src : null);

                    if (!src || (!src.startsWith('blob:') && !src.startsWith('http'))) continue;

                    // Reject if aria-label matches ANY negative product signature
                    if (negSigs.some(sig => wAria.includes(sig))) continue;

                    // Positive check: aria-label OR surrounding message text must match positive signatures
                    const hasPosAria = posSigs.some(sig => wAria.includes(sig));
                    const hasPosText = posSigs.some(sig => text.includes(sig));
                    if (!hasPosAria && !hasPosText) continue;

                    // Scene verification
                    let isS1 = wAria.includes('canh1') || wAria.includes('canh-1') || wAria.includes('cảnh 1');
                    let isS2 = wAria.includes('canh2') || wAria.includes('canh-2') || wAria.includes('cảnh 2');

                    // If message has 2 video wrappers, wrapper 0 is Scene 1, wrapper 1 is Scene 2
                    if (!isS1 && !isS2) {
                        if (wrappers.length >= 2) {
                            if (wIdx === 0) isS1 = true;
                            if (wIdx === 1) isS2 = true;
                        } else if (text.includes('cảnh 1')) {
                            isS1 = true;
                        } else if (text.includes('cảnh 2')) {
                            isS2 = true;
                        }
                    }

                    if (isS1 && !results.scene1) {
                        results.scene1 = { src, aria: wAria, text: text.substring(0, 100) };
                    }
                    if (isS2 && !results.scene2) {
                        results.scene2 = { src, aria: wAria, text: text.substring(0, 100) };
                    }
                }

                if (results.scene1 && results.scene2) break;
            }

            // Restore scroll to bottom
            const scroller = Array.from(document.querySelectorAll('*')).find(e => e.scrollHeight > e.clientHeight + 50 && e.clientHeight > 200);
            if (scroller) scroller.scrollTop = scroller.scrollHeight;
            return results;
        }""", {"targetSlug": target_slug, "posSigs": pos_sigs, "negSigs": neg_sigs})

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

            pos_sigs = _get_distinctive_phrases(pname)
            neg_sigs = _get_excluded_signatures(pname)
            target_slug = _slugify(pname)

            # Record state before prompting to guarantee we only capture new generations
            initial_counts = await page.evaluate("""() => {
                const msgs = document.querySelectorAll('[data-message-role="assistant"], [data-message-item="true"]');
                const wrappers = document.querySelectorAll('[data-hatch-video-wrapper="true"], [data-testid="hatch-chat-attachment-presentation-video"], video');
                return {
                    msgCount: msgs.length,
                    wrapperCount: wrappers.length
                };
            }""")
            init_msg_count = initial_counts.get("msgCount", 0)
            init_wrapper_count = initial_counts.get("wrapperCount", 0)

            # Input Prompt into Muse AI Chat
            await log_fn(f"Đang chuẩn bị Prompt Cảnh {scene_number} cho '{pname}' vào Muse AI...", 40)

            prompt_input = await page.query_selector(
                "textarea[placeholder*='Nhắn tin' i], textarea[aria-label*='Nhắn tin' i], " +
                "textarea[placeholder*='prompt' i], textarea[placeholder*='describe' i], " +
                "div[contenteditable='true'], textarea"
            )

            formatted_prompt = f"[Cảnh {scene_number} - {pname} | 9:16, 10s, 60fps] {scene_prompt}"
            # Normalize whitespace/newlines to single line so Playwright doesn't prematurely trigger Enter
            formatted_prompt = " ".join(formatted_prompt.split())

            if prompt_input:
                try:
                    await prompt_input.click(timeout=3000)
                    await prompt_input.fill("")
                    await prompt_input.fill(formatted_prompt)
                    await asyncio.sleep(0.5)
                except Exception as ex_type:
                    logger.warning(f"Error typing prompt: {ex_type}")

            # Upload reference image if available
            if ref_image and ref_image.exists():
                await log_fn(f"Đang đính kèm ảnh tham chiếu {pname}...", 48)
                attached = False
                attach_btn = await page.query_selector("button[aria-label='Đính kèm file']")
                if attach_btn:
                    try:
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await attach_btn.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(str(ref_image.resolve()))
                        attached = True
                    except Exception as e_fc:
                        logger.debug(f"File chooser event error: {e_fc}")

                if not attached:
                    file_input = await page.query_selector("input[type='file']")
                    if file_input:
                        try:
                            await file_input.set_input_files(str(ref_image.resolve()), timeout=3000)
                            attached = True
                        except Exception as e:
                            logger.warning(f"Failed to set reference image: {e}")

                # Wait for attachment preview chip to confirm upload
                for _ in range(15):
                    has_chip = await page.query_selector("button[aria-label='Gỡ file đính kèm']")
                    if has_chip:
                        break
                    await asyncio.sleep(0.4)

            # Send prompt
            await log_fn("Đang gửi yêu cầu tạo video trên Muse AI...", 55)
            send_btn = await page.query_selector("button[aria-label='Gửi']")
            if send_btn:
                try:
                    await send_btn.click(timeout=3000)
                except Exception:
                    if prompt_input:
                        await prompt_input.press("Enter")
            elif prompt_input:
                await prompt_input.press("Enter")

            await asyncio.sleep(2)

            # Step 3c: Wait for video generation (up to 300 seconds)
            await log_fn(f"Đang chờ Muse AI kết xuất video Cảnh {scene_number} (chuẩn 9:16 60 FPS)...", 60)

            downloaded = False
            for attempt in range(100):
                await asyncio.sleep(3)
                elapsed = (attempt + 1) * 3
                current_pct = min(60 + int(attempt * 0.35), 94)

                # Keep bottom scrolled into view
                await page.evaluate("""() => {
                    const scroller = Array.from(document.querySelectorAll('*')).find(e => e.scrollHeight > e.clientHeight + 50 && e.clientHeight > 200);
                    if (scroller) scroller.scrollTop = scroller.scrollHeight;
                    window.scrollTo(0, document.body.scrollHeight);
                }""")

                # Check if Muse is actively generating
                is_muse_busy = await page.evaluate("""() => {
                    const stopBtn = document.querySelector("button[aria-label='Dừng']");
                    const runningEl = Array.from(document.querySelectorAll('*')).find(e => (e.innerText || '').includes('Đang chạy:') || (e.innerText || '').includes('Đang tạo video'));
                    return Boolean(stopBtn || runningEl);
                }""")
                if is_muse_busy:
                    await log_fn(f"Muse AI đang tạo video Cảnh {scene_number} cho '{pname}' ({elapsed}s)...", current_pct)
                else:
                    await log_fn(f"Muse AI đang dựng video Cảnh {scene_number} cho '{pname}' ({elapsed}s)...", current_pct)

                # Look for newly generated video matching this scene and product
                newest_video = await page.evaluate("""async (args) => {
                    const { initMsgCount, sceneNum, posSigs, negSigs } = args;
                    const msgs = Array.from(document.querySelectorAll('[data-message-role="assistant"], [data-message-item="true"]'));
                    if (!msgs.length) return null;

                    // Scan backwards from newest to oldest
                    for (let i = msgs.length - 1; i >= 0; i--) {
                        const m = msgs[i];
                        const text = (m.innerText || '').toLowerCase();

                        // Fast negative check on message text
                        if (negSigs.some(sig => text.includes(sig))) continue;

                        const wrappers = Array.from(m.querySelectorAll('[data-hatch-video-wrapper="true"], [data-testid="hatch-chat-attachment-presentation-video"], video'));
                        if (!wrappers.length) continue;

                        for (let wIdx = 0; wIdx < wrappers.length; wIdx++) {
                            const w = wrappers[wIdx];
                            const wAria = (w.getAttribute('aria-label') || '').toLowerCase();
                            const video = w.tagName.toLowerCase() === 'video' ? w : w.querySelector('video');
                            const src = w.getAttribute('data-hatch-video-src') || (video ? video.src : null);
                            if (!src || (!src.startsWith('blob:') && !src.startsWith('http'))) continue;

                            // Reject if aria-label matches ANY negative product signature
                            if (negSigs.some(sig => wAria.includes(sig))) continue;

                            // Match verification: must either be in a newly created assistant message (i >= initMsgCount)
                            // OR strictly match positive signatures in aria-label or text
                            const hasPosAria = posSigs.some(sig => wAria.includes(sig));
                            const hasPosText = posSigs.some(sig => text.includes(sig));
                            const isNewMessage = i >= initMsgCount;

                            if (!hasPosAria && !hasPosText && !isNewMessage) continue;

                            // Scene verification
                            let isTargetScene = false;
                            const sKey = `canh${sceneNum}`;
                            const sKeyDash = `canh-${sceneNum}`;
                            const sKeyText = `cảnh ${sceneNum}`;

                            if (wAria.includes(sKey) || wAria.includes(sKeyDash) || text.includes(sKeyText)) {
                                isTargetScene = true;
                            } else if (wrappers.length >= 2) {
                                if (sceneNum === 1 && wIdx === 0) isTargetScene = true;
                                if (sceneNum === 2 && wIdx === 1) isTargetScene = true;
                            } else if (isNewMessage) {
                                const otherKey = sceneNum === 1 ? 'canh2' : 'canh1';
                                const otherText = sceneNum === 1 ? 'cảnh 2' : 'cảnh 1';
                                if (!wAria.includes(otherKey) && !text.includes(otherText)) {
                                    isTargetScene = true;
                                }
                            }

                            if (isTargetScene) {
                                return { src, aria: wAria, text: text.substring(0, 100), msgIndex: i, wrapperIndex: wIdx };
                            }
                        }
                    }
                    return null;
                }""", {
                    "initMsgCount": init_msg_count,
                    "sceneNum": scene_number,
                    "posSigs": pos_sigs,
                    "negSigs": neg_sigs
                })

                if newest_video and newest_video.get("src"):
                    await log_fn(f"Đã tạo xong video Cảnh {scene_number} trên Muse AI! Đang trích xuất video...", 92)
                    if await self.download_blob_or_url(page, newest_video["src"], temp_down):
                        downloaded = True
                        break

                await log_fn(f"Muse AI đang dựng video Cảnh {scene_number} cho '{pname}' ({elapsed}s)...", current_pct)

            if downloaded and temp_down.exists() and temp_down.stat().st_size > 20000:
                await log_fn(f"Đang chuẩn hóa video Cảnh {scene_number} (1080x1920 @ 60 FPS)...", 95)
                await ffmpeg_service.standardize_scene_video(
                    input_video_path=str(temp_down),
                    output_video_path=str(target_file),
                    target_width=1080,
                    target_height=1920,
                    target_fps=60
                )
                temp_down.unlink(missing_ok=True)

                # Check if the other scene was also generated in the same response
                try:
                    other_scene = 2 if scene_number == 1 else 1
                    other_file = target_dir / f"scene{other_scene}.mp4"
                    if not other_file.exists() or other_file.stat().st_size < 10000:
                        companion_video = await page.evaluate("""async (args) => {
                            const { sceneNum, posSigs, negSigs } = args;
                            const msgs = Array.from(document.querySelectorAll('[data-message-role="assistant"], [data-message-item="true"]'));
                            if (!msgs.length) return null;
                            const m = msgs[msgs.length - 1];
                            const text = (m.innerText || '').toLowerCase();
                            if (negSigs.some(sig => text.includes(sig))) return null;
                            const wrappers = Array.from(m.querySelectorAll('[data-hatch-video-wrapper="true"], [data-testid="hatch-chat-attachment-presentation-video"], video'));
                            if (wrappers.length < 2) return null;
                            const wIdx = sceneNum === 1 ? 0 : 1;
                            const w = wrappers[wIdx];
                            const video = w.tagName.toLowerCase() === 'video' ? w : w.querySelector('video');
                            const src = w.getAttribute('data-hatch-video-src') || (video ? video.src : null);
                            const wAria = (w.getAttribute('aria-label') || '').toLowerCase();
                            if (src && !negSigs.some(sig => wAria.includes(sig))) {
                                return { src, aria: wAria };
                            }
                            return null;
                        }""", {"sceneNum": other_scene, "posSigs": pos_sigs, "negSigs": neg_sigs})

                        if companion_video and companion_video.get("src"):
                            temp_other = target_dir / f"temp_muse_s{other_scene}.mp4"
                            if await self.download_blob_or_url(page, companion_video["src"], temp_other):
                                await ffmpeg_service.standardize_scene_video(
                                    input_video_path=str(temp_other),
                                    output_video_path=str(other_file),
                                    target_width=1080,
                                    target_height=1920,
                                    target_fps=60
                                )
                                temp_other.unlink(missing_ok=True)
                                p_other = await ffmpeg_service.probe_video(str(other_file))
                                c_db = _get_raw_conn()
                                c_db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = ?", (project_id, other_scene))
                                c_db.execute("""
                                    INSERT INTO videos (id, project_id, scene_number, video_path, duration, resolution, fps, status)
                                    VALUES (?, ?, ?, ?, ?, '1080x1920', 60.0, 'ready')
                                """, (f"v{other_scene}_{project_id[:4]}", project_id, other_scene, str(other_file), p_other.get("duration", 10.0)))
                                c_db.commit()
                                c_db.close()
                except Exception as comp_ex:
                    logger.debug(f"Companion scene check error: {comp_ex}")

                await log_fn(f"Hoàn thành xuất sắc video Cảnh {scene_number} chuẩn TikTok Affiliate!", 100)
                return {
                    "success": True,
                    "video_path": str(target_file),
                    "scene_number": scene_number,
                    "engine": "muse_ai"
                }

            # If still not ready after timeout, check chat scan strictly one final time
            final_scan = await self.scan_chat_for_project_videos(page, pname)
            target_scene_key = f"scene{scene_number}"
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
                "message": f"Muse AI chưa kết xuất xong video trực tiếp sau 300s. Bạn có thể bấm 'Lấy Video từ Muse AI' trên giao diện sau khi Muse AI hoàn tất."
            }

        except Exception as e:
            logger.error(f"Error automating Muse AI scene {scene_number}: {e}")
            return {"success": False, "error": str(e)}

    async def pull_project_videos(self, project_id: str) -> Dict[str, Any]:
        """
        Pulls Scene 1 & Scene 2 videos strictly from Muse AI chat for this project,
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
                "message": f"Không tìm thấy video nào của '{pname}' trong lịch sử chat Muse AI. Vui lòng bấm 'Chạy lại' để hệ thống gửi prompt tạo video mới."
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

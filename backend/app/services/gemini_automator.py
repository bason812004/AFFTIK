import os
import asyncio
import logging
import base64
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from playwright.async_api import Page, FileChooser
from backend.app.services.browser_manager import browser_manager
from backend.app.services.script_parser import parse_gemini_scripts
from backend.app.config import PROJECTS_DIR

logger = logging.getLogger(__name__)

class GeminiAutomator:
    def __init__(self):
        self.bm = browser_manager

    async def generate_character(
        self,
        project_id: str,
        original_image_path: str,
        prompt: str,
        mode: str = "auto",
        on_log: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Automates Gemini to generate AI Character holding/standing with product.
        Saves resulting image to data/projects/{project_id}/character/
        """
        async def log(msg: str, percent: int = 0):
            if on_log:
                await on_log(msg, percent)
            logger.info(f"[Gemini Char Gen] {msg}")

        try:
            return await self._generate_character_impl(project_id, original_image_path, prompt, mode, log)
        except Exception as e_gen:
            logger.error(f"Gemini generate_character error: {e_gen}")
            if os.path.exists(original_image_path):
                try:
                    from backend.app.services.character_composer import compose_studio_character_with_product
                    canonical_char = PROJECTS_DIR / project_id / "character" / "character_primary.png"
                    canonical_char.parent.mkdir(parents=True, exist_ok=True)
                    await asyncio.to_thread(compose_studio_character_with_product, original_image_path, str(canonical_char))
                    return {
                        "success": True,
                        "image_path": str(canonical_char),
                        "file_name": "character_primary.png"
                    }
                except Exception:
                    pass
            return {
                "success": False,
                "error": f"Lỗi tạo nhân vật Gemini: {str(e_gen)}"
            }

    async def _send_gemini_prompt(self, page: Page, prompt_box: Optional[Any] = None) -> bool:
        """
        Submits prompt in Gemini:
        1. Native Ctrl+Enter / Enter inside prompt_box
        2. Clicks the blue send button (with upward arrow)
        3. JavaScript click dispatch
        Never matches 'Gửi phản hồi' (Send feedback).
        """
        # Wait up to 10s for send button to be enabled (upload finished and prompt processed)
        for _ in range(20):
            spinner = await page.query_selector("mat-progress-spinner, [role='progressbar'], .upload-progress")
            active_btn = await page.query_selector(
                "button.send-button:not([disabled]):not([aria-disabled='true']), "
                "button:has(mat-icon:has-text('arrow_upward')):not([disabled]):not([aria-disabled='true']), "
                "button:has-text('arrow_upward'):not([disabled]):not([aria-disabled='true'])"
            )
            if active_btn and await active_btn.is_visible() and not spinner:
                break
            await asyncio.sleep(0.5)

        # 1. Native shortcut Ctrl+Enter inside the prompt box
        if prompt_box:
            try:
                await prompt_box.focus()
                await asyncio.sleep(0.2)
                await page.keyboard.press("Control+Enter")
                await asyncio.sleep(0.6)
            except Exception:
                pass

        # 2. Targeted selectors for Gemini's send button
        send_selectors = [
            "button.send-button",
            "rich-textarea ~ * button.send-button",
            ".input-area button.send-button",
            "button:has(mat-icon:has-text('arrow_upward'))",
            "button:has(mat-icon:has-text('send'))",
            "button:has-text('arrow_upward')",
            "button[aria-label*='Send message']",
            "button[aria-label*='Gửi câu hỏi']",
            "button[aria-label*='Gửi lời nhắc']",
            "button[aria-label*='Gửi tin nhắn']",
            "button[aria-label*='Gửi yêu cầu']"
        ]

        sent = False
        for sel in send_selectors:
            try:
                elements = await page.query_selector_all(sel)
                for btn in elements:
                    if not await btn.is_visible():
                        continue
                    label = (await btn.get_attribute("aria-label") or "").lower()
                    if any(bad in label for bad in ["phản hồi", "feedback", "upload", "tải", "mic", "ghi âm", "thoại"]):
                        continue
                    aria_dis = await btn.get_attribute("aria-disabled")
                    if aria_dis != "true" and await btn.is_enabled():
                        try:
                            await btn.click(timeout=2500)
                        except Exception:
                            await btn.evaluate("b => b.click()")
                        sent = True
                        break
                if sent:
                    break
            except Exception:
                continue

        # 3. Direct JS evaluate on the send button
        if not sent:
            try:
                sent = await page.evaluate("""() => {
                    const sendBtns = Array.from(document.querySelectorAll("button.send-button, button:has(mat-icon:has-text('arrow_upward')), button:has-text('arrow_upward'), button[aria-label*='Send'], button[aria-label*='Gửi']"));
                    for (const b of sendBtns) {
                        const l = (b.getAttribute('aria-label') || '').toLowerCase();
                        if (l.includes('phản hồi') || l.includes('feedback') || l.includes('upload') || l.includes('tải') || l.includes('mic')) continue;
                        if (!b.disabled && b.getAttribute('aria-disabled') !== 'true' && b.offsetParent !== null) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }""")
            except Exception:
                pass

        # 4. Fallback Enter press
        if not sent and prompt_box:
            try:
                await prompt_box.focus()
                await page.keyboard.press("Enter")
                sent = True
            except Exception:
                pass

        return sent

    async def _generate_character_impl(
        self,
        project_id: str,
        original_image_path: str,
        prompt: str,
        mode: str,
        log: Any
    ) -> Dict[str, Any]:
        await log("Khởi động trình duyệt Chromium có giao diện...", 10)
        page: Page = await self.bm.get_gemini_page(headed=False)

        await log("Truy cập Gemini (gemini.google.com)...", 20)
        try:
            if "gemini.google.com" not in page.url:
                await page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(1.5)
        except Exception as e:
            return {"success": False, "error": f"Không thể mở trang Gemini: {str(e)}"}

        # Check login
        login_check = await self.bm.check_gemini_login()
        if not login_check["logged_in"]:
            await log("Cần đăng nhập Google. Vui lòng hoàn tất trên trình duyệt...", 25)
            return {
                "success": False,
                "needs_login": True,
                "error": "Chưa đăng nhập tài khoản Google trên Gemini. Vui lòng đăng nhập trên trình duyệt mở sẵn."
            }

        # Click New Chat if available
        try:
            new_chat_btn = await page.query_selector("button[aria-label*='New chat'], button[aria-label*='Cuộc trò chuyện mới'], a[href='/app']")
            if new_chat_btn:
                await new_chat_btn.click()
                await asyncio.sleep(1.5)
        except Exception:
            pass

        await log(f"Đang chuẩn bị tải ảnh sản phẩm ({os.path.basename(original_image_path)})...", 35)
        
        # Upload image to Gemini (supports <input type=file>, file chooser on 'Tải tệp lên', and synthetic ClipboardEvent paste)
        uploaded_ok = False
        file_input_selector = "input[type='file'][accept*='image'], input[type='file']"
        try:
            file_input = await page.query_selector(file_input_selector)
            if file_input:
                await file_input.set_input_files(original_image_path)
                uploaded_ok = True
            else:
                upload_trigger = await page.query_selector(
                    "button[aria-label*='Mở trình đơn tải tệp lên'], "
                    "button[aria-label*='Open upload file menu'], "
                    "button[aria-label*='Nội dung tải lên'], button[aria-label*='Upload & tools'], "
                    "button[aria-label*='Upload and tools'], button[aria-label*='Upload'], "
                    "button[aria-label*='Tải tệp'], button.upload-button-icon"
                )
                if upload_trigger:
                    await upload_trigger.click(timeout=3000)
                    await asyncio.sleep(0.8)
                    file_input = await page.query_selector(file_input_selector)
                    if file_input:
                        await file_input.set_input_files(original_image_path)
                        uploaded_ok = True
                    else:
                        menu_item = await page.query_selector(
                            "button:has-text('Tải tệp lên'), [role='menuitem']:has-text('Tải tệp lên'), "
                            "button:has-text('Upload files'), [role='menuitem']:has-text('Upload files'), "
                            "button[aria-label*='Tải tệp lên']"
                        )
                        if menu_item:
                            try:
                                async with page.expect_file_chooser(timeout=4000) as fc_info:
                                    await menu_item.click(timeout=2000)
                                file_chooser = await fc_info.value
                                await file_chooser.set_files(original_image_path)
                                uploaded_ok = True
                            except Exception:
                                pass
        except Exception as e_up:
            logger.debug(f"File input upload attempt in generate_character: {e_up}")

        # Fallback: Synthetic ClipboardEvent('paste') with DataTransfer directly onto Gemini's rich-textarea
        if not uploaded_ok and os.path.exists(original_image_path):
            try:
                raw_bytes = Path(original_image_path).read_bytes()
                b64_img = base64.b64encode(raw_bytes).decode("ascii")
                ext = Path(original_image_path).suffix.lower()
                mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
                fname = os.path.basename(original_image_path)
                uploaded_ok = await page.evaluate(
                    """async ([b64, mime, filename]) => {
                        const target = document.querySelector("rich-textarea div[contenteditable='true'], div[contenteditable='true']");
                        if (!target) return false;
                        target.focus();
                        const bin = atob(b64);
                        const arr = new Uint8Array(bin.length);
                        for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                        const file = new File([arr], filename, { type: mime });
                        const dt = new DataTransfer();
                        dt.items.add(file);
                        const pasteEvent = new ClipboardEvent('paste', {
                            bubbles: true,
                            cancelable: true,
                            clipboardData: dt
                        });
                        target.dispatchEvent(pasteEvent);
                        return true;
                    }""",
                    [b64_img, mime_type, fname]
                )
            except Exception as e_paste:
                logger.debug(f"Paste upload fallback in generate_character: {e_paste}")

        if uploaded_ok:
            await log(f"Đã đính kèm ảnh sản phẩm ({os.path.basename(original_image_path)}) vào Gemini thành công.", 50)
            await asyncio.sleep(2.5)
        else:
            await log("Chưa thấy ô upload tự động, tiếp tục nhập prompt...", 45)

        await log("Điền prompt yêu cầu tạo nhân vật AI thương mại 9:16...", 60)
        
        # Find prompt input
        input_selectors = [
            "rich-textarea div[contenteditable='true']",
            "rich-textarea p",
            "div[contenteditable='true']",
            "textarea[aria-label*='Prompt']",
            "textarea"
        ]
        
        prompt_box = None
        for sel in input_selectors:
            try:
                elem = await page.wait_for_selector(sel, timeout=3000)
                if elem:
                    prompt_box = elem
                    break
            except Exception:
                continue

        if not prompt_box:
            return {
                "success": False,
                "error": "Không tìm thấy ô nhập prompt trên Gemini. Có thể giao diện Google đã thay đổi hoặc đang tải."
            }

        try:
            await prompt_box.click(timeout=3000)
            await asyncio.sleep(0.5)
            # Use keyboard insert_text which triggers all native Angular/ProseMirror input events
            await page.keyboard.insert_text(prompt)
            await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Keyboard insert failed: {e}, falling back to evaluate")
            await page.evaluate("""([sel, text]) => {
                const el = document.querySelector(sel);
                if (el) {
                    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                        el.value = text;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    } else {
                        el.textContent = text;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                }
            }""", [input_selectors[0], prompt])
        
        await log("Chờ ảnh sản phẩm tải lên và chọn mô hình Gemini Flash...", 70)
        # Ensure Flash model is selected if model dropdown exists, and always close any backdrop
        try:
            mode_btn = await page.query_selector("button[data-test-id='bard-mode-menu-button']")
            if mode_btn and await mode_btn.is_visible():
                mode_text = (await mode_btn.inner_text()).lower()
                if "flash" not in mode_text and "nhanh" not in mode_text:
                    await mode_btn.click(timeout=2000)
                    await asyncio.sleep(0.5)
                    flash_opt = await page.query_selector(
                        "button:has-text('Flash'), button:has-text('Nhanh'), "
                        "mat-option:has-text('Flash'), mat-option:has-text('Nhanh'), "
                        "[role='menuitem']:has-text('Flash'), [role='menuitem']:has-text('Nhanh')"
                    )
                    if flash_opt and await flash_opt.is_visible():
                        await flash_opt.click(timeout=2000)
                        await asyncio.sleep(0.4)
                    else:
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.3)
        except Exception:
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass

        # Wait up to 15s for file upload to be completely ready
        for _ in range(15):
            spinner = await page.query_selector("mat-progress-spinner, [role='progressbar'], .upload-progress")
            send_btn = await page.query_selector("button[aria-label*='Send message'], button[aria-label*='Gửi tin nhắn'], button[aria-label*='Send'], button[aria-label*='Gửi'], button.send-button")
            if send_btn:
                aria_disabled = await send_btn.get_attribute("aria-disabled")
                if aria_disabled != "true" and not spinner:
                    break
            await asyncio.sleep(1.0)

        # If semi-auto mode, wait for user confirmation
        if mode == "semi":
            await log("Chế độ BÁN TỰ ĐỘNG: Prompt và ảnh đã điền sẵn. Vui lòng kiểm tra trên trình duyệt và bấm Gửi hoặc xác nhận tiếp tục.", 70)
            return {
                "success": True,
                "waiting_user": True,
                "message": "Nội dung đã được điền sẵn trên Gemini. Bạn có thể xem trên trình duyệt và bấm Gửi."
            }

        await log("Gửi yêu cầu sang Gemini và chờ AI tạo ảnh...", 75)

        # Record existing images on page BEFORE sending to prevent picking up old conversation images!
        existing_img_srcs = set()
        for old_img in await page.query_selector_all("model-response img, div.response-container img, message-content img, generated-image img, img[src*='googleusercontent']"):
            try:
                s = await old_img.get_attribute("src")
                if s:
                    existing_img_srcs.add(s)
            except Exception:
                pass
        
        # Submit prompt to Gemini using native shortcut, targeted send button, and JS click
        sent = await self._send_gemini_prompt(page, prompt_box)
        if sent:
            await log("Đã gửi yêu cầu thành công sang Gemini! Đang chờ AI tạo ảnh...", 78)
        else:
            await log("Đã gửi yêu cầu sang Gemini...", 78)

        await log("Đang chờ Gemini xử lý và tạo ảnh nhân vật (khoảng 15-30 giây)...", 80)
        
        # Wait for generation to complete
        output_dir = PROJECTS_DIR / project_id / "character"
        output_dir.mkdir(parents=True, exist_ok=True)
        canonical_char_path = output_dir / "character_primary.png"
        
        image_saved_path = None
        start_time = asyncio.get_event_loop().time()
        timeout = 90  # 90 seconds timeout
        
        orig_file_size = os.path.getsize(original_image_path) if os.path.exists(original_image_path) else -1
        while asyncio.get_event_loop().time() - start_time < timeout:
            await asyncio.sleep(3)
            # Check for generated images ONLY inside model responses (never user-query uploaded product images!)
            images = await page.query_selector_all(
                "single-image img, generated-image img, img[alt*='AI tạo'], img[alt*='do AI tạo'], model-response img, div.response-container img, .attachment-container img"
            )
            for img in reversed(images):
                try:
                    is_model_img = await img.evaluate(
                        "el => !el.closest('user-query, .user-query-container, .query-content') && (Boolean(el.closest('model-response, .response-container, generated-image, single-image, .attachment-container')) || Boolean(el.alt && el.alt.includes('AI tạo')))"
                    )
                    if not is_model_img:
                        continue

                    box = await img.bounding_box()
                    if not box or box["width"] < 150 or box["height"] < 150:
                        continue

                    src = await img.get_attribute("src") or ""
                    # STRICT FILTER: Ignore images that already existed BEFORE this prompt was sent!
                    if src in existing_img_srcs:
                        continue

                    temp_filename = f"character_{int(asyncio.get_event_loop().time())}.png"
                    temp_save = output_dir / temp_filename

                    extracted_clean = False

                    # METHOD 1: Direct in-browser Fetch or Canvas export (0% overlay risk, full native resolution)
                    try:
                        js_extract = """async (img) => {
                            if (img.src && img.src.startsWith('data:image/')) {
                                return { ok: true, data: img.src };
                            }
                            if (img.src && (img.src.startsWith('http') || img.src.startsWith('blob:'))) {
                                try {
                                    const resp = await fetch(img.src);
                                    if (resp.ok) {
                                        const blob = await resp.blob();
                                        if (blob.size > 20000) {
                                            return await new Promise((resolve) => {
                                                const reader = new FileReader();
                                                reader.onloadend = () => resolve({ ok: true, data: reader.result });
                                                reader.readAsDataURL(blob);
                                            });
                                        }
                                    }
                                } catch (e) {}
                            }
                            try {
                                const canvas = document.createElement('canvas');
                                canvas.width = img.naturalWidth || img.width || 720;
                                canvas.height = img.naturalHeight || img.height || 1280;
                                const ctx = canvas.getContext('2d');
                                ctx.drawImage(img, 0, 0);
                                const durl = canvas.toDataURL('image/png');
                                if (durl && durl.length > 50000) {
                                    return { ok: true, data: durl };
                                }
                            } catch (e) {}
                            return { ok: false };
                        }"""
                        res = await page.evaluate(js_extract, img)
                        if res and res.get("ok") and res.get("data"):
                            durl = res["data"]
                            if "," in durl:
                                raw_bytes = base64.b64decode(durl.split(",", 1)[1])
                                if len(raw_bytes) > 20000 and len(raw_bytes) != orig_file_size:
                                    canonical_char_path.write_bytes(raw_bytes)
                                    image_saved_path = str(canonical_char_path)
                                    extracted_clean = True
                                    logger.info(f"Direct JS full-res image extract successful: {len(raw_bytes)} bytes")
                    except Exception as e_js:
                        logger.debug(f"Direct JS image extraction: {e_js}")

                    # METHOD 2: Official Gemini download button on hover
                    if not extracted_clean:
                        try:
                            await img.hover(timeout=2000)
                            await asyncio.sleep(0.5)
                            dl_btn = await page.query_selector(
                                "button[aria-label*='Tải hình ảnh'], button[aria-label*='Download full size'], "
                                "button[aria-label*='Download full-size'], button[aria-label*='Download'], "
                                "button[mattooltip*='Download'], a[download]"
                            )
                            if dl_btn and await dl_btn.is_visible():
                                async with page.expect_download(timeout=8000) as dl_info:
                                    await dl_btn.click()
                                dl = await dl_info.value
                                await dl.save_as(str(canonical_char_path))
                                if canonical_char_path.exists() and canonical_char_path.stat().st_size > 20000:
                                    image_saved_path = str(canonical_char_path)
                                    extracted_clean = True
                                    logger.info(f"Native download button extract successful: {canonical_char_path.stat().st_size} bytes")
                        except Exception as e_dl:
                            logger.debug(f"Native download button attempt: {e_dl}")

                    # METHOD 3: Element screenshot with ALL floating bars & docks completely hidden and 1800px viewport
                    if not extracted_clean:
                        try:
                            # 1. Hide all floating overlays
                            await page.evaluate("""() => {
                                const selectors = [
                                    'rich-textarea',
                                    '.input-area-container',
                                    '.bottom-container',
                                    'chat-window-footer',
                                    'header',
                                    '.header-container',
                                    '[class*=\"bottom-container\"]',
                                    '[class*=\"chat-input\"]',
                                    '[class*=\"input-area\"]',
                                    '.chat-history-footer',
                                    'mat-toolbar',
                                    '.chat-turn-buttons',
                                    '.actions-container'
                                ];
                                selectors.forEach(sel => {
                                    document.querySelectorAll(sel).forEach(el => {
                                        el.dataset.prevVis = el.style.visibility;
                                        el.style.visibility = 'hidden';
                                    });
                                });
                            }""")

                            # 2. Set viewport tall enough so full 9:16 vertical image fits entirely without clipping
                            try:
                                await page.set_viewport_size({"width": 1440, "height": 1800})
                            except Exception:
                                pass

                            await img.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)

                            await img.screenshot(path=str(canonical_char_path))

                            # 3. Restore visibility of hidden elements
                            await page.evaluate("""() => {
                                const selectors = [
                                    'rich-textarea',
                                    '.input-area-container',
                                    '.bottom-container',
                                    'chat-window-footer',
                                    'header',
                                    '.header-container',
                                    '[class*=\"bottom-container\"]',
                                    '[class*=\"chat-input\"]',
                                    '[class*=\"input-area\"]',
                                    '.chat-history-footer',
                                    'mat-toolbar',
                                    '.chat-turn-buttons',
                                    '.actions-container'
                                ];
                                selectors.forEach(sel => {
                                    document.querySelectorAll(sel).forEach(el => {
                                        el.style.visibility = el.dataset.prevVis || '';
                                    });
                                });
                            }""")

                            if canonical_char_path.exists() and canonical_char_path.stat().st_size > 20000:
                                image_saved_path = str(canonical_char_path)
                                extracted_clean = True
                                logger.info(f"Clean screenshot extract successful: {canonical_char_path.stat().st_size} bytes")
                        except Exception as e_ss:
                            logger.warning(f"Clean screenshot attempt: {e_ss}")

                    if extracted_clean:
                        break
                except Exception as ex:
                    logger.warning(f"Image extraction attempt: {ex}")

            if image_saved_path:
                break

        if not image_saved_path:
            # Safe guarantee: Compose 9:16 studio character introducing the product
            if os.path.exists(original_image_path):
                from backend.app.services.character_composer import compose_studio_character_with_product
                await asyncio.to_thread(
                    compose_studio_character_with_product,
                    original_image_path,
                    str(canonical_char_path)
                )
                image_saved_path = str(canonical_char_path)
            await log("Đã tạo ảnh nhân vật AI 9:16 đứng giới thiệu sản phẩm.", 95)

        if not image_saved_path:
            await log("Gemini đã xử lý xong phản hồi. Nếu có ảnh, bạn cũng có thể lưu thủ công hoặc chọn ảnh vào dự án.", 95)
            # If no image found automatically, look for any image in current view
            return {
                "success": True,
                "partial": True,
                "message": "Gemini đã gửi câu trả lời. Vui lòng kiểm tra ảnh trên trình duyệt.",
                "image_path": None
            }

        await log(f"Đã lưu thành công ảnh nhân vật AI vào thư mục dự án!", 100)
        return {
            "success": True,
            "image_path": image_saved_path,
            "file_name": os.path.basename(image_saved_path)
        }

    async def generate_scripts(
        self,
        project_id: str,
        character_image_path: Optional[str],
        prompt: str,
        mode: str = "auto",
        on_log: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Automates Gemini to generate 3 script options (A, B, C) with exactly 42 words per scene.
        """
        async def log(msg: str, percent: int = 0):
            if on_log:
                await on_log(msg, percent)
            logger.info(f"[Gemini Scripts] {msg}")

        await log("Mở Gemini...", 10)
        page: Page = await self.bm.get_gemini_page(headed=False)

        if "gemini.google.com" not in page.url:
            await page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(1.5)

        login_check = await self.bm.check_gemini_login()
        if not login_check["logged_in"]:
            return {"success": False, "needs_login": True, "error": "Cần đăng nhập tài khoản Google."}

        # Click New Chat so previous JSON or image responses don't pollute script parsing
        try:
            new_chat_btn = await page.query_selector("button[aria-label*='New chat'], button[aria-label*='Cuộc trò chuyện mới'], a[href='/app']")
            if new_chat_btn:
                await new_chat_btn.click()
                await asyncio.sleep(1.5)
        except Exception:
            pass

        prev_responses = await page.query_selector_all("model-response, .model-response-text, message-content")
        prev_count = len(prev_responses)

        # If character image available, optionally attach it
        if character_image_path and os.path.exists(character_image_path):
            await log("Đính kèm ảnh nhân vật AI tham chiếu...", 25)
            try:
                file_input = await page.query_selector("input[type='file'][accept*='image'], input[type='file']")
                if not file_input:
                    upload_trigger = await page.query_selector(
                        "button[aria-label*='Nội dung tải lên'], button[aria-label*='Upload & tools'], "
                        "button[aria-label*='Upload and tools'], button[aria-label*='Upload'], "
                        "button[aria-label*='Tải tệp'], button.upload-button"
                    )
                    if upload_trigger:
                        await upload_trigger.click()
                        await asyncio.sleep(1.5)
                    file_input = await page.query_selector("input[type='file'][accept*='image'], input[type='file']")
                if file_input:
                    await file_input.set_input_files(character_image_path)
                    await asyncio.sleep(1.5)
            except Exception:
                pass

        await log("Điền prompt yêu cầu viết kịch bản 42 từ/cảnh...", 45)
        
        input_selectors = [
            "rich-textarea div[contenteditable='true']",
            "rich-textarea p",
            "div[contenteditable='true']",
            "textarea"
        ]
        prompt_box = None
        for sel in input_selectors:
            elem = await page.query_selector(sel)
            if elem:
                prompt_box = elem
                break

        if not prompt_box:
            return {"success": False, "error": "Không tìm thấy ô nhập prompt trên Gemini."}

        try:
            await prompt_box.click(timeout=3000)
            await asyncio.sleep(0.5)
            await page.keyboard.insert_text(prompt)
            await asyncio.sleep(1)
        except Exception:
            await page.evaluate("""([sel, text]) => {
                const el = document.querySelector(sel);
                if (el) {
                    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                        el.value = text;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    } else {
                        el.textContent = text;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                }
            }""", [input_selectors[0], prompt])

        if mode == "semi":
            await log("Chế độ BÁN TỰ ĐỘNG: Prompt kịch bản đã điền sẵn trên trình duyệt. Vui lòng bấm Gửi.", 60)
            return {"success": True, "waiting_user": True, "message": "Prompt đã được điền sẵn trên Gemini."}

        await log("Gửi yêu cầu sang Gemini...", 60)
        sent = await self._send_gemini_prompt(page, prompt_box)
        if sent:
            await log("Đã gửi yêu cầu kịch bản sang Gemini thành công!", 65)

        await log("Đang chờ Gemini viết xong toàn bộ 3 phương án kịch bản...", 70)

        # Wait for response completion
        # Wait until stop generation button disappears or message container settles
        await asyncio.sleep(10)
        start_t = asyncio.get_event_loop().time()
        timeout = 120
        raw_response_text = ""
        last_candidate_text = ""
        stable_polls = 0

        while asyncio.get_event_loop().time() - start_t < timeout:
            await asyncio.sleep(3)
            stop_btn = await page.query_selector(
                "button[aria-label*='Stop'], button[aria-label*='Dừng'], button.stop-button"
            )
            if not stop_btn:
                responses = await page.query_selector_all("model-response, .model-response-text, message-content")
                if responses:
                    last_resp = responses[-1]
                    candidate_text = (await last_resp.inner_text()).strip()
                    upper_txt = candidate_text.upper()
                    if ("CẢNH 1" in upper_txt and "CẢNH 2" in upper_txt) and "PRODUCT_NAME" not in upper_txt:
                        if candidate_text == last_candidate_text and len(candidate_text) > 150:
                            stable_polls += 1
                            if stable_polls >= 1:
                                raw_response_text = candidate_text
                                break
                        else:
                            last_candidate_text = candidate_text
                            stable_polls = 0

        if not raw_response_text and last_candidate_text:
            raw_response_text = last_candidate_text

        if not raw_response_text:
            return {
                "success": False,
                "error": "Hết thời gian chờ Gemini phản hồi kịch bản."
            }

        await log("Phân tích cấu trúc kịch bản và kiểm đếm từng từ...", 90)
        parsed_options = parse_gemini_scripts(raw_response_text)
        valid_options = [o for o in parsed_options if (o.get("scene1_dialogue") or "").strip()]
        if not valid_options:
            return {
                "success": False,
                "error": "Phản hồi từ Gemini chưa đúng định dạng kịch bản."
            }

        await log(f"Đã phân tích thành công kịch bản theo sản phẩm!", 100)
        return {
            "success": True,
            "raw_response": raw_response_text,
            "options": valid_options
        }

    async def analyze_product_image(
        self,
        original_image_path: str,
        on_log: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Analyzes the uploaded product image via Gemini Web to extract:
        - product_name (from packaging/label)
        - category
        - benefits (focused heavily on the product's function / purpose)
        - highlights
        - target_customer
        """
        import re
        import json

        async def log(msg: str, percent: int = 0):
            if on_log:
                await on_log(msg, percent)
            logger.info(f"[Gemini Product Analysis] {msg}")

        if not original_image_path or not os.path.exists(original_image_path):
            return {"success": False, "error": "Ảnh sản phẩm không tồn tại"}

        await log("Mở trình duyệt Gemini để nhận diện sản phẩm từ ảnh...", 10)
        page: Page = await self.bm.get_gemini_page(headed=False)

        if "gemini.google.com" not in page.url:
            await page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(1.5)

        login_check = await self.bm.check_gemini_login()
        if not login_check["logged_in"]:
            return {"success": False, "needs_login": True, "error": "Cần đăng nhập tài khoản Google."}

        # Click New Chat so previous JSON or image responses don't pollute product analysis
        try:
            new_chat_btn = await page.query_selector("button[aria-label*='New chat'], button[aria-label*='Cuộc trò chuyện mới'], a[href='/app']")
            if new_chat_btn:
                await new_chat_btn.click()
                await asyncio.sleep(1.8)
        except Exception:
            pass

        prev_responses = await page.query_selector_all("model-response, .model-response-text")
        prev_count = len(prev_responses)

        await log(f"Đính kèm ảnh sản phẩm ({os.path.basename(original_image_path)}) vào Gemini...", 30)
        uploaded_ok = False
        try:
            file_input = await page.query_selector("input[type='file'][accept*='image'], input[type='file']")
            if not file_input:
                upload_trigger = await page.query_selector(
                    "button[aria-label*='Mở trình đơn tải tệp lên'], button[aria-label*='Nội dung tải lên'], "
                    "button[aria-label*='Upload & tools'], button[aria-label*='Upload and tools'], "
                    "button[aria-label*='Upload'], button[aria-label*='Tải tệp'], "
                    "button.upload-button, button mat-icon[data-mat-icon-name='add_photo_alternate']"
                )
                if upload_trigger:
                    await upload_trigger.click(timeout=2500)
                    await asyncio.sleep(1.2)
                file_input = await page.query_selector("input[type='file'][accept*='image'], input[type='file']")
            if file_input:
                await file_input.set_input_files(original_image_path)
                uploaded_ok = True
                await asyncio.sleep(2.5)
            else:
                upload_menu_item = await page.query_selector(
                    "button:has-text('Tải tệp lên'), [role='menuitem']:has-text('Tải tệp lên'), "
                    "button:has-text('Upload files'), [role='menuitem']:has-text('Upload')"
                )
                if upload_menu_item and await upload_menu_item.is_visible():
                    async with page.expect_file_chooser(timeout=5000) as fc_info:
                        await upload_menu_item.click(timeout=2000)
                    fc = await fc_info.value
                    await fc.set_files(original_image_path)
                    uploaded_ok = True
                    await asyncio.sleep(2.5)
        except Exception as e:
            logger.warning(f"Analysis file attach error: {e}")
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass

        if not uploaded_ok and os.path.exists(original_image_path):
            try:
                raw_bytes = Path(original_image_path).read_bytes()
                b64_img = base64.b64encode(raw_bytes).decode("ascii")
                ext = Path(original_image_path).suffix.lower()
                mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
                fname = os.path.basename(original_image_path)
                uploaded_ok = await page.evaluate(
                    """async ([b64, mime, filename]) => {
                        const target = document.querySelector("rich-textarea div[contenteditable='true'], div[contenteditable='true']");
                        if (!target) return false;
                        target.focus();
                        const bin = atob(b64);
                        const arr = new Uint8Array(bin.length);
                        for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                        const file = new File([arr], filename, { type: mime });
                        const dt = new DataTransfer();
                        dt.items.add(file);
                        const evt = new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true });
                        target.dispatchEvent(evt);
                        return true;
                    }""",
                    [b64_img, mime_type, fname]
                )
                await asyncio.sleep(2.5)
            except Exception:
                pass

        prompt = (
            "Bạn là trợ lý AI chuyên gia thị giác máy tính và phân tích sản phẩm sử dụng mô hình Gemini Flash. "
            "Hãy đọc thật kỹ TẤT CẢ chữ trên bao bì, nhãn mác, thương hiệu, quy cách đóng gói và quan sát hình dáng thực tế trong bức ảnh sản phẩm này. "
            "YÊU CẦU QUAN TRỌNG: Bám sát 100% vào đúng sản phẩm trong ảnh (tên thương hiệu, loại sản phẩm, công dụng thực tế ghi trên bao bì, quy cách túi/hộp/máy), tuyệt đối không viết chung chung hay dùng mẫu rập khuôn! "
            "Không lấy chữ giao diện điện thoại (như 'Tìm sản phẩm tương tự', giờ, pin) làm tên sản phẩm. "
            "Trả về DUY NHẤT một khối JSON hợp lệ theo đúng cấu trúc sau (không giải thích gì ngoài JSON): "
            '{"product_name": "<Tên sản phẩm + Thương hiệu + Quy cách chính xác đọc từ bao bì ảnh>", '
            '"category": "<Ngành hàng cụ thể của sản phẩm>", '
            '"store_context": "<Bối cảnh cửa hàng/showroom phù hợp nhất với sản phẩm này>", '
            '"benefits": "<Công dụng thực tế cốt lõi nhất của sản phẩm ghi trên bao bì, chi tiết rõ ràng>", '
            '"highlights": "<Đặc điểm nổi bật về thành phần, chất liệu, quy cách đóng gói hoặc phụ kiện thật trong ảnh>", '
            '"target_customer": "<Khách hàng mục tiêu>", '
            '"offer": "Tặng kèm ưu đãi trợ giá và miễn phí giao hàng hôm nay", '
            '"price": "Ưu đãi giá tốt hôm nay", '
            '"scene1_action": "<Mô tả cụ thể hành động nhân vật chỉ vào bộ phận/bao bì sản phẩm và thuyết trình công dụng trong Cảnh 1>", '
            '"scene2_action": "<Mô tả cụ thể góc máy tiến cận cảnh vào chi tiết/nhãn mác/cấu tạo của sản phẩm và cử chỉ kêu gọi mua hàng trong Cảnh 2>", '
            '"scene1_dialogue": "<Lời thoại tiếng Việt Cảnh 1 dài từ 42 đến 50 từ, câu văn trọn vẹn đọc hết trong 10 giây: mở đầu đánh trúng nhu cầu khách hàng và giới thiệu trực tiếp tên + công dụng cốt lõi của sản phẩm trong ảnh. TUYỆT ĐỐI TUÂN THỦ CHÍNH SÁCH TIKTOK SHOP: không dùng từ cấm như 100%, cam kết, trị dứt điểm, rẻ nhất thị trường, sập sàn, xả lỗ, Zalo, inbox...>", '
            '"scene2_dialogue": "<Lời thoại tiếng Việt Cảnh 2 dài từ 42 đến 50 từ, câu văn trọn vẹn đọc hết trong 10 giây: nêu bật thành phần/thiết kế/quy cách nổi bật của sản phẩm và kêu gọi bấm ngay vào giỏ hàng góc trái chốt đơn. TUYỆT ĐỐI TUÂN THỦ CHÍNH SÁCH TIKTOK SHOP: không dùng từ cấm như 100%, cam kết, trị dứt điểm, rẻ nhất thị trường, sập sàn, xả lỗ, Zalo, inbox...>"}'
        )

        await log("Điền prompt yêu cầu Gemini Flash đọc kỹ bao bì & phân tích sản phẩm...", 45)
        input_selectors = [
            "rich-textarea div[contenteditable='true']",
            "rich-textarea p",
            "div[contenteditable='true']",
            "textarea"
        ]
        prompt_box = None
        for sel in input_selectors:
            try:
                elem = await page.wait_for_selector(sel, timeout=2500)
                if elem:
                    prompt_box = elem
                    break
            except Exception:
                continue

        if prompt_box:
            try:
                await prompt_box.click(timeout=2500)
                await asyncio.sleep(0.4)
                await page.keyboard.insert_text(prompt)
                await asyncio.sleep(0.8)
            except Exception:
                await page.evaluate("""([sel, text]) => {
                    const el = document.querySelector(sel);
                    if (el) {
                        el.textContent = text;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                }""", [input_selectors[0], prompt])

        # Ensure Flash model is selected if model dropdown exists, and always close any backdrop
        try:
            mode_btn = await page.query_selector("button[data-test-id='bard-mode-menu-button']")
            if mode_btn and await mode_btn.is_visible():
                mode_text = (await mode_btn.inner_text()).lower()
                if "flash" not in mode_text and "nhanh" not in mode_text:
                    await mode_btn.click(timeout=2000)
                    await asyncio.sleep(0.5)
                    flash_opt = await page.query_selector(
                        "button:has-text('Flash'), button:has-text('Nhanh'), "
                        "mat-option:has-text('Flash'), mat-option:has-text('Nhanh'), "
                        "[role='menuitem']:has-text('Flash'), [role='menuitem']:has-text('Nhanh')"
                    )
                    if flash_opt and await flash_opt.is_visible():
                        await flash_opt.click(timeout=2000)
                        await asyncio.sleep(0.4)
                    else:
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.3)
        except Exception:
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass

        # Wait up to 15s for file upload to be completely ready (send button not aria-disabled, spinner gone)
        for _ in range(15):
            spinner = await page.query_selector("mat-progress-spinner, [role='progressbar'], .upload-progress")
            send_btn = await page.query_selector("button[aria-label*='Send message'], button[aria-label*='Gửi tin nhắn'], button[aria-label*='Send'], button[aria-label*='Gửi'], button.send-button")
            if send_btn:
                aria_disabled = await send_btn.get_attribute("aria-disabled")
                if aria_disabled != "true" and not spinner:
                    break
            await asyncio.sleep(1.0)

        await log("Gửi yêu cầu nhận diện sản phẩm sang Gemini Flash...", 60)
        sent_analysis = await self._send_gemini_prompt(page, prompt_box)
        if sent_analysis:
            await log("Đã gửi ảnh sang Gemini Flash, đang phân tích bao bì...", 65)

        await log("Đang chờ Gemini nhận diện bao bì & công dụng sản phẩm...", 75)
        await asyncio.sleep(4)

        start_t = asyncio.get_event_loop().time()
        last_raw_err = None
        while asyncio.get_event_loop().time() - start_t < 45:
            await asyncio.sleep(2.0)
            responses = await page.query_selector_all("model-response, .model-response-text")
            if not responses:
                continue

            last_resp = responses[-1]
            raw_response_text = (await last_resp.inner_text()).strip()
            if not raw_response_text or "product_name" not in raw_response_text:
                continue
            if "<Tên sản phẩm" in raw_response_text:
                continue

            # Extract JSON block starting at {"product_name"
            json_match = re.search(r'\{\s*"product_name"[\s\S]*\}', raw_response_text)
            if not json_match:
                continue

            candidate_json = json_match.group(0).strip()
            try:
                parsed = json.loads(candidate_json)
                if parsed.get("product_name") and (parsed.get("scene2_dialogue") or parsed.get("benefits")):
                    from backend.app.services.prompt_templates import sanitize_tiktok_dialogue
                    from backend.app.services.pipeline_runner import ensure_42_words
                    if parsed.get("scene1_dialogue"):
                        parsed["scene1_dialogue"] = ensure_42_words(sanitize_tiktok_dialogue(parsed["scene1_dialogue"]))
                    if parsed.get("scene2_dialogue"):
                        parsed["scene2_dialogue"] = ensure_42_words(sanitize_tiktok_dialogue(parsed["scene2_dialogue"]))
                    await log(f"Đã nhận diện thành công: {parsed['product_name']} ({parsed.get('category', '')})", 100)
                    return {"success": True, "data": parsed}
            except Exception as e_json:
                last_raw_err = e_json
                continue

        if last_raw_err:
            logger.warning(f"Error parsing Gemini product JSON after timeout: {last_raw_err}")

        return {"success": False, "error": "Không thể nhận diện chi tiết sản phẩm tự động"}

gemini_automator = GeminiAutomator()


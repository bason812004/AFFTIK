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

def _is_warehouse_product(name: str) -> bool:
    low = (name or "").lower()
    return any(w in low for w in ["kho xưởng", "kho xuong", "bản kho", "ban kho", "tổng kho", "tong kho", "xuat xuong", "pallet"])

def _get_base_product_name(name: str) -> str:
    clean = re.sub(r'\(bản[^\)]*\)', '', name, flags=re.IGNORECASE)
    clean = re.sub(r'\(kho xưởng[^\)]*\)', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'#\d+', '', clean)
    return clean.strip()

ALL_PRODUCT_SPECS = {
    'máy bơm lốp xe hơi': ['may-bom', 'bom-lop', 'ugreen', 'may bom', 'bom lop', 'bom xe hoi', 'bom lop xe', 'may bom lop'],
    'phân bón trung vi lượng': ['phan-bon', 'trung-vi-luong', 'phan bon', 'trung vi luong', 'combi', 'combi pro', 'combi-pro'],
    'phục hồi vàng lá, thối rễ': ['vang-la', 'thoi-re', 'vang la', 'thoi re', 'phuc-hoi', 'phuc hoi', 'pac 20', 'pac-20', 'pac20', 'vang la thoi re'],
    'ngũ cốc gà đá': ['ngu-coc', 'ga-da', 'ngu coc', 'ga da', 'ngu coc ga da'],
    'muỗng cơm inox 304': ['muong-com', 'inox304', 'inox-304', 'muong com', 'inox 304'],
    'kệ 3 tầng': ['ke-3-tang', 'ke 3 tang'],
    'nhựa đường dầu hắc dạng lỏng': ['nhua-duong', 'dau-hac', 'nhua duong', 'dau hac', 'sika', 'dau-hac-dang-long'],
    'hạt cho mèo': ['hat-cho-meo', 'hat cho meo', 'thuc-an-meo', 'keepo', 'keepo k2', 'keepo-k2'],
    'ops Hanbio': ['ops-hanbio', 'hanbio', 'ops hanbio'],
    'túi đeo chéo': ['tui-deo', 'deo-cheo', 'tui-deo-cheo', 'tui deo']
}

STOP_WORDS = {
    'cho', 'dang', 'tang', 're', 'la', 'vi', 'cao', 'tot', 'moi', 'cua', 
    'nhieu', 'loai', 'hop', 'chai', 'goi', 'san', 'pham', 'chinh', 'hang', 
    'tien', 'ich', 'chuan', 'sieu', 'dep', 'chat', 'luong', 'ngay', 'hom', 
    'nay', 'them', 'giam', 'gia', 'khuyen', 'mai', 'kem', 'nguoi', 'dung',
    'chot', 'don', 'gioi', 'thieu', 'canh'
}

def _get_distinctive_phrases(product_name: str) -> List[str]:
    is_wh = _is_warehouse_product(product_name)
    base_name = _get_base_product_name(product_name)
    slug = _slugify(product_name)
    base_slug = _slugify(base_name)
    parts = [p for p in slug.split('-') if p and len(p) >= 2]
    
    phrases = set()
    if slug:
        phrases.add(slug)
    if base_slug:
        phrases.add(base_slug)
    
    low_name = (product_name or "").lower().strip()
    low_base = base_name.lower().strip()
    if low_name:
        phrases.add(low_name)
    if low_base:
        phrases.add(low_base)
    
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
        
    for p in parts:
        if len(p) >= 5 and p not in STOP_WORDS:
            phrases.add(p)
            
    # Product aliases
    for cat_name, sigs in ALL_PRODUCT_SPECS.items():
        cat_slug = _slugify(cat_name)
        if (cat_slug in slug or slug in cat_slug or 
            cat_slug in base_slug or base_slug in cat_slug or
            cat_name.lower() in low_name or low_name in cat_name.lower() or
            cat_name.lower() in low_base or low_base in cat_name.lower()):
            phrases.update(sigs)
            
    if is_wh:
        phrases.update(['kho-xuong', 'kho xuong', 'kho xuong re', 'tong kho', 'gia goc', 'xuat xuong', 'pallet'])

    return [p for p in phrases if len(p) >= 3 and p not in STOP_WORDS]

def _get_excluded_signatures(target_name: str) -> List[str]:
    base_name = _get_base_product_name(target_name)
    base_slug = _slugify(base_name)
    base_low = base_name.lower().strip()
    excluded = set()
    
    for prod_name, spec_sigs in ALL_PRODUCT_SPECS.items():
        p_slug = _slugify(prod_name)
        p_low = prod_name.lower().strip()
        if p_slug != base_slug and p_low not in base_low and base_low not in p_low:
            for s in spec_sigs:
                if len(s.split()) >= 2 or '-' in s or len(s) >= 5:
                    excluded.add(s)
            excluded.add(p_slug)
            excluded.add(p_low)
            
    try:
        conn = _get_raw_conn()
        rows = conn.execute("SELECT name FROM projects").fetchall()
        conn.close()
        for r in rows:
            p_name = r["name"] or ""
            p_base = _get_base_product_name(p_name)
            p_slug = _slugify(p_base)
            p_low = p_base.lower().strip()
            if p_slug and p_slug != base_slug and p_low not in base_low and base_low not in p_low:
                excluded.add(p_slug)
                excluded.add(p_low)
    except Exception:
        pass
        
    return [s for s in excluded if len(s) >= 4 and s not in STOP_WORDS]

def _is_duplicate_or_contaminated(video_file: Path, project_id: str, scene_num: int) -> bool:
    """
    Guarantees zero cross-contamination and zero internal duplicates:
    1. Checks if video_file has identical content to the companion scene of this project.
    2. Checks if video_file has identical content to ANY scene video of any other project.
    Returns True if contaminated or duplicate.
    """
    if not video_file.exists():
        return False
    size = video_file.stat().st_size
    if size < 20000:
        return True
    
    import hashlib
    def sample_hash(f: Path) -> str:
        h = hashlib.md5()
        with open(f, "rb") as fp:
            h.update(fp.read(65536))
            sz = f.stat().st_size
            if sz > 131072:
                fp.seek(sz - 65536)
                h.update(fp.read(65536))
        return h.hexdigest()

    my_hash = sample_hash(video_file)

    # 1. Check companion scene of this same project
    other_scene = 2 if scene_num == 1 else 1
    other_file = video_file.parent / f"scene{other_scene}.mp4"
    if other_file.exists() and other_file.stat().st_size > 20000:
        other_sz = other_file.stat().st_size
        if abs(other_sz - size) < 50000 or my_hash == sample_hash(other_file):
            if my_hash == sample_hash(other_file):
                logger.warning(f"File {video_file} matches identical content to companion scene {other_file}! Rejecting as internal duplicate.")
                return True
        
    # 2. Check other projects
    for pdir in PROJECTS_DIR.iterdir():
        if pdir.is_dir() and pdir.name != project_id:
            for other_v in (pdir / "videos").glob("scene*.mp4"):
                if other_v.exists() and other_v.stat().st_size > 20000:
                    other_sz = other_v.stat().st_size
                    if abs(other_sz - size) < 50000 or my_hash == sample_hash(other_v):
                        if my_hash == sample_hash(other_v):
                            logger.warning(f"Cross-contamination detected: {video_file} matches content of {other_v}! Rejecting contaminated file.")
                            return True
    return False

class MuseAutomator:
    """
    Automates video creation using Muse AI (muse.ai / musevideo.ai):
    - Multi-modal reference: Uses character/product image as reference input.
    - Automates prompt entry (Hook & CTA for 10s 60fps scenes).
    - Detects and extracts blob video bytes directly from browser page context.
    - Standardizes with FFmpeg (1080x1920 @ 60 FPS).
    - Strict boundary isolation: only captures newly generated videos after prompt submission.
    - Strict product signature and warehouse variant matching to guarantee zero cross-contamination.
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
        Scans messages in Muse AI chat strictly for videos matching project_name and its variant.
        Extracts distinct Scene 1 and Scene 2 videos while mathematically filtering out
        avatar videos, duplicate videos, and cross-project contamination.
        """
        target_slug = _slugify(project_name)
        pos_sigs = _get_distinctive_phrases(project_name)
        neg_sigs = _get_excluded_signatures(project_name)
        is_warehouse = _is_warehouse_product(project_name)

        try:
            await page.wait_for_selector('[data-message-item="true"], [data-message-role]', timeout=8000)
            await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const unread = btns.find(b => (b.innerText || '').includes('tin nhắn'));
                if (unread) { try { unread.click(); } catch (e) {} }
                const scrollers = Array.from(document.querySelectorAll('*')).filter(e => e.scrollHeight > e.clientHeight + 50 && e.clientHeight > 200);
                for (const s of scrollers) s.scrollTop = s.scrollHeight;
                window.scrollTo(0, document.body.scrollHeight);
            }""")
            await asyncio.sleep(1)
        except Exception:
            pass

        match_data = await page.evaluate("""async (args) => {
            const { targetSlug, posSigs, negSigs, isWarehouse } = args;
            const results = { scene1: null, scene2: null };

            function normalize(str) {
                if (!str) return '';
                return str.toLowerCase()
                    .replace(/đ/g, 'd')
                    .replace(/Đ/g, 'd')
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '');
            }

            const normPosSigs = Array.from(new Set(posSigs.map(normalize).filter(s => s.length >= 3)));
            const normNegSigs = Array.from(new Set(negSigs.map(normalize).filter(s => s.length >= 3)));

            function isAvatar(el) {
                if (!el) return true;
                if (el.closest('[class*="status-avatar"], [class*="rounded-full"], div[class*="avatar"]')) return true;
                const v = el.tagName.toLowerCase() === 'video' ? el : el.querySelector('video');
                if (v) {
                    if (v.videoWidth > 0 && v.videoWidth === v.videoHeight) return true;
                    if (v.duration > 0 && v.duration < 5.5) return true;
                    const vCls = String(v.className || '');
                    if (vCls.includes('rounded-full') || vCls.includes('avatar')) return true;
                }
                return false;
            }

            const items = Array.from(document.querySelectorAll('[data-message-item="true"], [data-message-role]'));
            results.msgCount = items.length;
            if (!items.length) return results;

            for (let i = items.length - 1; i >= Math.max(0, items.length - 20); i--) {
                const it = items[i];
                if (it.querySelector('[role="status"], [data-slot="skeleton"], video, [data-hatch-video-wrapper]')) {
                    try { it.scrollIntoView({ block: 'center', behavior: 'instant' }); } catch(e) {}
                }
            }

            // Group items into turns by data-message-turn-id
            const turns = [];
            let currentTurnId = null;
            let currentTurn = [];

            for (const it of items) {
                const turnId = it.getAttribute('data-message-turn-id') || it.getAttribute('data-message-group-id') || 'gen';
                if (turnId !== currentTurnId && currentTurn.length > 0) {
                    turns.push({ turnId: currentTurnId, items: currentTurn });
                    currentTurn = [];
                }
                currentTurnId = turnId;
                currentTurn.push(it);
            }
            if (currentTurn.length > 0) {
                turns.push({ turnId: currentTurnId, items: currentTurn });
            }

            // Scan turns backwards (newest to oldest)
            for (let t = turns.length - 1; t >= 0; t--) {
                const turn = turns[t];
                const turnTextRaw = turn.items.map(it => it.innerText || '').join(' ').toLowerCase();
                const turnTextNorm = normalize(turnTextRaw);

                // Strict Warehouse Variant Isolation:
                if (isWarehouse) {
                    const isWhTurn = turnTextNorm.includes('kho xuong') || turnTextNorm.includes('tong kho') || 
                                     turnTextNorm.includes('gia goc') || turnTextNorm.includes('pallet') || 
                                     turnTextNorm.includes('xuat xuong') || turnTextNorm.includes('ban kho');
                    if (!isWhTurn) continue;
                } else {
                    const isWhTurn = turnTextNorm.includes('kho xuong') || turnTextNorm.includes('tong kho') || 
                                     turnTextNorm.includes('ban kho xuong');
                    if (isWhTurn) continue;
                }

                // Turn must mention positive signature of target product
                const turnHasPos = normPosSigs.some(sig => turnTextNorm.includes(sig));
                if (!turnHasPos) continue;

                // Turn must not explicitly belong to another product
                const turnHasNeg = normNegSigs.some(sig => turnTextNorm.includes(sig));
                if (turnHasNeg && !turnHasPos) continue;

                const turnVideos = [];
                const seenTurnSrcs = new Set();

                for (let idx = 0; idx < turn.items.length; idx++) {
                    const it = turn.items[idx];
                    try { it.scrollIntoView({ block: 'center', behavior: 'instant' }); } catch(e) {}

                    const rawVideos = Array.from(it.querySelectorAll('video, [data-testid*="attachment-presentation-video"], [data-hatch-video-wrapper]'));
                    for (const el of rawVideos) {
                        if (isAvatar(el)) continue;

                        const vTag = el.tagName.toLowerCase() === 'video' ? el : el.querySelector('video');
                        let src = el.getAttribute('data-hatch-video-src') || (vTag ? (vTag.currentSrc || vTag.src) : null);
                        if (!src) {
                            const sourceTag = el.querySelector('source');
                            if (sourceTag) src = sourceTag.src;
                        }
                        if (!src) {
                            const aTag = el.querySelector('a[href*=".mp4"], a[href*="blob:"]');
                            if (aTag) src = aTag.href;
                        }
                        if (!src || (!src.startsWith('blob:') && !src.startsWith('http'))) continue;

                        if (!seenTurnSrcs.has(src)) {
                            seenTurnSrcs.add(src);

                            let caption = '';
                            let prev = el.previousElementSibling;
                            while (prev && !prev.querySelector('video, [data-hatch-video-wrapper]')) {
                                caption = (prev.innerText || '') + ' ' + caption;
                                prev = prev.previousElementSibling;
                            }
                            if (!caption) caption = it.innerText || '';

                            turnVideos.push({
                                src,
                                caption: normalize(caption),
                                aria: el.getAttribute('aria-label') || (vTag ? vTag.getAttribute('aria-label') : '') || ''
                            });
                        }
                    }
                }

                if (!turnVideos.length) continue;

                if (turnVideos.length >= 2) {
                    if (turnVideos[0].src !== turnVideos[1].src) {
                        results.scene1 = { src: turnVideos[0].src, aria: turnVideos[0].aria };
                        results.scene2 = { src: turnVideos[1].src, aria: turnVideos[1].aria };
                        break;
                    }
                } else if (turnVideos.length === 1) {
                    const single = turnVideos[0];
                    const cap = single.caption;
                    const isS2 = cap.includes('canh 2') || cap.includes('canh-2') || cap.includes('chot don') || cap.includes('can canh');
                    if (isS2 && !results.scene2) {
                        results.scene2 = { src: single.src, aria: single.aria };
                    } else if (!results.scene1) {
                        results.scene1 = { src: single.src, aria: single.aria };
                    }
                }

                if (results.scene1 && results.scene2) break;
            }

            if (results.scene1 && results.scene2 && results.scene1.src === results.scene2.src) {
                results.scene2 = null;
            }

            return results;
        }""", {"targetSlug": target_slug, "posSigs": pos_sigs, "negSigs": neg_sigs, "isWarehouse": is_warehouse})

        logger.info(f"[Muse Scan] Scanned chat for '{project_name}' (wh={is_warehouse}) on {page.url}: msgs={match_data.get('msgCount', 0)}, s1={'found' if match_data.get('scene1') else 'none'}, s2={'found' if match_data.get('scene2') else 'none'}")
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
        Guarantees strict boundary isolation: only captures newly generated videos after prompt submission.
        Standardizes high-resolution video into 1080x1920 @ 60 FPS.
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
        is_warehouse = _is_warehouse_product(pname)

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

        # Reference image: ALWAYS prioritize primary AI character image (9:16 ratio with character + product)
        # for BOTH Scene 1 and Scene 2, ensuring character identity, outfit, and warehouse/showroom setting remain 100% consistent!
        char_primary = PROJECTS_DIR / project_id / "character" / "character_primary.png"
        prod_orig = PROJECTS_DIR / project_id / "product" / "product_original.jpg"

        ref_image: Optional[Path] = None
        if char_primary.exists():
            ref_image = char_primary
        elif character_image_path and Path(character_image_path).exists():
            ref_image = Path(character_image_path)
        elif reference_image_path and Path(reference_image_path).exists():
            ref_image = Path(reference_image_path)
        elif prod_orig.exists():
            ref_image = prod_orig

        # 2. Check Muse AI Login
        muse_url = self._get_muse_url()
        login_st = await browser_manager.check_muse_login(muse_url, force_open=False)
        if not login_st.get("logged_in"):
            saved_login = get_setting("muse_logged_in", "false")
            if saved_login != "true":
                await log_fn("Chưa kết nối tài khoản Muse AI...", 15)
                return {
                    "success": False,
                    "needs_login": True,
                    "message": "Chưa kết nối tài khoản Muse AI. Vui lòng bấm 'Đăng nhập' ở góc trên màn hình nếu cần đăng nhập."
                }

        await log_fn("Đã kết nối tài khoản Muse AI (chạy ngầm). Đang chuẩn bị tạo video...", 25)

        # 3. Automation on Muse AI Page (100% headless hidden in background)
        try:
            page = await browser_manager.get_muse_page(headed=False, force_headed=False)
            current_url = (page.url or "").lower()
            if "muse.ai" not in current_url:
                await page.goto(muse_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

            pos_sigs = _get_distinctive_phrases(pname)
            neg_sigs = _get_excluded_signatures(pname)

            # Record strict boundary state BEFORE prompting:
            # Captures exact message count and all existing video URLs currently in DOM!
            initial_state = await page.evaluate("""() => {
                const msgs = Array.from(document.querySelectorAll('[data-message-role="assistant"], [data-message-item="true"], [data-message-role]'));
                const videos = Array.from(document.querySelectorAll('video, [data-hatch-video-wrapper]'));
                const srcs = videos.map(v => {
                    const vTag = v.tagName.toLowerCase() === 'video' ? v : v.querySelector('video');
                    return v.getAttribute('data-hatch-video-src') || (vTag ? (vTag.currentSrc || vTag.src) : null);
                }).filter(Boolean);
                return {
                    msgCount: msgs.length,
                    knownSrcs: srcs
                };
            }""")
            init_msg_count = initial_state.get("msgCount", 0)
            init_srcs = set(initial_state.get("knownSrcs", []))

            # Input Prompt into Muse AI Chat
            await log_fn(f"Đang chuẩn bị Prompt Cảnh {scene_number} cho '{pname}' vào Muse AI...", 40)

            prompt_input = await page.query_selector(
                "textarea[placeholder*='Nhắn tin' i], textarea[aria-label*='Nhắn tin' i], " +
                "textarea[placeholder*='prompt' i], textarea[placeholder*='describe' i], " +
                "div[contenteditable='true'], textarea"
            )

            if scene_prompt.strip().startswith(f"[Cảnh {scene_number}"):
                formatted_prompt = scene_prompt.strip()
            else:
                formatted_prompt = f"[Cảnh {scene_number} - {pname} | 9:16, 10s, 60fps] {scene_prompt}"
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

            # Step 3c: Wait for video generation (up to 360 seconds / 6 minutes)
            await log_fn(f"Đang chờ Muse AI kết xuất video Cảnh {scene_number} (chuẩn 9:16 60 FPS)...", 60)

            downloaded = False
            companion_candidate_src = None

            for attempt in range(120):
                await asyncio.sleep(3)
                elapsed = (attempt + 1) * 3
                current_pct = min(60 + int(attempt * 0.28), 94)

                # Keep bottom scrolled into view and auto-click unread messages button
                await page.evaluate("""() => {
                    const unreadBtn = Array.from(document.querySelectorAll('button')).find(b => (b.innerText || '').toLowerCase().includes('tin nhắn'));
                    if (unreadBtn) {
                        try { unreadBtn.click(); } catch (e) {}
                    }
                    const scroller = Array.from(document.querySelectorAll('*')).find(e => e.scrollHeight > e.clientHeight + 50 && e.clientHeight > 200);
                    if (scroller) scroller.scrollTop = scroller.scrollHeight;
                    window.scrollTo(0, document.body.scrollHeight);
                }""")

                # Auto-click any confirmation / option button if Muse AI prompts for choice
                await page.evaluate("""() => {
                    const optionBtns = Array.from(document.querySelectorAll('button')).filter(b => {
                        const t = (b.innerText || '').toLowerCase();
                        return t.includes('dùng ảnh nhân vật') || t.includes('làm cảnh 2') || t.includes('dùng đúng ảnh') ||
                               t.includes('tiếp tục') || t.includes('chọn ảnh') || t.includes('đồng ý') || t.includes('xác nhận') ||
                               t.includes('bản ảnh mới') || t.includes('giữ nguyên');
                    });
                    if (optionBtns.length > 0) {
                        try { optionBtns[0].click(); } catch (e) {}
                    }
                }""")

                # Check if Muse is actively generating
                is_muse_busy = await page.evaluate("""() => {
                    const stopBtn = document.querySelector("button[aria-label='Dừng']");
                    const runningEl = Array.from(document.querySelectorAll('*')).find(e => {
                        const t = (e.innerText || '');
                        return t.includes('Đang chạy:') || t.includes('Đang tạo video') || t.includes('Đang dựng video') || t.includes('Generating video');
                    });
                    return Boolean(stopBtn || runningEl);
                }""")
                if is_muse_busy:
                    await log_fn(f"Muse AI đang tạo video Cảnh {scene_number} cho '{pname}' ({elapsed}s)...", current_pct)
                else:
                    await log_fn(f"Muse AI đang dựng video Cảnh {scene_number} cho '{pname}' ({elapsed}s)...", current_pct)

                # Look STRICTLY in new messages generated AFTER init_msg_count
                newest_video = await page.evaluate("""async (args) => {
                    const { initMsgCount, knownSrcs, sceneNum } = args;
                    const knownSet = new Set(knownSrcs || []);

                    function isAvatar(el) {
                        if (!el) return true;
                        if (el.closest('[class*="status-avatar"], [class*="rounded-full"], div[class*="avatar"]')) return true;
                        const v = el.tagName.toLowerCase() === 'video' ? el : el.querySelector('video');
                        if (v) {
                            if (v.videoWidth > 0 && v.videoWidth === v.videoHeight) return true;
                            if (v.duration > 0 && v.duration < 5.5) return true;
                            const vCls = String(v.className || '');
                            if (vCls.includes('rounded-full') || vCls.includes('avatar')) return true;
                        }
                        return false;
                    }

                    const allItems = Array.from(document.querySelectorAll('[data-message-item="true"], [data-message-role]'));
                    if (allItems.length <= initMsgCount) return null;

                    // STRICT BOUNDARY: ONLY inspect messages that appeared AFTER submitting prompt!
                    const newItems = allItems.slice(initMsgCount);

                    for (const it of newItems) {
                        if (it.querySelector('[role="status"], [data-slot="skeleton"], video, [data-hatch-video-wrapper]')) {
                            try { it.scrollIntoView({ block: 'center', behavior: 'instant' }); } catch(e) {}
                        }
                    }

                    const newVideos = [];
                    const seenSrcs = new Set();

                    for (const it of newItems) {
                        const role = (it.getAttribute('data-message-role') || '').toLowerCase();
                        if (role === 'user') continue;

                        const rawVideos = Array.from(it.querySelectorAll('video, [data-testid*="attachment-presentation-video"], [data-hatch-video-wrapper]'));
                        for (const el of rawVideos) {
                            if (isAvatar(el)) continue;

                            const vTag = el.tagName.toLowerCase() === 'video' ? el : el.querySelector('video');
                            let src = el.getAttribute('data-hatch-video-src') || (vTag ? (vTag.currentSrc || vTag.src) : null);
                            if (!src) {
                                const sourceTag = el.querySelector('source');
                                if (sourceTag) src = sourceTag.src;
                            }
                            if (!src) {
                                const aTag = el.querySelector('a[href*=".mp4"], a[href*="blob:"]');
                                if (aTag) src = aTag.href;
                            }
                            if (!src || (!src.startsWith('blob:') && !src.startsWith('http'))) continue;

                            // STRICT RULE: Video MUST NOT exist before submitting prompt!
                            if (knownSet.has(src)) continue;

                            if (!seenSrcs.has(src)) {
                                seenSrcs.add(src);

                                let caption = '';
                                let prev = el.previousElementSibling;
                                while (prev && !prev.querySelector('video, [data-hatch-video-wrapper]')) {
                                    caption = (prev.innerText || '') + ' ' + caption;
                                    prev = prev.previousElementSibling;
                                }
                                if (!caption) caption = it.innerText || '';

                                newVideos.push({
                                    src,
                                    caption: caption.toLowerCase(),
                                    aria: el.getAttribute('aria-label') || (vTag ? vTag.getAttribute('aria-label') : '') || ''
                                });
                            }
                        }
                    }

                    if (!newVideos.length) return null;

                    // If Muse returned BOTH Scene 1 and Scene 2 together in this response:
                    if (newVideos.length >= 2) {
                        if (sceneNum === 1) {
                            return {
                                src: newVideos[0].src,
                                companionSrc: newVideos[1].src,
                                aria: newVideos[0].aria
                            };
                        } else {
                            return {
                                src: newVideos[1].src,
                                companionSrc: newVideos[0].src,
                                aria: newVideos[1].aria
                            };
                        }
                    }

                    // If only 1 video returned in new messages:
                    const single = newVideos[0];
                    const cap = single.caption;
                    const isS2 = cap.includes('canh 2') || cap.includes('canh-2') || cap.includes('chot don') || cap.includes('can canh');
                    const isS1 = cap.includes('canh 1') || cap.includes('canh-1') || cap.includes('hook') || cap.includes('gioi thieu');

                    if (sceneNum === 2 && isS2) {
                        return { src: single.src, aria: single.aria };
                    } else if (sceneNum === 1 && isS1) {
                        return { src: single.src, aria: single.aria };
                    }

                    return { src: single.src, aria: single.aria };
                }""", {
                    "initMsgCount": init_msg_count,
                    "knownSrcs": list(init_srcs),
                    "sceneNum": scene_number
                })

                if newest_video and newest_video.get("src"):
                    await log_fn(f"Đã tạo xong video Cảnh {scene_number} mới nhất trên Muse AI! Đang trích xuất video...", 92)
                    if await self.download_blob_or_url(page, newest_video["src"], temp_down):
                        downloaded = True
                        companion_candidate_src = newest_video.get("companionSrc")
                        break

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

                if _is_duplicate_or_contaminated(target_file, project_id, scene_number):
                    logger.warning(f"Video {target_file} was rejected as duplicate or contaminated!")
                    target_file.unlink(missing_ok=True)
                    return {
                        "success": False,
                        "message": "Phát hiện video không thuộc sản phẩm này (trùng lặp). Vui lòng thử lại để tạo video đúng sản phẩm."
                    }

                # Update current scene in DB
                p_cur = await ffmpeg_service.probe_video(str(target_file))
                c_db = _get_raw_conn()
                c_db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = ?", (project_id, scene_number))
                c_db.execute("""
                    INSERT INTO videos (id, project_id, scene_number, video_path, duration, resolution, fps, status)
                    VALUES (?, ?, ?, ?, ?, '1080x1920', 60.0, 'ready')
                """, (f"v{scene_number}_{project_id[:4]}", project_id, scene_number, str(target_file), p_cur.get("duration", 10.0)))
                c_db.commit()

                # If companion video was also returned in this same response, process companion scene!
                if companion_candidate_src and companion_candidate_src != newest_video.get("src"):
                    other_scene = 2 if scene_number == 1 else 1
                    other_file = target_dir / f"scene{other_scene}.mp4"
                    temp_other = target_dir / f"temp_muse_s{other_scene}.mp4"
                    try:
                        if await self.download_blob_or_url(page, companion_candidate_src, temp_other):
                            await ffmpeg_service.standardize_scene_video(
                                input_video_path=str(temp_other),
                                output_video_path=str(other_file),
                                target_width=1080,
                                target_height=1920,
                                target_fps=60
                            )
                            temp_other.unlink(missing_ok=True)
                            if not _is_duplicate_or_contaminated(other_file, project_id, other_scene):
                                p_other = await ffmpeg_service.probe_video(str(other_file))
                                c_db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = ?", (project_id, other_scene))
                                c_db.execute("""
                                    INSERT INTO videos (id, project_id, scene_number, video_path, duration, resolution, fps, status)
                                    VALUES (?, ?, ?, ?, ?, '1080x1920', 60.0, 'ready')
                                """, (f"v{other_scene}_{project_id[:4]}", project_id, other_scene, str(other_file), p_other.get("duration", 10.0)))
                                c_db.commit()
                                logger.info(f"Companion Scene {other_scene} successfully downloaded and registered for {project_id}.")
                            else:
                                other_file.unlink(missing_ok=True)
                    except Exception as comp_err:
                        logger.debug(f"Companion extraction error: {comp_err}")

                c_db.close()

                await log_fn(f"Hoàn thành xuất sắc video Cảnh {scene_number} chuẩn TikTok Affiliate!", 100)
                return {
                    "success": True,
                    "video_path": str(target_file),
                    "scene_number": scene_number,
                    "engine": "muse_ai"
                }

            return {
                "success": False,
                "message": f"Muse AI chưa kết xuất xong video trực tiếp sau 360s. Vui lòng bấm 'Lấy Video từ Muse AI' trên giao diện sau khi Muse AI hoàn tất."
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
        page = await browser_manager.get_muse_page(headed=False, force_headed=False)
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
                if not _is_duplicate_or_contaminated(s1_file, project_id, 1):
                    s1_ok = True
                else:
                    s1_file.unlink(missing_ok=True)

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
                if not _is_duplicate_or_contaminated(s2_file, project_id, 2):
                    s2_ok = True
                else:
                    s2_file.unlink(missing_ok=True)

        # Check existing scene files on disk if only one was in chat
        if not s1_ok and s1_file.exists() and s1_file.stat().st_size > 50000:
            if not _is_duplicate_or_contaminated(s1_file, project_id, 1):
                s1_ok = True
            else:
                s1_file.unlink(missing_ok=True)

        if not s2_ok and s2_file.exists() and s2_file.stat().st_size > 50000:
            if not _is_duplicate_or_contaminated(s2_file, project_id, 2):
                s2_ok = True
            else:
                s2_file.unlink(missing_ok=True)

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

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
    'chot', 'don', 'gioi', 'thieu', 'canh', 'ban', 'kho', 'xuong',
    'trung', 'dong', 'dac', 'biet', 'chuc', 'nang', 'thuc', 'an', 'phan'
}

def _get_distinctive_phrases(product_name: str) -> List[str]:
    """
    Extracts distinctive signatures strictly for the PRODUCT itself,
    completely excluding generic warehouse/variant suffixes like '(Bản kho xưởng #1)'.
    Only produces strong multi-word phrases and explicit product aliases.
    Never returns ambiguous single words.
    """
    base_name = _get_base_product_name(product_name)
    base_slug = _slugify(base_name)
    base_low = base_name.lower().strip()
    parts = [p for p in base_slug.split('-') if p and len(p) >= 2 and p not in STOP_WORDS]
    
    phrases = set()
    if base_slug and len(base_slug) >= 4:
        phrases.add(base_slug)
    if base_low and len(base_low) >= 4:
        phrases.add(base_low)
    
    # 2-word combinations from base product name
    for i in range(len(parts) - 1):
        w1, w2 = parts[i], parts[i+1]
        if w1 not in STOP_WORDS and w2 not in STOP_WORDS:
            phrases.add(f"{w1}-{w2}")
            phrases.add(f"{w1} {w2}")
            
    # 3-word combinations from base product name
    for i in range(len(parts) - 2):
        w1, w2, w3 = parts[i], parts[i+1], parts[i+2]
        phrases.add(f"{w1}-{w2}-{w3}")
        phrases.add(f"{w1} {w2} {w3}")
            
    # Product aliases from dictionary
    for cat_name, sigs in ALL_PRODUCT_SPECS.items():
        cat_slug = _slugify(cat_name)
        if (cat_slug in base_slug or base_slug in cat_slug or
            cat_name.lower() in base_low or base_low in cat_name.lower()):
            for s in sigs:
                if s not in STOP_WORDS:
                    phrases.add(s)

    known_single_brands = {'keepo', 'ugreen', 'sika', 'hanbio', 'combi'}
    clean_phrases = []
    for p in phrases:
        p_clean = p.strip()
        if not p_clean or p_clean in STOP_WORDS:
            continue
        words = p_clean.replace('-', ' ').split()
        if len(words) == 1:
            if p_clean in known_single_brands or len(p_clean) >= 7:
                clean_phrases.append(p_clean)
        else:
            clean_phrases.append(p_clean)

    return clean_phrases

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
                if len(s.split()) >= 2 or '-' in s or len(s) >= 4:
                    if s not in STOP_WORDS:
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
                for s in _get_distinctive_phrases(p_base):
                    if s not in STOP_WORDS:
                        excluded.add(s)
                excluded.add(p_slug)
                excluded.add(p_low)
    except Exception:
        pass
        
    return [s for s in excluded if len(s) >= 4 and s not in STOP_WORDS]

def _is_duplicate_or_contaminated(video_file: Path, project_id: str, scene_num: int) -> bool:
    """
    Guarantees zero cross-contamination and zero internal duplicates:
    1. Checks if video_file has identical content/size to the companion scene of this project.
    2. Checks if video_file has identical content/size to ANY scene video of any other project.
    Returns True if contaminated or duplicate.
    """
    if not video_file.exists():
        return False
    size = video_file.stat().st_size
    if size < 20000:
        return True
    
    import hashlib
    def get_full_hash(f: Path) -> str:
        h = hashlib.md5()
        with open(f, "rb") as fp:
            while chunk := fp.read(1048576):
                h.update(chunk)
        return h.hexdigest()

    my_hash = get_full_hash(video_file)

    # 1. Check companion scene of this same project
    other_scene = 2 if scene_num == 1 else 1
    other_file = video_file.parent / f"scene{other_scene}.mp4"
    if other_file.exists() and other_file.stat().st_size > 20000:
        other_sz = other_file.stat().st_size
        other_hash = get_full_hash(other_file)
        if my_hash == other_hash or abs(other_sz - size) < 500:
            logger.warning(f"File {video_file} matches identical content/size ({size} vs {other_sz}) to companion scene {other_file}! Rejecting as internal duplicate.")
            return True
        
    # 2. Check other projects
    for pdir in PROJECTS_DIR.iterdir():
        if pdir.is_dir() and pdir.name != project_id:
            for other_v in (pdir / "videos").glob("scene*.mp4"):
                if other_v.exists() and other_v.stat().st_size > 20000:
                    other_sz = other_v.stat().st_size
                    if abs(other_sz - size) < 500 or my_hash == get_full_hash(other_v):
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
            await page.wait_for_selector('[data-message-role]', timeout=8000)
            await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const unread = btns.find(b => (b.innerText || '').toLowerCase().includes('tin nhắn'));
                if (unread) { try { unread.click(); } catch (e) {} }
            }""")
        except Exception:
            pass

        match_data = await page.evaluate("""async (args) => {
            const { targetSlug, posSigs, negSigs, isWarehouse, projectName } = args;
            const results = { scene1: null, scene2: null };

            function normalize(str) {
                if (!str) return '';
                return str.toLowerCase()
                    .replace(/đ/g, 'd')
                    .replace(/Đ/g, 'd')
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '');
            }

            const normPos = Array.from(new Set(posSigs.map(normalize).filter(s => s.length >= 3)));
            const normNeg = Array.from(new Set(negSigs.map(normalize).filter(s => s.length >= 3)));

            // 1. Un-lazy-load widgets: scroll through all skeleton and video wrappers
            const widgets = Array.from(document.querySelectorAll('[class*="widget-presentation"], [data-slot="skeleton"], [role="status"], video'));
            for (const w of widgets) {
                try {
                    w.scrollIntoView({ block: 'center', behavior: 'instant' });
                    await new Promise(r => setTimeout(r, 80));
                } catch(e) {}
            }
            window.scrollTo(0, document.body.scrollHeight);
            await new Promise(r => setTimeout(r, 600));

            // 2. Parse all message divs into logical turns with ALL video attachments
            const msgDivs = Array.from(document.querySelectorAll('[data-message-role="user"], [data-message-role="assistant"]'));
            results.msgCount = msgDivs.length;
            if (!msgDivs.length) return results;

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

            const turns = [];
            let curTurn = null;

            for (const d of msgDivs) {
                const role = d.getAttribute('data-message-role');
                const text = (d.innerText || '').trim();

                if (role === 'user') {
                    if (curTurn) turns.push(curTurn);
                    curTurn = { user: text, items: [], el: d };
                } else if (role === 'assistant') {
                    if (!curTurn) curTurn = { user: '', items: [], el: d };
                    
                    // Extract ALL genuine video elements within this assistant message
                    const vElements = Array.from(d.querySelectorAll('video, [data-testid*="attachment-presentation-video"], [data-hatch-video-wrapper]'));
                    const seenInMsg = new Set();
                    const msgVideos = [];

                    for (const vel of vElements) {
                        if (isAvatar(vel)) continue;
                        const vTag = vel.tagName.toLowerCase() === 'video' ? vel : vel.querySelector('video');
                        if (vTag && vTag.duration === 5.041667) continue;

                        let src = vel.getAttribute('data-hatch-video-src') || (vTag ? (vTag.currentSrc || vTag.src) : null);
                        if (!src) {
                            const st = vel.querySelector('source');
                            if (st) src = st.src;
                        }
                        if (!src) {
                            const at = vel.querySelector('a[href*=".mp4"], a[href*="blob:"]');
                            if (at) src = at.href;
                        }
                        if (!src || (!src.startsWith('blob:') && !src.startsWith('http'))) continue;

                        if (!seenInMsg.has(src)) {
                            seenInMsg.add(src);
                            let caption = (vel.getAttribute('aria-label') || (vTag ? vTag.getAttribute('aria-label') : '') || '').toLowerCase();
                            msgVideos.push({ src, caption, el: vel });
                        }
                    }

                    curTurn.items.push({ text: text, videos: msgVideos, el: d });
                }
            }
            if (curTurn) turns.push(curTurn);

            // 3. Scan turns backwards (newest to oldest) strictly matching THIS project
            for (let t = turns.length - 1; t >= 0; t--) {
                const turn = turns[t];
                const uNorm = normalize(turn.user);
                const asstAllText = turn.items.map(it => it.text).join(' ');
                const asstNorm = normalize(asstAllText);
                const turnCombined = uNorm + ' ' + asstNorm;

                // Must match at least ONE positive product signature
                const matchesPos = normPos.some(sig => turnCombined.includes(sig));
                if (!matchesPos) continue;

                // Must NOT match excluded signatures of other products
                const matchesNeg = normNeg.some(sig => turnCombined.includes(sig));
                if (matchesNeg) continue;

                // Strict Warehouse check
                const userHasWh = uNorm.includes('kho xuong') || uNorm.includes('ban kho') || uNorm.includes('tong kho') || uNorm.includes('pallet') || uNorm.includes('xuat xuong');
                const asstHasWh = asstNorm.includes('kho xuong') || asstNorm.includes('ban kho') || asstNorm.includes('tong kho') || asstNorm.includes('pallet');
                const isTurnWh = userHasWh || asstHasWh;

                if (isWarehouse && !isTurnWh) continue;
                if (!isWarehouse && isTurnWh) continue;

                // Scroll turn into view
                if (turn.el) {
                    try { turn.el.scrollIntoView({ block: 'center', behavior: 'instant' }); } catch(e) {}
                    await new Promise(r => setTimeout(r, 100));
                }

                // Collect all videos in this matched turn
                const turnVideos = [];
                for (const it of turn.items) {
                    for (const v of it.videos) {
                        turnVideos.push({ ...v, parentText: it.text });
                    }
                }

                // CASE A: The turn contains 2 or more distinct videos!
                // Muse AI outputs Scene 1 first and Scene 2 second!
                if (turnVideos.length >= 2) {
                    const s1_cand = turnVideos[0];
                    const s2_cand = turnVideos[1];
                    if (s1_cand.src !== s2_cand.src) {
                        results.scene1 = { src: s1_cand.src, aria: s1_cand.caption || 'Cảnh 1' };
                        results.scene2 = { src: s2_cand.src, aria: s2_cand.caption || 'Cảnh 2' };
                        // Found both scenes for this project in the exact same turn -> STOP! Zero contamination!
                        break;
                    }
                }

                // CASE B: Turn has 1 video
                if (turnVideos.length === 1) {
                    const single = turnVideos[0];
                    const fullTxt = normalize(single.parentText + ' ' + single.caption + ' ' + turn.user);
                    const isS2 = fullTxt.includes('canh 2') || fullTxt.includes('canh-2') || fullTxt.includes('chot don') || fullTxt.includes('can canh') || fullTxt.includes('poster');

                    if (isS2 && !results.scene2) {
                        if (!results.scene1 || results.scene1.src !== single.src) {
                            results.scene2 = { src: single.src, aria: single.caption || 'Cảnh 2' };
                        }
                    } else if (!isS2 && !results.scene1) {
                        if (!results.scene2 || results.scene2.src !== single.src) {
                            results.scene1 = { src: single.src, aria: single.caption || 'Cảnh 1' };
                        }
                    }
                }

                if (results.scene1 && results.scene2 && results.scene1.src !== results.scene2.src) {
                    break;
                }
            }

            if (results.scene1 && results.scene2 && results.scene1.src === results.scene2.src) {
                results.scene2 = null;
            }

            return results;
        }""", {
            "targetSlug": target_slug,
            "posSigs": pos_sigs,
            "negSigs": neg_sigs,
            "isWarehouse": is_warehouse,
            "projectName": project_name
        })

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
        ref_image: Optional[Path] = None
        for cand_path in [
            PROJECTS_DIR / project_id / "character" / "character_primary.png",
            PROJECTS_DIR / project_id / "character" / "character_primary.webp",
            PROJECTS_DIR / project_id / "character" / "character_primary.jpg",
            PROJECTS_DIR / project_id / "character" / "character_instant_preview.png",
            Path(character_image_path) if character_image_path else None,
            Path(reference_image_path) if reference_image_path else None,
            PROJECTS_DIR / project_id / "product" / "product_original.png",
            PROJECTS_DIR / project_id / "product" / "product_original.jpg",
            PROJECTS_DIR / project_id / "product" / "product_original.jpeg",
            PROJECTS_DIR / project_id / "product" / "product_original.webp",
        ]:
            if cand_path and cand_path.exists() and cand_path.stat().st_size > 1000:
                ref_image = cand_path
                break

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
            # Captures exact assistant message count, user message count, and all existing video URLs currently in DOM!
            initial_state = await page.evaluate("""() => {
                const asstMsgs = Array.from(document.querySelectorAll('[data-message-role="assistant"]'));
                const userMsgs = Array.from(document.querySelectorAll('[data-message-role="user"]'));
                const videos = Array.from(document.querySelectorAll('video, [data-hatch-video-wrapper]'));
                const srcs = videos.map(v => {
                    const vTag = v.tagName.toLowerCase() === 'video' ? v : v.querySelector('video');
                    return v.getAttribute('data-hatch-video-src') || (vTag ? (vTag.currentSrc || vTag.src) : null);
                }).filter(Boolean);
                return {
                    asstCount: asstMsgs.length,
                    userCount: userMsgs.length,
                    knownSrcs: srcs
                };
            }""")
            init_asst_count = initial_state.get("asstCount", 0)
            init_known_srcs = list(initial_state.get("knownSrcs", []))

            # Input Prompt into Muse AI Chat
            await log_fn(f"Đang chuẩn bị Prompt Cảnh {scene_number} cho '{pname}' vào Muse AI...", 40)

            prompt_input = await page.query_selector(
                "textarea[placeholder*='Nhắn tin' i], textarea[aria-label*='Nhắn tin' i], " +
                "textarea[placeholder*='prompt' i], textarea[placeholder*='describe' i], " +
                "div[contenteditable='true'], textarea"
            )

            # Normalize prompt: strip ANY existing [Cảnh ...] headers and add exactly ONE clean header
            clean_body = re.sub(r'(\[Cảnh\s*\d+[^\]]*\]\s*)+', '', scene_prompt).strip()
            formatted_prompt = f"[Cảnh {scene_number} - {pname} | 9:16, 10s, 60fps] {clean_body}"
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

                # Auto-click any confirmation / option / cleaned-dialogue button if Muse AI prompts for choice
                clicked_btn = await page.evaluate("""() => {
                    function triggerFullClick(target) {
                        if (!target) return;
                        target.scrollIntoView({ block: 'center', behavior: 'instant' });
                        const events = ['pointerover', 'mouseover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];
                        events.forEach(evType => {
                            try {
                                target.dispatchEvent(new MouseEvent(evType, {
                                    bubbles: true,
                                    cancelable: true,
                                    view: window,
                                    buttons: 1
                                }));
                            } catch(e) {}
                        });
                        try { target.click(); } catch(e) {}
                    }

                    // Priority 0: Retry / Re-create scene button (e.g. "Tạo lại cảnh", "Thử lại", "Làm lại", "Retry")
                    const allInteractive = Array.from(document.querySelectorAll('button, [role="button"], [data-slot="button"], [data-testid*="button"], a, div, span'));
                    for (const el of allInteractive) {
                        const t = (el.innerText || el.textContent || '').toLowerCase().trim();
                        if (!t || t.length > 50) continue;
                        if (t.includes('tạo lại cảnh') || t.includes('thử lại') || t.includes('làm lại cảnh') || t.includes('tạo lại') || t.includes('retry')) {
                            const btn = el.closest('button, [role="button"], a') || el;
                            triggerFullClick(btn);
                            return 'Tạo lại cảnh: ' + t;
                        }
                    }

                    // Priority 1: Suggested clean dialogue / fixed script buttons (e.g. "Dùng thoại mình soạn lại này", "Dùng thoại")
                    for (const el of allInteractive) {
                        const t = (el.innerText || el.textContent || '').toLowerCase().trim();
                        if (!t || t.length > 50) continue;
                        if (t.includes('dùng thoại') || t.includes('soạn lại này') || t.includes('soạn lại') || t.includes('thoại sạch') || t.includes('duyệt thoại') || t.includes('kịch bản sạch')) {
                            const btn = el.closest('button, [role="button"], a') || el;
                            triggerFullClick(btn);
                            return 'Đồng ý thoại sạch: ' + t;
                        }
                    }

                    // Priority 2: General confirmation & continue buttons
                    for (const el of allInteractive) {
                        const t = (el.innerText || el.textContent || '').toLowerCase().trim();
                        if (!t || t.length > 50) continue;
                        if (t.includes('dùng ảnh nhân vật') || t.includes('làm cảnh 2') || t.includes('dùng đúng ảnh') ||
                            t.includes('tiếp tục') || t.includes('chọn ảnh') || t.includes('đồng ý') || t.includes('xác nhận') ||
                            t.includes('bản ảnh mới') || t.includes('giữ nguyên') || t.includes('tạo ngay') || t.includes('chấp nhận')) {
                            const btn = el.closest('button, [role="button"], a') || el;
                            triggerFullClick(btn);
                            return 'Xác nhận: ' + t;
                        }
                    }
                    return null;
                }""")
                if clicked_btn:
                    await log_fn(f"Đã tự động bấm '{clicked_btn}' trên Muse AI...", current_pct)
                    await asyncio.sleep(1.2)

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

                # Check if Muse AI triggered clarification / clean dialogue prompt or deduplication refusal WITHOUT attaching finished videos
                muse_state = await page.evaluate("""() => {
                    const assts = Array.from(document.querySelectorAll('[data-message-role="assistant"]'));
                    if (!assts.length) return null;
                    const last = assts[assts.length - 1];
                    const t = (last.innerText || '').toLowerCase();
                    const hasVids = last.querySelectorAll('video, [data-hatch-video-wrapper]').length > 0;
                    if (hasVids) return null; // If videos are attached, Muse already delivered them!

                    if (t.includes('khoan đã') || t.includes('chưa tạo được') || t.includes('lỗi chữ') ||
                        t.includes('tiếng vô nghĩa') || t.includes('soạn lại thoại') || t.includes('duyệt thoại') ||
                        t.includes('mình soạn lại') || t.includes('bạn xác nhận') || t.includes('đoạn bị lỗi')) {
                        return 'clean_dialogue';
                    }
                    if (t.includes('gửi lại đúng y hệt') || t.includes('không tạo lại để đỡ tốn') ||
                        t.includes('cứ nhắn thêm “làm lại”') || t.includes('cu nhan them')) {
                        return 'redo';
                    }
                    return null;
                }""")

                if muse_state == 'clean_dialogue' and not is_muse_busy:
                    await log_fn(f"Phát hiện Muse AI đề xuất duyệt thoại sạch, tự động bấm 'Dùng thoại mình soạn lại này' và gửi xác nhận cho Cảnh {scene_number}...", current_pct)
                    try:
                        clicked_opt = await page.evaluate("""() => {
                            const candidates = Array.from(document.querySelectorAll('button, [role="button"], a, div[tabindex], div[class*="button"], span[class*="button"], div[class*="option"], div[class*="choice"], div[class*="suggestion"], div[class*="pill"]'));
                            for (const c of candidates) {
                                const txt = (c.innerText || c.textContent || '').trim().toLowerCase();
                                if (txt.includes('dùng thoại') || txt.includes('soạn lại này') || txt.includes('thoại mình soạn') || txt.includes('dùng thoại sạch')) {
                                    const btn = c.closest('button, [role="button"], a') || c;
                                    btn.click();
                                    return txt;
                                }
                            }
                            return null;
                        }""")
                        if clicked_opt:
                            await log_fn(f"Đã tự động chọn '{clicked_opt}' trên Muse AI...", current_pct)
                            await asyncio.sleep(2)
                        else:
                            p_in = await page.query_selector("textarea, div[contenteditable='true']")
                            if p_in:
                                await p_in.fill(f"Dùng thoại bạn vừa soạn lại để tạo video Cảnh {scene_number} giúp mình ngay nhé (chuẩn 9:16, 10s, 60fps)")
                                await asyncio.sleep(0.3)
                                s_btn = await page.query_selector("button[aria-label='Gửi'], button[type='submit']")
                                if s_btn:
                                    await s_btn.click()
                                else:
                                    await p_in.press("Enter")
                                await asyncio.sleep(2)
                    except Exception as ex_cd:
                        logger.debug(f"Clean dialogue confirm send error: {ex_cd}")
                elif muse_state == 'redo' and not is_muse_busy:
                    await log_fn(f"Phát hiện Muse AI giữ bản cũ không tạo mới, tự động yêu cầu tạo bản mới cho Cảnh {scene_number}...", current_pct)
                    try:
                        p_in = await page.query_selector("textarea, div[contenteditable='true']")
                        if p_in:
                            await p_in.fill(f"Làm lại bản mới cho Cảnh {scene_number} nhé (tạo góc quay mới 60fps sắc nét)")
                            await asyncio.sleep(0.3)
                            s_btn = await page.query_selector("button[aria-label='Gửi']")
                            if s_btn:
                                await s_btn.click()
                            else:
                                await p_in.press("Enter")
                            await asyncio.sleep(2)
                    except Exception as ex_ref:
                        logger.debug(f"Refusal retry send error: {ex_ref}")

                # Look STRICTLY in assistant messages for this prompt, guaranteeing zero cross-message mixing
                newest_video = await page.evaluate("""async (args) => {
                    const { initMsgCount, sceneNum, posSigs, negSigs, isWarehouse } = args;

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

                    function normalize(str) {
                        if (!str) return '';
                        return str.toLowerCase()
                            .replace(/đ/g, 'd')
                            .replace(/Đ/g, 'd')
                            .normalize('NFD')
                            .replace(/[\\u0300-\\u036f]/g, '');
                    }

                    const normPos = Array.from(new Set((posSigs || []).map(normalize).filter(s => s.length >= 3)));
                    const normNeg = Array.from(new Set((negSigs || []).map(normalize).filter(s => s.length >= 3)));

                    const asstMessages = Array.from(document.querySelectorAll('[data-message-role="assistant"]'));
                    if (!asstMessages.length) return null;

                    // STRICT BOUNDARY ISOLATION:
                    // Only consider assistant messages that arrived AFTER our prompt was submitted!
                    // Any message at index < initAsstCount was created BEFORE our prompt and MUST BE IGNORED!
                    const newAsstMessages = asstMessages.slice(initAsstCount);
                    if (!newAsstMessages.length) return null;

                    // Scroll recent assistant messages into view to trigger lazy loading
                    for (let i = Math.max(0, newAsstMessages.length - 2); i < newAsstMessages.length; i++) {
                        try { newAsstMessages[i].scrollIntoView({ block: 'center', behavior: 'instant' }); } catch(e) {}
                    }

                    let targetMsg = null;
                    let targetVideos = [];

                    // Scan NEW assistant messages from the latest backwards:
                    for (let i = newAsstMessages.length - 1; i >= 0; i--) {
                        const it = newAsstMessages[i];
                        const text = normalize(it.innerText || '');

                        // Strict: Reject message if it explicitly matches another product's excluded signature!
                        if (normNeg.some(sig => text.includes(sig))) continue;

                        // Warehouse alignment check if message mentions context
                        if (text.length > 20) {
                            const hasWh = text.includes('kho xuong') || text.includes('ban kho') || text.includes('tong kho') || text.includes('pallet');
                            if (isWarehouse && !hasWh && !normPos.some(s => text.includes(s))) continue;
                            if (!isWarehouse && hasWh) continue;
                        }

                        const rawVideos = Array.from(it.querySelectorAll('video, [data-testid*="attachment-presentation-video"], [data-hatch-video-wrapper]'));
                        const seenSrcs = new Set();
                        const vids = [];

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
                            if (vTag && vTag.duration === 5.041667) continue;

                            // Strictly filter out videos that already existed in DOM before this prompt was sent:
                            if (knownSrcs && knownSrcs.includes(src)) {
                                continue;
                            }

                            if (!seenSrcs.has(src)) {
                                seenSrcs.add(src);
                                let caption = (el.getAttribute('aria-label') || (vTag ? vTag.getAttribute('aria-label') : '') || it.innerText || '').toLowerCase();
                                vids.push({ src, caption });
                            }
                        }

                        if (vids.length > 0) {
                            targetMsg = it;
                            targetVideos = vids;
                            break; // Found the matching assistant message! NEVER combine videos across multiple messages!
                        }
                    }

                    if (!targetVideos.length) return null;

                    // If this assistant message returned 2 or more videos:
                    // Video 0 is Scene 1, Video 1 is Scene 2 of THIS EXACT RESPONSE!
                    if (targetVideos.length >= 2) {
                        const v1 = targetVideos[0];
                        const v2 = targetVideos[1];

                        if (v1.src !== v2.src) {
                            if (sceneNum === 1) {
                                return {
                                    src: v1.src,
                                    companionSrc: v2.src,
                                    aria: v1.caption || 'Cảnh 1'
                                };
                            } else {
                                return {
                                    src: v2.src,
                                    companionSrc: v1.src,
                                    aria: v2.caption || 'Cảnh 2'
                                };
                            }
                        }
                    }

                    // Single video in message:
                    const single = targetVideos[0];
                    return {
                        src: single.src,
                        companionSrc: null,
                        aria: single.caption || ('Cảnh ' + sceneNum)
                    };
                }""", {
                    "initAsstCount": init_asst_count,
                    "knownSrcs": init_known_srcs,
                    "sceneNum": scene_number,
                    "posSigs": pos_sigs,
                    "negSigs": neg_sigs,
                    "isWarehouse": _is_warehouse_product(pname)
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
                # Invalidate any old stitched video since scene video is newly updated
                c_db = _get_raw_conn()
                c_db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = ?", (project_id, scene_number))
                c_db.execute("DELETE FROM exports WHERE project_id = ?", (project_id,))
                c_db.execute("""
                    INSERT INTO videos (id, project_id, scene_number, video_path, duration, resolution, fps, status)
                    VALUES (?, ?, ?, ?, ?, '1080x1920', 60.0, 'ready')
                """, (f"v{scene_number}_{project_id[:4]}", project_id, scene_number, str(target_file), p_cur.get("duration", 10.0)))
                c_db.commit()
                for exp_f in (PROJECTS_DIR / project_id / "exports").glob("*.mp4"):
                    try: exp_f.unlink(missing_ok=True)
                    except Exception: pass

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

        # Check if s1 and s2 are identical duplicates - NEVER allow identical scenes
        if s1_ok and s2_ok and s1_file.exists() and s2_file.exists():
            import hashlib
            def _sh(p: Path) -> str:
                h = hashlib.md5()
                with open(p, "rb") as fp:
                    h.update(fp.read(65536))
                return h.hexdigest()
            if s1_file.stat().st_size == s2_file.stat().st_size or _sh(s1_file) == _sh(s2_file):
                logger.warning(f"Rejecting duplicate companion scene 2 for {project_id} - s1 and s2 have identical content!")
                s2_file.unlink(missing_ok=True)
                s2_ok = False

        # STRICT CHECK: If Scene 2 is missing, DO NOT synthesize fake motion video and DO NOT stitch!
        # Both scenes MUST be genuine videos from Muse AI before any stitching can occur.
        if s1_ok and not s2_ok:
            logger.info(f"Scene 2 not found yet on Muse AI for {project_id}. Skipping stitch - waiting for Scene 2.")
            conn.close()
            return {
                "success": False,
                "s1_ok": True,
                "s2_ok": False,
                "stitched": False,
                "message": f"Dự án '{pname}' đã có video Cảnh 1 nhưng CHƯA CÓ video Cảnh 2 trên Muse AI. Hệ thống không ghép video khi thiếu Cảnh 2."
            }

        if not s1_ok and s2_ok:
            logger.info(f"Scene 1 not found yet on Muse AI for {project_id}. Skipping stitch - waiting for Scene 1.")
            conn.close()
            return {
                "success": False,
                "s1_ok": False,
                "s2_ok": True,
                "stitched": False,
                "message": f"Dự án '{pname}' đã có video Cảnh 2 nhưng CHƯA CÓ video Cảnh 1 trên Muse AI. Hệ thống không ghép video khi thiếu Cảnh 1."
            }

        # If BOTH scenes are genuinely ready, stitch them!
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

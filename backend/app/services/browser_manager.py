import os
import time
import shutil
import logging
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright
from backend.app.config import GEMINI_PROFILE_DIR, FLOW_PROFILE_DIR, MUSE_PROFILE_DIR
from backend.app.database import get_setting, set_setting

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def _clean_profile_locks(profile_dir: Path):
    """Clean up stale Chromium lock files on Windows to prevent ProcessSingleton errors."""
    for fname in ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"]:
        f = profile_dir / fname
        if f.exists():
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass


def _kill_orphaned_chrome_for_profile(profile_dir: Path):
    """Kills any orphaned background chrome processes holding this profile's lockfile (fast filter by name first)."""
    try:
        import psutil
        safe_p = str(profile_dir.resolve()).lower()
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if (p.info.get('name') or '').lower() == 'chrome.exe':
                    cmdline = " ".join(p.cmdline() or []).lower()
                    if safe_p in cmdline:
                        p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
    except Exception:
        pass


def _clean_profile_session(profile_dir: Path):
    """
    Completely purges cookies, tokens, and cached Google account credentials
    from the Chrome profile so the browser opens fresh to a clean login screen.
    """
    default_dir = profile_dir / "Default"
    if not default_dir.exists():
        return
    targets = [
        default_dir / "Network" / "Cookies",
        default_dir / "Network" / "Cookies-journal",
        default_dir / "Cookies",
        default_dir / "Cookies-journal",
        default_dir / "Preferences",
        default_dir / "Web Data",
        default_dir / "Web Data-journal",
        default_dir / "Login Data",
        default_dir / "Login Data-journal",
    ]
    for f in targets:
        try:
            if f.exists():
                f.unlink(missing_ok=True)
        except Exception:
            pass
    for sub in ["Sessions", "Session Storage", "Local Storage", "IndexedDB"]:
        p = default_dir / sub
        try:
            if p.exists() and p.is_dir():
                shutil.rmtree(str(p), ignore_errors=True)
        except Exception:
            pass


def _is_hidden_sandbox_desktop() -> bool:
    """Checks if the current backend process is running inside an offscreen sandbox desktop (e.g., exebox)."""
    try:
        import ctypes
        hdesk = ctypes.windll.user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetUserObjectInformationW(hdesk, 2, buf, 512, None)
        desk_name = (buf.value or "").strip().lower()
        return bool(desk_name and desk_name != "default")
    except Exception:
        return False


class BrowserManager:
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.gemini_context: Optional[BrowserContext] = None
        self.flow_context: Optional[BrowserContext] = None
        self.muse_context: Optional[BrowserContext] = None
        self.gemini_page: Optional[Page] = None
        self.flow_page: Optional[Page] = None
        self.muse_page: Optional[Page] = None
        self._gemini_headless: bool = True
        self._flow_headless: bool = True
        self._muse_headless: bool = True
        self._gemini_switching: bool = False
        self._flow_switching: bool = False
        self._muse_switching: bool = False
        self._gemini_switch_ts: float = 0.0
        self._flow_switch_ts: float = 0.0
        self._muse_switch_ts: float = 0.0
        self._pw_lock: Optional[asyncio.Lock] = None
        self._gemini_lock: Optional[asyncio.Lock] = None
        self._flow_lock: Optional[asyncio.Lock] = None
        self._muse_lock: Optional[asyncio.Lock] = None

    def _get_pw_lock(self) -> asyncio.Lock:
        if self._pw_lock is None:
            self._pw_lock = asyncio.Lock()
        return self._pw_lock

    def _get_gemini_lock(self) -> asyncio.Lock:
        if self._gemini_lock is None:
            self._gemini_lock = asyncio.Lock()
        return self._gemini_lock

    def _get_flow_lock(self) -> asyncio.Lock:
        if self._flow_lock is None:
            self._flow_lock = asyncio.Lock()
        return self._flow_lock

    def _get_muse_lock(self) -> asyncio.Lock:
        if self._muse_lock is None:
            self._muse_lock = asyncio.Lock()
        return self._muse_lock

    async def _ensure_playwright(self):
        async with self._get_pw_lock():
            if not self.playwright:
                self.playwright = await async_playwright().start()

    async def _navigate_fast(self, page: Page, url: str):
        """Navigates quickly using commit wait_until so UI never blocks waiting for heavy SPA assets."""
        try:
            await page.goto(url, wait_until="commit", timeout=10000)
        except Exception:
            try:
                await page.evaluate(f"window.location.href = {repr(url)}")
            except Exception:
                pass

    def _pick_usable_page(self, context: BrowserContext) -> Optional[Page]:
        for pg in context.pages:
            u = (pg.url or "").lower()
            if not u.startswith("devtools://") and not u.startswith("chrome-extension://"):
                return pg
        return context.pages[0] if context.pages else None

    async def get_gemini_page(self, headed: bool = False, force_headed: bool = False) -> Page:
        """
        Retrieves the active Gemini page.
        By default, runs 100% headless in background without opening any desktop windows or taskbar icons.
        force_headed=True is used ONLY when the user clicks 'Đăng nhập Google' to interact.
        """
        async with self._get_gemini_lock():
            await self._ensure_playwright()

            is_headless = not force_headed and not headed

            if self.gemini_context and self.gemini_page and not self.gemini_page.is_closed():
                try:
                    await self.gemini_page.title()
                    if force_headed and self._gemini_headless:
                        await self.close_gemini_browser()
                    else:
                        return self.gemini_page
                except Exception:
                    self.gemini_page = None
                    self.gemini_context = None

            os.makedirs(GEMINI_PROFILE_DIR, exist_ok=True)
            _clean_profile_locks(GEMINI_PROFILE_DIR)

            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--lang=vi"
            ]
            if not is_headless:
                launch_args.append("--start-maximized")

            for attempt in range(3):
                try:
                    self.gemini_context = await self.playwright.chromium.launch_persistent_context(
                        user_data_dir=str(GEMINI_PROFILE_DIR),
                        channel="chrome",
                        headless=is_headless,
                        user_agent=USER_AGENT,
                        viewport=None if not is_headless else {"width": 1280, "height": 800},
                        args=launch_args,
                        ignore_default_args=["--enable-automation"]
                    )
                    break
                except Exception as e:
                    if attempt < 2:
                        _clean_profile_locks(GEMINI_PROFILE_DIR)
                        if "ProcessSingleton" in str(e):
                            await asyncio.to_thread(_kill_orphaned_chrome_for_profile, GEMINI_PROFILE_DIR)
                        await asyncio.sleep(0.5)
                    else:
                        raise e

            self._gemini_headless = is_headless
            self.gemini_page = self._pick_usable_page(self.gemini_context) or await self.gemini_context.new_page()

            await self.gemini_page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)

            return self.gemini_page

    async def get_flow_page(self, headed: bool = False, force_headed: bool = False) -> Page:
        """
        Retrieves the active Google Flow page.
        By default, runs 100% headless in background without opening any desktop windows or taskbar icons.
        force_headed=True is used ONLY when the user clicks 'Đăng nhập Google' to interact.
        """
        async with self._get_flow_lock():
            await self._ensure_playwright()

            is_headless = not force_headed and not headed

            if self.flow_context and self.flow_page and not self.flow_page.is_closed():
                try:
                    await self.flow_page.title()
                    if force_headed and self._flow_headless:
                        await self.close_flow_browser()
                    elif not force_headed and not headed and not self._flow_headless:
                        await self.close_flow_browser()
                    else:
                        return self.flow_page
                except Exception:
                    self.flow_page = None
                    self.flow_context = None

            os.makedirs(FLOW_PROFILE_DIR, exist_ok=True)
            _clean_profile_locks(FLOW_PROFILE_DIR)

            flow_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--lang=vi"
            ]
            if not is_headless:
                flow_args.append("--start-maximized")

            for attempt in range(3):
                try:
                    self.flow_context = await self.playwright.chromium.launch_persistent_context(
                        user_data_dir=str(FLOW_PROFILE_DIR),
                        channel="chrome",
                        headless=is_headless,
                        user_agent=USER_AGENT,
                        viewport=None if not is_headless else {"width": 1280, "height": 800},
                        args=flow_args,
                        ignore_default_args=["--enable-automation"]
                    )
                    break
                except Exception as e:
                    if attempt < 2:
                        _clean_profile_locks(FLOW_PROFILE_DIR)
                        if "ProcessSingleton" in str(e):
                            await asyncio.to_thread(_kill_orphaned_chrome_for_profile, FLOW_PROFILE_DIR)
                        await asyncio.sleep(0.5)
                    else:
                        raise e

            self._flow_headless = is_headless
            self.flow_page = self._pick_usable_page(self.flow_context) or await self.flow_context.new_page()

            await self.flow_page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)

            return self.flow_page

    async def get_muse_page(self, headed: bool = False, force_headed: bool = False) -> Page:
        """
        Retrieves the active Muse AI page.
        By default, runs headless in background.
        force_headed=True is used when the user clicks 'Đăng nhập Muse AI' to interact.
        """
        async with self._get_muse_lock():
            await self._ensure_playwright()

            is_headless = not force_headed and not headed

            if self.muse_context and self.muse_page and not self.muse_page.is_closed():
                try:
                    await self.muse_page.title()
                    if force_headed and self._muse_headless:
                        await self.close_muse_browser()
                    elif not force_headed and not headed and not self._muse_headless:
                        await self.close_muse_browser()
                    else:
                        return self.muse_page
                except Exception:
                    self.muse_page = None
                    self.muse_context = None

            os.makedirs(MUSE_PROFILE_DIR, exist_ok=True)
            _clean_profile_locks(MUSE_PROFILE_DIR)

            muse_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--lang=vi"
            ]
            if not is_headless:
                muse_args.append("--start-maximized")

            for attempt in range(3):
                try:
                    self.muse_context = await self.playwright.chromium.launch_persistent_context(
                        user_data_dir=str(MUSE_PROFILE_DIR),
                        channel="chrome",
                        headless=is_headless,
                        user_agent=USER_AGENT,
                        viewport=None if not is_headless else {"width": 1280, "height": 800},
                        args=muse_args,
                        ignore_default_args=["--enable-automation"]
                    )
                    break
                except Exception as e:
                    if attempt < 2:
                        _clean_profile_locks(MUSE_PROFILE_DIR)
                        if "ProcessSingleton" in str(e):
                            await asyncio.to_thread(_kill_orphaned_chrome_for_profile, MUSE_PROFILE_DIR)
                        await asyncio.sleep(0.5)
                    else:
                        raise e

            self._muse_headless = is_headless
            self.muse_page = self._pick_usable_page(self.muse_context) or await self.muse_context.new_page()

            await self.muse_page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)

            if (self.muse_page.url or "").lower() == "about:blank":
                try:
                    await self.muse_page.goto("https://muse.ai", wait_until="domcontentloaded", timeout=25000)
                except Exception:
                    pass

            return self.muse_page

    async def _extract_account_info(
        self,
        profile_dir: Path,
        page: Optional[Page] = None,
        setting_prefix: str = "flow"
    ) -> Dict[str, str]:
        """
        Extracts the currently logged-in Google account name, email, and avatar URL
        from the live browser page DOM and/or Chromium's Default/Preferences file.
        """
        import json
        import re

        dom_email = ""
        dom_name = ""
        dom_avatar = ""

        if page and not page.is_closed():
            try:
                dom_info = await page.evaluate("""() => {
                    let email = '';
                    let name = '';
                    let avatar = '';

                    const acctBtns = document.querySelectorAll(
                        "a[aria-label*='Tài khoản Google'], button[aria-label*='Tài khoản Google'], " +
                        "a[aria-label*='Google Account'], button[aria-label*='Google Account'], " +
                        "[aria-label*='@gmail.com'], [aria-label*='@']"
                    );
                    for (const el of acctBtns) {
                        const label = (el.getAttribute('aria-label') || '').trim();
                        const emailMatch = label.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})/);
                        if (emailMatch) {
                            email = emailMatch[1];
                            let cleaned = label
                                .replace(/Tài khoản Google:?/i, '')
                                .replace(/Google Account:?/i, '')
                                .replace(/,?\\s*Gói thành viên của Google/gi, '')
                                .replace(/,?\\s*Thành viên Google One/gi, '')
                                .replace(/,?\\s*Google One member/gi, '')
                                .replace(/,?\\s*Google One/gi, '')
                                .replace(emailMatch[0], '')
                                .replace(/[()\\n\\r]/g, ' ')
                                .replace(/^[\\s,:\\-]+|[\\s,:\\-]+$/g, '')
                                .trim();
                            if (cleaned && cleaned.length >= 2 && cleaned.length <= 60) {
                                name = cleaned;
                            }
                            break;
                        }
                    }

                    if (!email) {
                        const dataEmailEl = document.querySelector('[data-email]');
                        if (dataEmailEl) {
                            email = (dataEmailEl.getAttribute('data-email') || '').trim();
                        }
                    }

                    const avatarEl = document.querySelector("img[src*='googleusercontent.com/a/'], img.gb_A, img.gb_P");
                    if (avatarEl) {
                        avatar = avatarEl.getAttribute('src') || '';
                    }

                    return { email, name, avatar };
                }""")
                if isinstance(dom_info, dict):
                    dom_email = (dom_info.get("email") or "").strip()
                    dom_name = (dom_info.get("name") or "").strip()
                    dom_avatar = (dom_info.get("avatar") or "").strip()
            except Exception:
                pass

        pref_email = ""
        pref_name = ""
        pref_avatar = ""
        is_logged_in_setting = get_setting(f"{setting_prefix}_logged_in") == "true"

        # Only read cached profile Preferences if actively authenticated or if session is marked valid
        if dom_email or is_logged_in_setting:
            try:
                prefs_file = profile_dir / "Default" / "Preferences"
                if prefs_file.exists():
                    raw_text = prefs_file.read_text(encoding="utf-8", errors="ignore")
                    data = json.loads(raw_text)
                    acct_list = data.get("account_info") or []
                    if isinstance(acct_list, list) and len(acct_list) > 0:
                        chosen = None
                        if dom_email:
                            for item in acct_list:
                                if isinstance(item, dict) and (item.get("email") or "").lower() == dom_email.lower():
                                    chosen = item
                                    break
                        if not chosen and is_logged_in_setting:
                            for item in reversed(acct_list):
                                if isinstance(item, dict) and item.get("email"):
                                    chosen = item
                                    break
                        if chosen:
                            pref_email = (chosen.get("email") or "").strip()
                            pref_name = (chosen.get("full_name") or chosen.get("given_name") or "").strip()
                            pref_avatar = (chosen.get("picture_url") or "").strip()
            except Exception:
                pass

        saved_db_email = (get_setting(f"{setting_prefix}_account_email") or "").strip() if is_logged_in_setting else ""
        saved_db_name = (get_setting(f"{setting_prefix}_account_name") or "").strip() if is_logged_in_setting else ""
        saved_db_avatar = (get_setting(f"{setting_prefix}_account_avatar") or "").strip() if is_logged_in_setting else ""

        final_email = dom_email or pref_email or saved_db_email
        final_name = dom_name or pref_name or saved_db_name
        if final_name:
            final_name = re.sub(
                r',?\s*(?:Gói thành viên của Google|Thành viên Google One|Google One member|Google One)\b',
                '',
                final_name,
                flags=re.IGNORECASE
            ).strip(" ,:-")
        final_avatar = dom_avatar or pref_avatar or saved_db_avatar

        if is_logged_in_setting or dom_email:
            if final_email:
                set_setting(f"{setting_prefix}_account_email", final_email)
            if final_name:
                set_setting(f"{setting_prefix}_account_name", final_name)
            if final_avatar:
                set_setting(f"{setting_prefix}_account_avatar", final_avatar)

        if final_name and final_email and final_name.lower() != final_email.lower():
            display = f"{final_name} ({final_email})"
        elif final_email:
            display = final_email
        elif final_name:
            display = final_name
        else:
            display = ""

        return {
            "account_email": final_email,
            "account_name": final_name,
            "account_avatar": final_avatar,
            "account_display": display
        }

    def _clear_saved_account_info(self, setting_prefix: str = "flow"):
        try:
            set_setting(f"{setting_prefix}_account_email", "")
            set_setting(f"{setting_prefix}_account_name", "")
            set_setting(f"{setting_prefix}_account_avatar", "")
        except Exception:
            pass

    async def _is_gemini_page_authenticated(self, page: Page) -> bool:
        """Checks whether Gemini page is logged in."""
        try:
            from urllib.parse import urlparse
            current_url = page.url or ""
            parsed = urlparse(current_url)
            host = (parsed.netloc or "").lower()
            if not host or "accounts.google.com" in host or "myaccount.google.com" in host:
                return False
            if "gemini.google.com" not in host:
                return False

            dom_state = await page.evaluate("""() => {
                const hasSignInBtn = Boolean(
                    document.querySelector(
                        "a[href*='accounts.google.com/ServiceLogin'], " +
                        "a.gb_Ta, " +
                        "a[aria-label*='Sign in'], " +
                        "a[aria-label*='Đăng nhập'], " +
                        "button[aria-label*='Sign in'], " +
                        "button[aria-label*='Đăng nhập']"
                    )
                );
                const hasAuthEl = Boolean(
                    document.querySelector(
                        "a[aria-label*='Tài khoản Google'], " +
                        "button[aria-label*='Tài khoản Google'], " +
                        "a[aria-label*='Google Account'], " +
                        "button[aria-label*='Google Account'], " +
                        "a[href*='SignOutOptions'], " +
                        "img[src*='googleusercontent.com/a/'], " +
                        "rich-textarea, " +
                        "div[contenteditable='true'], " +
                        "textarea, " +
                        "button[aria-label*='Gửi'], " +
                        "button[aria-label*='Send prompt']"
                    )
                );
                return { hasSignInBtn, hasAuthEl };
            }""")
            if dom_state.get("hasSignInBtn"):
                return False
            if dom_state.get("hasAuthEl"):
                return True
            if "/app" in parsed.path and not dom_state.get("hasSignInBtn"):
                return True
            return False
        except Exception:
            return False

    async def check_gemini_login(self, target_url: str = "https://gemini.google.com/app", force_open: bool = False) -> Dict[str, Any]:
        """Checks Gemini login state."""
        empty_acct = {"account_email": "", "account_name": "", "account_avatar": "", "account_display": ""}
        saved_login = get_setting("gemini_logged_in")

        if not force_open:
            if self._gemini_switching:
                elapsed = time.time() - self._gemini_switch_ts
                if (not self.gemini_page or self.gemini_page.is_closed()) and elapsed > 5.0:
                    self._gemini_switching = False
                elif elapsed > 60.0:
                    self._gemini_switching = False

            if self._gemini_switching:
                if not self.gemini_page or self.gemini_page.is_closed():
                    return {
                        "logged_in": False,
                        "status": "switching_account",
                        "message": "Đang mở cửa sổ Chrome đăng nhập tài khoản Gemini mới...",
                        **empty_acct
                    }
                try:
                    is_logged_in = await self._is_gemini_page_authenticated(self.gemini_page)
                    if is_logged_in:
                        self._gemini_switching = False
                        set_setting("gemini_logged_in", "true")
                        acct = await self._extract_account_info(GEMINI_PROFILE_DIR, self.gemini_page, "gemini")
                        return {
                            "logged_in": True,
                            "status": "connected",
                            "message": f"Đã kết nối tài khoản mới: {acct['account_display']}" if acct["account_display"] else "Đã kết nối Gemini.",
                            **acct
                        }
                    else:
                        return {
                            "logged_in": False,
                            "status": "switching_account",
                            "message": "Vui lòng nhập email và mật khẩu tài khoản Google mới trên cửa sổ Chrome...",
                            **empty_acct
                        }
                except Exception:
                    return {
                        "logged_in": False,
                        "status": "switching_account",
                        "message": "Đang chờ bạn đăng nhập tài khoản Google mới trên cửa sổ Chrome...",
                        **empty_acct
                    }

            if not self.gemini_context or not self.gemini_page or self.gemini_page.is_closed():
                if saved_login == "true":
                    acct = await self._extract_account_info(GEMINI_PROFILE_DIR, None, "gemini")
                    if acct.get("account_email"):
                        return {
                            "logged_in": True,
                            "status": "connected",
                            "message": f"Đã kết nối Gemini ({acct['account_display']})" if acct["account_display"] else "Đã lưu phiên đăng nhập Gemini (Sẵn sàng).",
                            **acct
                        }
                return {
                    "logged_in": False,
                    "status": "needs_login",
                    "message": "Chưa kết nối Gemini. Nhấn 'Đăng nhập (Chọn TK)' để chọn tài khoản Google.",
                    **empty_acct
                }

            try:
                is_logged_in = await self._is_gemini_page_authenticated(self.gemini_page)
                if is_logged_in:
                    set_setting("gemini_logged_in", "true")
                    acct = await self._extract_account_info(GEMINI_PROFILE_DIR, self.gemini_page, "gemini")
                    return {
                        "logged_in": True,
                        "status": "connected",
                        "message": f"Gemini đang mở ({acct['account_display']})." if acct["account_display"] else "Gemini đang mở và sẵn sàng.",
                        **acct
                    }
                else:
                    set_setting("gemini_logged_in", "false")
                    return {
                        "logged_in": False,
                        "status": "needs_login",
                        "message": "Vui lòng hoàn thành đăng nhập trên cửa sổ Chrome.",
                        **empty_acct
                    }
            except Exception:
                if saved_login == "true":
                    acct = await self._extract_account_info(GEMINI_PROFILE_DIR, None, "gemini")
                    if acct.get("account_email"):
                        return {
                            "logged_in": True,
                            "status": "connected",
                            "message": f"Đã kết nối Gemini ({acct['account_display']})" if acct["account_display"] else "Đã lưu phiên đăng nhập Gemini.",
                            **acct
                        }
                return {
                    "logged_in": False,
                    "status": "needs_login",
                    "message": "Chưa kết nối Gemini.",
                    **empty_acct
                }

        # force_open=True: user explicitly clicked 'Đăng nhập' or 'Kết nối'
        try:
            self._gemini_switching = False
            page = await self.get_gemini_page(headed=True, force_headed=True)
            try:
                await page.bring_to_front()
            except Exception:
                pass
            current_url = (page.url or "").lower()

            if saved_login == "true":
                if "gemini.google.com" not in current_url:
                    await self._navigate_fast(page, target_url)
                    await asyncio.sleep(0.8)
                is_logged_in = await self._is_gemini_page_authenticated(page)
                if is_logged_in:
                    set_setting("gemini_logged_in", "true")
                    acct = await self._extract_account_info(GEMINI_PROFILE_DIR, page, "gemini")
                    return {
                        "logged_in": True,
                        "status": "connected",
                        "message": f"Đã kết nối Gemini ({acct['account_display']})" if acct["account_display"] else "Đã kết nối Gemini.",
                        **acct
                    }

            if "gemini.google.com" in current_url and await self._is_gemini_page_authenticated(page):
                set_setting("gemini_logged_in", "true")
                acct = await self._extract_account_info(GEMINI_PROFILE_DIR, page, "gemini")
                return {
                    "logged_in": True,
                    "status": "connected",
                    "message": f"Đã kết nối Gemini ({acct['account_display']})" if acct["account_display"] else "Đã kết nối Gemini.",
                    **acct
                }

            set_setting("gemini_logged_in", "false")
            chooser_url = f"https://accounts.google.com/ServiceLogin?continue={target_url}&hl=vi"
            if "accounts.google.com" not in current_url:
                await self._navigate_fast(page, chooser_url)
            return {
                "logged_in": False,
                "status": "needs_login",
                "message": "Đã mở cửa sổ đăng nhập Google. Vui lòng nhập tài khoản để đăng nhập Gemini.",
                **empty_acct
            }
        except Exception as e:
            return {
                "logged_in": False,
                "status": "error",
                "message": f"Không thể kiểm tra trạng thái Gemini: {str(e)}",
                **empty_acct
            }

    async def _is_flow_page_authenticated(self, page: Page) -> bool:
        """Checks whether Google Flow page is logged in."""
        try:
            from urllib.parse import urlparse
            current_url = page.url or ""
            parsed = urlparse(current_url)
            host = (parsed.netloc or "").lower()

            # Fast check via cookies in context: if authenticated Google cookies exist
            try:
                if page.context:
                    cookies = await page.context.cookies()
                    has_auth_cookies = any(
                        c.get("name") in ["SID", "SSID", "HSID", "__Secure-1PSID", "__Secure-3PSID"]
                        for c in cookies
                        if ".google.com" in (c.get("domain") or "").lower()
                    )
                    if has_auth_cookies:
                        if "accounts.google.com" in host or "myaccount.google.com" in host:
                            if not any(x in parsed.path for x in ["/signin", "/v2/signin", "/challenge"]):
                                asyncio.create_task(self._navigate_fast(page, "https://labs.google/fx/vi/tools/flow"))
                                return True
                        elif "labs.google" in host or "flow.google.com" in host:
                            return True
            except Exception:
                pass

            if not host or "accounts.google.com" in host or "myaccount.google.com" in host:
                return False
            if "labs.google" not in host and "flow.google.com" not in host:
                return False

            if "/project/" in parsed.path:
                return True

            dom_state = await asyncio.wait_for(page.evaluate("""() => {
                const hasAuthEl = Boolean(
                    document.querySelector(
                        "button[aria-label*='Tài khoản Google'], " +
                        "a[aria-label*='Tài khoản Google'], " +
                        "button[aria-label*='Google Account'], " +
                        "a[aria-label*='Google Account'], " +
                        "img[src*='googleusercontent.com'], " +
                        "a[href*='/project/'], " +
                        "flow-rich-text-editor, " +
                        "button.mat-mdc-list-item"
                    )
                );
                const buttons = Array.from(document.querySelectorAll('button, a')).map(b => (b.innerText || '').trim().toLowerCase());
                const hasProjectBtn = buttons.some(t =>
                    t.includes('dự án mới') || t.includes('new project') || t.includes('mở dự án') || t.includes('bắt đầu tạo') || t.includes('start creating')
                );
                const hasSignInBtn = Boolean(
                    document.querySelector("a[href*='accounts.google.com/ServiceLogin']") ||
                    buttons.some(t => t === 'sign in' || t === 'đăng nhập' || t.includes('sign in with google'))
                );
                return { hasAuthEl, hasProjectBtn, hasSignInBtn };
            }"""), timeout=2.5)

            if dom_state.get("hasAuthEl") or dom_state.get("hasProjectBtn"):
                return True
            if dom_state.get("hasSignInBtn"):
                return False
            return False
        except Exception:
            return False

    async def check_flow_login(self, target_url: str = "https://flow.google.com/", force_open: bool = False) -> Dict[str, Any]:
        """Checks Google Flow login state."""
        empty_acct = {"account_email": "", "account_name": "", "account_avatar": "", "account_display": ""}
        saved_login = get_setting("flow_logged_in")
        if not force_open:
            if self._flow_switching:
                elapsed = time.time() - self._flow_switch_ts
                if (not self.flow_page or self.flow_page.is_closed()) and elapsed > 3.0:
                    self._flow_switching = False
                elif elapsed > 20.0:
                    self._flow_switching = False

            # Check all open pages in context for active login
            if self.flow_context and self.flow_context.pages:
                for p in self.flow_context.pages:
                    if p and not p.is_closed():
                        try:
                            if await self._is_flow_page_authenticated(p):
                                self.flow_page = p
                                self._flow_switching = False
                                set_setting("flow_logged_in", "true")
                                acct = await self._extract_account_info(FLOW_PROFILE_DIR, p, "flow")
                                return {
                                    "logged_in": True,
                                    "status": "connected",
                                    "message": f"Đã kết nối Google Flow: {acct['account_display']}" if acct["account_display"] else "Đã kết nối Google Flow.",
                                    **acct
                                }
                        except Exception:
                            pass

            if self._flow_switching:
                if not self.flow_page or self.flow_page.is_closed():
                    return {
                        "logged_in": False,
                        "status": "switching_account",
                        "message": "Đang mở cửa sổ Chrome đăng nhập tài khoản Flow mới...",
                        **empty_acct
                    }
                try:
                    is_logged_in = await self._is_flow_page_authenticated(self.flow_page)
                    if is_logged_in:
                        self._flow_switching = False
                        set_setting("flow_logged_in", "true")
                        acct = await self._extract_account_info(FLOW_PROFILE_DIR, self.flow_page, "flow")
                        return {
                            "logged_in": True,
                            "status": "connected",
                            "message": f"Đã kết nối tài khoản Google Flow mới: {acct['account_display']}" if acct["account_display"] else "Đã kết nối Google Flow.",
                            **acct
                        }
                    else:
                        return {
                            "logged_in": False,
                            "status": "switching_account",
                            "message": "Vui lòng nhập email và mật khẩu tài khoản Google Flow mới trên cửa sổ Chrome vừa mở...",
                            **empty_acct
                        }
                except Exception:
                    return {
                        "logged_in": False,
                        "status": "switching_account",
                        "message": "Đang chờ bạn đăng nhập tài khoản Google Flow mới trên cửa sổ Chrome...",
                        **empty_acct
                    }

            if not self.flow_context or not self.flow_page or self.flow_page.is_closed():
                if saved_login == "true":
                    acct = await self._extract_account_info(FLOW_PROFILE_DIR, None, "flow")
                    if acct.get("account_email"):
                        return {
                            "logged_in": True,
                            "status": "connected",
                            "message": f"Đã kết nối Google Flow ({acct['account_display']})" if acct["account_display"] else "Đã lưu phiên đăng nhập Google Flow (Sẵn sàng).",
                            **acct
                        }
                return {
                    "logged_in": False,
                    "status": "needs_login",
                    "message": "Chưa kết nối Google Flow. Nhấn 'Đăng nhập / Chọn tài khoản' để chọn tài khoản Google.",
                    **empty_acct
                }
            try:
                is_logged_in = await self._is_flow_page_authenticated(self.flow_page)
                if is_logged_in:
                    set_setting("flow_logged_in", "true")
                    acct = await self._extract_account_info(FLOW_PROFILE_DIR, self.flow_page, "flow")
                    return {
                        "logged_in": True,
                        "status": "connected",
                        "message": f"Google Flow đang mở ({acct['account_display']})." if acct["account_display"] else "Google Flow đang mở và sẵn sàng.",
                        **acct
                    }
                else:
                    set_setting("flow_logged_in", "false")
                    return {
                        "logged_in": False,
                        "status": "needs_login",
                        "message": "Vui lòng chọn tài khoản đăng nhập.",
                        **empty_acct
                    }
            except Exception:
                if saved_login == "true":
                    acct = await self._extract_account_info(FLOW_PROFILE_DIR, None, "flow")
                    if acct.get("account_email"):
                        return {
                            "logged_in": True,
                            "status": "connected",
                            "message": f"Phiên đăng nhập Google Flow đã lưu ({acct['account_display']}).",
                            **acct
                        }
                return {
                    "logged_in": False,
                    "status": "needs_login",
                    "message": "Chưa kết nối Google Flow.",
                    **empty_acct
                }

        # force_open=True: user explicitly wants to interact and log in
        try:
            self._flow_switching = False
            page = await self.get_flow_page(headed=True, force_headed=True)
            try:
                await page.bring_to_front()
            except Exception:
                pass
            current_url = (page.url or "").lower()

            if saved_login == "true":
                if "flow.google.com" not in current_url and "labs.google" not in current_url:
                    await self._navigate_fast(page, target_url)
                    await asyncio.sleep(0.8)
                is_logged_in = await self._is_flow_page_authenticated(page)
                if is_logged_in:
                    set_setting("flow_logged_in", "true")
                    acct = await self._extract_account_info(FLOW_PROFILE_DIR, page, "flow")
                    return {
                        "logged_in": True,
                        "status": "connected",
                        "message": f"Đã kết nối Google Flow: {acct['account_display']}" if acct["account_display"] else "Đã kết nối Google Flow.",
                        **acct
                    }

            if ("flow.google.com" in current_url or "labs.google" in current_url) and await self._is_flow_page_authenticated(page):
                set_setting("flow_logged_in", "true")
                acct = await self._extract_account_info(FLOW_PROFILE_DIR, page, "flow")
                return {
                    "logged_in": True,
                    "status": "connected",
                    "message": f"Đã kết nối Google Flow: {acct['account_display']}" if acct["account_display"] else "Đã kết nối Google Flow.",
                    **acct
                }

            set_setting("flow_logged_in", "false")
            chooser_url = f"https://accounts.google.com/ServiceLogin?continue={target_url}&hl=vi"
            if "accounts.google.com" not in current_url:
                await self._navigate_fast(page, chooser_url)
            return {
                "logged_in": False,
                "status": "needs_login",
                "message": "Đã hiển thị form đăng nhập Google trên cửa sổ Chrome. Vui lòng đăng nhập tài khoản.",
                **empty_acct
            }
        except Exception as e:
            return {
                "logged_in": False,
                "status": "error",
                "message": f"Không thể kết nối Google Flow: {str(e)}",
                **empty_acct
            }

    async def close_gemini_browser(self):
        try:
            if self.gemini_context:
                await self.gemini_context.close()
        except Exception:
            pass
        self.gemini_page = None
        self.gemini_context = None
        await asyncio.sleep(0.2)
        _clean_profile_locks(GEMINI_PROFILE_DIR)

    async def close_flow_browser(self):
        try:
            if self.flow_context:
                await self.flow_context.close()
        except Exception:
            pass
        self.flow_page = None
        self.flow_context = None
        await asyncio.sleep(0.2)
        _clean_profile_locks(FLOW_PROFILE_DIR)

    async def clear_gemini_session(self, open_login: bool = True, full_logout: bool = True):
        self._gemini_switching = True
        self._gemini_switch_ts = time.time()
        set_setting("gemini_logged_in", "logged_out")
        self._clear_saved_account_info("gemini")
        await self.close_gemini_browser()
        await asyncio.to_thread(_kill_orphaned_chrome_for_profile, GEMINI_PROFILE_DIR)
        _clean_profile_locks(GEMINI_PROFILE_DIR)
        if full_logout:
            await asyncio.to_thread(_clean_profile_session, GEMINI_PROFILE_DIR)

        if open_login:
            page = await self.get_gemini_page(headed=True, force_headed=True)
            try:
                await page.bring_to_front()
            except Exception:
                pass
            login_url = (
                "https://accounts.google.com/ServiceLogin?continue=https://gemini.google.com/app&hl=vi"
                if full_logout
                else "https://accounts.google.com/AccountChooser?continue=https://gemini.google.com/app&hl=vi"
            )
            await self._navigate_fast(page, login_url)
        return True

    async def clear_flow_session(self, open_login: bool = True, full_logout: bool = True):
        async with self._get_flow_lock():
            self._flow_switching = True
            self._flow_switch_ts = time.time()
            set_setting("flow_logged_in", "logged_out")
            self._clear_saved_account_info("flow")
            try:
                if self.flow_context:
                    await self.flow_context.clear_cookies()
                if self.flow_page and not self.flow_page.is_closed():
                    await self.flow_page.evaluate("() => { try { localStorage.clear(); sessionStorage.clear(); } catch(e){} }")
            except Exception:
                pass
            await self.close_flow_browser()
            await asyncio.to_thread(_kill_orphaned_chrome_for_profile, FLOW_PROFILE_DIR)
            await asyncio.sleep(0.5)
            _clean_profile_locks(FLOW_PROFILE_DIR)
            if full_logout:
                await asyncio.to_thread(_clean_profile_session, FLOW_PROFILE_DIR)

            if open_login:
                page = await self.get_flow_page(headed=True, force_headed=True)
                try:
                    await page.bring_to_front()
                except Exception:
                    pass
                login_url = (
                    "https://accounts.google.com/ServiceLogin?continue=https://labs.google/fx/vi/tools/flow&hl=vi"
                    if full_logout
                    else "https://accounts.google.com/AccountChooser?continue=https://labs.google/fx/vi/tools/flow&hl=vi"
                )
                await self._navigate_fast(page, login_url)
            return True

    async def _is_muse_page_authenticated(self, page: Page) -> bool:
        """Checks whether Muse AI page is logged in."""
        try:
            from urllib.parse import urlparse
            current_url = page.url or ""
            parsed = urlparse(current_url)
            host = (parsed.netloc or "").lower()
            if not host:
                return False
            if "muse.ai" not in host and "musevideo.ai" not in host:
                return False

            if "/login" in parsed.path or "/join" in parsed.path or "/signup" in parsed.path:
                return False

            # Check context cookies first
            try:
                if page.context:
                    cookies = await page.context.cookies()
                    has_muse_cookie = any(
                        any(k in (c.get("name") or "").lower() for k in ["session", "auth", "token", "muse_", "jwt", "connect.sid"])
                        for c in cookies
                        if "muse.ai" in (c.get("domain") or "").lower()
                    )
                    if has_muse_cookie and parsed.path in ["/", "/dashboard", "/create", "/videos", "/projects", "/home"]:
                        return True
            except Exception:
                pass

            dom_state = await asyncio.wait_for(page.evaluate("""() => {
                const hasUserEl = Boolean(
                    document.querySelector(
                        "[aria-label*='account' i], [aria-label*='profile' i], [aria-label*='user' i], " +
                        "a[href*='/dashboard'], a[href*='/create'], a[href*='/settings'], a[href*='/profile'], " +
                        ".user-menu, .avatar, img[src*='avatar'], button.user-button, .user-name, [data-user]"
                    )
                );
                let hasLocalAuth = false;
                try {
                    hasLocalAuth = Boolean(localStorage.getItem('token') || localStorage.getItem('user') || localStorage.getItem('auth') || localStorage.getItem('sb-access-token'));
                } catch(e) {}
                const hasSignIn = Boolean(
                    document.querySelector("a[href*='/login'], a[href*='/signin'], button[aria-label*='Sign in' i], button[aria-label*='Log in' i]") ||
                    Array.from(document.querySelectorAll('button, a')).some(b => {
                        const t = (b.innerText || '').trim().toLowerCase();
                        return t === 'log in' || t === 'sign in' || t === 'đăng nhập';
                    })
                );
                return { hasUserEl, hasLocalAuth, hasSignIn };
            }"""), timeout=2.5)

            if dom_state.get("hasUserEl") or dom_state.get("hasLocalAuth"):
                return True
            if dom_state.get("hasSignIn"):
                return False
            if parsed.path in ["/", "/dashboard", "/create", "/videos", "/projects", "/home"] and not dom_state.get("hasSignIn"):
                return True
            return False
        except Exception:
            return False

    async def check_muse_login(self, target_url: str = "https://muse.ai", force_open: bool = False) -> Dict[str, Any]:
        """Checks Muse AI login state."""
        empty_acct = {"account_email": "", "account_name": "", "account_avatar": "", "account_display": ""}
        saved_login = get_setting("muse_logged_in")
        if not force_open:
            if self._muse_switching:
                elapsed = time.time() - self._muse_switch_ts
                if (not self.muse_page or self.muse_page.is_closed()) and elapsed > 3.0:
                    self._muse_switching = False
                elif elapsed > 20.0:
                    self._muse_switching = False

            # Check all open pages in muse context
            if self.muse_context and self.muse_context.pages:
                for p in self.muse_context.pages:
                    if p and not p.is_closed():
                        try:
                            if await self._is_muse_page_authenticated(p):
                                self.muse_page = p
                                self._muse_switching = False
                                set_setting("muse_logged_in", "true")
                                acct = await self._extract_account_info(MUSE_PROFILE_DIR, p, "muse")
                                return {
                                    "logged_in": True,
                                    "status": "connected",
                                    "message": f"Đã kết nối tài khoản Muse AI: {acct['account_display']}" if acct["account_display"] else "Đã kết nối Muse AI.",
                                    **acct
                                }
                        except Exception:
                            pass

            if self._muse_switching:
                if not self.muse_page or self.muse_page.is_closed():
                    return {
                        "logged_in": False,
                        "status": "switching_account",
                        "message": "Đang mở cửa sổ Chrome đăng nhập tài khoản Muse AI mới...",
                        **empty_acct
                    }
                try:
                    is_logged_in = await self._is_muse_page_authenticated(self.muse_page)
                    if is_logged_in:
                        self._muse_switching = False
                        set_setting("muse_logged_in", "true")
                        acct = await self._extract_account_info(MUSE_PROFILE_DIR, self.muse_page, "muse")
                        return {
                            "logged_in": True,
                            "status": "connected",
                            "message": f"Đã kết nối tài khoản Muse AI: {acct['account_display']}" if acct["account_display"] else "Đã kết nối Muse AI.",
                            **acct
                        }
                    else:
                        return {
                            "logged_in": False,
                            "status": "switching_account",
                            "message": "Vui lòng đăng nhập tài khoản Muse AI trên cửa sổ Chrome vừa mở...",
                            **empty_acct
                        }
                except Exception:
                    return {
                        "logged_in": False,
                        "status": "switching_account",
                        "message": "Đang chờ bạn đăng nhập tài khoản Muse AI trên cửa sổ Chrome...",
                        **empty_acct
                    }

            if not self.muse_context or not self.muse_page or self.muse_page.is_closed():
                if saved_login == "true":
                    acct = await self._extract_account_info(MUSE_PROFILE_DIR, None, "muse")
                    return {
                        "logged_in": True,
                        "status": "connected",
                        "message": f"Đã kết nối Muse AI ({acct['account_display']})" if acct['account_display'] else "Đã lưu phiên đăng nhập Muse AI (Sẵn sàng).",
                        **acct
                    }
                return {
                    "logged_in": False,
                    "status": "needs_login",
                    "message": "Chưa kết nối Muse AI. Nhấn 'Đăng nhập Muse AI' để kết nối.",
                    **empty_acct
                }
            try:
                is_logged_in = await self._is_muse_page_authenticated(self.muse_page)
                if is_logged_in:
                    set_setting("muse_logged_in", "true")
                    acct = await self._extract_account_info(MUSE_PROFILE_DIR, self.muse_page, "muse")
                    return {
                        "logged_in": True,
                        "status": "connected",
                        "message": f"Muse AI đang mở ({acct['account_display']})." if acct['account_display'] else "Muse AI đang mở và sẵn sàng.",
                        **acct
                    }
                else:
                    set_setting("muse_logged_in", "false")
                    return {
                        "logged_in": False,
                        "status": "needs_login",
                        "message": "Vui lòng đăng nhập tài khoản Muse AI trên cửa sổ Chrome.",
                        **empty_acct
                    }
            except Exception:
                if saved_login == "true":
                    acct = await self._extract_account_info(MUSE_PROFILE_DIR, None, "muse")
                    return {
                        "logged_in": True,
                        "status": "connected",
                        "message": f"Phiên đăng nhập Muse AI đã lưu ({acct['account_display']}).",
                        **acct
                    }
                return {
                    "logged_in": False,
                    "status": "needs_login",
                    "message": "Chưa kết nối Muse AI.",
                    **empty_acct
                }

        # force_open=True: user explicitly clicked 'Đăng nhập'
        try:
            self._muse_switching = False
            page = await self.get_muse_page(headed=True, force_headed=True)
            try:
                await page.bring_to_front()
            except Exception:
                pass
            current_url = (page.url or "").lower()

            if saved_login == "true":
                if "muse.ai" not in current_url and "musevideo.ai" not in current_url:
                    await self._navigate_fast(page, target_url)
                    await asyncio.sleep(0.8)
                is_logged_in = await self._is_muse_page_authenticated(page)
                if is_logged_in:
                    set_setting("muse_logged_in", "true")
                    acct = await self._extract_account_info(MUSE_PROFILE_DIR, page, "muse")
                    return {
                        "logged_in": True,
                        "status": "connected",
                        "message": f"Đã kết nối Muse AI: {acct['account_display']}" if acct["account_display"] else "Đã kết nối Muse AI.",
                        **acct
                    }

            if ("muse.ai" in current_url or "musevideo.ai" in current_url) and await self._is_muse_page_authenticated(page):
                set_setting("muse_logged_in", "true")
                acct = await self._extract_account_info(MUSE_PROFILE_DIR, page, "muse")
                return {
                    "logged_in": True,
                    "status": "connected",
                    "message": f"Đã kết nối Muse AI: {acct['account_display']}" if acct["account_display"] else "Đã kết nối Muse AI.",
                    **acct
                }

            set_setting("muse_logged_in", "false")
            login_url = "https://muse.ai/login"
            if "/login" not in current_url:
                await self._navigate_fast(page, login_url)
            return {
                "logged_in": False,
                "status": "needs_login",
                "message": "Đã hiển thị form đăng nhập Muse AI trên cửa sổ Chrome. Vui lòng đăng nhập tài khoản.",
                **empty_acct
            }
        except Exception as e:
            return {
                "logged_in": False,
                "status": "error",
                "message": f"Không thể kết nối Muse AI: {str(e)}",
                **empty_acct
            }

    async def close_muse_browser(self):
        try:
            if self.muse_context:
                await self.muse_context.close()
        except Exception:
            pass
        self.muse_page = None
        self.muse_context = None
        await asyncio.sleep(0.2)
        _clean_profile_locks(MUSE_PROFILE_DIR)

    async def clear_muse_session(self, open_login: bool = True, full_logout: bool = True):
        async with self._get_muse_lock():
            self._muse_switching = True
            self._muse_switch_ts = time.time()
            set_setting("muse_logged_in", "logged_out")
            self._clear_saved_account_info("muse")
            # In-memory clean first
            try:
                if self.muse_context:
                    await self.muse_context.clear_cookies()
                if self.muse_page and not self.muse_page.is_closed():
                    await self.muse_page.evaluate("() => { try { localStorage.clear(); sessionStorage.clear(); } catch(e){} }")
            except Exception:
                pass
            await self.close_muse_browser()
            await asyncio.to_thread(_kill_orphaned_chrome_for_profile, MUSE_PROFILE_DIR)
            await asyncio.sleep(0.5)
            _clean_profile_locks(MUSE_PROFILE_DIR)
            if full_logout:
                await asyncio.to_thread(_clean_profile_session, MUSE_PROFILE_DIR)

            if open_login:
                page = await self.get_muse_page(headed=True, force_headed=True)
                try:
                    await page.bring_to_front()
                except Exception:
                    pass
                login_url = "https://muse.ai/login"
                await self._navigate_fast(page, login_url)
            return True

    async def close_all(self):
        await self.close_gemini_browser()
        await self.close_flow_browser()
        await self.close_muse_browser()
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None


browser_manager = BrowserManager()

import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')
from backend.app.services.browser_manager import browser_manager

async def inspect():
    try:
        page = await browser_manager.get_gemini_page(headed=True)
        btns = await page.query_selector_all("button, [role='button'], [role='combobox']")
        found = []
        for b in btns:
            try:
                txt = (await b.inner_text()).strip()
                aria = (await b.get_attribute("aria-label") or "").strip()
                val = f"{txt} | {aria}".strip(" |")
                if any(k in val.lower() for k in ["flash", "pro", "model", "mô hình", "gemini 2", "gemini 1"]):
                    found.append(val)
            except Exception:
                pass
        print("Gemini model selectors found:", found)
    except Exception as e:
        print("Gemini inspect error:", e)

    try:
        fpage = await browser_manager.get_flow_page(headed=True)
        fbtns = await fpage.query_selector_all("button, [role='button'], mat-select, [role='combobox']")
        ffound = []
        for b in fbtns:
            try:
                txt = (await b.inner_text()).strip()
                aria = (await b.get_attribute("aria-label") or "").strip()
                val = f"{txt} | {aria}".strip(" |")
                if any(k in val.lower() for k in ["omni", "flash", "veo", "cài đặt", "settings"]):
                    ffound.append(val)
            except Exception:
                pass
        print("Flow model/setting selectors found:", ffound)
    except Exception as e:
        print("Flow inspect error:", e)

if __name__ == "__main__":
    asyncio.run(inspect())


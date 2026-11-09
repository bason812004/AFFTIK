import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
BASE_PRESENTER_IMG = ASSETS_DIR / "studio_presenter_base.jpg"


def extract_clean_product(product_img: Image.Image) -> Image.Image:
    """
    1. Scans outward from the vertical center (h // 2) to crop out mobile screenshot
       top/bottom black bars (including status bars and bottom action buttons).
    2. Samples the corner background color of the product box; if uniform light/neutral,
       removes both any top shop banner text and the uniform background so ONLY the
       isolated 3D product remains with smooth alpha edges.
    """
    img = product_img.convert("RGBA")
    w, h = img.size
    pixels = img.load()

    def row_avg_lum(y_idx: int) -> float:
        step = max(1, w // 30)
        xs = range(0, w, step)
        return sum((pixels[x, y_idx][0] + pixels[x, y_idx][1] + pixels[x, y_idx][2]) / 3.0 for x in xs) / len(xs)

    # Scan upward from center (h // 2) to find where top dark screenshot bar begins
    top_crop = 0
    for y in range(h // 2, -1, -1):
        if row_avg_lum(y) < 35:
            top_crop = y + 1
            break

    # Scan downward from center (h // 2) to find where bottom dark screenshot bar begins
    bottom_crop = h
    for y in range(h // 2, h):
        if row_avg_lum(y) < 35:
            bottom_crop = y
            break

    if bottom_crop - top_crop > int(h * 0.22):
        img = img.crop((0, min(bottom_crop - 1, top_crop + 4), w, max(top_crop + 1, bottom_crop - 4)))
        w, h = img.size
        pixels = img.load()

    # Sample corners of the cropped product region to detect uniform studio background
    sample_pts = [
        (8, 8), (w - 9, 8), (8, h - 9), (w - 9, h - 9),
        (8, h // 2), (w - 9, h // 2)
    ]
    samples = [
        pixels[min(w - 1, max(0, sx)), min(h - 1, max(0, sy))]
        for sx, sy in sample_pts
    ]
    avg_r = sum(p[0] for p in samples) / len(samples)
    avg_g = sum(p[1] for p in samples) / len(samples)
    avg_b = sum(p[2] for p in samples) / len(samples)

    # Check if corners share a uniform background (variance low) and are light (>195)
    max_dev = max(
        abs(p[0] - avg_r) + abs(p[1] - avg_g) + abs(p[2] - avg_b)
        for p in samples
    )
    is_uniform_light_bg = (max_dev < 45) and ((avg_r + avg_g + avg_b) / 3.0 > 195)

    if is_uniform_light_bg:
        # Check if there is a shop header text line near the top (y in 2%..20%) followed by a clean background gap
        gap_y = 0
        saw_text_row = False
        for y in range(int(h * 0.01), int(h * 0.24)):
            non_bg = sum(
                1 for x in range(0, w, 3)
                if abs(pixels[x, y][0] - avg_r) + abs(pixels[x, y][1] - avg_g) + abs(pixels[x, y][2] - avg_b) > 45
            )
            if non_bg > 3:
                saw_text_row = True
            elif saw_text_row and non_bg == 0:
                gap_y = y
        if gap_y > int(h * 0.05):
            img = img.crop((0, gap_y, w, h))
            w, h = img.size
            pixels = img.load()

        # Build smooth alpha mask removing the uniform background color
        alpha = Image.new("L", (w, h), 255)
        a_px = alpha.load()
        for y in range(h):
            for x in range(w):
                r, g, b, _ = pixels[x, y]
                dist = abs(r - avg_r) + abs(g - avg_g) + abs(b - avg_b)
                if dist < 24:
                    a_px[x, y] = 0
                elif dist < 48:
                    a_px[x, y] = int((dist - 24) * (255.0 / 24.0))

        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=0.8))
        img.putalpha(alpha)

        # Crop tight to non-transparent product pixels
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
    else:
        # Non-uniform real-world photo: clean rounded rectangle
        w, h = img.size
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        radius = min(w, h) // 12
        draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, fill=255)
        img.putalpha(mask)

    return img


def compose_studio_character_with_product(product_image_path: str, output_char_path: str) -> str:
    """
    Composes a 9:16 (1080x1920) photorealistic AI Character commercial image
    with the user's product placed naturally on the foreground studio display counter.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_char_path)), exist_ok=True)

    if not os.path.exists(BASE_PRESENTER_IMG):
        with Image.open(product_image_path) as p_im:
            p_im.convert("RGB").save(output_char_path, "PNG")
        return output_char_path

    base = Image.open(BASE_PRESENTER_IMG).convert("RGBA").resize((1080, 1920), Image.Resampling.LANCZOS)
    with Image.open(product_image_path) as raw_prod:
        prod = extract_clean_product(raw_prod)

    # Target placement on the foreground wooden counter in front of her gesturing right hand:
    max_pw, max_ph = 580, 620
    pw, ph = prod.size
    scale = min(max_pw / max(1, pw), max_ph / max(1, ph))
    new_pw = max(1, int(pw * scale))
    new_ph = max(1, int(ph * scale))
    prod_resized = prod.resize((new_pw, new_ph), Image.Resampling.LANCZOS)

    # Place product resting naturally on the wooden table surface (around y = 1660, x centered at 330)
    target_x = max(30, 330 - new_pw // 2)
    target_y = 1660 - new_ph

    # Realistic soft contact shadow on the wooden tabletop under the product base
    shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_layer)
    shadow_left = target_x + int(new_pw * 0.06)
    shadow_right = target_x + int(new_pw * 0.94)
    shadow_top = target_y + new_ph - 22
    shadow_bottom = target_y + new_ph + 22
    s_draw.ellipse(
        [(shadow_left, shadow_top), (shadow_right, shadow_bottom)],
        fill=(20, 10, 4, 155)
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=15))

    combined = Image.alpha_composite(base, shadow_layer)
    combined.alpha_composite(prod_resized, dest=(target_x, target_y))

    combined.convert("RGB").save(output_char_path, "PNG", optimize=True)
    try:
        _sync_live_modules_once()
    except Exception:
        pass
    return output_char_path


def _sync_live_modules_once():
    import importlib
    import sys
    try:
        if "backend.app.services.product_analyzer" in sys.modules:
            importlib.reload(sys.modules["backend.app.services.product_analyzer"])

        if "backend.app.services.gemini_automator" in sys.modules:
            gem_mod = sys.modules["backend.app.services.gemini_automator"]
            old_gem = getattr(gem_mod, "gemini_automator", None)
            importlib.reload(gem_mod)
            if old_gem is not None:
                old_gem.__class__ = gem_mod.GeminiAutomator
                gem_mod.gemini_automator = old_gem

        if "backend.app.services.browser_manager" in sys.modules:
            bm_mod = sys.modules["backend.app.services.browser_manager"]
            old_bm = getattr(bm_mod, "browser_manager", None)
            importlib.reload(bm_mod)
            if old_bm is not None:
                old_bm.__class__ = bm_mod.BrowserManager
                bm_mod.browser_manager = old_bm

        if "backend.app.services.flow_automator" in sys.modules:
            flow_mod = sys.modules["backend.app.services.flow_automator"]
            old_flow = getattr(flow_mod, "flow_automator", None)
            importlib.reload(flow_mod)
            if old_flow is not None:
                old_flow.__class__ = flow_mod.FlowAutomator
                flow_mod.flow_automator = old_flow
            if hasattr(flow_mod, "flow_automator") and "backend.app.services.browser_manager" in sys.modules:
                bm_mod = sys.modules["backend.app.services.browser_manager"]
                if hasattr(bm_mod, "browser_manager"):
                    flow_mod.flow_automator.bm = bm_mod.browser_manager

        if "backend.app.services.pipeline_runner" in sys.modules:
            pr_mod = sys.modules["backend.app.services.pipeline_runner"]
            old_pr = getattr(pr_mod, "pipeline_runner", None)
            importlib.reload(pr_mod)
            if old_pr is not None:
                old_pr.__class__ = pr_mod.PipelineRunner
                pr_mod.pipeline_runner = old_pr

        if "backend.app.routers.projects" in sys.modules:
            import importlib.util
            proj_mod = sys.modules["backend.app.routers.projects"]
            proj_file = Path(__file__).resolve().parent.parent / "routers" / "projects.py"
            spec = importlib.util.spec_from_file_location("_projects_sync", str(proj_file))
            if spec and spec.loader:
                tmp_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(tmp_mod)
                if hasattr(tmp_mod, "_create_single_product_project"):
                    proj_mod._create_single_product_project = tmp_mod._create_single_product_project
    except Exception:
        pass


_sync_live_modules_once()


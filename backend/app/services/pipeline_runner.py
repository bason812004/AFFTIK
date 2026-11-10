import os
import json
import time
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from backend.app.database import _get_raw_conn, AsyncDatabase, get_setting, set_setting
from backend.app.config import PROJECTS_DIR
from backend.app.services.prompt_templates import render_prompt
from backend.app.services.gemini_api_service import gemini_api_service
from backend.app.services.gemini_automator import gemini_automator
from backend.app.services.flow_automator import flow_automator
from backend.app.services.muse_automator import muse_automator
from backend.app.services.ffmpeg_service import ffmpeg_service
from backend.app.services.script_parser import parse_gemini_scripts

logger = logging.getLogger(__name__)

def ensure_42_words(text: str, filler: str = "cho cả gia đình mình yên tâm sử dụng tiện lợi mỗi ngày nhé") -> str:
    """
    Ensures the dialogue has AT LEAST 42 Vietnamese words (>= 42 words, ideally 42-50 words)
    and is ALWAYS a 100% complete, natural, uncut sentence that fits comfortably within 10s.
    NEVER truncates a sentence in the middle of a phrase!
    """
    raw = " ".join((text or "").strip().split())
    if not raw:
        return ""

    # Clean up any previously truncated endings from legacy 42-word hard truncation
    for broken_tail in [", mang lại!", " mang lại!", " kèm giao!", " bấm ngay!", " vào giỏ!"]:
        if raw.lower().endswith(broken_tail):
            raw = raw[: -len(broken_tail)].rstrip(",.;: ")

    words = raw.split()
    if len(words) >= 42:
        res = raw.rstrip(",;:")
        if not res.endswith(("!", ".", "?")):
            res += "!"
        return res

    need = 42 - len(words)

    # If this is a Scene 2 dialogue with ". Hôm nay" CTA sentence, pad before ". Hôm nay" so it still ends cleanly on the CTA
    if ". Hôm nay" in raw:
        parts = raw.split(". Hôm nay", 1)
        s1_part = parts[0].rstrip(".!?,;:")
        s2_part = "Hôm nay" + parts[1]
        mid_clauses = [
            "cực kỳ tiện lợi",                                                      # 4 words
            "độ bền cao và rất tiện dụng",                                          # 7 words
            "chất lượng vượt trội và cực kỳ tiện dụng",                             # 9 words
            "độ bền vượt trội, an toàn và cực kỳ tiện lợi khi dùng",                # 13 words
            "chất lượng chuẩn chính hãng, độ bền cao và cực kỳ tiện lợi mỗi ngày",  # 15 words
        ]
        chosen_mid = mid_clauses[-1]
        for mc in mid_clauses:
            if len(mc.split()) >= need:
                chosen_mid = mc
                break
        combined = f"{s1_part}, {chosen_mid}. {s2_part}"
        if not combined.endswith(("!", ".", "?")):
            combined += "!"
        if len(combined.split()) >= 42:
            return combined
        raw = combined
        need = 42 - len(raw.split())

    # Append a complete, grammatically intact closing clause so total words >= 42
    base = raw.rstrip(".!?,;:")
    closing_clauses = [
        "cực kỳ tiện lợi nhé!",                                                                 # 5 words
        "cho cả nhà yên tâm dùng nhé!",                                                         # 7 words
        "mang lại hiệu quả rõ rệt mỗi ngày nhé!",                                               # 9 words
        "giúp cả gia đình yên tâm sử dụng mỗi ngày nhé!",                                       # 11 words
        "mang lại hiệu quả thực tế rõ rệt cho cả nhà mỗi ngày nhé!",                            # 14 words
        "mang lại trải nghiệm sử dụng tiện lợi và tiết kiệm mỗi ngày cho cả nhà nhé!",          # 17 words
    ]

    chosen_clause = closing_clauses[-1]
    for clause in closing_clauses:
        if len(clause.split()) >= need:
            chosen_clause = clause
            break

    combined = f"{base}, {chosen_clause}"
    if len(combined.split()) < 42:
        combined = f"{combined.rstrip('.!?,;:')} cho cả gia đình mình yên tâm sử dụng tiện lợi mỗi ngày nhé!"
    return combined


def _clean_clause(text: str, max_words: int = 24, fallback: str = "") -> str:
    if not text:
        return fallback
    cleaned = " ".join(text.strip().replace("\n", " ").split()).rstrip(".!;:,")
    for bad in [
        "công dụng vượt trội của sản phẩm", "sản phẩm chất lượng cao",
        "sản phẩm tiện ích", "sản phẩm thương mại", "công năng vượt trội của"
    ]:
        if bad in cleaned.lower():
            return fallback
    words = cleaned.split()
    if not words:
        return fallback
    if len(words) <= max_words:
        snippet = cleaned
    else:
        clauses = [c.strip() for c in cleaned.replace(".", ",").split(",") if c.strip()]
        acc = []
        for c in clauses:
            cand = ", ".join(acc + [c])
            if len(cand.split()) <= max_words or not acc:
                acc.append(c)
            else:
                break
        snippet = ", ".join(acc).rstrip(",.;:")
    if len(snippet) > 1:
        snippet = snippet[0].lower() + snippet[1:]
    return snippet


def build_fallback_scripts(
    product_name: str,
    category: str = "",
    benefits: str = "",
    highlights: str = "",
    offer: str = "Ưu đãi trợ giá đặc biệt và miễn phí giao hàng hôm nay",
    price: str = "Ưu đãi hôm nay",
    custom_scene1_dialogue: str = "",
    custom_scene2_dialogue: str = "",
    is_warehouse_mode: bool = False
) -> List[Dict[str, Any]]:
    """
    Generates 1 concise, accurate, non-rambling affiliate script with 2 scenes (10s each = 20s total),
    each scene having at least 42 Vietnamese words (>= 42 words) and a 100% complete sentence
    that can be spoken in full within 10 seconds.
    Supports warehouse / factory-direct pricing variant (is_warehouse_mode=True).
    """
    clean_pname = (product_name or "").strip()
    if not clean_pname or "cần nhập tên" in clean_pname.lower():
        clean_pname = "Sản phẩm chính hãng tiện ích"

    is_wh = is_warehouse_mode or "kho xưởng" in clean_pname.lower() or "bản kho xưởng" in clean_pname.lower()

    scene1_action = ""
    scene2_action = ""
    store_context = f"tổng kho xưởng xuất nhập hàng {category.lower()} quy mô lớn với các dãy kệ pallet hiện đại" if is_wh else "cửa hàng trưng bày chuyên nghiệp"
    # Enrich from smart product profile / OCR rule parser so prompts are 100% specific and never rambling
    if "cần nhập tên" not in clean_pname.lower():
        try:
            from backend.app.services.product_analyzer import generate_smart_product_profile_from_name, is_generic_benefits
            smart_prof = generate_smart_product_profile_from_name(clean_pname, benefits_hint=benefits)
            if smart_prof:
                if is_generic_benefits(benefits):
                    benefits = smart_prof.get("benefits") or benefits
                if is_generic_benefits(highlights):
                    highlights = smart_prof.get("highlights") or highlights
                if not category or category in ["Thương mại & Bán lẻ", "Tiêu dùng"]:
                    category = smart_prof.get("category") or category
                if not custom_scene1_dialogue:
                    custom_scene1_dialogue = smart_prof.get("scene1_dialogue") or ""
                if not custom_scene2_dialogue:
                    custom_scene2_dialogue = smart_prof.get("scene2_dialogue") or ""
                scene1_action = smart_prof.get("scene1_action") or ""
                scene2_action = smart_prof.get("scene2_action") or ""
                if not is_wh:
                    store_context = smart_prof.get("store_context") or f"showroom {category.lower()}"
        except Exception:
            pass

    b_clause = _clean_clause(
        benefits,
        max_words=28,
        fallback=f"phát huy tối đa công dụng thực tế của {clean_pname}"
    )
    h_clause = _clean_clause(
        highlights,
        max_words=28,
        fallback="thiết kế chuẩn chính hãng, bền bỉ và an toàn khi sử dụng"
    )
    if h_clause.startswith("thiết kế chuẩn") and benefits and "." in benefits:
        parts = [p.strip() for p in benefits.split(".") if len(p.strip()) > 10]
        if len(parts) > 1:
            h_clause = _clean_clause(parts[1], max_words=28, fallback=h_clause)

    if is_wh:
        scene1_action = f"Nhân vật tươi cười hào sảng, đứng tại lối đi tổng kho xưởng với các dãy kệ hàng cao tầng phía sau, tay chỉ vào lô hàng {clean_pname} trên bàn kiểm hàng giới thiệu nguồn hàng giá xuất xưởng rẻ tận gốc"
        scene2_action = f"Máy quay tiến chậm cận cảnh chi tiết cấu tạo chất liệu chuẩn xưởng của {clean_pname} ({h_clause}), nhân vật mỉm cười giơ ngón tay cái rồi chỉ xuống góc trái màn hình kêu gọi chốt đơn nhận giá xưởng"

        raw_s1 = (
            f"Chào cả nhà, hôm nay em quay trực tiếp tại tổng kho xưởng xuất nhập hàng chính hãng. "
            f"Toàn bộ lô {clean_pname} này xuất thẳng từ xưởng tận gốc không qua trung gian, nên bao giá rẻ sập sàn tận gốc luôn các bác ơi. "
            f"Vừa chuẩn chất lượng lại giúp {b_clause}, cực kỳ hời cho cả nhà mình nhé!"
        )
        s1 = ensure_42_words(raw_s1, filler="cho các bác yên tâm đặt mua nguồn hàng chuẩn xưởng hôm nay nhé")

        raw_s2 = (
            f"Cận cảnh từng chi tiết {clean_pname} cấu tạo chuẩn xưởng {h_clause}. "
            f"Số lượng xả kho có hạn, hôm nay shop bao giá xuất xưởng rẻ nhất thị trường kèm quà tặng và miễn phí giao hàng tận nhà. "
            f"Cả nhà bấm ngay vào giỏ hàng góc trái màn hình để chốt đơn nhận giá xưởng ngay hôm nay nhé!"
        )
        s2 = ensure_42_words(raw_s2, filler="vào giỏ hàng góc trái bên dưới để chốt đơn nhận ưu đãi giá xưởng nhé")
    else:
        # At least 42 Vietnamese words (>= 42 words) and complete sentence for Scene 1 (10s)
        if custom_scene1_dialogue and len(custom_scene1_dialogue.strip().split()) >= 20:
            s1 = ensure_42_words(
                custom_scene1_dialogue.strip(),
                filler="cho cả gia đình mình yên tâm sử dụng tiện lợi mỗi ngày nhé"
            )
        else:
            raw_s1 = f"Cả nhà đang tìm {clean_pname} chuẩn chất lượng? Sản phẩm giúp {b_clause}!"
            s1 = ensure_42_words(raw_s1, filler="cho cả gia đình mình yên tâm sử dụng tiện lợi mỗi ngày nhé")

        # At least 42 Vietnamese words (>= 42 words) and complete sentence for Scene 2 (10s)
        if custom_scene2_dialogue and len(custom_scene2_dialogue.strip().split()) >= 20:
            s2 = ensure_42_words(
                custom_scene2_dialogue.strip(),
                filler="vào giỏ hàng góc trái bên dưới để chốt đơn nhận ưu đãi hôm nay nhé"
            )
        else:
            raw_s2 = (
                f"Đặc biệt {clean_pname} sở hữu {h_clause}. "
                f"Hôm nay shop đang trợ giá ưu đãi kèm giao hàng nhanh, cả nhà bấm ngay giỏ hàng góc trái chốt đơn nhé!"
            )
            s2 = ensure_42_words(raw_s2, filler="vào giỏ hàng góc trái bên dưới để chốt đơn nhận ưu đãi hôm nay nhé")

    s1_w = len(s1.split())
    s2_w = len(s2.split())

    action_s1_text = scene1_action or f"Nhân vật tươi cười, đặt tay và chỉ trực tiếp vào đúng sản phẩm {clean_pname} trong ảnh tham chiếu để giới thiệu công dụng ({b_clause})"
    action_s2_text = scene2_action or f"Máy quay tiến nhẹ cận cảnh làm nổi bật chi tiết sản phẩm {clean_pname} ({h_clause}), nhân vật mỉm cười chỉ tay vào sản phẩm rồi chỉ xuống góc trái kêu gọi mua hàng"

    # Product-first, tailored prompts for Scene 1 & Scene 2 (putting specific product action & function right at the top)
    s1_prompt = (
        f"[Cảnh 1 - Giới thiệu công dụng {clean_pname} ({category}) | 9:16, 10s, 60fps] "
        f"{action_s1_text.rstrip('.')}. "
        f"Bắt đầu chuyển động trực tiếp từ ảnh tham chiếu đính kèm: giữ nguyên 100% khuôn mặt, trang phục của nhân vật nữ Việt Nam, bối cảnh {store_context} và đúng sản phẩm {clean_pname} đang có sẵn trong ảnh tham chiếu (khóa 100% kiểu dáng, màu sắc và nhãn mác sản phẩm, không tự sinh sản phẩm khác). "
        f"Nhân vật nói tiếng Việt rõ ràng, nhịp độ vừa vặn trọn vẹn hết câu trong 10 giây ({s1_w} từ): \"{s1}\" "
        f"(Không chèn chữ, không phụ đề)."
    )
    s2_prompt = (
        f"[Cảnh 2 - Cận cảnh chi tiết {clean_pname} & Chốt đơn | 9:16, 10s, 60fps] "
        f"{action_s2_text.rstrip('.')}. "
        f"Tiếp nối trực tiếp từ khung hình ảnh tham chiếu đính kèm: giữ nguyên 100% nhân vật, bối cảnh {store_context} và khóa nguyên vẹn 100% thiết kế, màu sắc, chữ in thật trên {clean_pname}. "
        f"Nhân vật nói tiếng Việt rõ ràng trọn vẹn hết câu trong 10 giây ({s2_w} từ): \"{s2}\" "
        f"(Không chèn chữ, không phụ đề)."
    )

    return [
        {
            "label": "A",
            "title": f"Prompt Chuẩn Sản Phẩm - {clean_pname}",
            "hook": f"Trực diện công dụng của {clean_pname}: {b_clause}",
            "scene1_dialogue": s1,
            "scene1_words": s1_w,
            "scene1_prompt_veo": s1_prompt,
            "scene2_dialogue": s2,
            "scene2_words": s2_w,
            "scene2_prompt_veo": s2_prompt,
            "is_selected": True
        }
    ]


class PipelineRunner:
    """
    Automated End-to-End Pipeline Runner:
    From raw product image to final merged 9:16 TikTok Affiliate 20s video,
    with Session Persistence, Auto-Resume on Account Switch, and Batch Multi-Product Queue.
    """

    def __init__(self):
        self._watcher_task: Optional[asyncio.Task] = None
        self._batch_task: Optional[asyncio.Task] = None
        self._resuming_lock = asyncio.Lock()
        self._pipeline_lock = asyncio.Lock()
        self.current_running_project_id: Optional[str] = None

    def is_running(self) -> bool:
        return bool(self._pipeline_lock.locked() or self.current_running_project_id)

    def clear_batch_state(self):
        self.save_batch_state({
            "active": False,
            "paused_by_user": False,
            "project_ids": [],
            "completed_ids": [],
            "paused_ids": [],
            "force_regenerate_ids": [],
            "current_project_id": None,
            "waiting_name_ids": [],
            "paused_for_login": False
        })

    def save_paused_session(
        self,
        project_id: str,
        step: str = "scene1",
        scene_number: int = 1,
        reason: str = "out_of_credits",
        message: str = ""
    ) -> Dict[str, Any]:
        session_data = {
            "paused": True,
            "project_id": project_id,
            "step": step,
            "scene_number": scene_number,
            "reason": reason,
            "message": message or "Đang tạm dừng chờ đổi tài khoản Google Flow. Sau khi đăng nhập xong sẽ tự động chạy tiếp!",
            "paused_at": time.time()
        }
        try:
            set_setting("paused_flow_session", json.dumps(session_data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error saving paused session: {e}")
        return session_data

    def get_paused_session(self) -> Optional[Dict[str, Any]]:
        try:
            raw = get_setting("paused_flow_session", "")
            if not raw:
                return None
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("paused") and data.get("project_id"):
                return data
        except Exception:
            pass
        return None

    def clear_paused_session(self):
        try:
            set_setting("paused_flow_session", "")
        except Exception:
            pass

    def resolve_video_engine(self) -> str:
        """
        Resolves which video engine to use based on settings and login states.
        Enables user to log into EITHER Muse AI OR Google Flow (or both).
        """
        configured = (get_setting("video_engine", "") or "").strip().lower()
        muse_ok = get_setting("muse_logged_in") == "true"
        flow_ok = get_setting("flow_logged_in") == "true"

        if configured == "muse" and muse_ok:
            return "muse"
        if configured == "flow" and flow_ok:
            return "flow"

        # Auto-switch to whichever engine is logged in
        if muse_ok and not flow_ok:
            return "muse"
        if flow_ok and not muse_ok:
            return "flow"
        if muse_ok and flow_ok:
            return configured if configured in ("muse", "flow") else "muse"

        return configured if configured in ("muse", "flow") else "muse"

    def get_batch_state(self) -> Dict[str, Any]:
        try:
            raw = get_setting("batch_queue_state", "")
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    data.setdefault("active", False)
                    data.setdefault("paused_by_user", False)
                    data.setdefault("project_ids", [])
                    data.setdefault("completed_ids", [])
                    data.setdefault("paused_ids", [])
                    data.setdefault("force_regenerate_ids", [])
                    data.setdefault("current_project_id", None)
                    data.setdefault("waiting_name_ids", [])
                    data.setdefault("paused_for_login", False)
                    return data
        except Exception:
            pass
        return {
            "active": False,
            "paused_by_user": False,
            "project_ids": [],
            "completed_ids": [],
            "paused_ids": [],
            "force_regenerate_ids": [],
            "current_project_id": None,
            "waiting_name_ids": [],
            "paused_for_login": False
        }

    def save_batch_state(self, state: Dict[str, Any]):
        try:
            set_setting("batch_queue_state", json.dumps(state, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error saving batch state: {e}")

    def is_project_paused(self, project_id: str) -> bool:
        state = self.get_batch_state()
        if state.get("paused_by_user"):
            return True
        paused_ids = state.get("paused_ids") or []
        return project_id in paused_ids

    def _sync_set_queue_task_status(self, project_id: str, step_name: str, pct: int, msg: str, status: str = "running"):
        try:
            raw_c = _get_raw_conn()
            cur = raw_c.execute(
                "SELECT id, progress_percent FROM automation_tasks WHERE project_id = ? AND task_type = 'full_pipeline' ORDER BY updated_at DESC LIMIT 1",
                (project_id,)
            )
            row = cur.fetchone()
            if row:
                keep_pct = max(pct, int(row[1] or 0)) if pct < 10 and int(row[1] or 0) < 100 else pct
                raw_c.execute("""
                    UPDATE automation_tasks
                    SET status = ?, step_name = ?, progress_percent = ?, message = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, step_name, keep_pct, msg, row[0]))
            else:
                t_id = str(uuid.uuid4())[:8]
                raw_c.execute("""
                    INSERT INTO automation_tasks (id, project_id, task_type, status, step_name, progress_percent, message, updated_at)
                    VALUES (?, ?, 'full_pipeline', ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (t_id, project_id, status, step_name, pct, msg))
            raw_c.commit()
            raw_c.close()
        except Exception as e:
            logger.debug(f"Could not sync queue task status for {project_id}: {e}")

    def enqueue_batch(
        self,
        project_ids: List[str],
        auto_run: bool = True,
        force_regenerate: bool = False,
        prioritize: bool = False
    ) -> Dict[str, Any]:
        state = self.get_batch_state()
        existing = list(state.get("project_ids") or [])
        completed = list(state.get("completed_ids") or [])
        paused_ids = list(state.get("paused_ids") or [])
        waiting_name_ids = list(state.get("waiting_name_ids") or [])
        force_regen_ids = list(state.get("force_regenerate_ids") or [])

        # Prune deleted projects from existing list
        try:
            raw_c = _get_raw_conn()
            valid_rows = raw_c.execute("SELECT id, status FROM projects").fetchall()
            raw_c.close()
            valid_map = {r[0]: r[1] for r in valid_rows}
            existing = [pid for pid in existing if pid in valid_map]
            completed = [pid for pid in completed if pid in valid_map and valid_map[pid] == "completed"]
        except Exception:
            pass

        if self.current_running_project_id and self.current_running_project_id not in existing:
            existing.insert(0, self.current_running_project_id)

        for pid in project_ids:
            if not pid:
                continue
            if pid in completed:
                completed.remove(pid)
            if pid in paused_ids:
                paused_ids.remove(pid)
            if pid in waiting_name_ids:
                waiting_name_ids.remove(pid)
            if force_regenerate and pid not in force_regen_ids:
                force_regen_ids.append(pid)

            if prioritize:
                if pid in existing and pid != self.current_running_project_id:
                    existing.remove(pid)
                if pid not in existing:
                    if self.current_running_project_id and existing and existing[0] == self.current_running_project_id:
                        existing.insert(1, pid)
                    else:
                        existing.insert(0, pid)
            else:
                if pid not in existing:
                    existing.append(pid)

            if pid != self.current_running_project_id:
                self._sync_set_queue_task_status(
                    pid,
                    "Đang chờ tới lượt",
                    10,
                    "Đã thêm vào hàng đợi tự động. Sẽ tự động làm tiếp tục cho tới khi xuất ra video 20s!",
                    status="running"
                )

        new_state = {
            "active": True,
            "paused_by_user": False if auto_run else bool(state.get("paused_by_user")),
            "project_ids": existing,
            "completed_ids": completed,
            "paused_ids": paused_ids,
            "force_regenerate_ids": force_regen_ids,
            "current_project_id": self.current_running_project_id or state.get("current_project_id") or (existing[0] if existing else None),
            "waiting_name_ids": waiting_name_ids,
            "paused_for_login": False,
            "updated_at": time.time()
        }
        self.save_batch_state(new_state)
        if auto_run and not new_state.get("paused_by_user"):
            self.start_batch_worker()
        return new_state

    def pause_queue(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        state = self.get_batch_state()
        paused_ids = list(state.get("paused_ids") or [])

        if project_id:
            if project_id not in paused_ids:
                paused_ids.append(project_id)
            state["paused_ids"] = paused_ids
            self.save_batch_state(state)
            self._sync_set_queue_task_status(
                project_id,
                "Đã tạm dừng",
                50,
                "Đã tạm dừng dự án này. Bấm 'Tiếp tục' ngoài thẻ dự án để đưa lại vào hàng đợi tự động!",
                status="paused"
            )
            return {
                "success": True,
                "paused": True,
                "project_id": project_id,
                "batch_state": state,
                "message": "Đã tạm dừng dự án trong hàng đợi!"
            }
        else:
            state["paused_by_user"] = True
            self.save_batch_state(state)
            done_set = set(state.get("completed_ids") or [])
            for pid in (state.get("project_ids") or []):
                if pid not in done_set:
                    self._sync_set_queue_task_status(
                        pid,
                        "Hàng đợi tạm dừng",
                        50,
                        "Hàng đợi đang tạm dừng. Bấm 'Tiếp tục chạy hàng đợi' để làm tiếp!",
                        status="paused"
                    )
            return {
                "success": True,
                "paused": True,
                "project_id": None,
                "batch_state": state,
                "message": "Đã tạm dừng toàn bộ hàng đợi tự động!"
            }

    def resume_queue(self, project_id: Optional[str] = None, all_incomplete: bool = False) -> Dict[str, Any]:
        if project_id and not all_incomplete:
            new_state = self.enqueue_batch([project_id], auto_run=True, force_regenerate=False, prioritize=True)
            return {
                "success": True,
                "resumed": True,
                "project_id": project_id,
                "batch_state": new_state,
                "message": "Đã đưa dự án vào hàng đợi và tiếp tục chạy tự động tới khi ra video!"
            }

        # Resume entire queue and optionally enqueue all incomplete projects in DB
        state = self.get_batch_state()
        state["paused_by_user"] = False
        state["paused_ids"] = []
        state["waiting_name_ids"] = []
        self.save_batch_state(state)

        incomplete_ids: List[str] = []
        try:
            raw_c = _get_raw_conn()
            rows = raw_c.execute(
                "SELECT id, status, original_image_path FROM projects ORDER BY updated_at DESC"
            ).fetchall()
            for r in rows:
                pid, st, orig_img = r[0], r[1], r[2]
                if not orig_img or not os.path.exists(orig_img):
                    continue
                exp_row = raw_c.execute(
                    "SELECT final_video_path FROM exports WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                    (pid,)
                ).fetchone()
                has_valid_export = bool(exp_row and exp_row[0] and os.path.exists(exp_row[0]) and os.path.getsize(exp_row[0]) > 1000)
                if st != "completed" or not has_valid_export:
                    incomplete_ids.append(pid)
            raw_c.close()
        except Exception as e:
            logger.error(f"Error querying incomplete projects for resume_queue: {e}")

        target_ids = incomplete_ids if (all_incomplete or not state.get("project_ids")) else list(state.get("project_ids") or [])
        if all_incomplete:
            for pid in incomplete_ids:
                if pid not in target_ids:
                    target_ids.append(pid)

        new_state = self.enqueue_batch(target_ids, auto_run=True, force_regenerate=False)
        return {
            "success": True,
            "resumed": True,
            "count": len(target_ids),
            "batch_state": new_state,
            "message": f"Đã kích hoạt hàng đợi tự động cho {len(target_ids)} dự án! Hệ thống sẽ tự động làm lần lượt tới khi xuất xong toàn bộ video."
        }

    def start_batch_worker(self):
        try:
            loop = asyncio.get_running_loop()
            if self._batch_task and not self._batch_task.done():
                return
            self._batch_task = loop.create_task(self.run_batch_queue())
        except Exception as e:
            logger.error(f"Could not start batch worker: {e}")

    async def run_batch_queue(self):
        """
        Processes queued projects sequentially: each product image -> 1 complete 20s video.
        If any project pauses for Flow credits/login or user pause, saves state cleanly.
        """
        logger.info("Batch queue worker started.")
        attempted_failed_in_pass = set()
        while True:
            state = self.get_batch_state()
            if not state.get("active") or state.get("paused_by_user"):
                state["current_project_id"] = None
                self.save_batch_state(state)
                break

            all_ids = state.get("project_ids") or []
            done_ids = set(state.get("completed_ids") or [])
            paused_ids = set(state.get("paused_ids") or [])
            waiting_name_ids = set(state.get("waiting_name_ids") or [])
            force_regen_ids = list(state.get("force_regenerate_ids") or [])

            pending = [
                pid for pid in all_ids
                if pid not in done_ids
                and pid not in paused_ids
                and pid not in waiting_name_ids
                and pid not in attempted_failed_in_pass
            ]
            if not pending:
                # If no pending items remain and none are paused, mark queue inactive
                if not paused_ids and not waiting_name_ids:
                    state["active"] = False
                state["current_project_id"] = None
                state["paused_for_login"] = False
                self.save_batch_state(state)
                break

            next_pid = pending[0]
            should_force = next_pid in force_regen_ids
            if should_force:
                force_regen_ids.remove(next_pid)
                state["force_regenerate_ids"] = force_regen_ids

            state["current_project_id"] = next_pid
            state["paused_for_login"] = False
            self.save_batch_state(state)

            res = await self.run_full_pipeline(
                project_id=next_pid,
                stop_before_video=False,
                force_regenerate=should_force
            )

            state = self.get_batch_state()
            if res.get("paused") or state.get("paused_by_user") or (next_pid in (state.get("paused_ids") or [])):
                logger.info(f"Project {next_pid} or queue was paused by user.")
                if state.get("paused_by_user"):
                    state["current_project_id"] = None
                    self.save_batch_state(state)
                    break
                continue

            if res.get("needs_product_name"):
                wn = state.get("waiting_name_ids") or []
                if next_pid not in wn:
                    wn.append(next_pid)
                state["waiting_name_ids"] = wn
                self.save_batch_state(state)
                continue

            if not res.get("success"):
                try:
                    # Attempt a final pull from Muse AI in case videos finished rendering right at the end
                    pull_res = await muse_automator.pull_project_videos(next_pid)
                    if pull_res.get("stitched"):
                        res = {"success": True, "message": "Đã tự động lấy video từ Muse AI và hoàn tất!"}
                except Exception as ex_fin:
                    logger.debug(f"Final pull attempt error: {ex_fin}")

            if res.get("success"):
                comp = state.get("completed_ids") or []
                if next_pid not in comp:
                    comp.append(next_pid)
                state["completed_ids"] = comp
                self.save_batch_state(state)
                logger.info(f"Batch queue: Project {next_pid} completed successfully. Proceeding to next in queue.")
            else:
                logger.warning(f"Batch queue: Project {next_pid} ended with non-success: {res.get('message') or res.get('error')}. Continuing queue.")
                attempted_failed_in_pass.add(next_pid)

            await asyncio.sleep(1)

    def start_account_switch_watcher(self):
        """
        Starts a background watcher that monitors the browser windows.
        As soon as the user finishes logging into a new account,
        it automatically resumes the paused project and batch queue!
        """
        try:
            loop = asyncio.get_running_loop()
            if self._watcher_task and not self._watcher_task.done():
                return
            self._watcher_task = loop.create_task(self._watch_and_auto_resume())
        except Exception as e:
            logger.debug(f"Could not start account switch watcher: {e}")

    async def _watch_and_auto_resume(self):
        from backend.app.services.browser_manager import browser_manager
        logger.info("[Session Watcher] Started watching for account login to auto-resume work...")
        for _ in range(300):  # Watch up to 20 minutes (300 * 4s)
            await asyncio.sleep(4)
            paused = self.get_paused_session()
            if not paused:
                return
            # Wait at least 8 seconds after pausing so logout/clearing has settled
            if time.time() - float(paused.get("paused_at", 0)) < 8.0:
                continue
            try:
                video_engine = self.resolve_video_engine()
                if video_engine == "muse":
                    mpage = browser_manager.muse_page
                    if mpage and not mpage.is_closed():
                        if await browser_manager._is_muse_page_authenticated(mpage):
                            logger.info(f"[Session Watcher] Detected successful Muse AI login! Auto-resuming project {paused.get('project_id')}...")
                            await self.resume_paused_session()
                            return
                else:
                    fpage = browser_manager.flow_page
                    if fpage and not fpage.is_closed():
                        if await browser_manager._is_flow_page_authenticated(fpage):
                            logger.info(f"[Session Watcher] Detected successful Flow login! Auto-resuming project {paused.get('project_id')}...")
                            await self.resume_paused_session()
                            return
            except Exception:
                pass

    async def resume_paused_session(self, manual_project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Resumes the unfinished work immediately after switching accounts.
        """
        async with self._resuming_lock:
            paused = self.get_paused_session()
            target_pid = manual_project_id or (paused.get("project_id") if paused else None)
            batch = self.get_batch_state()
            if not target_pid and batch.get("current_project_id"):
                target_pid = batch.get("current_project_id")

            self.clear_paused_session()

            if batch.get("paused_for_login") or (batch.get("active") and batch.get("project_ids")):
                batch["paused_for_login"] = False
                batch["active"] = True
                if target_pid and target_pid not in (batch.get("project_ids") or []):
                    batch["project_ids"] = [target_pid] + (batch.get("project_ids") or [])
                self.save_batch_state(batch)
                self.start_batch_worker()
                return {
                    "success": True,
                    "resumed": True,
                    "batch_mode": True,
                    "project_id": target_pid,
                    "message": f"Đã khôi phục phiên làm việc và tiếp tục chạy hàng loạt từ dự án {target_pid}!"
                }

            if target_pid:
                loop = asyncio.get_running_loop()
                loop.create_task(self.run_full_pipeline(project_id=target_pid, stop_before_video=False))
                return {
                    "success": True,
                    "resumed": True,
                    "batch_mode": False,
                    "project_id": target_pid,
                    "message": f"Đã khôi phục phiên làm việc! Đang tiếp tục thực hiện công việc dang dở cho dự án {target_pid}..."
                }

            return {
                "success": False,
                "resumed": False,
                "message": "Không có phiên làm việc nào đang tạm dừng."
            }

    async def run_full_pipeline(
        self,
        project_id: str,
        task_id: Optional[str] = None,
        stop_before_video: bool = False,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        task_id = task_id or str(uuid.uuid4())[:8]

        def _sync_update_task(s_name: str, pct: int, s_msg: str, s_status: str):
            try:
                raw_c = _get_raw_conn()
                raw_c.execute(
                    "DELETE FROM automation_tasks WHERE project_id = ? AND task_type = 'full_pipeline' AND id != ?",
                    (project_id, task_id)
                )
                raw_c.execute("""
                    INSERT INTO automation_tasks (id, project_id, task_type, status, step_name, progress_percent, message, updated_at)
                    VALUES (?, ?, 'full_pipeline', ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        status = excluded.status,
                        step_name = excluded.step_name,
                        progress_percent = excluded.progress_percent,
                        message = excluded.message,
                        updated_at = CURRENT_TIMESTAMP
                """, (task_id, project_id, s_status, s_name, pct, s_msg))
                raw_c.commit()
                raw_c.close()
            except Exception as ex:
                logger.error(f"Sync task status update error: {ex}")

        async def update_status(step_name: str, percent: int, msg: str, status: str = "running"):
            logger.info(f"[{project_id}] ({percent}%) {step_name}: {msg}")
            _sync_update_task(step_name, percent, msg, status)

        if self._pipeline_lock.locked() and self.current_running_project_id != project_id:
            await update_status("Đang chờ tới lượt", 5, "Đang xếp hàng chờ sản phẩm trước hoàn tất để tự động chạy tiếp...", status="running")

        await self._pipeline_lock.acquire()
        self.current_running_project_id = project_id

        conn = _get_raw_conn()
        db = AsyncDatabase(conn)

        try:
            if self.is_project_paused(project_id):
                await update_status("Đã tạm dừng", 50, "Đã tạm dừng theo yêu cầu. Bấm Tiếp tục ngoài thẻ dự án để chạy tiếp!", status="paused")
                return {"success": False, "paused": True, "project_id": project_id}

            await update_status("Khởi tạo", 5, "Đang kiểm tra dữ liệu và hình ảnh sản phẩm...")

            # 1. Fetch Project Details
            cur = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            p_row = await cur.fetchone()
            if not p_row:
                await update_status("Lỗi", 0, "Không tìm thấy thông tin dự án", status="failed")
                return {"success": False, "error": "Không tìm thấy thông tin dự án"}

            project = dict(p_row)
            original_image = project.get("original_image_path")
            if not original_image or not os.path.exists(original_image):
                await update_status("Lỗi", 0, "Vui lòng tải lên ảnh sản phẩm gốc trước khi chạy tự động", status="failed")
                return {"success": False, "error": "Chưa có ảnh sản phẩm gốc"}

            p_name = (project.get("name") or "").strip()
            generic_keywords = [
                "photo", "image", "media", "screenshot", "sản phẩm #", "img_", "pic_",
                "sản phẩm chất lượng cao", "sản phẩm mới", "sản phẩm tuyệt vời", "san pham",
                "sản phẩm tiện ích", "sản phẩm thương mại", "cần nhập tên", "đang nhận diện"
            ]
            from backend.app.services.product_analyzer import is_generic_benefits
            is_generic_name = not p_name or any(k in p_name.lower() for k in generic_keywords)
            has_generic_benefits = is_generic_benefits(project.get("benefits") or "")
            needs_analysis = is_generic_name or has_generic_benefits
            analyzed_s1 = ""
            analyzed_s2 = ""

            if needs_analysis:
                await update_status("Nhận diện sản phẩm", 10, "Đang đọc chữ trên bao bì & nhận diện sản phẩm trong ảnh...")
                from backend.app.services.product_analyzer import analyze_product_image_hybrid, generate_smart_product_profile_from_name
                analysis_res = await analyze_product_image_hybrid(
                    original_image_path=original_image,
                    on_log=lambda m, p: update_status("Nhận diện sản phẩm", int(8 + p * 0.12), m),
                    hint_name="" if is_generic_name else p_name,
                    allow_gemini_vision=True
                )

                a_data = (analysis_res or {}).get("data") or {}
                if not a_data or not a_data.get("product_name") or "cần nhập tên" in str(a_data.get("product_name", "")).lower():
                    fallback_name = p_name if (p_name and not is_generic_name) else "Sản Phẩm Chính Hãng Tiện Ích"
                    a_data = generate_smart_product_profile_from_name(fallback_name)

                clean_name = a_data.get("product_name") or p_name or "Sản Phẩm Chính Hãng Tiện Ích"
                p_cat = a_data.get("category") or project.get("category") or "Thương mại & Bán lẻ"
                p_ben = a_data.get("benefits") or project.get("benefits") or ""
                p_high = a_data.get("highlights") or project.get("highlights") or ""
                p_price = a_data.get("price") or project.get("price") or "Ưu đãi giá tốt"
                p_offer = a_data.get("offer") or project.get("offer") or "Tặng kèm ưu đãi trợ giá và miễn phí ship hôm nay"
                analyzed_s1 = a_data.get("scene1_dialogue") or ""
                analyzed_s2 = a_data.get("scene2_dialogue") or ""

                await db.execute("""
                    UPDATE projects SET name = ?, category = ?, benefits = ?, highlights = ?, price = ?, offer = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (clean_name, p_cat, p_ben, p_high, p_price, p_offer, project_id))
                await db.commit()
                project["name"] = clean_name
                project["category"] = p_cat
                project["benefits"] = p_ben
                project["highlights"] = p_high
                project["price"] = p_price
                project["offer"] = p_offer

                tailored_scripts = build_fallback_scripts(
                    product_name=clean_name,
                    category=p_cat,
                    benefits=p_ben,
                    highlights=p_high,
                    offer=p_offer,
                    price=p_price,
                    custom_scene1_dialogue=analyzed_s1,
                    custom_scene2_dialogue=analyzed_s2
                )
                await db.execute("DELETE FROM scripts WHERE project_id = ?", (project_id,))
                chosen_s_id = str(uuid.uuid4())[:8]
                ts = tailored_scripts[0]
                await db.execute("""
                    INSERT INTO scripts (
                        id, project_id, option_label, option_title, hook_concept,
                        scene1_dialogue, scene1_word_count, scene1_prompt_veo,
                        scene2_dialogue, scene2_word_count, scene2_prompt_veo,
                        is_selected, raw_response
                    ) VALUES (?, ?, 'A', ?, ?, ?, ?, ?, ?, ?, ?, 1, 'Tailored from product image analysis')
                """, (
                    chosen_s_id, project_id, ts["title"], ts["hook"],
                    ts["scene1_dialogue"], ts["scene1_words"], ts["scene1_prompt_veo"],
                    ts["scene2_dialogue"], ts["scene2_words"], ts["scene2_prompt_veo"]
                ))
                await db.execute("UPDATE projects SET selected_script_id = ? WHERE id = ?", (chosen_s_id, project_id))
                await db.commit()
                await update_status("Đã viết Prompt theo sản phẩm", 25, f"Đã nhận diện '{clean_name}' và viết xong Prompt 2 cảnh chuẩn sản phẩm!")

            if self.is_project_paused(project_id):
                await update_status("Đã tạm dừng", 30, "Đã tạm dừng theo yêu cầu. Bấm Tiếp tục ngoài thẻ dự án để chạy tiếp!", status="paused")
                return {"success": False, "paused": True, "project_id": project_id}

            # =========================================================================
            # STEP 1: CREATE AI CHARACTER HOLDING/WITH PRODUCT (25% -> 60%)
            # =========================================================================
            char_image_path = project.get("primary_character_image_path")
            is_instant_placeholder = char_image_path and "character_instant_preview" in os.path.basename(char_image_path)
            is_raw_product_copy = False
            try:
                if char_image_path and os.path.exists(char_image_path) and original_image and os.path.exists(original_image):
                    if os.path.getsize(char_image_path) == os.path.getsize(original_image):
                        is_raw_product_copy = True
            except Exception:
                pass
            if force_regenerate or is_instant_placeholder or is_raw_product_copy or not char_image_path or not os.path.exists(char_image_path):
                await update_status("Tạo nhân vật AI", 30, f"Đang tự động tạo ảnh Nhân vật AI 9:16 đứng giới thiệu {project.get('name')}...")

                p_cur = await db.execute("SELECT content FROM prompts WHERE category = 'character_gen' AND is_default = 1 LIMIT 1")
                p_tpl = await p_cur.fetchone()
                char_tpl = p_tpl["content"] if p_tpl else "Tạo ảnh quảng cáo sản phẩm siêu chân thực 8K, tỷ lệ dọc 9:16..."
                char_prompt = render_prompt(char_tpl, {
                    "product_name": project.get("name", "Sản phẩm thương mại"),
                    "category": project.get("category", "Thương mại & Bán lẻ"),
                    "description": project.get("description", ""),
                    "benefits": project.get("benefits", "Công dụng tiện ích và hiệu quả vượt trội"),
                    "highlights": project.get("highlights", "Thiết kế chính hãng, chi tiết sắc nét"),
                    "target_customer": project.get("target_customer", "Khách hàng tiêu dùng thông thái")
                })

                char_res = None
                if gemini_api_service.is_configured():
                    await update_status("Tạo nhân vật AI", 35, "Đang gọi Google Imagen 3 API để tạo nhân vật thương mại 8K...")
                    char_res = await gemini_api_service.generate_character_image(project_id, char_prompt, original_image)

                if not char_res or not char_res.get("success"):
                    await update_status("Tạo nhân vật AI", 38, f"Đang đưa ảnh {project.get('name')} vào Gemini tạo nhân vật đứng giới thiệu 9:16...")
                    try:
                        char_res = await gemini_automator.generate_character(
                            project_id=project_id,
                            original_image_path=original_image,
                            prompt=char_prompt,
                            mode=project.get("automation_mode", "auto"),
                            on_log=lambda m, p: update_status("Tạo nhân vật AI", int(30 + (p * 0.25)), m)
                        )
                    except Exception as e_cg:
                        logger.warning(f"gemini_automator.generate_character error: {e_cg}")
                        char_res = {"success": False, "error": str(e_cg)}

                if char_res and char_res.get("needs_login"):
                    msg = "Cần đăng nhập tài khoản Google trên Gemini. Vui lòng bấm 'Kết nối Gemini' ở góc trên màn hình."
                    await update_status("Chờ đăng nhập", 35, msg, status="waiting_confirm")
                    return {"success": False, "needs_login": True, "message": msg}

                char_dir = PROJECTS_DIR / project_id / "character"
                char_dir.mkdir(parents=True, exist_ok=True)
                canonical_char = char_dir / "character_primary.png"

                if char_res and char_res.get("success") and char_res.get("image_path") and os.path.exists(char_res["image_path"]):
                    char_image_path = char_res["image_path"]
                else:
                    from backend.app.services.character_composer import compose_studio_character_with_product
                    await asyncio.to_thread(
                        compose_studio_character_with_product,
                        original_image,
                        str(canonical_char)
                    )
                    char_image_path = str(canonical_char)

                # Clean up any temporary instant preview file so only 1 character image exists
                try:
                    preview_file = char_dir / "character_instant_preview.png"
                    if preview_file.exists() and str(preview_file) != str(char_image_path):
                        preview_file.unlink()
                except Exception:
                    pass

                char_name = os.path.basename(char_image_path)
                f_size = os.path.getsize(char_image_path) if os.path.exists(char_image_path) else 0

                asset_id = str(uuid.uuid4())[:8]
                await db.execute("DELETE FROM assets WHERE project_id = ? AND asset_type = 'ai_character'", (project_id,))
                await db.execute("""
                    INSERT INTO assets (id, project_id, asset_type, file_path, file_name, file_size, is_primary)
                    VALUES (?, ?, 'ai_character', ?, ?, ?, 1)
                """, (asset_id, project_id, char_image_path, char_name, f_size))

                await db.execute("""
                    UPDATE projects SET primary_character_image_path = ?, status = 'character_created', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (char_image_path, project_id))
                await db.commit()
                await update_status("Tạo nhân vật AI", 55, f"Đã tạo xong ảnh Nhân vật AI 9:16 cùng {project.get('name')}!")
            else:
                await update_status("Tạo nhân vật AI", 55, "Đã có sẵn ảnh nhân vật AI cho dự án.")

            # =========================================================================
            # STEP 2: ENSURE TAILORED 2-SCENE SCRIPT & PROMPTS EXIST (55% -> 65%)
            # =========================================================================
            s_cur = await db.execute("SELECT * FROM scripts WHERE project_id = ? ORDER BY is_selected DESC LIMIT 1", (project_id,))
            existing_script_row = await s_cur.fetchone()
            existing_s1 = (existing_script_row["scene1_dialogue"] if existing_script_row else "") or ""
            existing_p1 = (existing_script_row["scene1_prompt_veo"] if existing_script_row else "") or ""
            script_is_stale = (
                not existing_script_row
                or len(existing_s1.strip()) < 20
                or is_generic_benefits(existing_s1)
                or "chuẩn chất lượng cho nhu cầu hằng ngày" in existing_s1.lower()
                or not existing_p1.strip().startswith("[Cảnh 1")
                or ("sản phẩm chất lượng cao" in existing_s1.lower() and "sản phẩm chất lượng cao" not in (project.get("name") or "").lower())
            )

            if script_is_stale:
                await update_status("Viết Prompt theo sản phẩm", 58, f"Đang tổng hợp kịch bản 2 cảnh và Prompt tạo video chuyên biệt cho {project.get('name')}...")
                parsed_scripts = build_fallback_scripts(
                    product_name=project.get("name", "Sản phẩm tiện ích"),
                    category=project.get("category", "Thương mại & Bán lẻ"),
                    benefits=project.get("benefits", ""),
                    highlights=project.get("highlights", ""),
                    offer=project.get("offer", "Tặng kèm ưu đãi trợ giá hôm nay"),
                    price=project.get("price", "Ưu đãi hôm nay"),
                    custom_scene1_dialogue=analyzed_s1,
                    custom_scene2_dialogue=analyzed_s2
                )

                await db.execute("DELETE FROM scripts WHERE project_id = ?", (project_id,))
                chosen_script_id = None
                for s in parsed_scripts:
                    s_id = str(uuid.uuid4())[:8]
                    if not chosen_script_id:
                        chosen_script_id = s_id
                    s1_text = s.get("scene1_dialogue", "")
                    s2_text = s.get("scene2_dialogue", "")
                    s1_w = len(s1_text.split())
                    s2_w = len(s2_text.split())
                    await db.execute("""
                        INSERT INTO scripts (
                            id, project_id, option_label, option_title, hook_concept,
                            scene1_dialogue, scene1_word_count, scene1_prompt_veo,
                            scene2_dialogue, scene2_word_count, scene2_prompt_veo,
                            is_selected, raw_response
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """, (
                        s_id, project_id,
                        s.get("option_label") or s.get("label", "A"),
                        s.get("option_title") or s.get("title", f"Kịch Bản & Prompt Video Chuẩn - {project.get('name', 'Sản phẩm')}"),
                        s.get("hook_concept") or s.get("hook", f"Đánh vào công dụng {project.get('name', 'sản phẩm')}"),
                        s1_text, s1_w, s.get("scene1_prompt_veo", ""),
                        s2_text, s2_w, s.get("scene2_prompt_veo", ""),
                        "Calibrated product script"
                    ))

                if chosen_script_id:
                    await db.execute("UPDATE projects SET selected_script_id = ? WHERE id = ?", (chosen_script_id, project_id))
                await db.commit()
                await update_status("Viết kịch bản & Prompt", 60, f"Đã viết xong Prompt tạo video 2 cảnh cho {project.get('name')}!")

            # =========================================================================
            # STEP 3: ENSURE SCRIPT IS SELECTED & CHECK IF MANUAL MODE (STOP BEFORE FLOW)
            # =========================================================================
            sel_cur = await db.execute("SELECT * FROM scripts WHERE project_id = ? AND is_selected = 1 LIMIT 1", (project_id,))
            selected_script = await sel_cur.fetchone()
            if not selected_script:
                first_cur = await db.execute("SELECT * FROM scripts WHERE project_id = ? ORDER BY option_label ASC LIMIT 1", (project_id,))
                selected_script = await first_cur.fetchone()
                if selected_script:
                    await db.execute("UPDATE scripts SET is_selected = 1 WHERE id = ?", (selected_script["id"],))
                    await db.execute("UPDATE projects SET selected_script_id = ? WHERE id = ?", (selected_script["id"], project_id))
                    await db.commit()

            if selected_script:
                await db.execute("UPDATE projects SET selected_script_id = ? WHERE id = ?", (selected_script["id"], project_id))
                await db.commit()

            script_dict = dict(selected_script) if selected_script else {}
            scene1_prompt = script_dict.get("scene1_prompt_veo", "") or f"Cô gái Việt Nam giới thiệu {project.get('name', 'sản phẩm')}"
            scene2_prompt = script_dict.get("scene2_prompt_veo", "") or f"Camera tiến chậm cận cảnh {project.get('name', 'sản phẩm')}"

            # If stop_before_video=True (e.g. initial upload in Manual Mode), finish here at 100%!
            if stop_before_video:
                await update_status(
                    "Hoàn tất Ảnh & Prompt",
                    100,
                    f"Đã tự động tạo xong Ảnh Nhân Vật 9:16 & viết Prompt 2 cảnh chuẩn cho {project.get('name')}! Bấm Copy để đưa qua nền tảng tạo video.",
                    status="completed"
                )
                return {
                    "success": True,
                    "project_id": project_id,
                    "character_image_path": char_image_path,
                    "message": f"Đã tự động tạo xong Ảnh Nhân Vật & Prompt cho {project.get('name')}!"
                }

            # =========================================================================
            # STEP 4: GENERATE SCENE 1 VIDEO (60% -> 75%)
            # =========================================================================
            if self.is_project_paused(project_id):
                await update_status("Đã tạm dừng", 60, "Đã tạm dừng theo yêu cầu. Bấm Tiếp tục ngoài thẻ dự án để tạo video tiếp!", status="paused")
                return {"success": False, "paused": True, "project_id": project_id}

            v1_cur = await db.execute("SELECT * FROM videos WHERE project_id = ? AND scene_number = 1", (project_id,))
            v1_row = await v1_cur.fetchone()
            v1_path = v1_row["video_path"] if v1_row and os.path.exists(v1_row["video_path"]) else None

            if force_regenerate:
                v1_path = None
                await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = 1", (project_id,))
                await db.commit()

            # Discard stale showcase demo videos (4837882 bytes or 9671950 bytes from old landing page loops)
            if v1_path and os.path.exists(v1_path) and os.path.getsize(v1_path) in [4837882, 9671950]:
                logger.info("Discarding stale demo showcase video for Scene 1")
                try:
                    os.unlink(v1_path)
                except Exception:
                    pass
                v1_path = None
                await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = 1", (project_id,))
                await db.commit()

            video_engine = self.resolve_video_engine()
            if not v1_path:
                v1_res = {}
                try:
                    if video_engine == "muse":
                        await update_status("Tạo video Cảnh 1", 62, "Đang đưa ảnh nhân vật và prompt Cảnh 1 vào Muse AI...")
                        v1_res = await muse_automator.generate_scene_video(
                            project_id=project_id,
                            scene_number=1,
                            prompt=scene1_prompt,
                            character_image_path=char_image_path or original_image,
                            reference_image_path=char_image_path or original_image,
                            progress_callback=lambda m, p: update_status("Tạo video Cảnh 1", int(60 + (p * 0.15)), m)
                        )
                    else:
                        await update_status("Tạo video Cảnh 1", 62, "Đang đưa ảnh nhân vật và prompt Cảnh 1 vào Google Flow (Veo 3)...")
                        v1_res = await flow_automator.generate_scene_video(
                            project_id=project_id,
                            scene_number=1,
                            prompt=scene1_prompt,
                            character_image_path=char_image_path or original_image,
                            reference_image_path=char_image_path or original_image,
                            on_log=lambda m, p: update_status("Tạo video Cảnh 1", int(60 + (p * 0.15)), m)
                        )
                except Exception as e_v1:
                    logger.warning(f"Engine {video_engine} Scene 1 error: {e_v1}")
                    v1_res = {"success": False, "error": str(e_v1)}

                if v1_res.get("success") and v1_res.get("video_path") and os.path.exists(v1_res["video_path"]) and os.path.getsize(v1_res["video_path"]) > 10000:
                    v1_path = v1_res["video_path"]
                else:
                    if video_engine == "muse":
                        # Auto-retry: scan chat or retry prompt once more before fallback
                        logger.info(f"Muse AI Scene 1 not received directly for {project_id}. Checking chat pull and retrying...")
                        await update_status("Tạo video Cảnh 1", 68, "Đang quét tìm video Cảnh 1 trên Muse AI...")
                        pull_chk = await muse_automator.pull_project_videos(project_id)
                        if pull_chk.get("s1_ok"):
                            s1_cand = str(PROJECTS_DIR / project_id / "videos" / "scene1.mp4")
                            if os.path.exists(s1_cand) and os.path.getsize(s1_cand) > 10000:
                                v1_path = s1_cand

                        if not v1_path:
                            # Retry generate once
                            await update_status("Tạo video Cảnh 1", 70, "Đang tự động gửi lại yêu cầu tạo Cảnh 1 lên Muse AI...")
                            try:
                                retry_res = await muse_automator.generate_scene_video(
                                    project_id=project_id,
                                    scene_number=1,
                                    prompt=scene1_prompt,
                                    character_image_path=char_image_path or original_image,
                                    reference_image_path=char_image_path or original_image,
                                    progress_callback=lambda m, p: update_status("Tạo video Cảnh 1", int(70 + (p * 0.05)), m)
                                )
                                if retry_res.get("success") and retry_res.get("video_path") and os.path.exists(retry_res["video_path"]):
                                    v1_path = retry_res["video_path"]
                            except Exception as ex_retry:
                                logger.warning(f"Muse retry 1 failed: {ex_retry}")

                    if not v1_path:
                        # Auto-fallback: Never freeze the tool! Create high quality 60 FPS motion video
                        await update_status("Tạo video Cảnh 1", 72, "Muse AI chưa trả video, tự động chuyển sang bộ kết xuất chuyển động 60 FPS...")
                        synth_path = str(PROJECTS_DIR / project_id / "videos" / "scene1.mp4")
                        await ffmpeg_service.create_scene_motion_video(
                            image_path=char_image_path or original_image,
                            output_path=synth_path,
                            duration=10.0,
                            motion_type="zoom_in",
                            dialogue_text=script_dict.get("scene1_dialogue", "") or f"Giới thiệu {project.get('name', 'sản phẩm')}",
                            fps=60
                        )
                        if not os.path.exists(synth_path) or os.path.getsize(synth_path) < 1000:
                            await ffmpeg_service.create_image_video(
                                image_path=char_image_path or original_image,
                                output_path=synth_path,
                                duration=10.0,
                                fps=60
                            )
                        v1_path = synth_path

                probe1 = await ffmpeg_service.probe_video(v1_path)
                v1_id = str(uuid.uuid4())[:8]
                await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = 1", (project_id,))
                await db.execute("""
                    INSERT INTO videos (id, project_id, script_id, scene_number, video_path, duration, resolution, fps, status)
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?, 'ready')
                """, (
                    v1_id, project_id, script_dict.get("id"), v1_path,
                    probe1.get("duration", 10.0), f"{probe1.get('width', 1080)}x{probe1.get('height', 1920)}",
                    probe1.get("fps", 60.0)
                ))
                await db.execute("UPDATE projects SET status = 'video1_ready' WHERE id = ?", (project_id,))
                await db.commit()
                await update_status("Tạo video Cảnh 1", 75, "Đã tạo thành công video Cảnh 1 (10s 60fps)!")
            else:
                await update_status("Tạo video Cảnh 1", 75, "Đã có sẵn video Cảnh 1 trong dự án.")

            # =========================================================================
            # STEP 5: GENERATE SCENE 2 VIDEO (75% -> 88%)
            # =========================================================================
            if self.is_project_paused(project_id):
                await update_status("Đã tạm dừng", 75, "Đã tạm dừng theo yêu cầu. Bấm Tiếp tục ngoài thẻ dự án để tạo video Cảnh 2 tiếp!", status="paused")
                return {"success": False, "paused": True, "project_id": project_id}

            v2_cur = await db.execute("SELECT * FROM videos WHERE project_id = ? AND scene_number = 2", (project_id,))
            v2_row = await v2_cur.fetchone()
            v2_path = v2_row["video_path"] if v2_row and os.path.exists(v2_row["video_path"]) else None

            if force_regenerate:
                v2_path = None
                await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = 2", (project_id,))
                await db.commit()

            # Discard stale showcase demo videos
            if v2_path and os.path.exists(v2_path) and os.path.getsize(v2_path) in [4837882, 9671950]:
                logger.info("Discarding stale demo showcase video for Scene 2")
                try:
                    os.unlink(v2_path)
                except Exception:
                    pass
                v2_path = None
                await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = 2", (project_id,))
                await db.commit()

            if not v2_path:
                # Check if Scene 2 was already pulled along with Scene 1 from Muse AI
                s2_file = PROJECTS_DIR / project_id / "videos" / "scene2.mp4"
                if s2_file.exists() and s2_file.stat().st_size > 10000 and (not v1_path or s2_file.stat().st_size != os.path.getsize(v1_path)):
                    v2_path = str(s2_file)
                    logger.info(f"Scene 2 already retrieved and verified distinct for {project_id}.")

            if not v2_path:
                v2_res = {}
                try:
                    if video_engine == "muse":
                        await update_status("Tạo video Cảnh 2", 78, "Đang đưa prompt Cảnh 2 vào Muse AI...")
                        v2_res = await muse_automator.generate_scene_video(
                            project_id=project_id,
                            scene_number=2,
                            prompt=scene2_prompt,
                            character_image_path=char_image_path or original_image,
                            reference_image_path=original_image or char_image_path,
                            progress_callback=lambda m, p: update_status("Tạo video Cảnh 2", int(75 + (p * 0.13)), m)
                        )
                    else:
                        await update_status("Tạo video Cảnh 2", 78, "Đang đưa prompt Cảnh 2 (zoom sản phẩm) vào Google Flow...")
                        v2_res = await flow_automator.generate_scene_video(
                            project_id=project_id,
                            scene_number=2,
                            prompt=scene2_prompt,
                            character_image_path=char_image_path or original_image,
                            reference_image_path=original_image or char_image_path,
                            on_log=lambda m, p: update_status("Tạo video Cảnh 2", int(75 + (p * 0.13)), m)
                        )
                except Exception as e_v2:
                    logger.warning(f"Engine {video_engine} Scene 2 error: {e_v2}")
                    v2_res = {"success": False, "error": str(e_v2)}

                if v2_res.get("success") and v2_res.get("video_path") and os.path.exists(v2_res["video_path"]) and os.path.getsize(v2_res["video_path"]) > 10000:
                    cand_v2 = v2_res["video_path"]
                    if not v1_path or os.path.getsize(v1_path) != os.path.getsize(cand_v2):
                        v2_path = cand_v2

                if not v2_path:
                    if video_engine == "muse":
                        # Auto-retry: check chat pull and retry once
                        logger.info(f"Muse AI Scene 2 not received directly for {project_id}. Checking chat pull and retrying...")
                        await update_status("Tạo video Cảnh 2", 82, "Đang quét tìm video Cảnh 2 trên Muse AI...")
                        pull_chk2 = await muse_automator.pull_project_videos(project_id)
                        if pull_chk2.get("s2_ok"):
                            s2_cand = str(PROJECTS_DIR / project_id / "videos" / "scene2.mp4")
                            if os.path.exists(s2_cand) and os.path.getsize(s2_cand) > 10000 and (not v1_path or os.path.getsize(v1_path) != os.path.getsize(s2_cand)):
                                v2_path = s2_cand

                        if not v2_path:
                            await update_status("Tạo video Cảnh 2", 84, "Đang tự động gửi lại yêu cầu tạo Cảnh 2 lên Muse AI...")
                            try:
                                retry_v2 = await muse_automator.generate_scene_video(
                                    project_id=project_id,
                                    scene_number=2,
                                    prompt=scene2_prompt,
                                    character_image_path=char_image_path or original_image,
                                    reference_image_path=original_image or char_image_path,
                                    progress_callback=lambda m, p: update_status("Tạo video Cảnh 2", int(84 + (p * 0.05)), m)
                                )
                                if retry_v2.get("success") and retry_v2.get("video_path") and os.path.exists(retry_v2["video_path"]):
                                    cand_v2 = retry_v2["video_path"]
                                    if not v1_path or os.path.getsize(v1_path) != os.path.getsize(cand_v2):
                                        v2_path = cand_v2
                            except Exception as ex_retry2:
                                logger.warning(f"Muse retry 2 failed: {ex_retry2}")

                    if not v2_path:
                        # Auto-fallback: Never freeze the tool! Create high quality 60 FPS closeup on product
                        await update_status("Tạo video Cảnh 2", 88, "Muse AI chưa trả video, tự động kết xuất video cận cảnh sản phẩm 60 FPS...")
                        synth_path2 = str(PROJECTS_DIR / project_id / "videos" / "scene2.mp4")
                        await ffmpeg_service.create_scene_motion_video(
                            image_path=original_image or char_image_path,
                            output_path=synth_path2,
                            duration=10.0,
                            motion_type="closeup",
                            dialogue_text=script_dict.get("scene2_dialogue", "") or f"Chi tiết {project.get('name', 'sản phẩm')}",
                            fps=60
                        )
                        if not os.path.exists(synth_path2) or os.path.getsize(synth_path2) < 1000:
                            await ffmpeg_service.create_image_video(
                                image_path=original_image or char_image_path,
                                output_path=synth_path2,
                                duration=10.0,
                                fps=60
                            )
                        v2_path = synth_path2

                probe2 = await ffmpeg_service.probe_video(v2_path)
                v2_id = str(uuid.uuid4())[:8]
                await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = 2", (project_id,))
                await db.execute("""
                    INSERT INTO videos (id, project_id, script_id, scene_number, video_path, duration, resolution, fps, status)
                    VALUES (?, ?, ?, 2, ?, ?, ?, ?, 'ready')
                """, (
                    v2_id, project_id, script_dict.get("id"), v2_path,
                    probe2.get("duration", 10.0), f"{probe2.get('width', 1080)}x{probe2.get('height', 1920)}",
                    probe2.get("fps", 60.0)
                ))
                await db.execute("UPDATE projects SET status = 'video2_ready' WHERE id = ?", (project_id,))
                await db.commit()
                await update_status("Tạo video Cảnh 2", 88, "Đã tạo thành công video Cảnh 2 (10s 60fps)!")
            else:
                await update_status("Tạo video Cảnh 2", 88, "Đã có sẵn video Cảnh 2 trong dự án.")

            # =========================================================================
            # STEP 6: FFMPEG STITCHING & EXPORT (88% -> 100%)
            # =========================================================================
            if not v1_path or not os.path.exists(v1_path):
                synth_path1 = str(PROJECTS_DIR / project_id / "videos" / "scene1.mp4")
                await ffmpeg_service.create_scene_motion_video(
                    image_path=char_image_path or original_image,
                    output_path=synth_path1,
                    duration=10.0,
                    motion_type="zoom_in",
                    dialogue_text=script_dict.get("scene1_dialogue", "") or f"Giới thiệu {project.get('name', 'sản phẩm')}",
                    fps=60
                )
                v1_path = synth_path1

            if not v2_path or not os.path.exists(v2_path):
                synth_path2 = str(PROJECTS_DIR / project_id / "videos" / "scene2.mp4")
                await ffmpeg_service.create_scene_motion_video(
                    image_path=char_image_path or original_image,
                    output_path=synth_path2,
                    duration=10.0,
                    motion_type="closeup",
                    dialogue_text=script_dict.get("scene2_dialogue", "") or f"Chi tiết {project.get('name', 'sản phẩm')}",
                    fps=60
                )
                v2_path = synth_path2

            if v1_path and v2_path and os.path.exists(v1_path) and os.path.exists(v2_path):
                # Guard against identical duplicate scene videos
                import hashlib
                def _calc_sample_hash(p: str) -> str:
                    try:
                        h = hashlib.md5()
                        with open(p, "rb") as fp:
                            h.update(fp.read(65536))
                            sz = os.path.getsize(p)
                            if sz > 131072:
                                fp.seek(sz - 65536)
                                h.update(fp.read(65536))
                        return h.hexdigest()
                    except Exception:
                        return ""

                is_internal_dup = (os.path.getsize(v1_path) == os.path.getsize(v2_path))
                if not is_internal_dup and abs(os.path.getsize(v1_path) - os.path.getsize(v2_path)) < 50000:
                    h1 = _calc_sample_hash(v1_path)
                    h2 = _calc_sample_hash(v2_path)
                    if h1 and h1 == h2:
                        is_internal_dup = True

                if is_internal_dup:
                    logger.warning(f"Detected duplicate scene videos for {project_id}! Scene 1 and Scene 2 have identical content. Regenerating distinct Scene 2...")
                    try:
                        os.unlink(v2_path)
                    except Exception:
                        pass
                    v2_path = None
                    await db.execute("DELETE FROM videos WHERE project_id = ? AND scene_number = 2", (project_id,))
                    await db.commit()

                    if video_engine == "muse":
                        await update_status("Tạo video Cảnh 2", 80, "Phát hiện Cảnh 2 trùng Cảnh 1, đang gửi yêu cầu tạo riêng Cảnh 2 cận cảnh trên Muse AI...")
                        try:
                            v2_retry = await muse_automator.generate_scene_video(
                                project_id=project_id,
                                scene_number=2,
                                prompt=scene2_prompt,
                                character_image_path=char_image_path or original_image,
                                reference_image_path=original_image or char_image_path,
                                progress_callback=lambda m, p: update_status("Tạo video Cảnh 2", int(80 + (p * 0.08)), m)
                            )
                            if v2_retry.get("success") and v2_retry.get("video_path") and os.path.exists(v2_retry["video_path"]):
                                if os.path.getsize(v2_retry["video_path"]) != os.path.getsize(v1_path):
                                    v2_path = v2_retry["video_path"]
                        except Exception as ex_m2:
                            logger.warning(f"Muse distinct Scene 2 retry error: {ex_m2}")

                    if not v2_path:
                        # Regenerate Scene 2 with distinct closeup on product
                        synth_path2 = str(PROJECTS_DIR / project_id / "videos" / "scene2.mp4")
                        await ffmpeg_service.create_scene_motion_video(
                            image_path=original_image or char_image_path,
                            output_path=synth_path2,
                            duration=10.0,
                            motion_type="closeup",
                            dialogue_text=script_dict.get("scene2_dialogue", "") or f"Chi tiết {project.get('name', 'sản phẩm')}",
                            fps=60
                        )
                        v2_path = synth_path2

                    probe2 = await ffmpeg_service.probe_video(v2_path)
                    v2_id = str(uuid.uuid4())[:8]
                    await db.execute("""
                        INSERT INTO videos (id, project_id, script_id, scene_number, video_path, duration, resolution, fps, status)
                        VALUES (?, ?, ?, 2, ?, ?, ?, ?, 'ready')
                    """, (
                        v2_id, project_id, script_dict.get("id"), v2_path,
                        probe2.get("duration", 10.0), f"{probe2.get('width', 1080)}x{probe2.get('height', 1920)}",
                        probe2.get("fps", 60.0)
                    ))
                    await db.commit()

                await update_status("Ghép video FFmpeg", 92, "Đang xử lý chuẩn hóa 1080x1920 @ 60fps và ghép 2 cảnh...")
                
                stitch_res = await ffmpeg_service.stitch_scenes(
                    project_id=project_id,
                    video1_path=v1_path,
                    video2_path=v2_path,
                    product_slug=project.get("name", "tiktok").replace(" ", "_").lower(),
                    transition="none",
                    volume=1.0
                )

                if stitch_res.get("success"):
                    final_path = stitch_res["final_video_path"]
                    file_name = stitch_res["file_name"]
                    export_id = str(uuid.uuid4())[:8]

                    await db.execute("DELETE FROM exports WHERE project_id = ?", (project_id,))
                    await db.execute("""
                        INSERT INTO exports (id, project_id, final_video_path, file_name, duration, resolution, fps, file_size, audio_info)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        export_id, project_id, final_path, file_name,
                        stitch_res.get("duration", 20.0),
                        stitch_res.get("resolution", "1080x1920"),
                        stitch_res.get("fps", 30.0),
                        stitch_res.get("file_size", 0),
                        "AAC 48kHz Stereo"
                    ))
                    await db.execute("UPDATE projects SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
                    await db.commit()

                    await update_status("Hoàn thành", 100, f"Video TikTok Affiliate hoàn chỉnh đã xuất thành công: {file_name}!", status="completed")
                    return {
                        "success": True,
                        "project_id": project_id,
                        "final_video_url": stitch_res.get("url"),
                        "final_video_path": final_path,
                        "message": "Toàn bộ quy trình sản xuất video TikTok đã hoàn thành 100%!"
                    }
                else:
                    await update_status("Lỗi ghép video", 95, f"Lỗi FFmpeg: {stitch_res.get('error')}", status="failed")
                    return {"success": False, "error": stitch_res.get("error")}
            else:
                await update_status("Lỗi tệp video", 90, "Không thể chuẩn bị tệp video cho 2 cảnh.", status="failed")
                return {
                    "success": False,
                    "error": "Không thể chuẩn bị tệp video cho 2 cảnh."
                }

        except Exception as e:
            import traceback
            err_details = str(e).strip() or repr(e) or type(e).__name__
            logger.error(f"Pipeline Runner exception: {err_details}\n{traceback.format_exc()}")
            _sync_update_task("Lỗi hệ thống", 0, f"Chi tiết: {err_details}", "failed")
            return {"success": False, "error": err_details}
        finally:
            if self.current_running_project_id == project_id:
                self.current_running_project_id = None
            try:
                if self._pipeline_lock.locked():
                    self._pipeline_lock.release()
            except Exception:
                pass
            try:
                await db.close()
            except Exception:
                pass

pipeline_runner = PipelineRunner()

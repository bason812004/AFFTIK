import re
from typing import Dict, Any, List
from backend.app.services.prompt_templates import count_vietnamese_words

# Absolute or risky medical/exaggerated advertising claims forbidden on TikTok
RISKY_PATTERNS = [
    (r'(?:trị dứt điểm|chữa dứt điểm|chữa khỏi hoàn toàn)', 'Tuyên bố chữa khỏi/trị dứt điểm tuyệt đối (Vi phạm chính sách y tế/dược phẩm TikTok)'),
    (r'(?:cam kết 100%|hiệu quả 100%|khỏi 100%|chắc chắn 100%)', 'Tuyên bố cam kết tuyệt đối 100% (Dễ bị TikTok quét cảnh cáo phóng đại)'),
    (r'(?:thần dược|thuốc tiên|thần thánh)', 'Sử dụng từ ngữ thần thánh hóa sản phẩm'),
    (r'(?:vĩnh viễn không tái phát|khỏi vĩnh viễn)', 'Cam kết vĩnh viễn không căn cứ khoa học'),
    (r'(?:thuốc trị|thuốc chữa|đặc trị)', 'Tự xưng là thuốc đặc trị (Sản phẩm mỹ phẩm/TĂCN không được tự xưng là thuốc)'),
    (r'(?:ngon nhất thế giới|tốt nhất thế giới|số 1 việt nam|duy nhất trên thị trường)', 'Tuyên bố số 1 hoặc tốt nhất không có giấy chứng nhận thẩm quyền'),
]

def check_script_quality(
    scene1_dialogue: str,
    scene2_dialogue: str,
    scene1_prompt: str,
    scene2_prompt: str,
    product_name: str = ""
) -> Dict[str, Any]:
    """
    Runs complete quality, compliance, and synchronization checks on a script option.
    """
    s1_count = count_vietnamese_words(scene1_dialogue)
    s2_count = count_vietnamese_words(scene2_dialogue)
    
    issues: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    checks: List[Dict[str, Any]] = []
    
    # 1. Word Count Checks (At least 42 words, natural 10s complete sentence)
    s1_valid = (42 <= s1_count <= 60)
    s2_valid = (42 <= s2_count <= 60)
    
    checks.append({
        "id": "scene1_word_count",
        "name": "Số từ Cảnh 1",
        "expected": 42,
        "actual": s1_count,
        "status": "pass" if s1_valid else "fail",
        "message": (
            f"Cảnh 1 đạt chuẩn {s1_count} từ (≥ 42 từ, trọn câu trong 10 giây)"
            if s1_valid else (
                f"Cảnh 1 đang có {s1_count} từ (thiếu {42 - s1_count} từ so với tối thiểu 42 từ)"
                if s1_count < 42 else
                f"Cảnh 1 đang có {s1_count} từ (hơi dài cho 10 giây, nên từ 42–55 từ trọn câu)"
            )
        )
    })
    
    checks.append({
        "id": "scene2_word_count",
        "name": "Số từ Cảnh 2",
        "expected": 42,
        "actual": s2_count,
        "status": "pass" if s2_valid else "fail",
        "message": (
            f"Cảnh 2 đạt chuẩn {s2_count} từ (≥ 42 từ, trọn câu trong 10 giây)"
            if s2_valid else (
                f"Cảnh 2 đang có {s2_count} từ (thiếu {42 - s2_count} từ so với tối thiểu 42 từ)"
                if s2_count < 42 else
                f"Cảnh 2 đang có {s2_count} từ (hơi dài cho 10 giây, nên từ 42–55 từ trọn câu)"
            )
        )
    })
    
    if not s1_valid:
        issues.append({"type": "word_count", "scene": "1", "message": f"Cảnh 1: {s1_count} từ. Cần ít nhất 42 từ trở lên và nói trọn vẹn hết câu trong 10 giây."})
    if not s2_valid:
        issues.append({"type": "word_count", "scene": "2", "message": f"Cảnh 2: {s2_count} từ. Cần ít nhất 42 từ trở lên và nói trọn vẹn hết câu trong 10 giây."})
        
    # 2. Duplicate content between Scene 1 and Scene 2
    if scene1_dialogue and scene2_dialogue:
        s1_words = set(scene1_dialogue.lower().split())
        s2_words = set(scene2_dialogue.lower().split())
        overlap = len(s1_words.intersection(s2_words)) / max(len(s1_words), 1)
        if overlap > 0.7:
            warnings.append({
                "type": "content_repetition",
                "message": "Cảnh 2 có mức độ trùng lặp từ ngữ cao với Cảnh 1 (>70%). Nên phân bổ nội dung đa dạng hơn."
            })
            
    # 3. Policy & Advertising Claim Risks
    combined_dialogue = f"{scene1_dialogue} {scene2_dialogue}"
    for pattern, reason in RISKY_PATTERNS:
        if re.search(pattern, combined_dialogue, re.IGNORECASE):
            warnings.append({
                "type": "policy_risk",
                "message": f"Phát hiện cụm từ rủi ro: '{reason}'"
            })
            
    # 4. Synchronization & Camera Direction in Prompt Veo 3
    s2_p_lower = scene2_prompt.lower() if scene2_prompt else ""
    has_zoom_or_focus = any(kw in s2_p_lower for kw in ["tiến", "cận cảnh", "lấy nét", "zoom", "push-in", "focus", "sản phẩm"])
    
    checks.append({
        "id": "scene2_camera_focus",
        "name": "Chỉ dẫn camera tiến sát sản phẩm ở Cảnh 2",
        "status": "pass" if has_zoom_or_focus else "warning",
        "message": "Prompt Cảnh 2 có chỉ dẫn camera tiến gần / lấy nét sản phẩm" if has_zoom_or_focus else "Prompt Cảnh 2 nên bổ sung chỉ dẫn camera từ từ tiến gần và lấy nét rõ sản phẩm"
    })
    
    # 5. Call-to-action reminder check
    has_cta = any(kw in scene2_dialogue.lower() for kw in ["góc trái", "giỏ hàng", "mua ngay", "bấm", "ưu đãi", "đừng bỏ lỡ", "nhanh tay"])
    checks.append({
        "id": "scene2_call_to_action",
        "name": "Kêu gọi hành động (CTA) Cảnh 2",
        "status": "pass" if has_cta else "warning",
        "message": "Có nhắc nhở mua hàng / giỏ hàng góc trái tự nhiên" if has_cta else "Nên bổ sung câu kêu gọi các bác xem giỏ hàng góc trái màn hình"
    })

    score = 100
    if not s1_valid:
        score -= 25
    if not s2_valid:
        score -= 25
    if warnings:
        score -= len(warnings) * 10
    score = max(score, 0)
    
    return {
        "score": score,
        "is_ready_for_production": (s1_valid and s2_valid and len(issues) == 0),
        "scene1_word_count": s1_count,
        "scene2_word_count": s2_count,
        "checks": checks,
        "issues": issues,
        "warnings": warnings
    }


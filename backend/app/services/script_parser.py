import re
from typing import List, Dict, Any
from backend.app.services.prompt_templates import count_vietnamese_words

def parse_gemini_scripts(raw_text: str) -> List[Dict[str, Any]]:
    """
    Parses Gemini's raw output into structured 3 options (A, B, C).
    Each option contains:
      - option_label: 'A', 'B', 'C'
      - option_title: string
      - hook_concept: string
      - scene1_dialogue: string
      - scene1_word_count: int
      - scene1_prompt_veo: string
      - scene2_dialogue: string
      - scene2_word_count: int
      - scene2_prompt_veo: string
      - raw_text: string
    """
    options = []
    
    # Try splitting into sections for A, B, C
    # Patterns like "### PHƯƠNG ÁN A", "**PHƯƠNG ÁN A**", "PHƯƠNG ÁN A:"
    pattern_split = re.compile(r'(?:###|\*\*|==)?\s*(?:PHƯƠNG ÁN|OPTION)\s*([A-C]|1|2|3)[\s:–—\-]*(.*?)(?=(?:###|\*\*|==)?\s*(?:PHƯƠNG ÁN|OPTION)\s*[A-C1-3]|\Z)', re.DOTALL | re.IGNORECASE)
    
    matches = list(pattern_split.finditer(raw_text))
    label_map = {"1": "A", "2": "B", "3": "C", "A": "A", "B": "B", "C": "C"}
    
    if matches:
        for match in matches:
            raw_label = match.group(1).upper()
            label = label_map.get(raw_label, raw_label)
            block = match.group(0)
            
            # Extract title / hook concept
            title_match = re.search(r'(?:PHƯƠNG ÁN|OPTION)\s*[A-C1-3][\s:–—\-]*([^\n\r*]+)', block, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else f"Phương án {label}"
            
            hook_match = re.search(r'(?:Ý tưởng|Hook|Ý tưởng và hook)[:\s*]+([^\n\r]+)', block, re.IGNORECASE)
            hook_concept = hook_match.group(1).strip() if hook_match else ""
            
            # Extract Scene 1 and Scene 2
            s1_dialogue, s1_prompt = extract_scene_data(block, scene_num=1)
            s2_dialogue, s2_prompt = extract_scene_data(block, scene_num=2)

            if s1_dialogue and s1_dialogue[:20] not in (s1_prompt or ""):
                base_p1 = (s1_prompt or "Video dọc tỷ lệ 9:16, thời lượng 10 giây, 60fps. Người mẫu nữ Việt Nam 21 tuổi mỉm cười tự nhiên giới thiệu sản phẩm ở tiền cảnh.").rstrip(". ")
                s1_prompt = f"{base_p1}. Giọng đọc nữ miền Bắc Hà Nội truyền cảm, nói trọn vẹn hết câu trong 10 giây: '{s1_dialogue}' Không chèn chữ, không phụ đề, không watermark."

            if s2_dialogue and s2_dialogue[:20] not in (s2_prompt or ""):
                base_p2 = (s2_prompt or "Video dọc tỷ lệ 9:16, thời lượng 10 giây, 60fps. Đồng nhất nhân vật và bối cảnh Cảnh 1, máy quay tiến chậm lấy nét cận cảnh sản phẩm.").rstrip(". ")
                s2_prompt = f"{base_p2}. Giọng đọc nữ miền Bắc Hà Nội thuyết phục, nói trọn vẹn hết câu trong 10 giây: '{s2_dialogue}' Không chèn chữ, không phụ đề, không biểu tượng giỏ hàng."

            s1_count = count_vietnamese_words(s1_dialogue)
            s2_count = count_vietnamese_words(s2_dialogue)
            
            options.append({
                "option_label": label,
                "option_title": title,
                "hook_concept": hook_concept,
                "scene1_dialogue": s1_dialogue,
                "scene1_word_count": s1_count,
                "scene1_prompt_veo": s1_prompt,
                "scene2_dialogue": s2_dialogue,
                "scene2_word_count": s2_count,
                "scene2_prompt_veo": s2_prompt,
                "raw_response": block.strip()
            })
            
    # If regex split failed to extract 3 options, fall back to heuristic extraction or template placeholders
    if len(options) < 3:
        # Create missing options with extracted or empty fields
        existing_labels = {o["option_label"] for o in options}
        for lbl in ["A", "B", "C"]:
            if lbl not in existing_labels:
                options.append({
                    "option_label": lbl,
                    "option_title": f"Phương án {lbl}",
                    "hook_concept": f"Ý tưởng phương án {lbl}",
                    "scene1_dialogue": "",
                    "scene1_word_count": 0,
                    "scene1_prompt_veo": "",
                    "scene2_dialogue": "",
                    "scene2_word_count": 0,
                    "scene2_prompt_veo": "",
                    "raw_response": raw_text if lbl == "A" and not options else ""
                })
                
    # Sort A, B, C
    options.sort(key=lambda x: x["option_label"])
    return options

def clean_dialogue(text: str) -> str:
    """
    Cleans raw dialogue extracted from Gemini or LLM:
    - Strips zero-width spaces (\u200b, \ufeff).
    - Removes trailing '- Bộ đếm: 42/42 từ-', 'Bộ đếm: ...', or leaked Veo prompts.
    - Strips surrounding quotes.
    """
    if not text:
        return ""
    t = text.replace('\u200b', '').replace('\ufeff', '').strip()
    # Strip any trailing word count badges, prompt leaks, or notes
    parts = re.split(r'[\r\n\s\-–—*•]+(?:Bộ\s*đếm|Prompt\s*Veo|Prompt|Veo\s*3|Lưu\s*ý|Ghi\s*chú|Note)', t, flags=re.IGNORECASE)
    cleaned = parts[0].strip(' "“”\'`\t\r\n')
    return cleaned

def extract_scene_data(block: str, scene_num: int) -> tuple[str, str]:
    """
    Extracts dialogue and Veo prompt for CẢNH 1 or CẢNH 2 within an option block.
    """
    other_num = 2 if scene_num == 1 else 1
    
    # Match block for specific scene
    scene_regex = rf'(?:CẢNH|SCENE)\s*{scene_num}[:\s*]*(.*?)(?=(?:CẢNH|SCENE)\s*{other_num}|\Z)'
    match = re.search(scene_regex, block, re.DOTALL | re.IGNORECASE)
    
    scene_text = match.group(1) if match else block
    
    # Dialogue pattern
    dialogue_match = re.search(r'(?:Lời thoại|Thoại|Dialogue)[:\s*]+([^\n\r]+(?:\n[^\n\r]+)*?)(?=(?:Bộ đếm|Prompt|Prompt Veo 3|\Z))', scene_text, re.IGNORECASE)
    dialogue = ""
    if dialogue_match:
        dialogue = dialogue_match.group(1).strip()
    elif "Lời thoại" in scene_text:
        parts = scene_text.split("Lời thoại")
        if len(parts) > 1:
            dialogue = parts[1].split("\n\n")[0].strip()

    # Apply strict cleaning
    dialogue = clean_dialogue(dialogue)
    
    # Prompt pattern
    prompt_match = re.search(r'(?:Prompt Veo 3|Prompt|Prompt Veo)[:\s*]+([^\n\r]+(?:\n[^\n\r]+)*?)(?=(?:###|\*\*|CẢNH|SCENE|\Z))', scene_text, re.IGNORECASE)
    prompt = ""
    if prompt_match:
        prompt = prompt_match.group(1).strip()
        prompt = prompt.replace('\u200b', '').replace('\ufeff', '').strip()
        
    return dialogue, prompt


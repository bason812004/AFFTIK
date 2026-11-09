from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ProjectCreate(BaseModel):
    name: Optional[str] = Field(default="Sản phẩm TikTok", description="Tên sản phẩm")
    category: Optional[str] = "Thương mại & Bán lẻ"
    description: Optional[str] = ""
    benefits: Optional[str] = ""
    highlights: Optional[str] = ""
    materials: Optional[str] = ""
    target_customer: Optional[str] = ""
    usage_guide: Optional[str] = ""
    price: Optional[str] = ""
    offer: Optional[str] = ""
    warranty: Optional[str] = ""
    notes: Optional[str] = ""
    tiktok_url: Optional[str] = ""
    automation_mode: Optional[str] = "auto"

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    benefits: Optional[str] = None
    highlights: Optional[str] = None
    materials: Optional[str] = None
    target_customer: Optional[str] = None
    usage_guide: Optional[str] = None
    price: Optional[str] = None
    offer: Optional[str] = None
    warranty: Optional[str] = None
    notes: Optional[str] = None
    tiktok_url: Optional[str] = None
    selected_script_id: Optional[str] = None
    primary_character_image_path: Optional[str] = None
    automation_mode: Optional[str] = None
    status: Optional[str] = None

class ScriptUpdate(BaseModel):
    option_title: Optional[str] = None
    hook_concept: Optional[str] = None
    scene1_dialogue: Optional[str] = None
    scene1_prompt_veo: Optional[str] = None
    scene2_dialogue: Optional[str] = None
    scene2_prompt_veo: Optional[str] = None

class QualityCheckRequest(BaseModel):
    scene1_dialogue: str
    scene2_dialogue: str
    scene1_prompt: Optional[str] = ""
    scene2_prompt: Optional[str] = ""
    product_name: Optional[str] = ""

class StitchRequest(BaseModel):
    project_id: str
    transition: Optional[str] = "none"
    transition_duration: Optional[float] = 0.5
    volume: Optional[float] = 1.0
    trim_v1_start: Optional[float] = 0.0
    trim_v2_end: Optional[float] = 0.0
    custom_name: Optional[str] = None

class PromptCreate(BaseModel):
    category: str
    title: str
    content: str
    variables: Optional[List[str]] = []
    project_id: Optional[str] = None

class PromptUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[List[str]] = None

class RenderPromptRequest(BaseModel):
    prompt_id: Optional[str] = None
    custom_content: Optional[str] = None
    project_id: str


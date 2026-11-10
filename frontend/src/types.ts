export type AutomationMode = 'auto' | 'semi' | 'manual';

export interface Project {
  id: string;
  name: string;
  category: string;
  description: string;
  benefits: string;
  highlights: string;
  materials: string;
  target_customer: string;
  usage_guide: string;
  price: string;
  offer: string;
  warranty: string;
  notes: string;
  tiktok_url: string;
  original_image_path?: string;
  primary_character_image_path?: string;
  character_prompt?: string;
  selected_script_id?: string;
  status: 'created' | 'image_uploaded' | 'character_created' | 'scripts_created' | 'option_selected' | 'video1_ready' | 'video2_ready' | 'videos_stitched' | 'completed';
  automation_mode: AutomationMode;
  created_at: string;
  updated_at: string;
  character_count?: number;
  video_count?: number;
  has_export?: boolean;
  final_video_path?: string;
  is_running_now?: boolean;
  is_paused?: boolean;
  in_queue?: boolean;
  queue_position?: number | null;
  section_group?: 'running' | 'paused' | 'completed';
  task_status?: string;
  step_name?: string;
  progress_percent?: number;
  task_message?: string;
}

export interface ScriptOption {
  id: string;
  project_id: string;
  option_label: 'A' | 'B' | 'C';
  option_title: string;
  hook_concept: string;
  scene1_dialogue: string;
  scene1_word_count: number;
  scene1_prompt_veo: string;
  scene2_dialogue: string;
  scene2_word_count: number;
  scene2_prompt_veo: string;
  is_selected: boolean;
  raw_response?: string;
}

export interface Asset {
  id: string;
  project_id: string;
  asset_type: 'original_product' | 'ai_character' | 'scene1_video' | 'scene2_video' | 'final_video';
  file_path: string;
  file_name: string;
  file_size: number;
  width?: number;
  height?: number;
  duration_seconds?: number;
  is_primary: boolean;
  created_at: string;
}

export interface VideoItem {
  id: string;
  project_id: string;
  script_id?: string;
  scene_number: 1 | 2;
  video_path: string;
  duration: number;
  resolution: string;
  fps: number;
  status: string;
  error_message?: string;
  created_at: string;
}

export interface ExportItem {
  id: string;
  project_id: string;
  final_video_path: string;
  file_name: string;
  duration: number;
  resolution: string;
  fps: number;
  file_size: number;
  audio_info: string;
  created_at: string;
}

export interface PromptTemplate {
  id: string;
  project_id?: string;
  category: 'character_gen' | 'script_gen' | 'veo3_scene1' | 'veo3_scene2' | 'dialogue_fix' | 'hook_gen' | 'variant_gen';
  title: string;
  content: string;
  variables: string[];
  is_default: boolean;
  is_system: boolean;
}

export interface AutomationTask {
  id: string;
  project_id?: string;
  task_type: string;
  status: 'pending' | 'running' | 'waiting_confirm' | 'completed' | 'failed' | 'cancelled';
  step_name?: string;
  progress_percent: number;
  message?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface QualityCheckResult {
  score: number;
  is_ready_for_production: boolean;
  scene1_word_count: number;
  scene2_word_count: number;
  checks: Array<{
    id: string;
    name: string;
    expected?: number;
    actual?: number;
    status: 'pass' | 'fail' | 'warning';
    message: string;
  }>;
  issues: Array<{ type: string; scene?: string; message: string }>;
  warnings: Array<{ type: string; message: string }>;
}


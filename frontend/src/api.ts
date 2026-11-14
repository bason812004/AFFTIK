import {
  Project,
  ScriptOption,
  PromptTemplate,
  AutomationTask,
  QualityCheckResult
} from './types';

const API_BASE = '/api';

export function countVietnameseWords(text: string): number {
  if (!text) return 0;
  const cleaned = text.replace(/["'`“”‘’«»()[\]{}–—:;,.!?/\\]/g, ' ');
  return cleaned.trim().split(/\s+/).filter(Boolean).length;
}

async function handleResponse<T = any>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `Lỗi máy chủ (${res.status})`;
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      try {
        const text = await res.text();
        if (text) errorDetail = text;
      } catch {}
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export const api = {
  // Stats
  async getDashboardStats() {
    const res = await fetch(`${API_BASE}/settings/dashboard-stats`);
    return handleResponse(res);
  },

  // Projects
  async listProjects(): Promise<Project[]> {
    const res = await fetch(`${API_BASE}/projects`);
    return handleResponse<Project[]>(res);
  },

  async createProject(data: Partial<Project>): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse<Project>(res);
  },

  async quickCreateProject(file: File, name?: string, autoRun: boolean = true, promptStyle: string = 'warehouse'): Promise<{ project_id: string; task_id?: string; success: boolean; name: string; needs_product_name?: boolean }> {
    const fd = new FormData();
    fd.append('file', file);
    if (name) fd.append('name', name);
    fd.append('auto_run', autoRun ? 'true' : 'false');
    fd.append('prompt_style', promptStyle);
    const res = await fetch(`${API_BASE}/projects/quick-create`, {
      method: 'POST',
      body: fd
    });
    return handleResponse(res);
  },

  async batchCreateProjects(files: File[], names: string[] = [], autoRun: boolean = true, promptStyle: string = 'warehouse'): Promise<{
    success: boolean;
    count: number;
    projects: Array<{ project_id: string; task_id?: string; name: string; needs_product_name?: boolean }>;
    first_project_id: string | null;
    waiting_name_count: number;
    message: string;
  }> {
    const fd = new FormData();
    for (const f of files) {
      fd.append('files', f);
    }
    if (names.length > 0) {
      fd.append('names_json', JSON.stringify(names));
    }
    fd.append('auto_run', autoRun ? 'true' : 'false');
    fd.append('prompt_style', promptStyle);
    const res = await fetch(`${API_BASE}/projects/batch-create`, {
      method: 'POST',
      body: fd
    });
    return handleResponse(res);
  },

  async getSessionState(): Promise<{
    paused_session: {
      paused: boolean;
      project_id: string;
      step: string;
      scene_number: number;
      reason: string;
      message: string;
    } | null;
    paused_project_name?: string | null;
    running_project_id?: string | null;
    batch_state: {
      active: boolean;
      paused_by_user?: boolean;
      project_ids: string[];
      completed_ids: string[];
      paused_ids?: string[];
      current_project_id: string | null;
      waiting_name_ids: string[];
      paused_for_login: boolean;
    };
    batch_projects: Array<{
      id: string;
      name: string;
      category?: string;
      status: string;
      original_image_path?: string;
      primary_character_image_path?: string;
      video_count?: number;
      has_export?: boolean;
      task_status?: string;
      step_name?: string;
      progress_percent?: number;
      task_message?: string;
    }>;
  }> {
    const res = await fetch(`${API_BASE}/projects/session-state`);
    return handleResponse(res);
  },

  async clearBatchQueue(): Promise<{ success: boolean; cleared: boolean }> {
    const res = await fetch(`${API_BASE}/projects/clear-batch-queue`, { method: 'POST' });
    return handleResponse(res);
  },

  async resumeSession(projectId?: string): Promise<{ success: boolean; resumed: boolean; project_id?: string; message: string }> {
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    const res = await fetch(`${API_BASE}/projects/resume-session${query}`, { method: 'POST' });
    return handleResponse(res);
  },

  async pauseQueue(projectId?: string): Promise<{ success: boolean; paused: boolean; project_id?: string | null; message: string }> {
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    const res = await fetch(`${API_BASE}/projects/queue/pause${query}`, { method: 'POST' });
    return handleResponse(res);
  },

  async resumeQueue(projectId?: string, allIncomplete: boolean = false): Promise<{ success: boolean; resumed: boolean; project_id?: string | null; count?: number; message: string }> {
    const params = new URLSearchParams();
    if (projectId) params.set('project_id', projectId);
    if (allIncomplete) params.set('all_incomplete', 'true');
    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/projects/queue/resume${query}`, { method: 'POST' });
    return handleResponse(res);
  },

  async enqueueProject(projectId: string, forceRegenerate: boolean = false, prioritize: boolean = false): Promise<{ success: boolean; project_id: string; message: string }> {
    const params = new URLSearchParams();
    if (forceRegenerate) params.set('force_regenerate', 'true');
    if (prioritize) params.set('prioritize', 'true');
    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/projects/${projectId}/enqueue${query}`, { method: 'POST' });
    return handleResponse(res);
  },

  async confirmProductName(projectId: string, productName: string, autoRun: boolean = true): Promise<{
    success: boolean;
    project_id: string;
    name: string;
    category: string;
    message: string;
  }> {
    const fd = new FormData();
    fd.append('product_name', productName);
    fd.append('auto_run', autoRun ? 'true' : 'false');
    const res = await fetch(`${API_BASE}/projects/${projectId}/confirm-product-name`, {
      method: 'POST',
      body: fd
    });
    return handleResponse(res);
  },

  async cloneVideoVariant(projectId: string, autoRun: boolean = true): Promise<{
    success: boolean;
    project_id: string;
    name: string;
    message: string;
  }> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/clone-video-variant?auto_run=${autoRun ? 'true' : 'false'}`, {
      method: 'POST'
    });
    return handleResponse(res);
  },

  async quickCreateFromClipboard(autoRun: boolean = true, name?: string): Promise<{ project_id: string; task_id?: string; success: boolean; name: string; category?: string; benefits?: string; message?: string }> {
    const query = new URLSearchParams();
    query.set('auto_run', autoRun ? 'true' : 'false');
    if (name) query.set('name', name);
    const res = await fetch(`${API_BASE}/projects/quick-create-from-clipboard?${query.toString()}`, {
      method: 'POST'
    });
    return handleResponse(res);
  },

  async getProject(id: string): Promise<Project & { assets: any[]; character_images: any[]; scripts: ScriptOption[]; videos: any[]; export: any }> {
    const res = await fetch(`${API_BASE}/projects/${id}`);
    return handleResponse(res);
  },

  async ensureManualProject(): Promise<Project & { assets: any[]; character_images: any[]; scripts: ScriptOption[]; videos: any[]; export: any }> {
    const res = await fetch(`${API_BASE}/projects/ensure-manual`, { method: 'POST' });
    return handleResponse(res);
  },

  async manualPrepareProject(projectId: string, data: { name?: string; benefits?: string; file?: File }): Promise<Project & { assets: any[]; character_images: any[]; scripts: ScriptOption[]; videos: any[]; export: any }> {
    const fd = new FormData();
    if (data.name !== undefined) fd.append('name', data.name);
    if (data.benefits !== undefined) fd.append('benefits', data.benefits);
    if (data.file) fd.append('file', data.file);
    const res = await fetch(`${API_BASE}/projects/${projectId}/manual-prepare`, {
      method: 'POST',
      body: fd
    });
    return handleResponse(res);
  },

  async updateProject(id: string, data: Partial<Project>): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse<Project>(res);
  },

  async deleteProject(id: string) {
    const res = await fetch(`${API_BASE}/projects/${id}`, { method: 'DELETE' });
    return handleResponse(res);
  },

  async duplicateProject(id: string) {
    const res = await fetch(`${API_BASE}/projects/${id}/duplicate`, { method: 'POST' });
    return handleResponse(res);
  },

  // 1-Click Full Auto Pipeline
  async runFullAuto(projectId: string) {
    const res = await fetch(`${API_BASE}/projects/${projectId}/run-full-auto`, { method: 'POST' });
    return handleResponse(res);
  },

  async getPipelineStatus(projectId: string) {
    const res = await fetch(`${API_BASE}/projects/${projectId}/pipeline-status`);
    return handleResponse(res);
  },

  async uploadProductImage(projectId: string, file: File) {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`${API_BASE}/projects/${projectId}/upload-product-image`, {
      method: 'POST',
      body: fd
    });
    return handleResponse(res);
  },

  async uploadCharacterImage(projectId: string, file: File) {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`${API_BASE}/projects/${projectId}/upload-character-image`, {
      method: 'POST',
      body: fd
    });
    return handleResponse(res);
  },

  async setPrimaryCharacter(projectId: string, assetId: string) {
    const fd = new FormData();
    fd.append('asset_id', assetId);
    const res = await fetch(`${API_BASE}/projects/${projectId}/set-primary-character`, {
      method: 'POST',
      body: fd
    });
    return handleResponse(res);
  },

  // Gemini Automation
  async getGeminiStatus() {
    const res = await fetch(`${API_BASE}/gemini/status`);
    return handleResponse(res);
  },

  async connectGemini() {
    const res = await fetch(`${API_BASE}/gemini/connect`, { method: 'POST' });
    return handleResponse(res);
  },

  async logoutGemini(fullLogout: boolean = true) {
    const res = await fetch(`${API_BASE}/gemini/logout?full_logout=${fullLogout}`, { method: 'POST' });
    return handleResponse(res);
  },

  async generateCharacter(projectId: string, customPrompt?: string) {
    const res = await fetch(`${API_BASE}/gemini/generate-character`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, custom_prompt: customPrompt })
    });
    return handleResponse(res);
  },

  async generateScripts(projectId: string, customPrompt?: string) {
    const res = await fetch(`${API_BASE}/gemini/generate-scripts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, custom_prompt: customPrompt })
    });
    return handleResponse(res);
  },

  async updateScript(scriptId: string, data: Partial<ScriptOption>): Promise<ScriptOption> {
    const res = await fetch(`${API_BASE}/gemini/scripts/${scriptId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse<ScriptOption>(res);
  },

  async selectScript(scriptId: string) {
    const res = await fetch(`${API_BASE}/gemini/scripts/${scriptId}/select`, { method: 'POST' });
    return handleResponse(res);
  },

  // Google Flow Automation
  async getFlowStatus() {
    const res = await fetch(`${API_BASE}/flow/status`);
    return handleResponse(res);
  },

  async connectFlow() {
    const res = await fetch(`${API_BASE}/flow/connect`, { method: 'POST' });
    return handleResponse(res);
  },

  async logoutFlow(fullLogout: boolean = true) {
    const res = await fetch(`${API_BASE}/flow/logout?full_logout=${fullLogout}`, { method: 'POST' });
    return handleResponse(res);
  },

  async generateFlowVideo(projectId: string, sceneNumber: 1 | 2) {
    const res = await fetch(`${API_BASE}/flow/generate-video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, scene_number: sceneNumber })
    });
    return handleResponse(res);
  },

  async generateFastVideo(projectId: string, sceneNumber: 1 | 2) {
    const res = await fetch(`${API_BASE}/flow/generate-fast-video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, scene_number: sceneNumber })
    });
    return handleResponse(res);
  },

  // Muse AI Automation
  async getMuseStatus() {
    const res = await fetch(`${API_BASE}/muse/status`);
    return handleResponse(res);
  },

  async connectMuse() {
    const res = await fetch(`${API_BASE}/muse/connect`, { method: 'POST' });
    return handleResponse(res);
  },

  async logoutMuse(fullLogout: boolean = true) {
    const res = await fetch(`${API_BASE}/muse/logout?full_logout=${fullLogout}`, { method: 'POST' });
    return handleResponse(res);
  },

  async generateMuseVideo(projectId: string, sceneNumber: 1 | 2) {
    const res = await fetch(`${API_BASE}/muse/generate-video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, scene_number: sceneNumber })
    });
    return handleResponse(res);
  },

  async uploadManualMuseVideo(projectId: string, sceneNumber: 1 | 2, file: File) {
    const fd = new FormData();
    fd.append('project_id', projectId);
    fd.append('scene_number', sceneNumber.toString());
    fd.append('file', file);
    const res = await fetch(`${API_BASE}/muse/upload-manual-video`, {
      method: 'POST',
      body: fd
    });
    return handleResponse(res);
  },

  async pullMuseVideos(projectId: string) {
    const res = await fetch(`${API_BASE}/muse/pull-videos/${projectId}`, {
      method: 'POST'
    });
    return handleResponse(res);
  },

  async pullAllMuseVideos() {
    const res = await fetch(`${API_BASE}/muse/pull-all-available`, {
      method: 'POST'
    });
    return handleResponse(res);
  },

  async uploadManualVideo(projectId: string, sceneNumber: 1 | 2, file: File) {
    const fd = new FormData();
    fd.append('project_id', projectId);
    fd.append('scene_number', sceneNumber.toString());
    fd.append('file', file);
    const res = await fetch(`${API_BASE}/flow/upload-manual-video`, {
      method: 'POST',
      body: fd
    });
    return handleResponse(res);
  },

  async getRecentFlowVideos(): Promise<Array<{ filename: string; path: string; size_mb: number; time_str: string }>> {
    const res = await fetch(`${API_BASE}/flow/recent-videos`);
    return handleResponse(res);
  },

  async importFlowVideo(projectId: string, sceneNumber: 1 | 2, sourcePath?: string) {
    const res = await fetch(`${API_BASE}/flow/import-video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, scene_number: sceneNumber, source_path: sourcePath })
    });
    return handleResponse(res);
  },

  async pasteClipboardVideo(projectId: string, sceneNumber: 1 | 2) {
    const res = await fetch(`${API_BASE}/flow/paste-clipboard-video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, scene_number: sceneNumber })
    });
    return handleResponse(res);
  },

  async copyImageToClipboard(projectId: string, imageType: 'character' | 'product' = 'character') {
    const res = await fetch(`${API_BASE}/projects/${projectId}/copy-image-clipboard?image_type=${imageType}`, {
      method: 'POST'
    });
    return handleResponse(res);
  },

  async pasteClipboardImage(projectId: string, imageType: 'product' | 'character' = 'product') {
    const res = await fetch(`${API_BASE}/projects/${projectId}/paste-clipboard-image?image_type=${imageType}`, {
      method: 'POST'
    });
    return handleResponse(res);
  },

  async deleteProjectImage(projectId: string, imageType: 'product' | 'character', assetId?: string) {
    const query = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : '';
    const res = await fetch(`${API_BASE}/projects/${projectId}/image/${imageType}${query}`, {
      method: 'DELETE'
    });
    return handleResponse(res);
  },

  async deleteSceneVideo(projectId: string, sceneNumber: 1 | 2) {
    const res = await fetch(`${API_BASE}/flow/video/${projectId}/${sceneNumber}`, {
      method: 'DELETE'
    });
    return handleResponse(res);
  },

  async deleteExportVideo(projectId: string) {
    const res = await fetch(`${API_BASE}/flow/export/${projectId}`, {
      method: 'DELETE'
    });
    return handleResponse(res);
  },

  // FFmpeg Video Stitching
  async getFFmpegStatus() {
    const res = await fetch(`${API_BASE}/ffmpeg/status`);
    return handleResponse(res);
  },

  async stitchVideos(options: {
    project_id: string;
    transition?: string;
    transition_duration?: number;
    volume?: number;
    trim_v1_start?: number;
    trim_v2_end?: number;
    custom_name?: string;
  }) {
    const res = await fetch(`${API_BASE}/ffmpeg/stitch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options)
    });
    return handleResponse(res);
  },

  async openProjectFolder(projectId: string) {
    const res = await fetch(`${API_BASE}/ffmpeg/open-folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId })
    });
    return handleResponse(res);
  },

  // Prompts Library
  async listPrompts(category?: string): Promise<PromptTemplate[]> {
    const url = category ? `${API_BASE}/prompts?category=${category}` : `${API_BASE}/prompts`;
    const res = await fetch(url);
    return handleResponse<PromptTemplate[]>(res);
  },

  async createPrompt(data: Partial<PromptTemplate>): Promise<PromptTemplate> {
    const res = await fetch(`${API_BASE}/prompts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse<PromptTemplate>(res);
  },

  async updatePrompt(id: string, data: Partial<PromptTemplate>): Promise<PromptTemplate> {
    const res = await fetch(`${API_BASE}/prompts/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse<PromptTemplate>(res);
  },

  async deletePrompt(id: string) {
    const res = await fetch(`${API_BASE}/prompts/${id}`, { method: 'DELETE' });
    return handleResponse(res);
  },

  async duplicatePrompt(id: string) {
    const res = await fetch(`${API_BASE}/prompts/${id}/duplicate`, { method: 'POST' });
    return handleResponse(res);
  },

  async resetDefaultPrompts() {
    const res = await fetch(`${API_BASE}/prompts/reset-defaults`, { method: 'POST' });
    return handleResponse(res);
  },

  async renderPrompt(projectId: string, promptId?: string, customContent?: string): Promise<{ rendered: string }> {
    const res = await fetch(`${API_BASE}/prompts/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, prompt_id: promptId, custom_content: customContent })
    });
    return handleResponse(res);
  },

  // Quality & Safety Check
  async checkQuality(data: {
    scene1_dialogue: string;
    scene2_dialogue: string;
    scene1_prompt?: string;
    scene2_prompt?: string;
    product_name?: string;
  }): Promise<QualityCheckResult> {
    const res = await fetch(`${API_BASE}/quality/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse(res);
  },

  // Settings
  async getSettings() {
    const res = await fetch(`${API_BASE}/settings`);
    return handleResponse(res);
  },

  async updateSettings(data: Record<string, any>) {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse(res);
  },

  // Tasks Logs
  async getLogs(projectId?: string): Promise<AutomationTask[]> {
    const url = projectId ? `${API_BASE}/logs?project_id=${projectId}` : `${API_BASE}/logs`;
    const res = await fetch(url);
    return handleResponse<AutomationTask[]>(res);
  }
};

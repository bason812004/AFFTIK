import React, { useEffect, useState } from 'react';
import { 
  FolderKanban, 
  Image as ImageIcon, 
  Film, 
  CheckCircle2, 
  Clock, 
  Plus, 
  ArrowRight, 
  Sparkles, 
  Bot, 
  ExternalLink,
  Flame,
  Zap,
  Loader2,
  Play,
  Pause
} from 'lucide-react';
import { Project } from '../types';
import { api } from '../api';

interface DashboardViewProps {
  onNewProject: () => void;
  onOpenProject: (projectId: string) => void;
  geminiStatus: any;
  flowStatus: any;
  museStatus?: any;
  ffmpegStatus: any;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  onNewProject,
  onOpenProject,
  geminiStatus,
  flowStatus,
  museStatus,
  ffmpegStatus
}) => {
  const [stats, setStats] = useState({
    total_projects: 0,
    completed_projects: 0,
    ongoing_projects: 0,
    total_characters: 0,
    total_scene_videos: 0,
    total_exports: 0
  });
  const [recentProjects, setRecentProjects] = useState<Project[]>([]);
  const [sessionState, setSessionState] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData(silent: boolean = false) {
      try {
        const [statsData, projectsData, sess] = await Promise.all([
          api.getDashboardStats(),
          api.listProjects(),
          api.getSessionState().catch(() => null)
        ]);
        setStats(statsData);
        setRecentProjects(projectsData.slice(0, 6));
        if (sess) setSessionState(sess);
      } catch (e) {
        console.error(e);
      } finally {
        if (!silent) setLoading(false);
      }
    }
    loadData(false);
    const timer = setInterval(() => loadData(true), 4000);
    return () => clearInterval(timer);
  }, []);

  const statCards = [
    { label: 'Tổng số dự án', value: stats.total_projects, icon: FolderKanban, color: 'from-blue-500/20 to-indigo-500/10', text: 'text-blue-400', border: 'border-blue-500/30' },
    { label: 'Ảnh nhân vật AI đã tạo', value: stats.total_characters, icon: ImageIcon, color: 'from-cyan-500/20 to-teal-500/10', text: 'text-cyan-400', border: 'border-cyan-500/30' },
    { label: 'Video cảnh đã tạo (Flow)', value: stats.total_scene_videos, icon: Film, color: 'from-purple-500/20 to-pink-500/10', text: 'text-purple-400', border: 'border-purple-500/30' },
    { label: 'Video hoàn chỉnh (Ghép)', value: stats.total_exports, icon: CheckCircle2, color: 'from-emerald-500/20 to-green-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30' },
  ];

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-[#181d29] via-[#1b2233] to-[#141924] border border-[#232a3b] p-8 shadow-2xl">
        <div className="relative z-10 max-w-2xl space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-pink-500/15 border border-pink-500/30 text-pink-400 text-xs font-semibold">
            <Flame className="w-3.5 h-3.5 text-[#fe2c55]" />
            <span>TikTok Affiliate Automation Studio v1.0 PRO</span>
          </div>
          <h2 className="text-3xl font-extrabold text-white tracking-tight leading-tight">
            Sản xuất Video TikTok Affiliate <br />
            <span className="gradient-text-tiktok">Chuẩn 42 Từ 10 Giây Tự Động</span>
          </h2>
          <p className="text-slate-400 text-sm leading-relaxed">
            Quy trình khép kín: Tải ảnh sản phẩm &rarr; Gemini tạo nhân vật thương mại & kịch bản A/B/C &rarr; Google Flow tạo 2 video cảnh &rarr; FFmpeg tự động ghép hoàn chỉnh.
          </p>
          <div className="pt-2 flex items-center gap-3">
            <button
              onClick={onNewProject}
              className="px-5 py-3 rounded-xl bg-gradient-to-r from-[#fe2c55] to-[#ff0050] hover:from-[#e02449] hover:to-[#fe2c55] text-white font-bold text-sm shadow-lg shadow-pink-500/25 flex items-center gap-2 transition-all transform hover:-translate-y-0.5"
            >
              <Plus className="w-4 h-4" />
              <span>Tạo Dự Án Mới Ngay</span>
            </button>
            <div className="text-xs text-slate-400 flex items-center gap-2 pl-2">
              <Zap className="w-3.5 h-3.5 text-[#25f4ee]" />
              <span>Chạy hoàn toàn cục bộ trên máy tính của bạn</span>
            </div>
          </div>
        </div>

        {/* Ambient background glow */}
        <div className="absolute right-0 top-0 bottom-0 w-96 bg-gradient-to-l from-pink-500/10 via-purple-500/10 to-transparent pointer-events-none" />
      </div>

      {/* Stats Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div
              key={idx}
              className={`p-5 rounded-2xl bg-gradient-to-br ${card.color} border ${card.border} backdrop-blur-sm space-y-3`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-300">{card.label}</span>
                <div className={`p-2 rounded-xl bg-[#12161f]/80 ${card.text}`}>
                  <Icon className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-black text-white tracking-tight">
                {card.value}
              </div>
            </div>
          );
        })}
      </div>

      {/* Service Health & Connection Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-[#181d29] border border-[#232a3b] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
              <Bot className="w-4 h-4 text-cyan-400" />
            </div>
            <div>
              <div className="text-xs font-semibold text-white">Google Gemini</div>
              <div className="text-[11px] text-slate-400">Tạo nhân vật & 3 kịch bản</div>
            </div>
          </div>
          <span className={`text-[11px] px-2.5 py-1 rounded-full font-semibold border ${
            geminiStatus?.logged_in
              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
              : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
          }`}>
            {geminiStatus?.logged_in ? 'Đã kết nối' : 'Cần đăng nhập'}
          </span>
        </div>

        <div className="p-4 rounded-xl bg-[#181d29] border border-[#232a3b] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-purple-500/10 border border-purple-500/30 flex items-center justify-center">
              <Film className="w-4 h-4 text-purple-400" />
            </div>
            <div>
              <div className="text-xs font-semibold text-white">Video AI (Muse / Flow)</div>
              <div className="text-[11px] text-slate-400">Chỉ cần 1 trong 2 để tạo video</div>
            </div>
          </div>
          <span className={`text-[11px] px-2.5 py-1 rounded-full font-semibold border ${
            (flowStatus?.logged_in || museStatus?.logged_in)
              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
              : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
          }`}>
            {museStatus?.logged_in && flowStatus?.logged_in
              ? 'Cả 2 đã sẵn sàng'
              : museStatus?.logged_in
                ? 'Muse AI: Đã kết nối'
                : flowStatus?.logged_in
                  ? 'Flow: Đã kết nối'
                  : 'Cần đăng nhập 1 trong 2'}
          </span>
        </div>

        <div className="p-4 rounded-xl bg-[#181d29] border border-[#232a3b] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <div className="text-xs font-semibold text-white">FFmpeg Engine</div>
              <div className="text-[11px] text-slate-400">Ghép video chuẩn 9:16 1080p</div>
            </div>
          </div>
          <span className={`text-[11px] px-2.5 py-1 rounded-full font-semibold border ${
            ffmpegStatus?.installed
              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
              : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
          }`}>
            {ffmpegStatus?.installed ? 'Đã sẵn sàng' : 'Chưa cài đặt'}
          </span>
        </div>
      </div>

      {/* Recent Projects List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-pink-400" />
            <span>Dự Án Gần Đây</span>
          </h3>
          <span className="text-xs text-slate-400">{recentProjects.length} dự án</span>
        </div>

        {recentProjects.length === 0 ? (
          <div className="p-12 rounded-2xl bg-[#181d29] border border-[#232a3b] text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-pink-500/10 border border-pink-500/20 flex items-center justify-center mx-auto text-pink-400">
              <FolderKanban className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h4 className="text-base font-semibold text-white">Chưa có dự án nào</h4>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                Bắt đầu bằng cách tải lên ảnh sản phẩm tìm được trên TikTok để AI tự động sản xuất video.
              </p>
            </div>
            <button
              onClick={onNewProject}
              className="px-4 py-2 rounded-xl bg-pink-500 hover:bg-pink-600 text-white text-xs font-bold shadow-md shadow-pink-500/20"
            >
              + Tạo Dự Án Đầu Tiên
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recentProjects.map((p) => {
              const statusMap: Record<string, { label: string; color: string }> = {
                created: { label: 'Đã tạo dự án', color: 'bg-slate-500/20 text-slate-300' },
                image_uploaded: { label: 'Đã có ảnh SP', color: 'bg-blue-500/20 text-blue-300' },
                character_created: { label: 'Đã tạo nhân vật', color: 'bg-cyan-500/20 text-cyan-300' },
                scripts_created: { label: 'Đã tạo 3 kịch bản', color: 'bg-purple-500/20 text-purple-300' },
                option_selected: { label: 'Đã chọn kịch bản', color: 'bg-indigo-500/20 text-indigo-300' },
                video1_ready: { label: 'Đã có Video 1', color: 'bg-amber-500/20 text-amber-300' },
                video2_ready: { label: 'Đã có 2 Video', color: 'bg-orange-500/20 text-orange-300' },
                completed: { label: 'Đã hoàn thành video', color: 'bg-emerald-500/20 text-emerald-300' }
              };
              const sInfo = statusMap[p.status] || { label: p.status, color: 'bg-slate-500/20 text-slate-300' };
              const activeRunId = sessionState?.running_project_id || null;
              const batchItem = (sessionState?.batch_projects || []).find((bp: any) => bp.id === p.id);
              const isCompleted = Boolean(p.has_export || p.status === 'completed');
              const isPaused = Boolean(p.is_paused || batchItem?.task_status === 'paused' || p.task_status === 'paused');
              const isRunningNow = Boolean(!isPaused && !isCompleted && (p.id === activeRunId || p.is_running_now));
              const isQueued = Boolean(!isRunningNow && !isPaused && !isCompleted && (p.in_queue || p.step_name === 'Đang chờ tới lượt'));

              return (
                <div
                  key={p.id}
                  onClick={() => onOpenProject(p.id)}
                  className={`p-4 rounded-xl bg-[#181d29] border transition-all cursor-pointer group space-y-3 ${
                    isRunningNow ? 'border-pink-500/80 ring-1 ring-pink-500/30' : 'border-[#232a3b] hover:border-pink-500/40'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="w-14 h-14 rounded-lg bg-[#12161f] border border-[#232a3b] overflow-hidden shrink-0 flex items-center justify-center">
                      {p.original_image_path ? (
                        <img
                          src={`/data/projects/${p.id}/product/${p.original_image_path.split('\\').pop()?.split('/').pop()}`}
                          alt={p.name}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                      ) : (
                        <ImageIcon className="w-6 h-6 text-slate-500" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-bold text-white truncate group-hover:text-pink-400 transition-colors">
                        {p.name}
                      </h4>
                      <div className="text-[11px] text-slate-400 truncate">{p.category}</div>
                      {isRunningNow && (
                        <div className="text-[10px] font-extrabold text-pink-300 flex items-center gap-1 mt-1">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          <span className="truncate">{batchItem?.step_name || p.step_name || 'Đang chạy tự động...'}</span>
                        </div>
                      )}
                      {isQueued && (
                        <div className="text-[10px] font-bold text-indigo-300 mt-1 truncate">
                          ⏳ Trong hàng đợi tự động
                        </div>
                      )}
                      {isPaused && (
                        <div className="text-[10px] font-bold text-amber-300 mt-1 truncate">
                          ⏸ Đã tạm dừng
                        </div>
                      )}
                      {p.price && <div className="text-xs font-semibold text-pink-400 mt-1">{p.price}</div>}
                    </div>
                  </div>

                  <div
                    onClick={(e) => e.stopPropagation()}
                    className="flex items-center justify-between pt-2 border-t border-[#232a3b] text-xs gap-2"
                  >
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${sInfo.color}`}>
                      {sInfo.label}
                    </span>

                    <div className="flex items-center gap-1.5">
                      {(isRunningNow || isQueued) ? (
                        <button
                          type="button"
                          onClick={async (e) => {
                            e.stopPropagation();
                            await api.pauseQueue(p.id);
                          }}
                          className="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/50 text-amber-300 text-[10px] font-extrabold flex items-center gap-1"
                        >
                          <Pause className="w-3 h-3" />
                          <span>Tạm dừng</span>
                        </button>
                      ) : !isCompleted ? (
                        <button
                          type="button"
                          onClick={async (e) => {
                            e.stopPropagation();
                            await api.resumeQueue(p.id, false);
                          }}
                          className="px-2.5 py-1 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-black text-[10px] font-black flex items-center gap-1"
                        >
                          <Play className="w-3 h-3 fill-current" />
                          <span>Tiếp tục / Hàng đợi</span>
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};


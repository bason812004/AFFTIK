import React, { useState, useEffect, useRef } from 'react';
import {
  FolderKanban,
  Search,
  Plus,
  Copy,
  Download,
  Trash2,
  Image as ImageIcon,
  Film,
  CheckCircle2,
  Loader2,
  Sparkles,
  Play,
  Pause,
  Upload,
  ClipboardPaste,
  RotateCcw
} from 'lucide-react';
import { Project } from '../types';
import { api } from '../api';

interface ProjectsListViewProps {
  onNewProject: () => void;
  onOpenProject: (projectId: string) => void;
}

type StatusTab = 'all' | 'running' | 'paused' | 'completed';

export const ProjectsListView: React.FC<ProjectsListViewProps> = ({
  onNewProject,
  onOpenProject
}) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [sessionState, setSessionState] = useState<any>(null);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedStatusTab, setSelectedStatusTab] = useState<StatusTab>('all');
  const [loading, setLoading] = useState(true);
  const [busyActionId, setBusyActionId] = useState<string | null>(null);
  const [uploadingBatch, setUploadingBatch] = useState(false);
  const [bannerNotice, setBannerNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const showTempNotice = (msg: string) => {
    setBannerNotice(msg);
    setTimeout(() => {
      setBannerNotice((prev) => (prev === msg ? null : prev));
    }, 5500);
  };

  const loadProjects = async (silent: boolean = false) => {
    try {
      if (!silent) setLoading(true);
      const [data, sess] = await Promise.all([
        api.listProjects(),
        api.getSessionState().catch(() => null)
      ]);
      setProjects(data);
      if (sess) setSessionState(sess);
    } catch (e) {
      console.error(e);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
    const timer = setInterval(() => {
      loadProjects(true);
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  // Support Ctrl+V directly on ProjectsListView to paste image into queue
  useEffect(() => {
    const onPaste = async (e: ClipboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      const items = e.clipboardData?.items;
      if (items) {
        const files: File[] = [];
        for (let i = 0; i < items.length; i++) {
          if (items[i].type.startsWith('image/')) {
            const f = items[i].getAsFile();
            if (f) files.push(f);
          }
        }
        if (files.length > 0) {
          e.preventDefault();
          await handleBatchUploadFiles(files);
        }
      }
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, []);

  const handleBatchUploadFiles = async (files: File[]) => {
    if (!files.length) return;
    try {
      setUploadingBatch(true);
      if (files.length === 1) {
        const res = await api.quickCreateProject(files[0], undefined, true);
        showTempNotice(`🚀 Đã thêm "${res.name || 'Sản phẩm mới'}" vào mục Đang chạy & Hàng đợi tự động!`);
      } else {
        const res = await api.batchCreateProjects(files, [], true);
        showTempNotice(`🚀 Đã thêm ${res.count} sản phẩm vào mục Đang chạy & Hàng đợi tự động!`);
      }
      await loadProjects(true);
    } catch (err: any) {
      alert('Lỗi thêm ảnh sản phẩm vào hàng đợi: ' + (err.message || err));
    } finally {
      setUploadingBatch(false);
    }
  };

  const handlePasteFromClipboardButton = async () => {
    try {
      setUploadingBatch(true);
      const res = await api.quickCreateFromClipboard(true);
      if (res.success) {
        showTempNotice(`📋 Đã dán "${res.name || 'Sản phẩm mới'}" vào mục Đang chạy & Hàng đợi!`);
        await loadProjects(true);
      }
    } catch (err: any) {
      alert(err.message || 'Không tìm thấy ảnh trong Clipboard! Hãy Copy ảnh (Ctrl+C) rồi bấm Dán.');
    } finally {
      setUploadingBatch(false);
    }
  };

  const handlePauseProject = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      setBusyActionId(id);
      await api.pauseQueue(id);
      showTempNotice('⏸ Đã chuyển dự án sang mục Đã tạm dừng.');
      await loadProjects(true);
    } catch (err: any) {
      alert('Lỗi tạm dừng: ' + (err.message || err));
    } finally {
      setBusyActionId(null);
    }
  };

  const handleResumeOrEnqueueProject = async (e: React.MouseEvent, id: string, forceRegenerate: boolean = false) => {
    e.stopPropagation();
    try {
      setBusyActionId(id);
      if (forceRegenerate) {
        await api.enqueueProject(id, true, true);
        showTempNotice('🔄 Đã xóa ảnh nhân vật & video cũ (giữ nguyên ảnh sản phẩm) và đưa vào mục Đang chạy để làm lại từ đầu!');
      } else {
        await api.resumeQueue(id, false);
        showTempNotice('▶️ Đã đưa dự án sang mục Đang chạy để tiếp tục làm tới khi ra video!');
      }
      await loadProjects(true);
    } catch (err: any) {
      alert('Lỗi tiếp tục hàng đợi: ' + (err.message || err));
    } finally {
      setBusyActionId(null);
    }
  };

  const handlePauseGlobalQueue = async () => {
    try {
      setBusyActionId('GLOBAL_PAUSE');
      await api.pauseQueue();
      showTempNotice('⏸ Đã tạm dừng toàn bộ hàng đợi tự động.');
      await loadProjects(true);
    } catch (err: any) {
      alert('Lỗi tạm dừng hàng đợi: ' + (err.message || err));
    } finally {
      setBusyActionId(null);
    }
  };

  const handleResumeAllIncomplete = async () => {
    try {
      setBusyActionId('GLOBAL_RESUME');
      const res = await api.resumeQueue(undefined, true);
      showTempNotice(res.message || '▶️ Đã thêm tất cả dự án đang tạm dừng vào hàng đợi tự động!');
      await loadProjects(true);
    } catch (err: any) {
      alert('Lỗi chạy hàng đợi: ' + (err.message || err));
    } finally {
      setBusyActionId(null);
    }
  };

  const handleDuplicate = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await api.duplicateProject(id);
      await loadProjects(true);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string, name: string) => {
    e.stopPropagation();
    if (confirm(`Bạn có chắc chắn muốn xóa dự án "${name}" không? Toàn bộ file ảnh, kịch bản và video liên quan sẽ bị xóa.`)) {
      try {
        await api.deleteProject(id);
        await loadProjects(true);
      } catch (err) {
        console.error(err);
      }
    }
  };

  const handleExportZip = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    window.open(`/api/projects/${id}/export-zip`, '_blank');
  };

  const activeRunId = sessionState?.running_project_id || sessionState?.batch_state?.current_project_id;
  const globalPaused = Boolean(sessionState?.batch_state?.paused_by_user);

  const classifyProject = (p: Project): 'running' | 'paused' | 'completed' => {
    if (p.section_group === 'running' || p.section_group === 'paused' || p.section_group === 'completed') {
      return p.section_group;
    }
    const batchItem = (sessionState?.batch_projects || []).find((bp: any) => bp.id === p.id);
    const isPaused = Boolean(
      p.is_paused ||
      batchItem?.task_status === 'paused' ||
      p.task_status === 'paused'
    );
    const isRunningNow = Boolean(!isPaused && (p.id === activeRunId || p.is_running_now));
    const isQueued = Boolean(
      !isRunningNow &&
      !isPaused &&
      (p.in_queue || batchItem?.step_name === 'Đang chờ tới lượt' || p.step_name === 'Đang chờ tới lượt')
    );
    if (isRunningNow || isQueued) return 'running';
    if (p.has_export || p.status === 'completed') return 'completed';
    return 'paused';
  };

  const categories = ['all', ...Array.from(new Set(projects.map(p => p.category).filter(Boolean)))];

  // Filter by search & product category first
  const baseFiltered = projects.filter(p => {
    const matchesSearch =
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.category?.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || p.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  // Group into the 3 requested sections: Đang chạy, Đã tạm dừng, Đã hoàn thành
  const runningSectionProjects = baseFiltered
    .filter(p => classifyProject(p) === 'running')
    .sort((a, b) => {
      if (a.is_running_now && !b.is_running_now) return -1;
      if (!a.is_running_now && b.is_running_now) return 1;
      return (a.queue_position || 999) - (b.queue_position || 999);
    });
  const pausedSectionProjects = baseFiltered.filter(p => classifyProject(p) === 'paused');
  const completedSectionProjects = baseFiltered.filter(p => classifyProject(p) === 'completed');

  // Total counts across all projects (for top bar badges)
  const totalRunningCount = projects.filter(p => classifyProject(p) === 'running').length;
  const totalPausedCount = projects.filter(p => classifyProject(p) === 'paused').length;
  const totalCompletedCount = projects.filter(p => classifyProject(p) === 'completed').length;
  const runningProject = projects.find(p => p.id === activeRunId || p.is_running_now);

  const statusMap: Record<string, { label: string; color: string }> = {
    created: { label: 'Đã tạo dự án', color: 'bg-slate-500/20 text-slate-300' },
    image_uploaded: { label: 'Đã có ảnh SP gốc', color: 'bg-blue-500/20 text-blue-300' },
    character_created: { label: 'Đã tạo nhân vật', color: 'bg-cyan-500/20 text-cyan-300' },
    scripts_created: { label: 'Đã tạo kịch bản', color: 'bg-purple-500/20 text-purple-300' },
    option_selected: { label: 'Đã chọn kịch bản', color: 'bg-indigo-500/20 text-indigo-300' },
    video1_ready: { label: 'Đã có Video 1', color: 'bg-amber-500/20 text-amber-300' },
    video2_ready: { label: 'Đã có 2 Video', color: 'bg-orange-500/20 text-orange-300' },
    completed: { label: 'Đã hoàn thành video', color: 'bg-emerald-500/20 text-emerald-300' }
  };

  const renderProjectCard = (p: Project) => {
    const group = classifyProject(p);
    const batchItem = (sessionState?.batch_projects || []).find((bp: any) => bp.id === p.id);
    const isRunningNow = group === 'running' && Boolean(p.id === activeRunId || p.is_running_now);
    const isQueued = group === 'running' && !isRunningNow;
    const isPaused = group === 'paused';
    const isCompleted = group === 'completed';

    const sInfo = isCompleted
      ? statusMap.completed
      : (statusMap[p.status] || { label: p.status, color: 'bg-slate-500/20 text-slate-300' });
    const stepLabel = batchItem?.step_name || p.step_name || '';
    const progressPct = isCompleted
      ? 100
      : (batchItem?.progress_percent ?? p.progress_percent ?? 10);
    const isBusy = busyActionId === p.id;

    return (
      <div
        key={p.id}
        onClick={() => onOpenProject(p.id)}
        className={`rounded-2xl bg-[#181d29] border transition-all cursor-pointer group flex flex-col justify-between overflow-hidden shadow-lg shadow-black/20 ${
          isRunningNow
            ? 'border-pink-500/90 ring-2 ring-pink-500/30'
            : isQueued
              ? 'border-indigo-500/60 hover:border-pink-500/50'
              : isPaused
                ? 'border-amber-500/60 hover:border-amber-400'
                : 'border-emerald-500/40 hover:border-emerald-400/70'
        }`}
      >
        <div className="p-5 space-y-3.5">
          {/* Top row: Image & Basic Info */}
          <div className="flex items-start gap-3.5">
            <div className="w-16 h-16 rounded-xl bg-[#12161f] border border-[#232a3b] overflow-hidden shrink-0 flex items-center justify-center relative">
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
                <ImageIcon className="w-6 h-6 text-slate-600" />
              )}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#12161f] text-slate-400 border border-[#232a3b]">
                  {p.category}
                </span>
                {isRunningNow && (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-pink-500/20 text-pink-300 font-extrabold border border-pink-500/40 flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>ĐANG CHẠY {progressPct ? `${progressPct}%` : ''}</span>
                  </span>
                )}
                {isQueued && (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/40">
                    ⏳ HÀNG ĐỢI {p.queue_position ? `#${p.queue_position}` : ''}
                  </span>
                )}
                {isPaused && (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40">
                    ⏸ ĐÃ TẠM DỪNG
                  </span>
                )}
                {isCompleted && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30">
                    ✅ ĐÃ HOÀN THÀNH
                  </span>
                )}
              </div>
              <h3 className="text-sm font-bold text-white group-hover:text-pink-400 transition-colors line-clamp-2 leading-snug">
                {p.name}
              </h3>
              {(isRunningNow || isQueued || isPaused) && stepLabel && (
                <div className="text-[11px] font-bold text-cyan-300 mt-1 truncate">
                  {isRunningNow ? '🤖 ' : isPaused ? '⏸ ' : '⏳ '}
                  {stepLabel}
                </div>
              )}
              {p.price && <div className="text-xs font-semibold text-pink-400 mt-1">{p.price}</div>}
            </div>
          </div>

          {/* Progress bar if running / queued / paused */}
          {(isRunningNow || isQueued || isPaused) && (
            <div className="w-full h-1.5 rounded-full bg-[#12161f] overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  isRunningNow
                    ? 'bg-gradient-to-r from-pink-500 to-cyan-400'
                    : isPaused
                      ? 'bg-amber-400'
                      : 'bg-indigo-400'
                }`}
                style={{ width: `${Math.max(8, Math.min(100, progressPct || 10))}%` }}
              />
            </div>
          )}

          {/* Summary badges */}
          <div className="flex items-center justify-between gap-2 text-xs text-slate-400 pt-2 border-t border-[#232a3b]/60">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                <ImageIcon className="w-3.5 h-3.5 text-cyan-400" />
                <span>{p.character_count || 0} ảnh nhân vật</span>
              </div>
              <div className="flex items-center gap-1">
                <Film className="w-3.5 h-3.5 text-purple-400" />
                <span>{p.video_count || 0} video cảnh</span>
              </div>
            </div>

            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${sInfo.color}`}>
              {sInfo.label}
            </span>
          </div>
        </div>

        {/* Footer with Direct External Queue Action Buttons */}
        <div
          onClick={(e) => e.stopPropagation()}
          className="px-4 py-3 bg-[#12161f]/90 border-t border-[#232a3b] flex items-center justify-between gap-2 text-xs"
        >
          <div className="flex items-center gap-1.5 flex-wrap">
            {(isRunningNow || isQueued) && (
              <button
                type="button"
                onClick={(e) => handlePauseProject(e, p.id)}
                disabled={isBusy}
                className="px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/50 text-amber-300 text-[11px] font-extrabold flex items-center gap-1 transition-all"
              >
                {isBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Pause className="w-3.5 h-3.5" />}
                <span>Tạm dừng</span>
              </button>
            )}

            {isPaused && (
              <button
                type="button"
                onClick={(e) => handleResumeOrEnqueueProject(e, p.id, false)}
                disabled={isBusy}
                className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black text-[11px] font-black shadow-md flex items-center gap-1 transition-all"
              >
                {isBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                <span>Tiếp tục chạy</span>
              </button>
            )}

            <button
              type="button"
              onClick={(e) => handleResumeOrEnqueueProject(e, p.id, true)}
              disabled={isBusy}
              title="Xóa toàn bộ ảnh nhân vật & video cũ (giữ nguyên ảnh sản phẩm gốc) để chạy lại từ đầu"
              className="px-2.5 py-1.5 rounded-lg bg-[#181d29] hover:bg-pink-500/20 border border-[#2d364c] hover:border-pink-500/50 text-slate-300 hover:text-pink-200 text-[11px] font-bold flex items-center gap-1 transition-all"
            >
              {isBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
              <span>Chạy lại</span>
            </button>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={(e) => handleDuplicate(e, p.id)}
              title="Nhân bản dự án"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#232a3b] transition-colors"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={(e) => handleExportZip(e, p.id)}
              title="Tải gói ZIP dự án"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#232a3b] transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={(e) => handleDelete(e, p.id, p.name)}
              title="Xóa dự án"
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleBatchUploadFiles(Array.from(e.target.files));
            e.target.value = '';
          }
        }}
      />

      {/* Top Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FolderKanban className="w-5 h-5 text-pink-400" />
            <span>Quản Lý Dự Án Sản Phẩm ({projects.length})</span>
          </h2>
          <p className="text-xs text-slate-400">
            Phân chia trực quan theo 3 mục: Đang chạy, Đã tạm dừng, Đã hoàn thành. Khi chọn &ldquo;Chạy lại&rdquo;, hệ thống tự động xóa ảnh nhân vật & video cũ (giữ lại ảnh sản phẩm gốc) để làm lại từ đầu.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            type="button"
            onClick={handlePasteFromClipboardButton}
            disabled={uploadingBatch}
            className="px-3.5 py-2.5 rounded-xl bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/40 text-emerald-300 text-xs font-bold flex items-center gap-1.5 transition-all"
          >
            <ClipboardPaste className="w-4 h-4" />
            <span>📋 Dán Ảnh Vào Hàng Đợi (Ctrl+V)</span>
          </button>

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadingBatch}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-black text-xs font-extrabold shadow-md flex items-center gap-1.5 transition-all"
          >
            {uploadingBatch ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            <span>📥 Thêm 1 Hoặc Nhiều Ảnh Vào Hàng Đợi</span>
          </button>

          <button
            type="button"
            onClick={onNewProject}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-[#fe2c55] to-[#ff0050] hover:from-[#e02449] hover:to-[#fe2c55] text-white text-xs font-bold shadow-md shadow-pink-500/20 flex items-center gap-2 transition-all shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span>Tạo Dự Án Mới</span>
          </button>
        </div>
      </div>

      {/* =========================================================================
          GLOBAL QUEUE CONTROL BAR (PAUSE / RESUME / ENQUEUE ALL WITHOUT CLICKING IN)
          ========================================================================= */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-[#181d29] via-[#1c2233] to-[#151a26] border-2 border-pink-500/35 shadow-xl space-y-3">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <Sparkles className={`w-4 h-4 text-pink-400 ${totalRunningCount > 0 && !globalPaused ? 'animate-spin' : ''}`} />
              <span className="text-xs font-black text-white uppercase tracking-wider">
                ⚡ ĐIỀU KHIỂN HÀNG ĐỢI TỰ ĐỘNG (TỰ ĐỘNG CHẠY TỚI KHI RA VIDEO 20 GIÂY)
              </span>
              <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-pink-500/20 text-pink-300 border border-pink-500/40 font-bold">
                ⚡ Đang chạy: {totalRunningCount}
              </span>
              <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold">
                ⏸ Đã tạm dừng: {totalPausedCount}
              </span>
              <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-bold">
                ✅ Đã hoàn thành: {totalCompletedCount}/{projects.length}
              </span>
            </div>

            <div className="text-xs text-slate-300">
              {runningProject && totalRunningCount > 0 && !globalPaused ? (
                <span>
                  🤖 Đang làm tự động:{' '}
                  <b className="text-pink-300">{runningProject.name}</b> —{' '}
                  <span className="text-cyan-300 font-semibold">
                    {runningProject.step_name || 'Đang xử lý...'} ({runningProject.progress_percent || 15}%)
                  </span>
                </span>
              ) : totalPausedCount > 0 ? (
                <span className="text-amber-300 font-semibold">
                  ⏸ Đang có {totalPausedCount} dự án trong mục Đã tạm dừng. Bấm &ldquo;Tiếp Tục Chạy Hàng Đợi&rdquo; để hệ thống tự động làm tiếp!
                </span>
              ) : (
                <span className="text-emerald-300 font-semibold">
                  ✅ Tất cả dự án hiện tại đã hoàn thành xuất video 20 giây! Bạn có thể bấm &ldquo;Chạy lại&rdquo; ở bất kỳ dự án nào để làm mới từ đầu.
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap shrink-0">
            {totalRunningCount > 0 && !globalPaused && (
              <button
                type="button"
                onClick={handlePauseGlobalQueue}
                disabled={busyActionId === 'GLOBAL_PAUSE'}
                className="px-4 py-2.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/50 text-amber-300 text-xs font-extrabold flex items-center gap-1.5 transition-all"
              >
                {busyActionId === 'GLOBAL_PAUSE' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Pause className="w-4 h-4" />
                )}
                <span>⏸ Tạm Dừng Hàng Đợi</span>
              </button>
            )}

            {(globalPaused || totalPausedCount > 0) && (
              <button
                type="button"
                onClick={handleResumeAllIncomplete}
                disabled={busyActionId === 'GLOBAL_RESUME'}
                className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black text-xs font-black shadow-lg flex items-center gap-1.5 transition-all"
              >
                {busyActionId === 'GLOBAL_RESUME' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4 fill-current" />
                )}
                <span>▶️ Tiếp Tục Chạy Tất Cả Đã Tạm Dừng ({totalPausedCount})</span>
              </button>
            )}
          </div>
        </div>

        {bannerNotice && (
          <div className="px-3.5 py-2 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-200 text-xs font-bold flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{bannerNotice}</span>
          </div>
        )}
      </div>

      {/* =========================================================================
          3-SECTION STATUS TABS (ĐANG CHẠY / ĐÃ TẠM DỪNG / ĐÃ HOÀN THÀNH)
          ========================================================================= */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <button
          type="button"
          onClick={() => setSelectedStatusTab('all')}
          className={`p-3.5 rounded-2xl border text-left transition-all flex items-center justify-between ${
            selectedStatusTab === 'all'
              ? 'bg-slate-800/90 border-white/40 ring-2 ring-white/15 shadow-lg'
              : 'bg-[#181d29] border-[#232a3b] hover:border-slate-600'
          }`}
        >
          <div>
            <div className="text-[11px] font-bold text-slate-400 uppercase">Hiển thị tất cả</div>
            <div className="text-sm font-black text-white mt-0.5">Tất cả các mục</div>
          </div>
          <span className="px-2.5 py-1 rounded-xl bg-slate-700/70 text-white text-xs font-black">
            {baseFiltered.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setSelectedStatusTab('running')}
          className={`p-3.5 rounded-2xl border text-left transition-all flex items-center justify-between ${
            selectedStatusTab === 'running'
              ? 'bg-pink-500/20 border-pink-500 ring-2 ring-pink-500/30 shadow-lg'
              : 'bg-[#181d29] border-pink-500/30 hover:border-pink-500/60'
          }`}
        >
          <div>
            <div className="text-[11px] font-bold text-pink-300 uppercase flex items-center gap-1">
              <Loader2 className={`w-3 h-3 ${runningSectionProjects.length > 0 ? 'animate-spin' : ''}`} />
              <span>Mục 1</span>
            </div>
            <div className="text-sm font-black text-white mt-0.5">⚡ Đang chạy & Hàng đợi</div>
          </div>
          <span className="px-2.5 py-1 rounded-xl bg-pink-500/25 border border-pink-500/40 text-pink-200 text-xs font-black">
            {runningSectionProjects.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setSelectedStatusTab('paused')}
          className={`p-3.5 rounded-2xl border text-left transition-all flex items-center justify-between ${
            selectedStatusTab === 'paused'
              ? 'bg-amber-500/20 border-amber-500 ring-2 ring-amber-500/30 shadow-lg'
              : 'bg-[#181d29] border-amber-500/30 hover:border-amber-500/60'
          }`}
        >
          <div>
            <div className="text-[11px] font-bold text-amber-300 uppercase">Mục 2</div>
            <div className="text-sm font-black text-white mt-0.5">⏸ Đã tạm dừng</div>
          </div>
          <span className="px-2.5 py-1 rounded-xl bg-amber-500/25 border border-amber-500/40 text-amber-200 text-xs font-black">
            {pausedSectionProjects.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setSelectedStatusTab('completed')}
          className={`p-3.5 rounded-2xl border text-left transition-all flex items-center justify-between ${
            selectedStatusTab === 'completed'
              ? 'bg-emerald-500/20 border-emerald-500 ring-2 ring-emerald-500/30 shadow-lg'
              : 'bg-[#181d29] border-emerald-500/30 hover:border-emerald-500/60'
          }`}
        >
          <div>
            <div className="text-[11px] font-bold text-emerald-300 uppercase">Mục 3</div>
            <div className="text-sm font-black text-white mt-0.5">✅ Đã hoàn thành</div>
          </div>
          <span className="px-2.5 py-1 rounded-xl bg-emerald-500/25 border border-emerald-500/40 text-emerald-200 text-xs font-black">
            {completedSectionProjects.length}
          </span>
        </button>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col md:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Tìm kiếm dự án theo tên sản phẩm, ngành hàng..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-[#181d29] border border-[#232a3b] text-white text-xs focus:border-pink-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-2 rounded-xl text-xs font-medium whitespace-nowrap transition-colors border ${
                selectedCategory === cat
                  ? 'bg-pink-500/15 text-pink-400 border-pink-500/30 font-semibold'
                  : 'bg-[#181d29] text-slate-400 border-[#232a3b] hover:text-white'
              }`}
            >
              {cat === 'all' ? 'Tất cả ngành hàng' : cat}
            </button>
          ))}
        </div>
      </div>

      {/* =========================================================================
          SECTIONS DISPLAY: ĐANG CHẠY / ĐÃ TẠM DỪNG / ĐÃ HOÀN THÀNH
          ========================================================================= */}
      {baseFiltered.length === 0 ? (
        <div className="p-12 rounded-2xl bg-[#181d29] border border-[#232a3b] text-center space-y-4">
          <FolderKanban className="w-12 h-12 text-slate-600 mx-auto" />
          <div className="text-sm font-semibold text-slate-300">Không tìm thấy dự án phù hợp</div>
          <button
            onClick={onNewProject}
            className="px-4 py-2 rounded-xl bg-pink-500 text-white text-xs font-semibold"
          >
            Tạo dự án mới ngay
          </button>
        </div>
      ) : (
        <div className="space-y-8">
          {/* MỤC 1: ĐANG CHẠY & HÀNG ĐỢI */}
          {(selectedStatusTab === 'all' || selectedStatusTab === 'running') && (
            <div className="space-y-3.5">
              <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-gradient-to-r from-pink-500/15 via-indigo-500/10 to-transparent border border-pink-500/30">
                <div className="flex items-center gap-2.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-pink-500 animate-ping" />
                  <h3 className="text-sm font-black text-white uppercase tracking-wide">
                    ⚡ MỤC ĐANG CHẠY & TRONG HÀNG ĐỢI ({runningSectionProjects.length})
                  </h3>
                </div>
                {runningSectionProjects.length > 0 && (
                  <button
                    type="button"
                    onClick={handlePauseGlobalQueue}
                    className="px-3 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/40 text-amber-300 text-xs font-bold flex items-center gap-1"
                  >
                    <Pause className="w-3.5 h-3.5" />
                    <span>Tạm dừng tất cả</span>
                  </button>
                )}
              </div>

              {runningSectionProjects.length === 0 ? (
                <div className="p-6 rounded-2xl bg-[#181d29]/60 border border-dashed border-[#2b344a] text-center text-xs text-slate-400">
                  Hiện không có dự án nào đang chạy. Bạn có thể dán ảnh mới (Ctrl+V) hoặc bấm <b>&ldquo;Chạy lại&rdquo;</b> ở các dự án bên dưới để chạy lại từ đầu!
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {runningSectionProjects.map(renderProjectCard)}
                </div>
              )}
            </div>
          )}

          {/* MỤC 2: ĐÃ TẠM DỪNG */}
          {(selectedStatusTab === 'all' || selectedStatusTab === 'paused') && (
            <div className="space-y-3.5">
              <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-gradient-to-r from-amber-500/15 via-amber-500/5 to-transparent border border-amber-500/30">
                <div className="flex items-center gap-2.5">
                  <Pause className="w-4 h-4 text-amber-400" />
                  <h3 className="text-sm font-black text-white uppercase tracking-wide">
                    ⏸ MỤC ĐÃ TẠM DỪNG ({pausedSectionProjects.length})
                  </h3>
                </div>
                {pausedSectionProjects.length > 0 && (
                  <button
                    type="button"
                    onClick={handleResumeAllIncomplete}
                    className="px-3 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/40 text-emerald-300 text-xs font-bold flex items-center gap-1"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>Tiếp tục chạy tất cả ({pausedSectionProjects.length})</span>
                  </button>
                )}
              </div>

              {pausedSectionProjects.length === 0 ? (
                <div className="p-6 rounded-2xl bg-[#181d29]/60 border border-dashed border-[#2b344a] text-center text-xs text-slate-400">
                  Không có dự án nào đang tạm dừng.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {pausedSectionProjects.map(renderProjectCard)}
                </div>
              )}
            </div>
          )}

          {/* MỤC 3: ĐÃ HOÀN THÀNH */}
          {(selectedStatusTab === 'all' || selectedStatusTab === 'completed') && (
            <div className="space-y-3.5">
              <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-gradient-to-r from-emerald-500/15 via-emerald-500/5 to-transparent border border-emerald-500/30">
                <div className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-black text-white uppercase tracking-wide">
                    ✅ MỤC ĐÃ HOÀN THÀNH ({completedSectionProjects.length})
                  </h3>
                </div>
                <span className="text-[11px] text-slate-400">
                  Bấm <b>&ldquo;Chạy lại&rdquo;</b> trên thẻ để xóa ảnh nhân vật & video cũ (giữ nguyên ảnh sản phẩm) và tạo lại từ đầu
                </span>
              </div>

              {completedSectionProjects.length === 0 ? (
                <div className="p-6 rounded-2xl bg-[#181d29]/60 border border-dashed border-[#2b344a] text-center text-xs text-slate-400">
                  Chưa có dự án nào hoàn thành xuất video.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {completedSectionProjects.map(renderProjectCard)}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

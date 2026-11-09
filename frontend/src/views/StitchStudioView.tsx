import React, { useState, useEffect } from 'react';
import { 
  Combine, 
  Upload, 
  Play, 
  Download, 
  FolderOpen, 
  Sliders, 
  CheckCircle2, 
  Loader2, 
  Film,
  Sparkles
} from 'lucide-react';
import { Project } from '../types';
import { api } from '../api';

export const StitchStudioView: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [transition, setTransition] = useState<string>('none');
  const [volume, setVolume] = useState<number>(1.0);
  const [customName, setCustomName] = useState<string>('');
  const [stitching, setStitching] = useState(false);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    async function load() {
      try {
        const list = await api.listProjects();
        setProjects(list);
        if (list.length > 0) {
          setSelectedProjectId(list[0].id);
        }
      } catch (e) {
        console.error(e);
      }
    }
    load();
  }, []);

  const handleStitch = async () => {
    if (!selectedProjectId) {
      alert('Vui lòng chọn một dự án có đủ 2 video cảnh');
      return;
    }
    try {
      setStitching(true);
      setResult(null);
      const res = await api.stitchVideos({
        project_id: selectedProjectId,
        transition: transition,
        volume: volume,
        custom_name: customName.trim() ? customName.trim() : undefined
      });
      setResult(res);
    } catch (e: any) {
      alert('Lỗi ghép video: ' + e.message);
    } finally {
      setStitching(false);
    }
  };

  const handleOpenFolder = async () => {
    if (selectedProjectId) {
      await api.openProjectFolder(selectedProjectId);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Combine className="w-5 h-5 text-emerald-400" />
          <span>Ghép Video FFmpeg Chuyên Nghiệp (Chuẩn TikTok 9:16 60FPS)</span>
        </h2>
        <p className="text-xs text-slate-400">
          Tự động ghép nối Video Cảnh 1 và Cảnh 2 thành video TikTok Affiliate hoàn chỉnh 1080x1920 @ 60fps.
        </p>
      </div>

      <div className="p-6 rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-6">
        {/* Project Selector */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300 block">Chọn dự án cần ghép:</label>
          <select
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            className="w-full px-3.5 py-2.5 rounded-xl bg-[#12161f] border border-[#232a3b] text-white text-xs focus:border-emerald-500 focus:outline-none"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.category}) - ID: {p.id}
              </option>
            ))}
          </select>
        </div>

        {/* Settings Form */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 block">Hiệu ứng chuyển cảnh</label>
            <select
              value={transition}
              onChange={(e) => setTransition(e.target.value)}
              className="w-full px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white text-xs focus:border-emerald-500 focus:outline-none"
            >
              <option value="none">Nối trực tiếp (Giữ liên tục lời thoại)</option>
              <option value="fade">Mờ dần nhẹ (Dissolve 0.5s)</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 block">Âm lượng thoại (Volume)</label>
            <select
              value={volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              className="w-full px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white text-xs focus:border-emerald-500 focus:outline-none"
            >
              <option value={1.0}>100% (Mặc định)</option>
              <option value={1.2}>120% (Tăng âm lượng)</option>
              <option value={1.5}>150% (Rõ to rõ ràng)</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 block">Tên tệp xuất (Tùy chọn)</label>
            <input
              type="text"
              placeholder="ten-san-pham_tiktok-affiliate.mp4"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              className="w-full px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white text-xs focus:border-emerald-500 focus:outline-none font-mono"
            />
          </div>
        </div>

        {/* Concat Button */}
        <div className="pt-2 flex items-center justify-end gap-3 border-t border-[#232a3b]">
          <button
            onClick={handleStitch}
            disabled={stitching || !selectedProjectId}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white text-xs font-bold shadow-lg shadow-emerald-500/20 flex items-center gap-2 transition-all disabled:opacity-50"
          >
            {stitching ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Đang xử lý FFmpeg...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Bắt Đầu Ghép Video FFmpeg</span>
              </>
            )}
          </button>
        </div>

        {/* Result Area */}
        {result && (
          <div className="p-6 rounded-2xl bg-[#12161f] border border-emerald-500/30 space-y-4">
            <div className="flex items-center justify-between border-b border-[#232a3b] pb-3">
              <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                <CheckCircle2 className="w-5 h-5" />
                <span>Ghép video thành công!</span>
              </div>

              <div className="flex items-center gap-2">
                <a
                  href={`/api/ffmpeg/download/${selectedProjectId}/${result.file_name}`}
                  download
                  className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Tải video</span>
                </a>
                <button
                  onClick={handleOpenFolder}
                  className="px-3 py-1.5 rounded-lg bg-[#232a3b] text-slate-200 text-xs font-semibold flex items-center gap-1.5"
                >
                  <FolderOpen className="w-3.5 h-3.5 text-amber-400" />
                  <span>Mở thư mục</span>
                </button>
              </div>
            </div>

            <div className="text-xs text-slate-300">
              Tệp: <span className="font-mono text-white">{result.file_name}</span> &bull; Độ phân giải: {result.resolution} &bull; FPS: {result.fps} &bull; Thời lượng: {result.duration}s
            </div>

            <div className="max-w-xs mx-auto aspect-[9/16] bg-black rounded-xl overflow-hidden border border-[#232a3b]">
              <video src={result.url} controls className="w-full h-full object-contain" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};


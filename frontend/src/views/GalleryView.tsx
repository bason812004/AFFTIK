import React, { useState, useEffect } from 'react';
import { 
  Image as ImageIcon, 
  Film, 
  Download, 
  ExternalLink, 
  Play, 
  X,
  Calendar,
  Layers
} from 'lucide-react';
import { Project } from '../types';
import { api } from '../api';

interface GalleryViewProps {
  initialType?: 'image' | 'video';
  onOpenProject: (projectId: string) => void;
}

export const GalleryView: React.FC<GalleryViewProps> = ({
  initialType = 'image',
  onOpenProject
}) => {
  const [activeTab, setActiveTab] = useState<'image' | 'video'>(initialType);
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [lightboxMedia, setLightboxMedia] = useState<{ url: string; type: 'image' | 'video'; title: string } | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const list = await api.listProjects();
        // For each project, fetch assets and exports
        const fullProjects = await Promise.all(
          list.map(p => api.getProject(p.id))
        );
        setProjects(fullProjects);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const allCharacters = projects.flatMap(p => 
    (p.character_images || []).map((img: any) => ({
      ...img,
      project_name: p.name,
      project_id: p.id,
      url: `/data/projects/${p.id}/character/${img.file_path.split('\\').pop()?.split('/').pop()}`
    }))
  );

  const allVideos = projects.flatMap(p => {
    const list = [];
    if (p.videos) {
      p.videos.forEach((v: any) => {
        list.push({
          ...v,
          project_name: p.name,
          project_id: p.id,
          title: `Cảnh ${v.scene_number} - ${p.name}`,
          url: `/data/projects/${p.id}/videos/scene${v.scene_number}.mp4`,
          is_export: false
        });
      });
    }
    if (p.export) {
      list.push({
        ...p.export,
        project_name: p.name,
        project_id: p.id,
        title: `Video Hoàn Chỉnh - ${p.name}`,
        url: `/data/projects/${p.id}/exports/${p.export.file_name}`,
        is_export: true
      });
    }
    return list;
  });

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header & Tabs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#232a3b] pb-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            {activeTab === 'image' ? (
              <ImageIcon className="w-5 h-5 text-cyan-400" />
            ) : (
              <Film className="w-5 h-5 text-purple-400" />
            )}
            <span>{activeTab === 'image' ? 'Kho Ảnh Nhân Vật AI' : 'Kho Video Sản Xuất'}</span>
          </h2>
          <p className="text-xs text-slate-400">Toàn bộ tư liệu ảnh AI và video đã tạo trong các dự án</p>
        </div>

        <div className="flex items-center bg-[#181d29] p-1 rounded-xl border border-[#232a3b]">
          <button
            onClick={() => setActiveTab('image')}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === 'image'
                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <ImageIcon className="w-3.5 h-3.5" />
            <span>Ảnh Nhân Vật AI ({allCharacters.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('video')}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === 'video'
                ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            <span>Video Đã Tạo ({allVideos.length})</span>
          </button>
        </div>
      </div>

      {/* Characters Tab */}
      {activeTab === 'image' && (
        <div>
          {allCharacters.length === 0 ? (
            <div className="p-12 text-center rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-2">
              <ImageIcon className="w-10 h-10 text-slate-600 mx-auto" />
              <div className="text-sm font-semibold text-slate-300">Chưa có ảnh nhân vật AI nào</div>
              <p className="text-xs text-slate-500">Mở một dự án và bấm "Tạo nhân vật AI bằng Gemini"</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {allCharacters.map((c, i) => (
                <div
                  key={i}
                  className="rounded-xl overflow-hidden bg-[#181d29] border border-[#232a3b] group hover:border-cyan-500/40 transition-all flex flex-col justify-between"
                >
                  <div
                    onClick={() => setLightboxMedia({ url: c.url, type: 'image', title: c.project_name })}
                    className="aspect-[9/16] bg-black relative cursor-pointer overflow-hidden"
                  >
                    <img src={c.url} alt="Character" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <span className="text-xs text-white font-semibold px-2 py-1 bg-black/60 rounded">Xem to</span>
                    </div>
                  </div>

                  <div className="p-2.5 space-y-1">
                    <div className="text-xs font-bold text-white truncate">{c.project_name}</div>
                    <div className="flex items-center justify-between pt-1">
                      <button
                        onClick={() => onOpenProject(c.project_id)}
                        className="text-[10px] text-cyan-400 hover:underline flex items-center gap-1"
                      >
                        Vào dự án
                      </button>
                      <a
                        href={c.url}
                        download
                        className="p-1 text-slate-400 hover:text-white"
                        title="Tải ảnh"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Videos Tab */}
      {activeTab === 'video' && (
        <div>
          {allVideos.length === 0 ? (
            <div className="p-12 text-center rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-2">
              <Film className="w-10 h-10 text-slate-600 mx-auto" />
              <div className="text-sm font-semibold text-slate-300">Chưa có video nào</div>
              <p className="text-xs text-slate-500">Mở dự án và tạo video trên Flow hoặc ghép bằng FFmpeg</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {allVideos.map((v, i) => (
                <div
                  key={i}
                  className={`rounded-2xl overflow-hidden bg-[#181d29] border transition-all space-y-2 p-3 ${
                    v.is_export ? 'border-emerald-500/40 shadow-lg shadow-emerald-500/10' : 'border-[#232a3b]'
                  }`}
                >
                  <div className="aspect-[9/16] bg-black rounded-xl overflow-hidden relative group">
                    <video src={v.url} controls className="w-full h-full object-contain" />
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                        v.is_export ? 'bg-emerald-500/20 text-emerald-400' : 'bg-purple-500/20 text-purple-400'
                      }`}>
                        {v.is_export ? 'HOÀN CHỈNH' : `CẢNH ${v.scene_number}`}
                      </span>
                      {v.duration && <span className="text-[10px] text-slate-400">{v.duration}s</span>}
                    </div>
                    <div className="text-xs font-bold text-white truncate">{v.title}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Lightbox Modal */}
      {lightboxMedia && (
        <div
          onClick={() => setLightboxMedia(null)}
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="max-w-md w-full max-h-[90vh] flex flex-col items-center space-y-3"
          >
            <div className="flex items-center justify-between w-full text-white text-xs font-bold">
              <span>{lightboxMedia.title}</span>
              <button onClick={() => setLightboxMedia(null)} className="p-1 hover:text-pink-400">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="max-h-[80vh] aspect-[9/16] rounded-2xl overflow-hidden border border-[#232a3b] bg-black">
              {lightboxMedia.type === 'image' ? (
                <img src={lightboxMedia.url} alt="Lightbox" className="w-full h-full object-contain" />
              ) : (
                <video src={lightboxMedia.url} controls autoPlay className="w-full h-full object-contain" />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


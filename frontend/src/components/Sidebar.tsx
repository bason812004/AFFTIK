import React from 'react';
import { 
  LayoutDashboard, 
  PlusCircle, 
  FolderKanban, 
  Image as ImageIcon, 
  Film, 
  BookOpen, 
  Bot, 
  Sparkles, 
  Combine, 
  Settings, 
  Flame, 
  Wand2,
  Video
} from 'lucide-react';

interface SidebarProps {
  currentView: string;
  onSelectView: (view: string) => void;
  projectCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onSelectView,
  projectCount = 0
}) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'new_project', label: 'Tạo dự án mới', icon: PlusCircle, highlight: true },
    { id: 'manual_studio', label: 'Luồng Thủ Công (Copy & Ghép)', icon: Wand2 },
    { id: 'projects', label: 'Dự án của tôi', icon: FolderKanban, badge: projectCount },
    { id: 'character_gallery', label: 'Kho ảnh AI', icon: ImageIcon },
    { id: 'video_gallery', label: 'Kho video', icon: Film },
    { id: 'prompt_library', label: 'Kho Prompt', icon: BookOpen },
    { id: 'gemini_studio', label: 'Gemini Automation', icon: Bot },
    { id: 'flow_studio', label: 'Google Flow Studio', icon: Sparkles },
    { id: 'muse_studio', label: 'Muse AI Studio', icon: Video },
    { id: 'stitch_studio', label: 'Ghép video (FFmpeg)', icon: Combine },
    { id: 'settings', label: 'Cài đặt', icon: Settings },
  ];

  return (
    <aside className="w-64 border-r border-[#232a3b] bg-[#12161f]/60 backdrop-blur-md flex flex-col justify-between p-4 shrink-0 h-[calc(100vh-4rem)]">
      <div className="space-y-6">
        {/* Navigation list */}
        <div className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            
            if (item.highlight) {
              return (
                <button
                  key={item.id}
                  onClick={() => onSelectView(item.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-3 rounded-xl font-semibold text-sm transition-all mb-3 shadow-lg ${
                    isActive
                      ? 'bg-gradient-to-r from-[#fe2c55] to-[#ff0050] text-white shadow-pink-500/30'
                      : 'bg-gradient-to-r from-[#fe2c55]/90 to-[#fe2c55]/70 hover:from-[#fe2c55] hover:to-[#fe2c55] text-white shadow-pink-500/15'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4" />
                    <span>{item.label}</span>
                  </div>
                  <Flame className="w-4 h-4 text-amber-300 animate-pulse" />
                </button>
              );
            }

            return (
              <button
                key={item.id}
                onClick={() => onSelectView(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-pink-500/10 text-pink-400 border border-pink-500/30 shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-[#181d29]'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-pink-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#232a3b] text-slate-300 font-semibold">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Pro Badge Card */}
      <div className="p-3.5 rounded-xl bg-gradient-to-br from-[#181d29] to-[#12161f] border border-[#232a3b] text-xs">
        <div className="flex items-center gap-2 text-white font-semibold mb-1">
          <Sparkles className="w-3.5 h-3.5 text-[#25f4ee]" />
          <span>Local Engine Windows</span>
        </div>
        <p className="text-slate-400 text-[11px] leading-relaxed">
          100% dữ liệu, hình ảnh & video lưu trữ an toàn trên ổ cứng máy tính cá nhân.
        </p>
      </div>
    </aside>
  );
};


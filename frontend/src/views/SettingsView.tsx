import React, { useState, useEffect } from 'react';
import { 
  Settings as SettingsIcon, 
  Save, 
  Bot, 
  Film, 
  HardDrive, 
  Sliders, 
  CheckCircle2, 
  AlertCircle,
  FolderOpen
} from 'lucide-react';
import { api } from '../api';

export const SettingsView: React.FC = () => {
  const [settings, setSettings] = useState({
    target_duration: '10',
    target_word_count: '42',
    aspect_ratio: '9:16',
    target_resolution: '1080x1920',
    target_fps: '30',
    output_format: 'mp4',
    voice_accent: 'northern_hanoi',
    voice_tone: 'friendly_consultative',
    gemini_url: 'https://gemini.google.com/app',
    flow_url: 'https://labs.google/flow',
    default_mode: 'auto',
    gemini_api_key: '',
    browser_headless: 'true'
  });
  const [services, setServices] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getSettings();
        if (data.settings) {
          setSettings(prev => ({ ...prev, ...data.settings }));
        }
        if (data.services) {
          setServices(data.services);
        }
      } catch (e) {
        console.error(e);
      }
    }
    load();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      await api.updateSettings(settings);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e: any) {
      alert('Lỗi lưu cài đặt: ' + e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between border-b border-[#232a3b] pb-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <SettingsIcon className="w-5 h-5 text-slate-400" />
            <span>Cài Đặt Hệ Thống & Tham Số Sản Xuất</span>
          </h2>
          <p className="text-xs text-slate-400">Tùy chỉnh thông số chuẩn 42 từ, thời lượng 10s, giọng đọc và các cổng kết nối</p>
        </div>

        {saveSuccess && (
          <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-semibold bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20">
            <CheckCircle2 className="w-4 h-4" />
            <span>Đã lưu thành công!</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Section 1: Video Production Specs */}
        <div className="p-6 rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-[#232a3b] pb-3">
            <Film className="w-4 h-4 text-pink-400" />
            <span>1. Tiêu Chuẩn Sản Xuất Video TikTok Affiliate</span>
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="font-semibold text-slate-300 block mb-1">Số từ mục tiêu mỗi cảnh (Bắt buộc)</label>
              <input
                type="number"
                value={settings.target_word_count}
                onChange={(e) => setSettings({ ...settings, target_word_count: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white font-bold focus:border-pink-500 focus:outline-none"
              />
              <span className="text-[10px] text-pink-400 mt-1 block">Mặc định: 42 từ (Khớp nhịp 10 giây)</span>
            </div>

            <div>
              <label className="font-semibold text-slate-300 block mb-1">Thời lượng mục tiêu mỗi cảnh</label>
              <input
                type="text"
                value={`${settings.target_duration} giây`}
                disabled
                className="w-full px-3.5 py-2 rounded-xl bg-[#12161f]/50 border border-[#232a3b] text-slate-400 cursor-not-allowed"
              />
              <span className="text-[10px] text-slate-400 mt-1 block">Cố định: 10 giây/cảnh (Ghép thành 20s)</span>
            </div>

            <div>
              <label className="font-semibold text-slate-300 block mb-1">Tỷ lệ khung hình</label>
              <select
                value={settings.aspect_ratio}
                onChange={(e) => setSettings({ ...settings, aspect_ratio: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white focus:border-pink-500 focus:outline-none"
              >
                <option value="9:16">9:16 (Dọc TikTok/Reels/Shorts)</option>
              </select>
            </div>

            <div>
              <label className="font-semibold text-slate-300 block mb-1">Độ phân giải đầu ra</label>
              <input
                type="text"
                value={settings.target_resolution}
                onChange={(e) => setSettings({ ...settings, target_resolution: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white focus:border-pink-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="font-semibold text-slate-300 block mb-1">Tốc độ khung hình (FPS)</label>
              <input
                type="text"
                value={settings.target_fps}
                onChange={(e) => setSettings({ ...settings, target_fps: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white focus:border-pink-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="font-semibold text-slate-300 block mb-1">Định dạng file</label>
              <input
                type="text"
                value="MP4 (H.264 + AAC Audio)"
                disabled
                className="w-full px-3.5 py-2 rounded-xl bg-[#12161f]/50 border border-[#232a3b] text-slate-400 cursor-not-allowed"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Persona & Voice */}
        <div className="p-6 rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-[#232a3b] pb-3">
            <Sliders className="w-4 h-4 text-purple-400" />
            <span>2. Định Dạng Giọng Đọc & Phong Cách Nhân Vật</span>
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="font-semibold text-slate-300 block mb-1">Giọng đọc & Vùng miền</label>
              <input
                type="text"
                value="Nữ miền Bắc (Hà Nội tự nhiên, phát âm chuẩn rõ ràng)"
                disabled
                className="w-full px-3.5 py-2 rounded-xl bg-[#12161f]/50 border border-[#232a3b] text-slate-300 cursor-not-allowed"
              />
            </div>

            <div>
              <label className="font-semibold text-slate-300 block mb-1">Đại từ xưng hô kịch bản</label>
              <input
                type="text"
                value="Xưng 'em', gọi người xem là 'các bác'"
                disabled
                className="w-full px-3.5 py-2 rounded-xl bg-[#12161f]/50 border border-[#232a3b] text-slate-300 cursor-not-allowed"
              />
            </div>
          </div>
        </div>

        {/* Section 2.5: Gemini API & Headless Engine */}
        <div className="p-6 rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center justify-between border-b border-[#232a3b] pb-3">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-[#25f4ee]" />
              <span>3. Cấu Hình Gemini API & Chế Độ Chạy Ngầm (Không Cần Mở Trình Duyệt)</span>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30">
              {settings.gemini_api_key ? 'ĐÃ KẾT NỐI API' : 'WEB AUTOMATION'}
            </span>
          </h3>

          <div className="space-y-4 text-xs">
            <div>
              <label className="font-semibold text-slate-300 block mb-1">
                Google Gemini API Key (Khuyên dùng để chạy trực tiếp không mở trình duyệt)
              </label>
              <input
                type="password"
                placeholder="AIzaSy... (Lấy miễn phí tại aistudio.google.com)"
                value={settings.gemini_api_key}
                onChange={(e) => setSettings({ ...settings, gemini_api_key: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white font-mono focus:border-cyan-400 focus:outline-none"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Khi có API Key, hệ thống sẽ gọi trực tiếp Google Gemini Flash & Imagen 3 trong 2-3 giây, 100% tự động chạy ngầm, không mở bất kỳ cửa sổ trình duyệt nào.
              </p>
            </div>

            <div>
              <label className="font-semibold text-slate-300 block mb-1">
                Chế độ tự động hóa Web (Khi dùng tài khoản Google Web)
              </label>
              <select
                value={settings.browser_headless}
                onChange={(e) => setSettings({ ...settings, browser_headless: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white focus:border-pink-500 focus:outline-none"
              >
                <option value="true">Chạy ngầm 100% (Headless - Ẩn hoàn toàn cửa sổ Chrome, không hiện lên màn hình)</option>
                <option value="false">Mở cửa sổ Chrome (Headed - Có thể quan sát thao tác từng bước)</option>
              </select>
              <p className="text-[11px] text-slate-400 mt-1">
                Mặc định ẩn cửa sổ Chrome để bạn làm việc khác mà không bị gián đoạn hay nhảy cửa sổ.
              </p>
            </div>
          </div>
        </div>

        {/* Section 4: Engine & FFmpeg info */}
        <div className="p-6 rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-[#232a3b] pb-3">
            <HardDrive className="w-4 h-4 text-emerald-400" />
            <span>4. Trạng Thái FFmpeg & Lưu Trữ Cục Bộ</span>
          </h3>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between p-3 rounded-xl bg-[#12161f] border border-[#232a3b]">
              <div>
                <div className="font-semibold text-white">FFmpeg Binary Engine</div>
                <div className="text-[11px] text-slate-400 font-mono truncate max-w-md">
                  {services?.ffmpeg?.path || 'Đang sử dụng bundled ffmpeg x86_64'}
                </div>
              </div>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                services?.ffmpeg?.available ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
              }`}>
                {services?.ffmpeg?.available ? 'SẴN SÀNG' : 'CHƯA CÓ'}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[#12161f] border border-[#232a3b] text-slate-400 text-[11px] leading-relaxed">
              Toàn bộ dữ liệu dự án, ảnh sản phẩm, kịch bản và video xuất ra được lưu trực tiếp tại: <br />
              <code className="text-cyan-400 font-mono bg-black/40 px-1 py-0.5 rounded mt-1 inline-block">
                d:\toolAFF\data\projects\
              </code>
            </div>
          </div>
        </div>

        {/* Save button */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-2.5 rounded-xl bg-pink-500 hover:bg-pink-600 text-white font-bold text-xs shadow-lg shadow-pink-500/20 flex items-center gap-2 transition-all disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Đang lưu...' : 'Lưu Tất Cả Cài Đặt'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};


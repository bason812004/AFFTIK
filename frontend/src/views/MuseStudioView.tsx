import React, { useState } from 'react';
import { 
  Sparkles, 
  ExternalLink, 
  LogOut, 
  RefreshCw, 
  ShieldCheck, 
  Video, 
  Loader2, 
  CheckCircle2, 
  AlertCircle,
  Settings,
  Tv
} from 'lucide-react';
import { api } from '../api';

interface MuseStudioViewProps {
  status: any;
  onRefresh: () => void;
}

export const MuseStudioView: React.FC<MuseStudioViewProps> = ({
  status,
  onRefresh
}) => {
  const [connecting, setConnecting] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [museUrl, setMuseUrl] = useState('https://muse.ai');
  const [savingUrl, setSavingUrl] = useState(false);

  const handleConnect = async () => {
    try {
      setConnecting(true);
      await api.connectMuse();
      await onRefresh();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setConnecting(false);
    }
  };

  const handleLogout = async () => {
    try {
      setLoggingOut(true);
      await api.logoutMuse(true);
      await onRefresh();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setLoggingOut(false);
    }
  };

  const handleSaveUrl = async () => {
    try {
      setSavingUrl(true);
      await api.updateSettings({ muse_url: museUrl });
      alert('Đã cập nhật đường dẫn Muse AI Studio!');
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSavingUrl(false);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Video className="w-5 h-5 text-emerald-400" />
          <span>Muse AI Automation Studio (Text/Image to Video AI)</span>
        </h2>
        <p className="text-xs text-slate-400">
          Tạo video TikTok Affiliate 9:16 chất lượng cao với công nghệ Muse AI. Tự động liên kết ảnh tham chiếu nhân vật và sản phẩm.
        </p>
      </div>

      {/* Connection Card */}
      <div className="p-6 rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#232a3b] pb-4">
          <div className="flex items-center gap-3">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center border ${
              status?.logged_in
                ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
                : 'bg-amber-500/15 border-amber-500/30 text-amber-400'
            }`}>
              {status?.logged_in ? <CheckCircle2 className="w-6 h-6" /> : <AlertCircle className="w-6 h-6" />}
            </div>
            <div>
              <div className="text-sm font-bold text-white flex items-center gap-2 flex-wrap">
                <span>Trạng thái kết nối Muse AI:</span>
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                  status?.logged_in ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
                }`}>
                  {status?.logged_in
                    ? `ĐÃ ĐĂNG NHẬP: ${status?.account_display || status?.account_email || 'Tài khoản Muse AI'}`
                    : status?.status === 'switching_account'
                    ? 'CHỜ ĐĂNG NHẬP CHROME...'
                    : 'CẦN ĐĂNG NHẬP MUSE AI'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {status?.message || 'Lưu phiên trong data/browser_profiles/muse'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white text-xs font-bold flex items-center gap-2 shadow-md shadow-emerald-500/20 transition-all disabled:opacity-50"
            >
              {connecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />}
              <span>{status?.logged_in ? 'Mở Cửa Sổ Muse AI' : '🔑 Đăng Nhập Muse AI'}</span>
            </button>

            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="px-3.5 py-2.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/35 border border-rose-500/40 text-rose-200 text-xs font-bold flex items-center gap-1.5 transition-colors"
              title="Đăng xuất tài khoản Muse AI và mở cửa sổ đăng nhập tài khoản khác"
            >
              {loggingOut ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LogOut className="w-3.5 h-3.5" />}
              <span>{loggingOut ? 'Đang mở form...' : '🔄 Đổi Tài Khoản Khác'}</span>
            </button>

            <button
              onClick={onRefresh}
              className="p-2.5 rounded-xl bg-[#12161f] hover:bg-[#232a3b] border border-[#232a3b] text-slate-300 transition-colors"
              title="Kiểm tra lại trạng thái"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Custom URL Setting */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <Settings className="w-3.5 h-3.5 text-slate-400" />
            <span>Đường dẫn Studio Muse AI:</span>
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={museUrl}
              onChange={(e) => setMuseUrl(e.target.value)}
              placeholder="https://muse.ai"
              className="flex-1 bg-[#12161f] border border-[#232a3b] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500 transition-colors"
            />
            <button
              onClick={handleSaveUrl}
              disabled={savingUrl}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 transition-colors disabled:opacity-50"
            >
              {savingUrl ? 'Đang lưu...' : 'Lưu URL'}
            </button>
          </div>
          <p className="text-[11px] text-slate-500">
            Mặc định: <code className="text-slate-400">https://muse.ai</code> hoặc nền tảng Muse Video AI của bạn.
          </p>
        </div>

        {/* Security & Features */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs pt-2">
          <div className="p-3.5 rounded-xl bg-[#12161f] border border-[#232a3b] space-y-1">
            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Chỉ Cần Đăng Nhập 1 Lần</span>
            </div>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Bạn chỉ cần đăng nhập tài khoản một lần trên cửa sổ Chrome, session được lưu an toàn trong máy tính.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-[#12161f] border border-[#232a3b] space-y-1">
            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-pink-400" />
              <span>Chuẩn 1080x1920 @ 60 FPS</span>
            </div>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Mọi video tải về từ Muse AI đều được tự động scale và chuẩn hóa 60 FPS bằng FFmpeg phần cứng.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-[#12161f] border border-[#232a3b] space-y-1">
            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
              <Tv className="w-4 h-4 text-cyan-400" />
              <span>Ghép Video Tự Động</span>
            </div>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Hệ thống tự động liên kết Cảnh 1 và Cảnh 2 để xuất file 20 giây hoàn thiện cho TikTok Shop.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};


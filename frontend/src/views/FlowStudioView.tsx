import React, { useState } from 'react';
import { 
  Sparkles, 
  ExternalLink, 
  LogOut, 
  RefreshCw, 
  ShieldCheck, 
  Film, 
  Loader2, 
  CheckCircle2, 
  AlertCircle,
  Settings
} from 'lucide-react';
import { api } from '../api';

interface FlowStudioViewProps {
  status: any;
  onRefresh: () => void;
}

export const FlowStudioView: React.FC<FlowStudioViewProps> = ({
  status,
  onRefresh
}) => {
  const [connecting, setConnecting] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [flowUrl, setFlowUrl] = useState('https://labs.google/flow');
  const [savingUrl, setSavingUrl] = useState(false);

  const handleConnect = async () => {
    try {
      setConnecting(true);
      await api.connectFlow();
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
      await api.logoutFlow();
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
      await api.updateSettings({ flow_url: flowUrl });
      alert('Đã cập nhật đường dẫn Google Flow!');
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
          <Film className="w-5 h-5 text-purple-400" />
          <span>Google Flow Automation Studio (Veo 3 Video AI)</span>
        </h2>
        <p className="text-xs text-slate-400">
          Kết nối Google Flow tạo video dọc 9:16 chất lượng điện ảnh bằng mô hình Veo 3, bảo đảm sự đồng bộ hình ảnh giữa Cảnh 1 và Cảnh 2.
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
                <span>Trạng thái kết nối Google Flow:</span>
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                  status?.logged_in ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
                }`}>
                  {status?.logged_in
                    ? `ĐÃ ĐĂNG NHẬP: ${status?.account_display || status?.account_email || 'Tài khoản Google'}`
                    : 'CẦN ĐĂNG NHẬP GOOGLE'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {status?.message || 'Lưu phiên trong data/browser_profiles/flow'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-600 hover:to-indigo-700 text-white text-xs font-bold flex items-center gap-2 shadow-md shadow-purple-500/20 transition-all disabled:opacity-50"
            >
              {connecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />}
              <span>{status?.logged_in ? 'Mở Cửa Sổ Google Flow' : '🔑 Đăng Nhập / Chọn Tài Khoản Google'}</span>
            </button>

            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="px-3.5 py-2.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/35 border border-rose-500/40 text-rose-200 text-xs font-bold flex items-center gap-1.5 transition-colors"
              title="Đăng xuất tài khoản hiện tại và mở form Chọn một tài khoản Google khác"
            >
              {loggingOut ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LogOut className="w-3.5 h-3.5" />}
              <span>{loggingOut ? 'Đang mở form...' : '🔄 Đổi Tài Khoản Khác'}</span>
            </button>

            <button
              onClick={onRefresh}
              className="p-2.5 rounded-xl bg-[#12161f] hover:bg-[#232a3b] border border-[#232a3b] text-slate-300 transition-colors"
              title="Kiểm tra lại"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Custom URL Setting (If Google changes URL) */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <Settings className="w-3.5 h-3.5 text-slate-400" />
            <span>Địa chỉ URL Google Flow / VideoFX:</span>
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={flowUrl}
              onChange={(e) => setFlowUrl(e.target.value)}
              className="flex-1 px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white text-xs font-mono focus:border-purple-500 focus:outline-none"
            />
            <button
              onClick={handleSaveUrl}
              disabled={savingUrl}
              className="px-4 py-2 rounded-xl bg-[#232a3b] hover:bg-[#2e374d] text-white text-xs font-semibold transition-colors"
            >
              {savingUrl ? 'Đang lưu...' : 'Lưu URL'}
            </button>
          </div>
        </div>

        {/* Info Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-[#12161f] border border-[#232a3b] space-y-1">
            <div className="font-semibold text-white">Đồng bộ nhân vật & sản phẩm</div>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Cảnh 1 và Cảnh 2 luôn sử dụng chung một ảnh nhân vật AI tham chiếu để bảo đảm khuôn mặt, trang phục, bối cảnh và màu sắc sản phẩm giữ nguyên 100%.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-[#12161f] border border-[#232a3b] space-y-1">
            <div className="font-semibold text-white">Chế độ tiếp tục thông minh</div>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Nếu Video 1 đã tạo thành công nhưng Video 2 gặp gián đoạn, tool sẽ giữ nguyên Video 1 và chỉ tạo lại Video 2, tránh lãng phí thời gian.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};


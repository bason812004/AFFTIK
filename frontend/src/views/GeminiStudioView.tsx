import React, { useState } from 'react';
import { 
  Bot, 
  ExternalLink, 
  LogOut, 
  RefreshCw, 
  ShieldCheck, 
  Sparkles, 
  Loader2, 
  Send,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { api } from '../api';

interface GeminiStudioViewProps {
  status: any;
  onRefresh: () => void;
}

export const GeminiStudioView: React.FC<GeminiStudioViewProps> = ({
  status,
  onRefresh
}) => {
  const [connecting, setConnecting] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [testPrompt, setTestPrompt] = useState('Hãy chào người dùng TikTok Việt Nam bằng 1 câu hook ngắn 10 từ');
  const [testResult, setTestResult] = useState('');
  const [testing, setTesting] = useState(false);

  const handleConnect = async () => {
    try {
      setConnecting(true);
      await api.connectGemini();
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
      await api.logoutGemini(true);
      await onRefresh();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Bot className="w-5 h-5 text-cyan-400" />
          <span>Gemini Automation Studio (Playwright Persistent Context)</span>
        </h2>
        <p className="text-xs text-slate-400">
          Kết nối tài khoản Google của bạn trực tiếp trên trình duyệt Chromium có giao diện. Phiên đăng nhập được lưu cục bộ an toàn trong thư mục máy tính.
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
              <div className="text-sm font-bold text-white flex items-center gap-2">
                <span>Trạng thái kết nối Gemini:</span>
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                  status?.logged_in ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
                }`}>
                  {status?.logged_in ? 'ĐÃ ĐĂNG NHẬP' : 'CẦN ĐĂNG NHẬP GOOGLE'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {status?.message || 'Trình duyệt sử dụng persistent profile trong data/browser_profiles/gemini'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white text-xs font-bold flex items-center gap-2 shadow-md shadow-cyan-500/20 transition-all disabled:opacity-50"
            >
              {connecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />}
              <span>{status?.logged_in ? 'Mở lại cửa sổ Gemini' : 'Kết nối / Đăng nhập Gemini'}</span>
            </button>

            <button
              onClick={onRefresh}
              className="p-2.5 rounded-xl bg-[#12161f] hover:bg-[#232a3b] border border-[#232a3b] text-slate-300 transition-colors"
              title="Kiểm tra lại trạng thái"
            >
              <RefreshCw className="w-4 h-4" />
            </button>

            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="px-3.5 py-2.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/35 border border-rose-500/40 text-rose-200 text-xs font-bold flex items-center gap-1.5 transition-colors"
              title="Đăng xuất tài khoản hiện tại và mở cửa sổ Chrome để đăng nhập tài khoản khác"
            >
              {loggingOut ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LogOut className="w-3.5 h-3.5" />}
              <span>{loggingOut ? 'Đang mở Chrome...' : '🔄 Đổi Tài Khoản Khác'}</span>
            </button>
          </div>
        </div>

        {/* Security & Isolation Features */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-3.5 rounded-xl bg-[#12161f] border border-[#232a3b] space-y-1">
            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Bảo mật tuyệt đối</span>
            </div>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Không lưu mật khẩu dạng text, không gửi cookie lên máy chủ ngoài, phiên lưu trong profile Chrome local.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-[#12161f] border border-[#232a3b] space-y-1">
            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-pink-400" />
              <span>Trình duyệt có giao diện</span>
            </div>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Trình duyệt mở trên màn hình cho phép người dùng quan sát trực tiếp và xử lý CAPTCHA/2FA nếu xuất hiện.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-[#12161f] border border-[#232a3b] space-y-1">
            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
              <RefreshCw className="w-4 h-4 text-cyan-400" />
              <span>Tự động nhận diện</span>
            </div>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Tự động tải ảnh sản phẩm lên, điền prompt, đếm từ 42 đơn vị tiếng và trích xuất ảnh nhân vật AI về máy.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};


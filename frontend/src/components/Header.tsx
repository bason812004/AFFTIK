import React, { useState } from 'react';
import { AutomationMode } from '../types';
import { 
  Sparkles, 
  Bot, 
  Film, 
  CheckCircle2, 
  Loader2, 
  Sliders,
  Tv,
  RefreshCw,
  UserCheck
} from 'lucide-react';
import { api } from '../api';

interface ServiceAccountStatus {
  logged_in?: boolean;
  status?: string;
  message?: string;
  account_email?: string;
  account_name?: string;
  account_avatar?: string;
  account_display?: string;
}

interface HeaderProps {
  mode: AutomationMode;
  onModeChange: (mode: AutomationMode) => void;
  geminiStatus: ServiceAccountStatus;
  flowStatus: ServiceAccountStatus;
  ffmpegStatus: { installed?: boolean; version?: string };
  onRefreshStatus: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  mode,
  onModeChange,
  geminiStatus,
  flowStatus,
  ffmpegStatus,
  onRefreshStatus
}) => {
  const [connectingGemini, setConnectingGemini] = useState(false);
  const [switchingGemini, setSwitchingGemini] = useState(false);
  const [connectingFlow, setConnectingFlow] = useState(false);
  const [switchingFlow, setSwitchingFlow] = useState(false);

  const handleConnectGemini = async () => {
    try {
      setConnectingGemini(true);
      await api.connectGemini();
      await onRefreshStatus();
    } catch (e) {
      console.error(e);
    } finally {
      setConnectingGemini(false);
    }
  };

  const handleSwitchGeminiAccount = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setSwitchingGemini(true);
      await api.logoutGemini();
      await onRefreshStatus();
    } catch (err) {
      console.error(err);
    } finally {
      setSwitchingGemini(false);
    }
  };

  const handleConnectFlow = async () => {
    try {
      setConnectingFlow(true);
      await api.connectFlow();
      await onRefreshStatus();
    } catch (e) {
      console.error(e);
    } finally {
      setConnectingFlow(false);
    }
  };

  const handleSwitchFlowAccount = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setSwitchingFlow(true);
      await api.logoutFlow();
      await onRefreshStatus();
    } catch (err) {
      console.error(err);
    } finally {
      setSwitchingFlow(false);
    }
  };

  const geminiAccountLabel = geminiStatus?.account_display || geminiStatus?.account_email || geminiStatus?.account_name || '';
  const flowAccountLabel = flowStatus?.account_display || flowStatus?.account_email || flowStatus?.account_name || '';

  return (
    <header className="min-h-16 py-2 border-b border-[#232a3b] bg-[#12161f]/95 backdrop-blur-md px-5 flex items-center justify-between gap-3 flex-wrap sticky top-0 z-40">
      {/* Brand Logo */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#fe2c55] via-[#8b5cf6] to-[#25f4ee] flex items-center justify-center p-0.5 shadow-lg shadow-pink-500/10 shrink-0">
          <div className="w-full h-full bg-[#12161f] rounded-[10px] flex items-center justify-center">
            <Tv className="w-5 h-5 text-[#fe2c55]" />
          </div>
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
              <span>TIKTOK AFFILIATE</span>
              <span className="gradient-text-tiktok font-extrabold">AI STUDIO</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-pink-500/20 text-pink-400 font-black border border-pink-500/30">PRO</span>
            </h1>
          </div>
          <p className="text-[11px] text-slate-400">Tự động sản xuất video TikTok Affiliate chuẩn 42 từ &bull; 20s 60fps</p>
        </div>
      </div>

      {/* Right Actions: Mode Selector & Account Status Indicators */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Automation Mode Switcher */}
        <div className="flex items-center bg-[#181d29] p-1 rounded-xl border border-[#232a3b] text-xs">
          <button
            onClick={() => onModeChange('auto')}
            className={`px-2.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 ${
              mode === 'auto'
                ? 'bg-gradient-to-r from-pink-500 to-rose-600 text-white shadow-md shadow-pink-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>TỰ ĐỘNG</span>
          </button>
          <button
            onClick={() => onModeChange('semi')}
            className={`px-2.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 ${
              mode === 'semi'
                ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-md shadow-indigo-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>BÁN TỰ ĐỘNG</span>
          </button>
          <button
            onClick={() => onModeChange('manual')}
            className={`px-2.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 ${
              mode === 'manual'
                ? 'bg-slate-700 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <span>THỦ CÔNG</span>
          </button>
        </div>

        <div className="h-5 w-px bg-[#232a3b] hidden md:block" />

        {/* Live Account Badges with Account Name + 1-Click Switch Account */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Gemini Account Badge */}
          <div
            className={`flex items-center rounded-xl border text-xs transition-all overflow-hidden ${
              geminiStatus?.logged_in
                ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
            }`}
          >
            <button
              onClick={handleConnectGemini}
              disabled={connectingGemini}
              title={geminiStatus?.message || 'Nhấn để mở / kiểm tra tài khoản Gemini'}
              className="flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-white/5 transition-colors"
            >
              {connectingGemini ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
              ) : (
                <Bot className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              )}
              <span className="font-bold text-slate-300">Gemini:</span>
              {geminiStatus?.status === 'switching_account' ? (
                <span className="font-bold text-amber-300 animate-pulse flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin text-amber-400" />
                  <span>Chờ đăng nhập Chrome...</span>
                </span>
              ) : geminiStatus?.logged_in ? (
                <span className="font-extrabold text-cyan-300 max-w-[190px] truncate">
                  {geminiAccountLabel || 'Đã kết nối'}
                </span>
              ) : (
                <span className="font-bold text-amber-300">Đăng nhập (Chọn TK)</span>
              )}
            </button>
            <button
              onClick={handleSwitchGeminiAccount}
              disabled={switchingGemini}
              title="Mở form Google Account Chooser để chọn hoặc đổi tài khoản Gemini"
              className="px-2 py-1.5 border-l border-cyan-500/25 bg-cyan-500/15 hover:bg-cyan-500/30 text-[11px] font-bold text-cyan-200 flex items-center gap-1 transition-colors"
            >
              <RefreshCw className={`w-3 h-3 ${switchingGemini ? 'animate-spin' : ''}`} />
              <span>{geminiStatus?.logged_in ? 'Đổi TK' : 'Chọn TK'}</span>
            </button>
          </div>

          {/* Google Flow Account Badge */}
          <div
            className={`flex items-center rounded-xl border text-xs transition-all overflow-hidden ${
              flowStatus?.logged_in
                ? 'bg-purple-500/10 border-purple-500/35 text-purple-200'
                : 'bg-amber-500/15 border-amber-500/40 text-amber-200'
            }`}
          >
            <button
              onClick={handleConnectFlow}
              disabled={connectingFlow}
              title={flowStatus?.message || 'Nhấn để mở form chọn tài khoản Google Flow'}
              className="flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-white/5 transition-colors"
            >
              {connectingFlow ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
              ) : (
                <Film className="w-3.5 h-3.5 text-purple-400 shrink-0" />
              )}
              <span className="font-bold text-slate-300">TK Flow:</span>
              {flowStatus?.status === 'switching_account' ? (
                <span className="font-bold text-amber-300 animate-pulse flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin text-amber-400" />
                  <span>Chờ đăng nhập Chrome...</span>
                </span>
              ) : flowStatus?.logged_in ? (
                <span className="font-extrabold text-emerald-300 flex items-center gap-1 max-w-[230px] truncate">
                  <UserCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span className="truncate">{flowAccountLabel || 'Đã kết nối'}</span>
                </span>
              ) : (
                <span className="font-extrabold text-amber-300 animate-pulse">
                  Đăng nhập (Chọn TK Google)
                </span>
              )}
            </button>
            <button
              onClick={handleSwitchFlowAccount}
              disabled={switchingFlow}
              title="Mở form Google Account Chooser (Chọn một tài khoản) để chọn hoặc đổi tài khoản Google Flow"
              className="px-2.5 py-1.5 border-l border-purple-500/30 bg-rose-500/25 hover:bg-rose-500/40 text-[11px] font-extrabold text-rose-200 flex items-center gap-1 transition-colors"
            >
              <RefreshCw className={`w-3 h-3 ${switchingFlow ? 'animate-spin' : ''}`} />
              <span>{flowStatus?.logged_in ? 'Đổi TK Flow' : 'Chọn TK Flow'}</span>
            </button>
          </div>

          {/* FFmpeg */}
          <div
            title={ffmpegStatus?.version || 'FFmpeg Video Engine'}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs border ${
              ffmpegStatus?.installed
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span className="font-semibold">FFmpeg</span>
          </div>
        </div>
      </div>
    </header>
  );
};

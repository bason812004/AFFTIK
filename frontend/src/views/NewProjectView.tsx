import React, { useState, useEffect, useRef } from 'react';
import { 
  Upload, 
  Sparkles, 
  X, 
  ArrowLeft, 
  CheckCircle2, 
  ChevronDown,
  Layers,
  FileImage,
  ClipboardPaste,
  Trash2,
  Loader2,
  Plus
} from 'lucide-react';
import { AutomationMode } from '../types';
import { api } from '../api';

interface NewProjectViewProps {
  onBack: () => void;
  onProjectCreated: (projectId: string) => void;
  defaultMode: AutomationMode;
}

interface BatchProductItem {
  id: string;
  file: File;
  previewUrl: string;
  name: string;
}

export const NewProjectView: React.FC<NewProjectViewProps> = ({
  onBack,
  onProjectCreated,
}) => {
  const [items, setItems] = useState<BatchProductItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [pasting, setPasting] = useState(false);
  const [pastedSuccess, setPastedSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const lastPasteTimeRef = useRef<number>(0);

  const [extraOffer, setExtraOffer] = useState('Ưu đãi trợ giá đặc biệt và miễn phí giao hàng hôm nay');
  const [extraPrice, setExtraPrice] = useState('Ưu đãi hôm nay');

  const deriveCleanProductName = (filename: string) => {
    const stem = filename.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ").trim();
    const isGeneric = [
      'image', 'media', 'photo', 'screenshot', 'img', 'pic',
      'san pham', 'clipboard', 'clip', 'zalo', 'whatsapp', 'download', 'untitled'
    ].some(p => stem.toLowerCase().startsWith(p));
    if (stem.length > 4 && !isGeneric && !/^[0-9a-f\s]+$/i.test(stem)) {
      return stem.charAt(0).toUpperCase() + stem.slice(1);
    }
    return '';
  };

  const addFilesToQueue = (newFiles: File[], fromPaste: boolean = false) => {
    const validFiles = newFiles.filter(f => f && (f.type.startsWith('image/') || /\.(jpg|jpeg|png|webp|bmp)$/i.test(f.name)));
    if (validFiles.length === 0) return;

    const added: BatchProductItem[] = validFiles.map((file, idx) => ({
      id: `${Date.now()}_${idx}_${Math.random().toString(36).slice(2, 7)}`,
      file,
      previewUrl: URL.createObjectURL(file),
      name: deriveCleanProductName(file.name)
    }));

    setItems(prev => [...prev, ...added]);
    setError(null);

    if (fromPaste) {
      setPastedSuccess(true);
      setTimeout(() => setPastedSuccess(false), 3000);
    }
  };

  const removeItem = (id: string) => {
    setItems(prev => prev.filter(item => item.id !== id));
  };

  const updateItemName = (id: string, newName: string) => {
    setItems(prev => prev.map(item => item.id === id ? { ...item, name: newName } : item));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFilesToQueue(Array.from(e.target.files), false);
      e.target.value = '';
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFilesToQueue(Array.from(e.dataTransfer.files), false);
    }
  };

  const handlePasteFromClipboardButton = async () => {
    if (Date.now() - lastPasteTimeRef.current < 700) return;
    lastPasteTimeRef.current = Date.now();
    try {
      setPasting(true);
      setError(null);

      if (navigator.clipboard && 'read' in navigator.clipboard) {
        try {
          const clipItems = await navigator.clipboard.read();
          for (const item of clipItems) {
            const imgType = item.types.find(t => t.startsWith('image/'));
            if (imgType) {
              const blob = await item.getType(imgType);
              const ext = imgType.split('/')[1] || 'png';
              const file = new File([blob], `san_pham_paste.${ext}`, { type: imgType });
              addFilesToQueue([file], true);
              return;
            }
          }
        } catch {
          // Fallback to Windows OS Clipboard via backend
        }
      }

      const resp = await fetch(`/api/projects/clipboard-image-blob?t=${Date.now()}`);
      if (!resp.ok) {
        let errDetail = 'Không tìm thấy hình ảnh trong Clipboard! Hãy Copy ảnh (Ctrl+C hoặc chụp màn hình Win+Shift+S) rồi bấm Dán Ảnh.';
        try {
          const errJson = await resp.json();
          if (errJson?.detail) errDetail = errJson.detail;
        } catch {}
        throw new Error(errDetail);
      }
      const blob = await resp.blob();
      const file = new File([blob], 'san_pham_clipboard.png', { type: blob.type || 'image/png' });
      addFilesToQueue([file], true);
    } catch (err: any) {
      setError(err?.message || 'Không thể dán ảnh từ Clipboard.');
    } finally {
      setPasting(false);
    }
  };

  const handlePasteEvent = async (e: ClipboardEvent | React.ClipboardEvent) => {
    if (Date.now() - lastPasteTimeRef.current < 700) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    const target = e.target as HTMLElement;
    const isInput = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA');

    const cd = (e as ClipboardEvent).clipboardData || (e as React.ClipboardEvent).clipboardData;
    if (cd) {
      if (cd.files && cd.files.length > 0) {
        const imgFiles = Array.from(cd.files).filter(f => f.type.startsWith('image/'));
        if (imgFiles.length > 0) {
          lastPasteTimeRef.current = Date.now();
          e.preventDefault();
          e.stopPropagation();
          addFilesToQueue([imgFiles[0]], true);
          return;
        }
      }
      if (cd.items && cd.items.length > 0) {
        const extracted: File[] = [];
        for (let i = 0; i < cd.items.length; i++) {
          const item = cd.items[i];
          if (item.type.startsWith('image/')) {
            const f = item.getAsFile();
            if (f) {
              extracted.push(f);
              break;
            }
          }
        }
        if (extracted.length > 0) {
          lastPasteTimeRef.current = Date.now();
          e.preventDefault();
          e.stopPropagation();
          addFilesToQueue([extracted[0]], true);
          return;
        }
      }
    }

    if (isInput && cd && cd.getData('text/plain')) {
      return;
    }

    e.preventDefault();
    e.stopPropagation();
    await handlePasteFromClipboardButton();
  };

  useEffect(() => {
    const onWindowPaste = (e: ClipboardEvent) => {
      handlePasteEvent(e);
    };
    window.addEventListener('paste', onWindowPaste);
    return () => window.removeEventListener('paste', onWindowPaste);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (items.length === 0) {
      setError('Vui lòng tải lên, kéo thả hoặc dán ít nhất 1 ảnh sản phẩm');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      if (items.length === 1) {
        const single = items[0];
        const res = await api.quickCreateProject(
          single.file,
          single.name.trim() || undefined,
          true
        );
        if (res && res.project_id) {
          onProjectCreated(res.project_id);
          return;
        }
      } else {
        const files = items.map(i => i.file);
        const names = items.map(i => i.name.trim());
        const batchRes = await api.batchCreateProjects(files, names, true);
        if (batchRes && batchRes.first_project_id) {
          onProjectCreated(batchRes.first_project_id);
          return;
        }
      }

      throw new Error('Không thể khởi tạo dự án');
    } catch (err: any) {
      setError(err?.message || 'Có lỗi xảy ra khi tạo video tự động');
      setSubmitting(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2.5 rounded-xl bg-[#181d29] border border-[#232a3b] hover:bg-[#232a3b] text-slate-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2 flex-wrap">
              <span>Tạo Video TikTok Affiliate Tự Động (Đơn Lẻ & Hàng Loạt)</span>
              <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-pink-500/20 text-pink-400 font-black border border-pink-500/30">
                1 ẢNH SẢN PHẨM = 1 VIDEO 20 GIÂY
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Chọn hoặc dán 1 hay nhiều ảnh sản phẩm cùng lúc &bull; Mỗi ảnh sản phẩm sẽ tự động tạo 1 nhân vật AI + 2 cảnh video ghép thành 1 video 20s hoàn chỉnh
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-semibold flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)}><X className="w-4 h-4" /></button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Main Upload Box */}
        <div className="p-6 rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-5">
          <div className="flex items-center justify-between border-b border-[#232a3b] pb-3 flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <FileImage className="w-4 h-4 text-pink-400" />
              <span className="text-sm font-bold text-white">
                Danh Sách Ảnh Sản Phẩm ({items.length} sản phẩm = {items.length} video 20s)
              </span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-3 py-1.5 rounded-xl bg-pink-500/20 hover:bg-pink-500/30 text-pink-300 border border-pink-500/40 text-xs font-bold flex items-center gap-1.5 transition-all"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Chọn Nhiều Ảnh Sản Phẩm</span>
              </button>
              <button
                type="button"
                onClick={handlePasteFromClipboardButton}
                disabled={pasting}
                className="px-3 py-1.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-bold flex items-center gap-1.5 transition-all"
              >
                {pasting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ClipboardPaste className="w-3.5 h-3.5" />}
                <span>{pastedSuccess ? '✓ Đã Dán Thêm Ảnh!' : 'Dán Ảnh (Ctrl+V)'}</span>
              </button>
              {items.length > 0 && (
                <button
                  type="button"
                  onClick={() => setItems([])}
                  className="px-2.5 py-1.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30 text-xs font-bold flex items-center gap-1 transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Xóa hết</span>
                </button>
              )}
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={handleFileChange}
            className="hidden"
          />

          {/* Drag, Drop & Paste Zone */}
          <div
            tabIndex={0}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className={`relative border-2 border-dashed rounded-2xl min-h-[240px] flex flex-col items-center justify-center p-5 transition-all outline-none ${
              items.length > 0
                ? 'border-pink-500/50 bg-[#12161f]/80'
                : 'border-[#2d374d] hover:border-pink-500/60 focus:border-pink-400 bg-[#12161f]/40 hover:bg-[#12161f]/70 text-center'
            }`}
          >
            {items.length > 0 ? (
              <div className="w-full space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {items.map((item, idx) => (
                    <div
                      key={item.id}
                      className="p-3.5 rounded-xl bg-[#181d29] border border-[#2b354b] flex gap-3.5 items-start relative group"
                    >
                      <div className="w-20 h-24 rounded-lg overflow-hidden bg-black/40 border border-pink-500/30 shrink-0 flex items-center justify-center">
                        <img
                          src={item.previewUrl}
                          alt={`Product ${idx + 1}`}
                          className="w-full h-full object-contain"
                        />
                      </div>

                      <div className="flex-1 min-w-0 space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="px-2 py-0.5 rounded-md bg-pink-500/20 text-pink-300 border border-pink-500/30 text-[10px] font-extrabold">
                            Sản phẩm #{idx + 1} &bull; 1 Video 20s
                          </span>
                          <button
                            type="button"
                            onClick={() => removeItem(item.id)}
                            className="p-1 rounded-lg bg-rose-500/20 hover:bg-rose-500 text-rose-300 hover:text-white transition-colors"
                            title="Xóa sản phẩm này"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>

                        <div>
                          <label className="text-[11px] font-semibold text-slate-300 block mb-1">
                            Tên sản phẩm (Nhập tên nếu ảnh không rõ chữ):
                          </label>
                          <input
                            type="text"
                            placeholder="Để trống AI tự đọc bao bì, hoặc nhập tên chuẩn..."
                            value={item.name}
                            onChange={(e) => updateItemName(item.id, e.target.value)}
                            className="w-full px-3 py-1.5 rounded-lg bg-[#12161f] border border-[#2d374d] text-white text-xs focus:border-pink-500 focus:outline-none"
                          />
                        </div>
                        <div className="text-[10px] text-slate-500 truncate">
                          Tệp: {item.file.name}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-center gap-3 pt-2 border-t border-[#232a3b] flex-wrap">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="px-4 py-2 rounded-xl bg-[#232a3b] hover:bg-[#2d364b] text-slate-200 text-xs font-bold flex items-center gap-1.5 transition-colors"
                  >
                    <Plus className="w-4 h-4 text-pink-400" />
                    <span>Thêm Nhiều Ảnh Sản Phẩm Khác</span>
                  </button>

                  <button
                    type="button"
                    onClick={handlePasteFromClipboardButton}
                    disabled={pasting}
                    className="px-4 py-2 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-bold flex items-center gap-1.5 transition-colors"
                  >
                    <ClipboardPaste className="w-4 h-4" />
                    <span>Dán Thêm Ảnh Từ Clipboard (Ctrl+V)</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4 flex flex-col items-center">
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="w-16 h-16 rounded-2xl bg-gradient-to-br from-pink-500/20 to-purple-500/20 border border-pink-500/30 flex items-center justify-center shadow-lg shadow-pink-500/10 cursor-pointer hover:scale-105 transition-transform"
                >
                  <Upload className="w-8 h-8 text-pink-400 animate-bounce" />
                </div>

                <div>
                  <div className="text-sm font-bold text-white">
                    Kéo thả 1 hoặc nhiều ảnh sản phẩm vào đây, bấm <span className="text-amber-300">Ctrl + V</span> để dán ảnh, hoặc chọn tệp:
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Hỗ trợ chọn hàng loạt nhiều ảnh cùng lúc &bull; Mỗi ảnh sản phẩm sẽ xuất ra 1 video TikTok 20 giây chuẩn 9:16
                  </p>
                </div>

                <div className="flex items-center justify-center gap-3 flex-wrap pt-1">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 text-white text-xs font-extrabold shadow-lg shadow-pink-500/25 flex items-center gap-2 transition-all"
                  >
                    <Layers className="w-4 h-4" />
                    <span>📂 Chọn 1 Hoặc Nhiều Ảnh Sản Phẩm</span>
                  </button>

                  <button
                    type="button"
                    onClick={handlePasteFromClipboardButton}
                    disabled={pasting}
                    className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white text-xs font-extrabold shadow-lg shadow-amber-500/25 flex items-center gap-2 transition-all"
                  >
                    {pasting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ClipboardPaste className="w-4 h-4" />}
                    <span>📋 Dán Ảnh Sản Phẩm (Ctrl+V)</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-[11px] text-amber-200 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              <b>Lưu ý thông minh:</b> Nếu ảnh sản phẩm có bao bì/nhãn mác rõ chữ, AI sẽ tự đọc chuẩn tên sản phẩm. Nếu ảnh chụp sản phẩm trần không có chữ và bạn để trống tên, hệ thống sẽ nhắc bạn nhập tên sản phẩm chứ tuyệt đối không tự đặt tên lan man!
            </span>
          </div>
        </div>

        {/* Collapsible Advanced Info */}
        <div className="rounded-2xl bg-[#181d29] border border-[#232a3b] overflow-hidden">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full px-6 py-3.5 flex items-center justify-between text-xs font-semibold text-slate-400 hover:text-slate-200 transition-colors"
          >
            <span>⚙️ Tùy chỉnh giá bán & ưu đãi thêm (Không bắt buộc)</span>
            <ChevronDown className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
          </button>

          {showAdvanced && (
            <div className="px-6 pb-6 pt-2 border-t border-[#232a3b] grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="text-slate-300 font-medium block mb-1">Giá bán hiển thị trên video</label>
                <input
                  type="text"
                  value={extraPrice}
                  onChange={(e) => setExtraPrice(e.target.value)}
                  placeholder="199.000đ"
                  className="w-full px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white focus:border-pink-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-slate-300 font-medium block mb-1">Ưu đãi / Quà tặng hấp dẫn</label>
                <input
                  type="text"
                  value={extraOffer}
                  onChange={(e) => setExtraOffer(e.target.value)}
                  placeholder="Mua 1 tặng 1 miễn phí ship hôm nay"
                  className="w-full px-3.5 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white focus:border-pink-500 focus:outline-none"
                />
              </div>
            </div>
          )}
        </div>

        {/* Big 1-Click Action Button */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={submitting || items.length === 0}
            className="w-full py-4 rounded-2xl bg-gradient-to-r from-[#fe2c55] via-[#ff0050] to-[#8b5cf6] hover:opacity-95 text-white text-sm font-black shadow-xl shadow-pink-500/25 flex items-center justify-center gap-2.5 transition-all transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
          >
            <Sparkles className={`w-5 h-5 ${submitting ? 'animate-spin' : 'animate-pulse'}`} />
            <span>
              {submitting
                ? `Đang Khởi Tạo ${items.length} Dự Án Video 20s...`
                : items.length > 1
                  ? `🚀 TẠO HÀNG LOẠT ${items.length} SẢN PHẨM (${items.length} VIDEO 20 GIÂY FULL AUTO)`
                  : '🚀 TỰ ĐỘNG TẠO VIDEO TIKTOK 20 GIÂY (1-CLICK FULL AUTO)'}
            </span>
          </button>
          <p className="text-center text-[11px] text-slate-500 mt-2">
            Mỗi ảnh sản phẩm &rarr; 1 Ảnh Nhân Vật AI 9:16 &rarr; Prompt chuẩn sản phẩm (42 từ/cảnh) &rarr; Cảnh 1 (10s) + Cảnh 2 (10s) &rarr; Ghép thành 1 Video 20s 1080x1920 60fps.
          </p>
        </div>
      </form>
    </div>
  );
};

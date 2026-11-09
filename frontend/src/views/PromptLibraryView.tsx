import React, { useState, useEffect } from 'react';
import { 
  BookOpen, 
  Plus, 
  Copy, 
  RotateCcw, 
  Check, 
  Trash2, 
  Edit3, 
  Save, 
  Sparkles,
  Tag,
  Layers
} from 'lucide-react';
import { PromptTemplate } from '../types';
import { api } from '../api';

export const PromptLibraryView: React.FC = () => {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [editingPrompt, setEditingPrompt] = useState<PromptTemplate | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const categories = [
    { id: 'all', label: 'Tất cả mẫu' },
    { id: 'character_gen', label: '1. Tạo nhân vật AI' },
    { id: 'script_gen', label: '2. Kịch bản 42 từ (A/B/C)' },
    { id: 'veo3_scene1', label: '3. Prompt Veo 3 Cảnh 1' },
    { id: 'veo3_scene2', label: '4. Prompt Veo 3 Cảnh 2' },
    { id: 'dialogue_fix', label: '5. Chỉnh sửa lời thoại 42 từ' },
    { id: 'hook_gen', label: '6. Tạo hook quảng cáo' },
    { id: 'variant_gen', label: '7. Tạo biến thể nội dung' },
  ];

  const loadPrompts = async () => {
    try {
      setLoading(true);
      const data = await api.listPrompts(activeCategory === 'all' ? undefined : activeCategory);
      setPrompts(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPrompts();
  }, [activeCategory]);

  const handleCopy = (id: string, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleDuplicate = async (id: string) => {
    try {
      await api.duplicatePrompt(id);
      await loadPrompts();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Bạn có chắc chắn muốn xóa mẫu prompt này?')) {
      try {
        await api.deletePrompt(id);
        await loadPrompts();
      } catch (err: any) {
        alert(err.message);
      }
    }
  };

  const handleResetDefaults = async () => {
    if (confirm('Khôi phục các mẫu prompt gốc mặc định của hệ thống?')) {
      try {
        await api.resetDefaultPrompts();
        await loadPrompts();
        alert('Đã khôi phục các mẫu prompt gốc thành công!');
      } catch (err: any) {
        alert(err.message);
      }
    }
  };

  const handleSaveEdit = async () => {
    if (!editingPrompt) return;
    try {
      await api.updatePrompt(editingPrompt.id, {
        title: editingPrompt.title,
        content: editingPrompt.content
      });
      setEditingPrompt(null);
      await loadPrompts();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-pink-400" />
            <span>Kho Prompt & Mẫu Kịch Bản Chuẩn TikTok</span>
          </h2>
          <p className="text-xs text-slate-400">
            Quản lý các mẫu prompt AI cho Gemini và Veo 3, hỗ trợ chèn biến tự động như {'{{product_name}}'}, {'{{benefits}}'}, {'{{price}}'}.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleResetDefaults}
            className="px-3.5 py-2 rounded-xl bg-[#181d29] hover:bg-[#232a3b] text-slate-300 text-xs font-semibold border border-[#232a3b] flex items-center gap-1.5 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5 text-amber-400" />
            <span>Khôi phục mẫu gốc</span>
          </button>
        </div>
      </div>

      {/* Category Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setActiveCategory(cat.id)}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-all border ${
              activeCategory === cat.id
                ? 'bg-gradient-to-r from-pink-500/20 to-purple-500/20 text-pink-400 border-pink-500/40 shadow-sm'
                : 'bg-[#181d29] text-slate-400 border-[#232a3b] hover:text-white'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Prompts Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {prompts.map((p) => {
          const isCopied = copiedId === p.id;
          const isEditing = editingPrompt?.id === p.id;

          return (
            <div
              key={p.id}
              className="p-5 rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-3 flex flex-col justify-between shadow-lg"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2 border-b border-[#232a3b] pb-2.5">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#12161f] text-pink-400 border border-pink-500/20 font-semibold">
                        {p.category}
                      </span>
                      {p.is_system && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 font-semibold">
                          Hệ thống
                        </span>
                      )}
                    </div>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editingPrompt.title}
                        onChange={(e) => setEditingPrompt({ ...editingPrompt, title: e.target.value })}
                        className="w-full px-2.5 py-1 rounded bg-[#12161f] border border-[#232a3b] text-white text-xs font-bold"
                      />
                    ) : (
                      <h4 className="text-sm font-bold text-white">{p.title}</h4>
                    )}
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleCopy(p.id, p.content)}
                      title="Sao chép nội dung"
                      className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#232a3b] transition-colors"
                    >
                      {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                    {!isEditing ? (
                      <button
                        onClick={() => setEditingPrompt(p)}
                        title="Chỉnh sửa mẫu"
                        className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#232a3b] transition-colors"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                    ) : (
                      <button
                        onClick={handleSaveEdit}
                        title="Lưu"
                        className="p-1.5 rounded-lg text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                      >
                        <Save className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <button
                      onClick={() => handleDuplicate(p.id)}
                      title="Nhân bản mẫu"
                      className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#232a3b] transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                    {!p.is_system && (
                      <button
                        onClick={() => handleDelete(p.id)}
                        title="Xóa mẫu"
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {isEditing ? (
                  <textarea
                    rows={8}
                    value={editingPrompt.content}
                    onChange={(e) => setEditingPrompt({ ...editingPrompt, content: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-slate-200 text-xs font-mono leading-relaxed focus:border-pink-500 focus:outline-none"
                  />
                ) : (
                  <pre className="p-3.5 rounded-xl bg-[#12161f] text-slate-300 text-[11px] font-mono whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto border border-[#232a3b]">
                    {p.content}
                  </pre>
                )}
              </div>

              {p.variables && p.variables.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap pt-2 border-t border-[#232a3b]/60">
                  <span className="text-[10px] text-slate-500 font-medium">Biến hỗ trợ:</span>
                  {p.variables.map((v) => (
                    <span key={v} className="text-[10px] px-1.5 py-0.5 rounded bg-[#12161f] text-cyan-400 border border-cyan-500/20 font-mono">
                      {`{{${v}}}`}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};


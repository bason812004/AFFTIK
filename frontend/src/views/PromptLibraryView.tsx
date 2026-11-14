import React, { useState, useEffect, useMemo, useRef } from 'react';
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
  Layers,
  Search,
  X,
  Eye,
  EyeOff,
  Clock,
  AlignLeft,
  Factory,
  Store,
  Video,
  FileText,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Wand2,
  ExternalLink
} from 'lucide-react';
import { PromptTemplate } from '../types';
import { api } from '../api';

const SAMPLE_DEMO_PRODUCT = {
  product_name: "Tấm Bạt Che Nắng Mưa Ngoài Trời Cắm Trại Dã Ngoại (Viền May Gia Cố Chắc Chắn)",
  category: "Đồ Dã Ngoại & Cắm Trại",
  description: "Bạt dày dặn chống thấm nước tuyệt đối, bọc đệm 4 góc và viền may 6 đường chỉ siêu bền",
  benefits: "chống thấm nước tuyệt đối, che nắng mưa bền bỉ khi cắm trại, dã ngoại hoặc che chắn sân vườn, kho hàng ngoài trời",
  highlights: "bạt dày dặn phủ chống tia UV, viền may 6 đường chỉ gia cố siêu chắc, 4 góc bọc đệm bảo vệ kèm khoen khuy inox bền bỉ",
  price: "Ưu đãi giá xuất xưởng",
  offer: "Tặng kèm ưu đãi trợ giá và miễn phí giao hàng hôm nay",
  target_customer: "Người yêu thích cắm trại dã ngoại, hộ gia đình cần bạt che nắng mưa sân vườn",
  dialogue_1: "Muốn mua bạt che nắng mưa thì mua ngay tại xưởng sản xuất cho rẻ anh chị ơi! Nay bên em mới mở shop trên TikTok nên để cho cả nhà giá sỉ xuất xưởng tận gốc cực hời. Cả nhà bấm vào giỏ hàng góc trái bên dưới chốt đơn liền tay nhé!",
  dialogue_2: "Mỗi một tài khoản các bác săn được tấm bạt che nắng này giá rẻ lắm ạ! Không phải giá cao tiền trăm ngoài thị trường đâu, hôm nay xả kho giá xuất xưởng cực sốc. Chất liệu chuẩn xưởng viền may 6 đường cực bền, số lượng có hạn cả nhà bấm giỏ hàng góc trái chốt đơn nhé!"
};

const COMMON_VARIABLES = [
  { key: 'product_name', label: 'Tên sản phẩm', desc: 'Tên sản phẩm chính hãng hoặc biến thể' },
  { key: 'category', label: 'Ngành hàng', desc: 'Ngành hàng / Phân loại sản phẩm' },
  { key: 'benefits', label: 'Công dụng chính', desc: 'Lợi ích thực tế giải quyết vấn đề khách hàng' },
  { key: 'highlights', label: 'Điểm nổi bật', desc: 'Đặc điểm chất liệu, cấu tạo chuẩn xưởng' },
  { key: 'price', label: 'Giá bán', desc: 'Mức giá ưu đãi / giá xuất xưởng' },
  { key: 'offer', label: 'Ưu đãi & Quà tặng', desc: 'Trợ giá, miễn phí giao hàng' },
  { key: 'target_customer', label: 'Khách hàng', desc: 'Đối tượng mục tiêu' },
  { key: 'dialogue_1', label: 'Thoại Cảnh 1', desc: 'Lời thoại Cảnh 1 (>=42 từ)' },
  { key: 'dialogue_2', label: 'Thoại Cảnh 2', desc: 'Lời thoại Cảnh 2 (>=42 từ)' }
];

export const PromptLibraryView: React.FC = () => {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Edit / Create Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('edit');
  const [editingPrompt, setEditingPrompt] = useState<{
    id?: string;
    title: string;
    category: string;
    content: string;
    variables: string[];
  }>({
    title: '',
    category: 'script_gen_warehouse',
    content: '',
    variables: []
  });
  const [previewMode, setPreviewMode] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const categories = [
    { id: 'all', label: '🌟 Tất cả mẫu', icon: Sparkles },
    { id: 'warehouse', label: '🏭 Bản Kho Xưởng / Giá Tận Gốc', icon: Factory, highlight: true },
    { id: 'character_gen', label: '👩 Người Mẫu Cửa Hàng (Showroom)', icon: Store },
    { id: 'script_gen', label: '📝 Kịch Bản 42 Từ Chuẩn TikTok', icon: FileText },
    { id: 'veo3_scene1', label: '🎥 Video Cảnh 1 (Hook & Xưởng)', icon: Video },
    { id: 'veo3_scene2', label: '🎬 Video Cảnh 2 (Cận Cảnh & Chốt Đơn)', icon: Video },
    { id: 'dialogue_fix', label: '✂️ Chỉnh Thoại 42 Từ', icon: AlignLeft },
    { id: 'hook_gen', label: '💡 Hook Triệu View', icon: Sparkles },
  ];

  const categoryOptions = [
    { value: 'character_gen_warehouse', label: '🏭 1. Tạo Ảnh Nhân Vật Tại Kho Xưởng (9:16)' },
    { value: 'script_gen_warehouse', label: '🏭 2. Kịch Bản Thoại Giá Xuất Xưởng Tận Gốc (≥42 từ)' },
    { value: 'veo3_scene1_warehouse', label: '🏭 3. Prompt Video Cảnh 1 - Bước Đi Tại Xưởng' },
    { value: 'veo3_scene2_warehouse', label: '🏭 4. Prompt Video Cảnh 2 - Cận Cảnh & Chốt Đơn Giá Xưởng' },
    { value: 'character_gen', label: '👩 5. Tạo Ảnh Người Mẫu Cửa Hàng (Showroom)' },
    { value: 'script_gen', label: '📝 6. Kịch Bản 42 Từ Cửa Hàng (A/B/C)' },
    { value: 'veo3_scene1', label: '🎥 7. Prompt Video Cảnh 1 (Cửa hàng)' },
    { value: 'veo3_scene2', label: '🎬 8. Prompt Video Cảnh 2 (Cửa hàng)' },
    { value: 'dialogue_fix', label: '✂️ 9. Chỉnh Sửa Lời Thoại Chuẩn 42 Từ' },
    { value: 'hook_gen', label: '💡 10. Tạo Hook Quảng Cáo' },
    { value: 'variant_gen', label: '📑 11. Tạo Biến Thể Nội Dung' },
  ];

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const loadPrompts = async () => {
    try {
      setLoading(true);
      const data = await api.listPrompts();
      setPrompts(data);
    } catch (e) {
      console.error(e);
      showToast('Lỗi khi tải danh sách prompt');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPrompts();
  }, []);

  // Filtered prompts
  const filteredPrompts = useMemo(() => {
    let result = prompts;

    // Filter by Category
    if (activeCategory === 'warehouse') {
      result = result.filter(p => 
        p.category.includes('warehouse') || 
        p.id.includes('warehouse') || 
        p.id.includes('factory') || 
        p.title.toLowerCase().includes('kho xưởng') ||
        p.title.toLowerCase().includes('xuất xưởng') ||
        p.content.toLowerCase().includes('xưởng sản xuất')
      );
    } else if (activeCategory !== 'all') {
      result = result.filter(p => p.category === activeCategory);
    }

    // Filter by Search Query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(p => 
        p.title.toLowerCase().includes(q) ||
        p.content.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q) ||
        (p.variables && p.variables.some(v => v.toLowerCase().includes(q)))
      );
    }

    return result;
  }, [prompts, activeCategory, searchQuery]);

  const handleCopy = (id: string, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedId(id);
    showToast('Đã sao chép nội dung Prompt vào bộ nhớ tạm!');
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleDuplicate = async (id: string) => {
    try {
      await api.duplicatePrompt(id);
      await loadPrompts();
      showToast('Đã nhân bản mẫu prompt thành công!');
    } catch (e) {
      console.error(e);
      showToast('Lỗi khi nhân bản prompt');
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Bạn có chắc chắn muốn xóa mẫu prompt tùy chỉnh này?')) {
      try {
        await api.deletePrompt(id);
        await loadPrompts();
        showToast('Đã xóa mẫu prompt thành công!');
      } catch (err: any) {
        alert(err.message || 'Lỗi khi xóa prompt');
      }
    }
  };

  const handleResetDefaults = async () => {
    if (confirm('Khôi phục tất cả mẫu prompt gốc của hệ thống (bao gồm các mẫu Bản Kho Xưởng mới)?')) {
      try {
        await api.resetDefaultPrompts();
        await loadPrompts();
        showToast('Đã khôi phục các mẫu prompt gốc thành công!');
      } catch (err: any) {
        alert(err.message || 'Lỗi khi khôi phục');
      }
    }
  };

  // Open Edit Modal
  const openEditModal = (p: PromptTemplate) => {
    setModalMode('edit');
    setEditingPrompt({
      id: p.id,
      title: p.title,
      category: p.category,
      content: p.content,
      variables: p.variables || []
    });
    setPreviewMode(false);
    setIsModalOpen(true);
  };

  // Open Create Modal
  const openCreateModal = () => {
    setModalMode('create');
    setEditingPrompt({
      title: '',
      category: activeCategory !== 'all' && activeCategory !== 'warehouse' ? activeCategory : 'script_gen_warehouse',
      content: '',
      variables: ['product_name', 'category', 'benefits', 'highlights']
    });
    setPreviewMode(false);
    setIsModalOpen(true);
  };

  // Insert Variable at cursor position
  const handleInsertVariable = (varName: string) => {
    const textarea = textareaRef.current;
    const tag = `{{${varName}}}`;
    if (!textarea) {
      setEditingPrompt(prev => ({ ...prev, content: prev.content + tag }));
      return;
    }
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const current = editingPrompt.content;
    const nextContent = current.substring(0, start) + tag + current.substring(end);
    setEditingPrompt(prev => ({
      ...prev,
      content: nextContent,
      variables: Array.from(new Set([...(prev.variables || []), varName]))
    }));
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + tag.length, start + tag.length);
    }, 50);
  };

  // Save Modal
  const handleSaveModal = async () => {
    if (!editingPrompt.title.trim()) {
      alert('Vui lòng nhập tiêu đề mẫu prompt.');
      return;
    }
    if (!editingPrompt.content.trim()) {
      alert('Vui lòng nhập nội dung mẫu prompt.');
      return;
    }

    try {
      if (modalMode === 'edit' && editingPrompt.id) {
        await api.updatePrompt(editingPrompt.id, {
          title: editingPrompt.title,
          content: editingPrompt.content,
          category: editingPrompt.category as any,
          variables: editingPrompt.variables
        });
        showToast('Đã lưu thay đổi mẫu prompt thành công!');
      } else {
        await api.createPrompt({
          title: editingPrompt.title,
          category: editingPrompt.category as any,
          content: editingPrompt.content,
          variables: editingPrompt.variables
        });
        showToast('Đã tạo mẫu prompt mới thành công!');
      }
      setIsModalOpen(false);
      await loadPrompts();
    } catch (err: any) {
      alert(err.message || 'Lỗi khi lưu prompt');
    }
  };

  // Word count & stats helper
  const getPromptStats = (text: string) => {
    const cleaned = text.replace(/["'`“”‘’«»()[\]{}–—:;,.!?/\\]/g, ' ');
    const words = cleaned.split(/\s+/).filter(Boolean);
    const wordCount = words.length;
    const charCount = text.length;
    const estSec = Math.max(1, Math.round(wordCount / 4.2)); // ~4.2 words per second in Vietnamese
    return { wordCount, charCount, estSec };
  };

  // Live preview renderer with sample data
  const renderPreviewContent = (template: string) => {
    let rendered = template;
    for (const [k, v] of Object.entries(SAMPLE_DEMO_PRODUCT)) {
      rendered = rendered.split(`{{${k}}}`).join(v);
    }
    return rendered;
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-3 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white text-xs font-bold shadow-2xl flex items-center gap-2 border border-emerald-400/30 animate-in fade-in slide-in-from-bottom-3 duration-200">
          <CheckCircle2 className="w-4 h-4 text-emerald-200" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gradient-to-r from-[#181d29] via-[#1c2230] to-[#181d29] p-6 rounded-3xl border border-[#232a3b] shadow-xl">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-pink-500/20 to-purple-500/20 border border-pink-500/30 flex items-center justify-center text-pink-400 shadow-inner">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-black text-white tracking-wide flex items-center gap-2">
                <span>Kho Prompt & Mẫu Kịch Bản Chuẩn TikTok Shop</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-extrabold border border-emerald-500/30">
                  {prompts.length} Mẫu
                </span>
              </h2>
              <p className="text-xs text-slate-400 font-medium">
                Tối ưu hóa các mẫu prompt AI cho Gemini, Imagen 3, Muse AI và Google Veo 3. Hỗ trợ đầy đủ biến tự động và bối cảnh kho xưởng triệu view.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={openCreateModal}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-pink-500/20 transition-all transform hover:-translate-y-0.5"
          >
            <Plus className="w-4 h-4" />
            <span>Thêm Mẫu Prompt Mới</span>
          </button>

          <button
            onClick={handleResetDefaults}
            title="Khôi phục toàn bộ các mẫu mặc định ban đầu"
            className="px-3.5 py-2.5 rounded-xl bg-[#12161f] hover:bg-[#232a3b] text-slate-300 text-xs font-semibold border border-[#232a3b] flex items-center gap-1.5 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5 text-amber-400" />
            <span className="hidden sm:inline">Khôi phục mẫu gốc</span>
          </button>
        </div>
      </div>

      {/* Search & Statistics Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#181d29] p-3 rounded-2xl border border-[#232a3b]">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Tìm kiếm prompt theo tên, nội dung hoặc biến..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-8 py-2 rounded-xl bg-[#12161f] border border-[#232a3b] text-white text-xs focus:border-pink-500 focus:outline-none placeholder-slate-500"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <div className="text-xs text-slate-400 flex items-center gap-3 w-full sm:w-auto justify-end">
          <span>
            Hiển thị <strong className="text-pink-400 font-bold">{filteredPrompts.length}</strong> / {prompts.length} mẫu
          </span>
        </div>
      </div>

      {/* Category Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
        {categories.map((cat) => {
          const Icon = cat.icon;
          const isActive = activeCategory === cat.id;
          
          // Calculate count in this category
          const count = prompts.filter(p => {
            if (cat.id === 'all') return true;
            if (cat.id === 'warehouse') {
              return p.category.includes('warehouse') || p.id.includes('warehouse') || p.id.includes('factory') || p.title.toLowerCase().includes('kho xưởng') || p.title.toLowerCase().includes('xuất xưởng');
            }
            return p.category === cat.id;
          }).length;

          return (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`px-3.5 py-2.5 rounded-xl text-xs font-bold whitespace-nowrap transition-all flex items-center gap-2 border ${
                isActive
                  ? cat.highlight
                    ? 'bg-gradient-to-r from-amber-500/25 to-orange-500/25 text-amber-300 border-amber-500/50 shadow-md shadow-amber-500/10'
                    : 'bg-gradient-to-r from-pink-500/25 to-purple-500/25 text-pink-300 border-pink-500/50 shadow-md shadow-pink-500/10'
                  : cat.highlight
                  ? 'bg-[#181d29] text-amber-400/80 border-amber-500/30 hover:border-amber-500 hover:text-amber-300'
                  : 'bg-[#181d29] text-slate-400 border-[#232a3b] hover:text-white hover:border-slate-600'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? (cat.highlight ? 'text-amber-400' : 'text-pink-400') : ''}`} />
              <span>{cat.label}</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                isActive ? 'bg-white/20 text-white' : 'bg-[#12161f] text-slate-400'
              }`}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Prompts Grid */}
      {loading ? (
        <div className="py-20 text-center text-slate-400 text-xs">Đang tải danh sách prompt...</div>
      ) : filteredPrompts.length === 0 ? (
        <div className="p-12 text-center rounded-3xl bg-[#181d29] border border-[#232a3b] space-y-3">
          <BookOpen className="w-10 h-10 text-slate-600 mx-auto" />
          <h4 className="text-sm font-bold text-white">Không tìm thấy mẫu prompt phù hợp</h4>
          <p className="text-xs text-slate-400">Hãy thử đổi từ khóa tìm kiếm hoặc chọn danh mục khác.</p>
          <button
            onClick={() => { setActiveCategory('all'); setSearchQuery(''); }}
            className="px-4 py-2 rounded-xl bg-[#232a3b] hover:bg-[#2e374d] text-slate-200 text-xs font-semibold"
          >
            Xem tất cả mẫu
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filteredPrompts.map((p) => {
            const isCopied = copiedId === p.id;
            const isWarehouse = p.category.includes('warehouse') || p.id.includes('warehouse') || p.id.includes('factory');
            const stats = getPromptStats(p.content);

            return (
              <div
                key={p.id}
                className={`p-5 rounded-3xl bg-[#181d29] border transition-all flex flex-col justify-between shadow-xl hover:shadow-2xl hover:border-pink-500/40 ${
                  isWarehouse ? 'border-amber-500/30' : 'border-[#232a3b]'
                }`}
              >
                <div className="space-y-3.5">
                  {/* Top Badge & Action Buttons */}
                  <div className="flex items-start justify-between gap-3 border-b border-[#232a3b] pb-3">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {isWarehouse && (
                          <span className="text-[10px] px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/30 font-extrabold flex items-center gap-1">
                            <Factory className="w-3 h-3" /> Kho Xưởng Triệu View
                          </span>
                        )}
                        <span className="text-[10px] px-2 py-0.5 rounded-md bg-[#12161f] text-cyan-400 border border-cyan-500/20 font-mono font-semibold">
                          {p.category}
                        </span>
                        {p.is_system && (
                          <span className="text-[10px] px-2 py-0.5 rounded-md bg-blue-500/15 text-blue-300 font-semibold border border-blue-500/20">
                            Hệ thống
                          </span>
                        )}
                      </div>
                      <h4 className="text-sm font-black text-white leading-snug">{p.title}</h4>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleCopy(p.id, p.content)}
                        title="Sao chép nội dung prompt"
                        className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-[#232a3b] transition-all"
                      >
                        {isCopied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </button>

                      <button
                        onClick={() => openEditModal(p)}
                        title="Chỉnh sửa mẫu prompt này"
                        className="p-2 rounded-xl text-slate-400 hover:text-pink-400 hover:bg-pink-500/10 transition-all"
                      >
                        <Edit3 className="w-4 h-4" />
                      </button>

                      <button
                        onClick={() => handleDuplicate(p.id)}
                        title="Nhân bản mẫu prompt này"
                        className="p-2 rounded-xl text-slate-400 hover:text-cyan-400 hover:bg-cyan-500/10 transition-all"
                      >
                        <Plus className="w-4 h-4" />
                      </button>

                      {!p.is_system && (
                        <button
                          onClick={() => handleDelete(p.id)}
                          title="Xóa mẫu tùy chỉnh này"
                          className="p-2 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Prompt Content Preview */}
                  <div className="relative group">
                    <pre className="p-4 rounded-2xl bg-[#12161f] text-slate-300 text-[11px] font-mono whitespace-pre-wrap leading-relaxed max-h-56 overflow-y-auto border border-[#232a3b] select-text">
                      {p.content}
                    </pre>

                    {/* Quick Stats Overlay Pill */}
                    <div className="absolute bottom-2.5 right-2.5 flex items-center gap-2 pointer-events-none">
                      <span className="text-[10px] px-2 py-0.5 rounded-lg bg-black/80 text-slate-400 border border-slate-700 font-mono backdrop-blur-sm">
                        {stats.wordCount} từ &bull; {stats.charCount} ký tự
                      </span>
                    </div>
                  </div>
                </div>

                {/* Variables Support Section */}
                <div className="pt-3 mt-3 border-t border-[#232a3b]/60 flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[10px] text-slate-500 font-semibold">Biến tự động:</span>
                    {p.variables && p.variables.length > 0 ? (
                      p.variables.map((v) => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => {
                            navigator.clipboard.writeText(`{{${v}}}`);
                            showToast(`Đã sao chép biến {{${v}}}`);
                          }}
                          title={`Bấm để sao chép biến {{${v}}}`}
                          className="text-[10px] px-2 py-0.5 rounded-md bg-[#12161f] hover:bg-cyan-500/20 text-cyan-400 hover:text-cyan-200 border border-cyan-500/20 font-mono transition-colors"
                        >
                          {`{{${v}}}`}
                        </button>
                      ))
                    ) : (
                      <span className="text-[10px] text-slate-600 italic">Không có biến</span>
                    )}
                  </div>

                  <button
                    onClick={() => openEditModal(p)}
                    className="text-[11px] text-pink-400 hover:text-pink-300 font-bold flex items-center gap-1 hover:underline ml-auto"
                  >
                    <span>Mở Trình Sửa</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Edit & Create Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-4xl max-h-[92vh] flex flex-col rounded-3xl bg-[#181d29] border border-[#2a3449] shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-[#232a3b] flex items-center justify-between bg-gradient-to-r from-[#1c2230] to-[#181d29]">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-pink-500/20 border border-pink-500/30 flex items-center justify-center text-pink-400">
                  {modalMode === 'create' ? <Plus className="w-5 h-5" /> : <Edit3 className="w-5 h-5" />}
                </div>
                <div>
                  <h3 className="text-base font-black text-white">
                    {modalMode === 'create' ? 'Tạo Mẫu Prompt Mới' : 'Chỉnh Sửa Mẫu Prompt Chuẩn'}
                  </h3>
                  <p className="text-xs text-slate-400">
                    Tùy chỉnh nội dung, chèn biến linh hoạt và xem trước kết quả trực tiếp với dữ liệu mẫu.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPreviewMode(!previewMode)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all border ${
                    previewMode
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm'
                      : 'bg-[#12161f] text-slate-300 border-[#232a3b] hover:text-white'
                  }`}
                >
                  {previewMode ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5 text-emerald-400" />}
                  <span>{previewMode ? 'Quay lại soạn thảo' : 'Xem trước (Live Preview)'}</span>
                </button>

                <button
                  onClick={() => setIsModalOpen(false)}
                  className="p-1.5 rounded-xl text-slate-400 hover:text-white hover:bg-[#232a3b] transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-4 flex-1">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-2 space-y-1.5">
                  <label className="text-xs font-bold text-slate-300">Tiêu đề mẫu Prompt:</label>
                  <input
                    type="text"
                    placeholder="Nhập tên gợi nhớ cho mẫu prompt..."
                    value={editingPrompt.title}
                    onChange={(e) => setEditingPrompt({ ...editingPrompt, title: e.target.value })}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-[#12161f] border border-[#232a3b] text-white text-xs font-bold focus:border-pink-500 focus:outline-none"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-300">Danh mục:</label>
                  <select
                    value={editingPrompt.category}
                    onChange={(e) => setEditingPrompt({ ...editingPrompt, category: e.target.value })}
                    className="w-full px-3 py-2.5 rounded-xl bg-[#12161f] border border-[#232a3b] text-white text-xs font-semibold focus:border-pink-500 focus:outline-none"
                  >
                    {categoryOptions.map((opt) => (
                      <option key={opt.value} value={opt.value} className="bg-[#12161f] text-white">
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Quick Variable Insertion Tool */}
              <div className="p-3.5 rounded-2xl bg-[#12161f] border border-[#232a3b] space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-300 flex items-center gap-1.5">
                    <Wand2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Bấm để chèn nhanh biến vào Prompt:</span>
                  </span>
                  <span className="text-[11px] text-slate-500">Biến sẽ tự động thay bằng dữ liệu của sản phẩm khi chạy</span>
                </div>

                <div className="flex items-center gap-1.5 flex-wrap">
                  {COMMON_VARIABLES.map((v) => (
                    <button
                      key={v.key}
                      type="button"
                      onClick={() => handleInsertVariable(v.key)}
                      title={v.desc}
                      className="px-2.5 py-1 rounded-lg bg-[#181d29] hover:bg-cyan-500/20 text-cyan-300 hover:text-cyan-100 border border-cyan-500/25 text-xs font-mono transition-all transform hover:-translate-y-0.5 active:translate-y-0"
                    >
                      + {`{{${v.key}}}`}
                    </button>
                  ))}
                </div>
              </div>

              {/* Editor / Live Preview */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <label className="font-bold text-slate-300 flex items-center gap-2">
                    <span>{previewMode ? 'Kết quả render thực tế (Dữ liệu mẫu demo):' : 'Nội dung mẫu Prompt:'}</span>
                  </label>
                  {!previewMode && (
                    <div className="flex items-center gap-3 text-slate-400 text-[11px] font-mono">
                      <span>{getPromptStats(editingPrompt.content).wordCount} từ</span>
                      <span>&bull;</span>
                      <span>{getPromptStats(editingPrompt.content).charCount} ký tự</span>
                      <span>&bull;</span>
                      <span className="text-emerald-400 font-bold">~{getPromptStats(editingPrompt.content).estSec}s đọc</span>
                    </div>
                  )}
                </div>

                {previewMode ? (
                  <div className="p-4 rounded-2xl bg-[#0f1219] border border-emerald-500/30 text-slate-200 text-xs font-mono whitespace-pre-wrap leading-relaxed max-h-[46vh] overflow-y-auto shadow-inner">
                    {renderPreviewContent(editingPrompt.content)}
                  </div>
                ) : (
                  <textarea
                    ref={textareaRef}
                    rows={14}
                    value={editingPrompt.content}
                    onChange={(e) => setEditingPrompt({ ...editingPrompt, content: e.target.value })}
                    placeholder="Soạn nội dung prompt tại đây. Chèn các biến như {{product_name}}, {{category}}, {{benefits}}..."
                    className="w-full p-4 rounded-2xl bg-[#12161f] border border-[#232a3b] text-slate-200 text-xs font-mono leading-relaxed focus:border-pink-500 focus:outline-none resize-y min-h-[260px] shadow-inner"
                  />
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-[#232a3b] flex items-center justify-between bg-[#12161f]">
              <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
                <HelpCircle className="w-3.5 h-3.5 text-slate-500" />
                <span>Mẹo: Kịch bản video TikTok 10s đạt chuẩn cần khoảng 42 đến 48 từ tiếng Việt đọc vừa vặn.</span>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-[#181d29] hover:bg-[#232a3b] text-slate-300 text-xs font-semibold border border-[#232a3b] transition-colors"
                >
                  Hủy
                </button>

                <button
                  type="button"
                  onClick={handleSaveModal}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-pink-500/20 transition-all transform hover:-translate-y-0.5"
                >
                  <Save className="w-4 h-4" />
                  <span>{modalMode === 'create' ? 'Tạo Prompt Mới' : 'Lưu Thay Đổi'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

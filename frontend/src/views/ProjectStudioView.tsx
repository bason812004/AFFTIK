import React, { useState, useEffect, useRef } from 'react';
import { 
  ArrowLeft, 
  Sparkles, 
  Bot, 
  Film, 
  CheckCircle2, 
  Upload, 
  Play, 
  Download, 
  FolderOpen, 
  AlertTriangle, 
  RefreshCw, 
  ChevronRight, 
  ShieldAlert, 
  ExternalLink,
  Loader2,
  FileText,
  Check,
  X,
  Copy,
  Zap,
  ClipboardPaste,
  Combine,
  Image as ImageIcon,
  Wand2,
  Trash2,
  Layers,
  Eye,
  EyeOff
} from 'lucide-react';
import { ScriptOption, Asset, QualityCheckResult, AutomationMode } from '../types';
import { api } from '../api';
import { WordCounterBadge } from '../components/WordCounterBadge';

interface ProjectStudioViewProps {
  projectId: string | null;
  onBack: () => void;
  geminiStatus: any;
  flowStatus: any;
  museStatus?: any;
  ffmpegStatus: any;
  onRefreshStatus?: () => void;
  mode?: AutomationMode;
  initialTab?: 'manual_flow' | 'character' | 'scripts' | 'flow' | 'stitch';
  onProjectCreated?: (newId: string) => void;
}

async function convertBlobToPng(blob: Blob): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    const url = URL.createObjectURL(blob);
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth || img.width || 1080;
      canvas.height = img.naturalHeight || img.height || 1920;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        URL.revokeObjectURL(url);
        reject(new Error('Canvas context unavailable'));
        return;
      }
      ctx.drawImage(img, 0, 0);
      canvas.toBlob((pngBlob) => {
        URL.revokeObjectURL(url);
        if (pngBlob) resolve(pngBlob);
        else reject(new Error('PNG conversion failed'));
      }, 'image/png');
    };
    img.onerror = (err) => {
      URL.revokeObjectURL(url);
      reject(err);
    };
    img.src = url;
  });
}

export const ProjectStudioView: React.FC<ProjectStudioViewProps> = ({
  projectId,
  onBack,
  flowStatus,
  museStatus,
  onRefreshStatus,
  mode = 'auto',
  initialTab,
  onProjectCreated
}) => {
  const [project, setProject] = useState<any>(null);
  const [studioMode, setStudioMode] = useState<'manual' | 'auto'>(
    mode === 'manual' || initialTab === 'manual_flow' ? 'manual' : 'auto'
  );
  const [activeTab, setActiveTab] = useState<'manual_flow' | 'character' | 'scripts' | 'flow' | 'stitch'>(
    initialTab || (mode === 'manual' ? 'manual_flow' : 'character')
  );
  const [selectedScriptTab, setSelectedScriptTab] = useState<'A' | 'B' | 'C'>('A');
  const [loading, setLoading] = useState(true);

  // Copy feedback state
  const [copiedId, setCopiedId] = useState<string>('');

  // Character generation state
  const [generatingChar, setGeneratingChar] = useState(false);
  const [charProgressMsg, setCharProgressMsg] = useState('');

  // Script generation state
  const [generatingScripts, setGeneratingScripts] = useState(false);
  const [scriptProgressMsg, setScriptProgressMsg] = useState('');

  // Flow & Manual video states
  const [generatingVideo1, setGeneratingVideo1] = useState(false);
  const [generatingVideo2, setGeneratingVideo2] = useState(false);
  const [generatingFast1, setGeneratingFast1] = useState(false);
  const [generatingFast2, setGeneratingFast2] = useState(false);
  const [uploadingVideo1, setUploadingVideo1] = useState(false);
  const [uploadingVideo2, setUploadingVideo2] = useState(false);
  const [pastingVideo1, setPastingVideo1] = useState(false);
  const [pastingVideo2, setPastingVideo2] = useState(false);
  const [dragOverScene, setDragOverScene] = useState<1 | 2 | null>(null);
  const [videoProgressMsg, setVideoProgressMsg] = useState('');

  // Quick new product upload inside studio
  const [uploadingNewProduct, setUploadingNewProduct] = useState(false);
  const [preparingManual, setPreparingManual] = useState(false);
  const [manualProductName, setManualProductName] = useState('');
  const [manualProductBenefits, setManualProductBenefits] = useState('');
  const [imgCacheKey, setImgCacheKey] = useState<number>(() => Date.now());

  // FFmpeg Stitching state
  const [stitching, setStitching] = useState(false);

  // Quality check modal
  const [qualityResult, setQualityResult] = useState<QualityCheckResult | null>(null);
  const [checkingQuality, setCheckingQuality] = useState(false);
  const [showQualityModal, setShowQualityModal] = useState(false);

  // Editable script states
  const [editableScripts, setEditableScripts] = useState<Record<string, Partial<ScriptOption>>>({});

  // 1-Click Full Automation state
  const [pipelineTask, setPipelineTask] = useState<any>(null);
  const [runningFullAuto, setRunningFullAuto] = useState<boolean>(false);
  const [cloningVariant, setCloningVariant] = useState<boolean>(false);
  const [queueToast, setQueueToast] = useState<{ message: string; projectId?: string } | null>(null);
  const [showCharPromptText, setShowCharPromptText] = useState<boolean>(false);
  const [customCharPrompt, setCustomCharPrompt] = useState<string>('');

  const effectiveId = projectId || project?.id || 'manual01';
  const activeProjectIdRef = useRef<string | null>(effectiveId);
  activeProjectIdRef.current = effectiveId;
  const prevTaskStatusByProjectRef = useRef<Record<string, string>>({});

  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
      setStudioMode(initialTab === 'manual_flow' ? 'manual' : 'auto');
    } else if (mode === 'manual') {
      setStudioMode('manual');
      setActiveTab('manual_flow');
    }
  }, [initialTab, mode]);

  const handleSwitchStudioMode = (targetMode: 'manual' | 'auto') => {
    setStudioMode(targetMode);
    if (targetMode === 'manual') {
      setActiveTab('manual_flow');
    } else if (activeTab === 'manual_flow') {
      setActiveTab('character');
    }
  };

  const showCopied = (key: string) => {
    setCopiedId(key);
    setTimeout(() => {
      setCopiedId((prev) => (prev === key ? '' : prev));
    }, 2500);
  };

  const handleCopyText = async (text: string, key: string) => {
    try {
      await navigator.clipboard.writeText(text);
      showCopied(key);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      showCopied(key);
    }
  };

  const handleCopyImage = async (type: 'character' | 'product') => {
    const key = `img_${type}`;
    try {
      // 1. Copy via Windows OS native clipboard
      await api.copyImageToClipboard(effectiveId, type);

      // 2. Also copy via Browser Clipboard API
      const imgPath = type === 'character'
        ? (project?.primary_character_image_path || project?.original_image_path)
        : project?.original_image_path;
      if (imgPath && navigator.clipboard && 'write' in navigator.clipboard) {
        try {
          const url = getMediaUrl(imgPath, type === 'character' ? 'character' : 'product');
          const resp = await fetch(url);
          const blob = await resp.blob();
          const pngBlob = blob.type === 'image/png' ? blob : await convertBlobToPng(blob);
          await navigator.clipboard.write([new ClipboardItem({ 'image/png': pngBlob })]);
        } catch {}
      }
      showCopied(key);
    } catch (e: any) {
      alert('Lỗi sao chép ảnh: ' + e.message);
    }
  };

  const [sessionState, setSessionState] = useState<any>(null);
  const [resumingSession, setResumingSession] = useState<boolean>(false);
  const [requiredProductNameInput, setRequiredProductNameInput] = useState<string>('');
  const [confirmingProductName, setConfirmingProductName] = useState<boolean>(false);

  const showQueueToast = (message: string, targetProjectId?: string) => {
    setQueueToast({ message, projectId: targetProjectId });
    setTimeout(() => {
      setQueueToast((prev) => (prev?.message === message ? null : prev));
    }, 6500);
  };

  const checkPipeline = async (targetId?: string) => {
    const idToCheck = targetId || projectId || project?.id;
    if (!idToCheck) return;
    try {
      const [status, sess] = await Promise.all([
        api.getPipelineStatus(idToCheck),
        api.getSessionState().catch(() => null)
      ]);
      if (sess) {
        setSessionState(sess);
      }
      // Guard against stale async responses after user clicked another project
      if (activeProjectIdRef.current && idToCheck !== activeProjectIdRef.current) {
        return;
      }
      if (status && status.has_task) {
        const prevStatus = prevTaskStatusByProjectRef.current[idToCheck];
        prevTaskStatusByProjectRef.current[idToCheck] = status.status;
        setPipelineTask(status);
        const isQueuedWaiting = status.step_name === 'Đang chờ tới lượt';
        const isActuallyRunningHere =
          status.status === 'running' &&
          (!isQueuedWaiting || sess?.running_project_id === idToCheck);

        if (isActuallyRunningHere) {
          setRunningFullAuto(true);
        } else {
          setRunningFullAuto(false);
          if (status.status === 'completed' || status.status === 'waiting_product_name') {
            if (prevStatus === 'running') {
              await loadProject(true, idToCheck);
              if (status.status === 'completed' && studioMode === 'auto') {
                setActiveTab('stitch');
              }
            }
          }
        }
      } else {
        setPipelineTask(null);
        setRunningFullAuto(false);
      }
    } catch (e) {
      console.error('Check pipeline error:', e);
    }
  };

  useEffect(() => {
    if (projectId) {
      checkPipeline(projectId);
    } else {
      checkPipeline();
    }
  }, [projectId]);

  useEffect(() => {
    const isBatchOrRunning = Boolean(
      runningFullAuto ||
      sessionState?.running_project_id ||
      sessionState?.paused_session?.paused ||
      sessionState?.batch_state?.active
    );
    if (!isBatchOrRunning) return;
    const interval = setInterval(async () => {
      const currentTargetId = activeProjectIdRef.current || effectiveId;
      await checkPipeline(currentTargetId);
      await loadProject(true, currentTargetId);
    }, 3000);
    return () => clearInterval(interval);
  }, [runningFullAuto, sessionState?.running_project_id, sessionState?.paused_session?.paused, sessionState?.batch_state?.active, projectId]);

  const handleSelectProjectInStudio = async (targetId: string) => {
    if (!targetId) return;
    activeProjectIdRef.current = targetId;
    if (onProjectCreated) {
      onProjectCreated(targetId);
    }
    await loadProject(false, targetId);
    await checkPipeline(targetId);
  };

  const handleClearBatchQueue = async () => {
    try {
      await api.clearBatchQueue();
      const sess = await api.getSessionState().catch(() => null);
      if (sess) setSessionState(sess);
    } catch (e) {
      console.error('Clear batch queue error:', e);
    }
  };

  const handleResumeSavedSession = async () => {
    try {
      setResumingSession(true);
      const res = await api.resumeSession(effectiveId);
      setRunningFullAuto(true);
      await checkPipeline();
      await loadProject(true);
      if (res?.project_id && res.project_id !== effectiveId && onProjectCreated) {
        onProjectCreated(res.project_id);
      }
    } catch (e: any) {
      alert('Lỗi tiếp tục phiên làm việc: ' + (e.message || e));
    } finally {
      setResumingSession(false);
    }
  };

  const handleConfirmProductName = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const clean = requiredProductNameInput.trim();
    if (clean.length < 2) {
      alert('Vui lòng nhập tên sản phẩm chính xác (ít nhất 2 ký tự)!');
      return;
    }
    try {
      setConfirmingProductName(true);
      const shouldAutoRun = true;
      await api.confirmProductName(effectiveId, clean, shouldAutoRun);
      setRequiredProductNameInput('');
      setRunningFullAuto(true);
      await loadProject(true, effectiveId);
      await checkPipeline(effectiveId);
    } catch (err: any) {
      alert('Lỗi xác nhận tên sản phẩm: ' + (err.message || err));
    } finally {
      setConfirmingProductName(false);
    }
  };

  const handleRunFullAuto = async () => {
    try {
      setRunningFullAuto(true);
      await api.runFullAuto(effectiveId);
      await api.resumeQueue(undefined, true).catch(() => {});
      await checkPipeline(effectiveId);
    } catch (e: any) {
      alert('Lỗi kích hoạt tự động: ' + e.message);
      setRunningFullAuto(false);
    }
  };

  const handleCloneVideoVariant = async () => {
    if (!effectiveId) return;
    try {
      setCloningVariant(true);
      const res = await api.cloneVideoVariant(effectiveId, true);
      if (res?.project_id) {
        if (onProjectCreated) {
          onProjectCreated(res.project_id);
        } else {
          await loadProject(false, res.project_id);
        }
      }
    } catch (e: any) {
      alert('Lỗi nhân bản video kho xưởng: ' + (e?.message || e));
    } finally {
      setCloningVariant(false);
    }
  };

  const applyProjectData = (data: any) => {
    if (!data) return;
    setProject((prev: any) => {
      const isDifferentProject = !prev || prev.id !== data.id;
      const mediaChanged =
        isDifferentProject ||
        prev.original_image_path !== data.original_image_path ||
        prev.primary_character_image_path !== data.primary_character_image_path ||
        (prev.videos?.length || 0) !== (data.videos?.length || 0) ||
        Boolean(prev.export) !== Boolean(data.export) ||
        prev.updated_at !== data.updated_at;
      if (mediaChanged) {
        setImgCacheKey(Date.now());
      }
      if (isDifferentProject || prev?.benefits !== data.benefits || prev?.name !== data.name) {
        setManualProductName(data.name || '');
        setManualProductBenefits(data.benefits || '');
      } else {
        const activeTag = document.activeElement?.tagName;
        if (activeTag !== 'INPUT' && activeTag !== 'TEXTAREA') {
          setManualProductName(data.name || '');
          setManualProductBenefits(data.benefits || '');
        }
      }
      return data;
    });
    if (data.scripts && data.scripts.length > 0) {
      const scriptMap: Record<string, Partial<ScriptOption>> = {};
      data.scripts.forEach((s: ScriptOption) => {
        scriptMap[s.option_label] = { ...s };
        if (s.is_selected) {
          setSelectedScriptTab(s.option_label);
        }
      });
      setEditableScripts(scriptMap);
    } else {
      setEditableScripts({});
    }
  };

  const loadProject = async (silent: boolean = false, targetId?: string) => {
    const idToLoad = targetId || projectId || project?.id;
    try {
      if (!silent && (!project || (idToLoad && project.id !== idToLoad))) {
        setLoading(true);
      }
      let data: any = null;
      if (idToLoad) {
        try {
          data = await api.getProject(idToLoad);
        } catch {
          data = null;
        }
      }
      // Never fall back to ensureManualProject when a projectId was already selected
      if (!data && !idToLoad) {
        data = await api.ensureManualProject();
        if (data?.id && onProjectCreated && data.id !== projectId) {
          onProjectCreated(data.id);
        }
      }
      if (data && (!activeProjectIdRef.current || data.id === activeProjectIdRef.current || !idToLoad)) {
        applyProjectData(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    if (projectId) {
      loadProject(false, projectId);
    } else {
      loadProject(false);
    }
  }, [projectId]);

  const handleManualPrepare = async (file?: File, silent: boolean = false) => {
    try {
      if (!silent) setPreparingManual(true);
      const updated = await api.manualPrepareProject(effectiveId, {
        name: manualProductName,
        benefits: manualProductBenefits,
        file
      });
      applyProjectData(updated);
      if (!silent) showCopied('manual_prepared');
    } catch (err: any) {
      if (!silent) alert('Lỗi cập nhật sản phẩm & kịch bản: ' + err.message);
    } finally {
      if (!silent) setPreparingManual(false);
    }
  };

  // Auto-update prompts when the user edits product name or benefits (debounced, no button click required)
  useEffect(() => {
    if (!project || runningFullAuto) return;
    const nameChanged = manualProductName.trim() && manualProductName.trim() !== (project.name || '').trim();
    const benefitsChanged = manualProductBenefits.trim() && manualProductBenefits.trim() !== (project.benefits || '').trim();
    if (!nameChanged && !benefitsChanged) return;
    const timer = setTimeout(() => {
      handleManualPrepare(undefined, true);
    }, 900);
    return () => clearTimeout(timer);
  }, [manualProductName, manualProductBenefits]);

  const lastPasteTimeRef = useRef<number>(0);

  // Global Ctrl+V listener: allows pasting product image from clipboard once without duplicate firing
  useEffect(() => {
    const handleGlobalPasteNewProject = async (e: ClipboardEvent) => {
      if (e.defaultPrevented || Date.now() - lastPasteTimeRef.current < 800) {
        return;
      }
      const activeEl = document.activeElement;
      const isInput = activeEl && (
        activeEl.tagName === 'INPUT' || 
        activeEl.tagName === 'TEXTAREA' || 
        (activeEl as HTMLElement).isContentEditable
      );
      if (isInput) return;

      let pastedFile: File | null = null;
      if (e.clipboardData && e.clipboardData.files && e.clipboardData.files.length > 0) {
        for (let i = 0; i < e.clipboardData.files.length; i++) {
          const file = e.clipboardData.files[i];
          if (file.type.startsWith('image/')) {
            pastedFile = file;
            break;
          }
        }
      } else if (e.clipboardData && e.clipboardData.items && e.clipboardData.items.length > 0) {
        for (let i = 0; i < e.clipboardData.items.length; i++) {
          const item = e.clipboardData.items[i];
          if (item.type.startsWith('image/')) {
            pastedFile = item.getAsFile();
            if (pastedFile) break;
          }
        }
      }

      if (pastedFile) {
        lastPasteTimeRef.current = Date.now();
        e.preventDefault();
        e.stopPropagation();
        if (studioMode === 'manual' && activeTab === 'manual_flow') {
          await handleManualPrepare(pastedFile);
        } else {
          await handleCreateNewProjectWithFile(pastedFile);
        }
      }
    };

    window.addEventListener('paste', handleGlobalPasteNewProject);
    return () => window.removeEventListener('paste', handleGlobalPasteNewProject);
  }, [studioMode, activeTab, effectiveId, onProjectCreated]);

  // Stepper calculations
  const s1Obj = project?.videos?.find((v: any) => v.scene_number === 1);
  const s2Obj = project?.videos?.find((v: any) => v.scene_number === 2);
  const stepHasS1 = Boolean(s1Obj);
  const stepHasS2 = Boolean(s2Obj);
  const stepIsDup = Boolean(
    s1Obj && s2Obj &&
    ((s1Obj.file_size && s2Obj.file_size && s1Obj.file_size === s2Obj.file_size) ||
     (s1Obj.video_path && s2Obj.video_path && s1Obj.video_path === s2Obj.video_path))
  );
  const steps = [
    { id: 1, label: 'Tạo dự án', done: true },
    { id: 2, label: 'Ảnh sản phẩm', done: !!project?.original_image_path },
    { id: 3, label: 'Nhân vật AI', done: !!project?.primary_character_image_path },
    { id: 4, label: 'Prompt & Kịch bản', done: project?.scripts && project.scripts.length > 0 },
    { id: 5, label: 'Video Cảnh 1', done: stepHasS1 },
    { id: 6, label: 'Video Cảnh 2', done: stepHasS2 && !stepIsDup },
    { id: 7, label: 'Ghép Video Hoàn Thành', done: !!project?.export && stepHasS1 && stepHasS2 && !stepIsDup },
  ];

  // Female Model Master Prompt (Chuẩn 9 phần)
  const defaultFemaleCharPrompt = project?.character_prompt || `Tạo ảnh quảng cáo sản phẩm siêu chân thực 8K, tỷ lệ dọc 9:16, phong cách chụp ảnh thương mại cao cấp, sang trọng, chuyên nghiệp, giống ảnh chụp thực tế bằng máy ảnh full-frame chuyên nghiệp với ống kính 50mm.

## 1. BỐI CẢNH CỬA HÀNG PHÙ HỢP VỚI SẢN PHẨM

Dựa hoàn toàn vào hình ảnh sản phẩm tham chiếu để thiết kế một cửa hàng trưng bày có phong cách, công năng và cách bố trí phù hợp với chính sản phẩm đó. Không sử dụng bối cảnh cửa hàng chung chung hoặc không liên quan đến sản phẩm.

Cửa hàng có thiết kế hiện đại, cao cấp, sạch sẽ, rộng rãi và chuyên nghiệp. Màu sắc nội thất, vật liệu trang trí, quầy trưng bày, kệ sản phẩm và các chi tiết xung quanh phải hài hòa với màu sắc, kiểu dáng và phân khúc của sản phẩm tham chiếu.

Bố trí khu vực trưng bày sản phẩm nổi bật ở tiền cảnh. Phía sau là các kệ trưng bày hoặc những sản phẩm cùng dòng, cùng nhóm hàng phù hợp với sản phẩm chính. Các sản phẩm phụ chỉ đóng vai trò tạo không gian cửa hàng chân thực, không được lấn át sản phẩm chính. Không tự ý thêm những mặt hàng không liên quan.

Không gian có chiều sâu tự nhiên, bố cục gọn gàng, tinh tế, thể hiện hình ảnh một cửa hàng uy tín với phong cách thương hiệu cao cấp. Có thể bổ sung quầy tư vấn, tủ trưng bày và bảng thông tin sản phẩm phù hợp với ngành hàng, nhưng không để các chi tiết này che khuất sản phẩm chính.

## 2. KHÓA SẢN PHẨM – BẮT BUỘC GIỮ NGUYÊN 100%

Sử dụng chính xác sản phẩm trong hình ảnh tham chiếu. Giữ nguyên tuyệt đối hình dáng, kích thước, tỷ lệ, màu sắc, chất liệu, cấu trúc, thiết kế, logo, chữ viết và toàn bộ chi tiết gốc.

Tuyệt đối không thiết kế lại, không thay đổi màu sắc, không bóp méo, không kéo giãn, không làm biến dạng, không thêm hoặc xóa bất kỳ chi tiết nào trên sản phẩm.

Đặt sản phẩm trên một bàn trưng bày cao cấp hoặc bục trưng bày sang trọng phù hợp với kích thước và công năng của sản phẩm. Sản phẩm nằm ở tiền cảnh, gần máy ảnh, chiếm vị trí nổi bật, nhìn thấy đầy đủ từ trên xuống dưới và từ trái sang phải, không bị cắt mất bất kỳ phần nào.

Sản phẩm có kích thước chân thực, nổi bật nhưng không phóng đại quá mức. Mặt trước sản phẩm hướng thẳng về phía máy ảnh, hạn chế góc nghiêng để thấy rõ thiết kế, logo và các chi tiết.
## 3. NGƯỜI MẪU NỮ CAO CẤP

Một người mẫu nữ Việt Nam 21 tuổi, xinh đẹp nổi bật, gương mặt thanh tú, đường nét hài hòa, đôi mắt sáng có thần, làn da tự nhiên, mái tóc được tạo kiểu tinh tế và lớp trang điểm nhẹ nhàng sang trọng.

Người mẫu mặc đồng phục nhân viên cửa hàng cao cấp, thiết kế hiện đại, thanh lịch, màu sắc hài hòa với sản phẩm và không gian cửa hàng. Trang phục chỉn chu, vừa vặn, chất liệu chân thực.

Người mẫu đứng sát bên cạnh hoặc hơi phía sau sản phẩm, ở vị trí gần máy ảnh. Một tay nhẹ nhàng giới thiệu sản phẩm, tay còn lại tạo dáng tự nhiên. Nụ cười thân thiện, ánh mắt tự tin, thần thái chuyên nghiệp như người đại diện thương hiệu trong chiến dịch quảng cáo cao cấp.

Khuôn mặt, đôi mắt, mái tóc, trang phục và bàn tay của người mẫu phải rõ nét, tự nhiên, chân thực; không làm mịn da quá mức, không tạo gương mặt giả hoặc biểu cảm cứng đờ.

## 4. BỐ CỤC VÀ KHOẢNG CÁCH MÁY ẢNH

Khung hình dọc 9:16, góc máy chính diện, bố cục quảng cáo thương mại chuyên nghiệp.

Đưa sản phẩm và người mẫu lại gần máy ảnh hơn, tạo cảm giác gần gũi và nổi bật. Sản phẩm chiếm phần lớn tiền cảnh nhưng vẫn giữ nguyên tỷ lệ thực tế và hiển thị trọn vẹn. Người mẫu đứng ngay cạnh sản phẩm để cả hai trở thành hai chủ thể chính trong khung hình.

Không để người mẫu đứng quá xa. Không để quầy kệ hoặc vật dụng trong cửa hàng che khuất sản phẩm. Cân đối khoảng trống phía trên và hai bên, tạo cảm giác sang trọng, rõ ràng và dễ nhìn.

## 5. LẤY NÉT CỰC RÕ VÀO CẢ SẢN PHẨM LẪN NGƯỜI MẪU

Bắt buộc lấy nét đồng thời vào sản phẩm và người mẫu. Cả hai phải sắc nét rõ ràng trong cùng một khung hình, không được chỉ nét sản phẩm mà mờ người mẫu, hoặc chỉ nét người mẫu mà mờ sản phẩm.

Logo, chữ viết, bề mặt, đường viền, kết cấu và mọi chi tiết trên sản phẩm đều rõ nét. Khuôn mặt, đôi mắt, tóc, trang phục và bàn tay người mẫu cũng rõ nét.

Sử dụng độ sâu trường ảnh đủ lớn, khẩu độ tham khảo f/8–f/11, ISO thấp và tốc độ màn trập phù hợp. Hạn chế xóa phông mạnh, không sử dụng hiệu ứng bokeh quá mức. Hậu cảnh cửa hàng vẫn nhận diện được rõ ràng nhưng không cạnh tranh sự chú ý với hai chủ thể chính.

## 6. ÁNH SÁNG TRẮNG SÁNG RÕ

Sử dụng hệ thống đèn LED ánh sáng trắng trung tính khoảng 5500K, chiếu sáng đồng đều toàn bộ cửa hàng, sản phẩm và người mẫu.
Ánh sáng phải sáng rõ, sạch, tự nhiên, cao cấp và chuyên nghiệp. Sản phẩm thể hiện đúng màu sắc thực tế, không bị ám vàng, ám xanh hoặc đổi màu. Khuôn mặt người mẫu đủ sáng, không bị tối, không có bóng đổ gắt. Giữ lại chi tiết ở vùng sáng, không cháy sáng, không làm mất kết cấu sản phẩm.

## 7. LOGO VÀ NHẬN DIỆN THƯƠNG HIỆU

Nếu có hình ảnh logo công ty được cung cấp, đặt logo trên bảng hiệu sang trọng ở bức tường phía sau quầy trưng bày. Logo có thể được thiết kế dạng chữ nổi hoặc hộp đèn phát sáng tinh tế, dễ nhìn và phù hợp với nội thất cửa hàng.

Giữ nguyên chính xác hình dáng, màu sắc, tỷ lệ và nội dung logo tham chiếu. Không tự sáng tạo tên công ty, không viết sai chữ, không thay đổi logo gốc. Logo trên sản phẩm cũng phải được giữ nguyên tuyệt đối.

## 8. CHẤT LƯỢNG HÌNH ẢNH

Ảnh quảng cáo sản phẩm siêu chân thực 8K, chi tiết cao, độ nét cao, màu sắc trung thực, ánh sáng trắng đồng đều, chất liệu chân thực, bố cục sang trọng, phong cách nhiếp ảnh quảng cáo chuyên nghiệp. Sản phẩm và người mẫu là hai điểm thu hút chính, nổi bật rõ ràng ngay từ cái nhìn đầu tiên.
chỉnh sửa sao cho kích thước sản phẩm hợp lý

## 9. NEGATIVE PROMPT – CÁC LỖI CẦN TRÁNH

Không sai sản phẩm, không đổi thiết kế, không đổi màu, không bóp méo, không kéo giãn, không sai tỷ lệ, không sai logo, không chữ sai, không thêm chi tiết lạ, không mất chi tiết gốc, không cắt cụt sản phẩm, không phóng đại sản phẩm quá mức, không làm mờ sản phẩm, không làm mờ người mẫu, không lấy nét sai, không xóa phông quá mạnh, không bokeh quá mức, không nhòe chuyển động, không ánh sáng tối, không ám vàng, không bóng đổ gắt, không cháy sáng, không da nhựa, không gương mặt biến dạng, không tay lỗi, không thừa ngón tay, không cửa hàng bừa bộn, không nội thất cũ kỹ, không bối cảnh nhà máy hoặc kho hàng, không thêm sản phẩm không liên quan, không chữ ngẫu nhiên, không watermark, không phong cách hoạt hình hoặc CGI giả tạo.`;

  const charPromptToUse = customCharPrompt || defaultFemaleCharPrompt;

  // Handlers for Step 1: Character Gen
  const handleGenerateCharacter = async () => {
    try {
      setGeneratingChar(true);
      setCharProgressMsg('Đang mở Gemini và đính kèm ảnh sản phẩm để tạo nhân vật 9:16...');

      const res = await api.generateCharacter(effectiveId, customCharPrompt || undefined);
      if (res.success) {
        await loadProject(true);
      } else if (res.needs_login) {
        alert(res.error || 'Vui lòng đăng nhập Google trên trình duyệt mở sẵn.');
      }
    } catch (e: any) {
      alert(e.message || 'Lỗi khi tạo nhân vật AI');
    } finally {
      setGeneratingChar(false);
      setCharProgressMsg('');
    }
  };

  const handleManualCharacterUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      try {
        await api.uploadCharacterImage(effectiveId, e.target.files[0]);
        await loadProject(true);
      } catch (err: any) {
        alert('Lỗi tải ảnh: ' + err.message);
      }
    }
  };

  const handleReplaceProductUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      try {
        setUploadingNewProduct(true);
        await api.uploadProductImage(effectiveId, file);
        setRunningFullAuto(true);
        await loadProject(true);
        await checkPipeline();
        showCopied('manual_prepared');
      } catch (err: any) {
        alert('Lỗi tải ảnh sản phẩm: ' + err.message);
      } finally {
        setUploadingNewProduct(false);
        e.target.value = '';
      }
    }
  };

  const handleCreateNewProjectWithFile = async (file: File) => {
    try {
      setUploadingNewProduct(true);
      const shouldAutoRun = true;
      const isAlreadyRunning = Boolean(
        runningFullAuto ||
        sessionState?.running_project_id ||
        sessionState?.batch_state?.active
      );
      const res = await api.quickCreateProject(file, undefined, shouldAutoRun);
      if (res.success && res.project_id) {
        if (shouldAutoRun) {
          setStudioMode('auto');
          if (activeTab === 'manual_flow') {
            setActiveTab('character');
          }
        }
        if (isAlreadyRunning && shouldAutoRun) {
          // Stay on current project while adding new product to the queue
          await checkPipeline(effectiveId);
          showQueueToast(
            `📥 Đã thêm "${res.name || 'Sản phẩm mới'}" vào Hàng Đợi Sản Xuất! Hệ thống sẽ tự động chạy khi tới lượt.`,
            res.project_id
          );
        } else {
          activeProjectIdRef.current = res.project_id;
          if (onProjectCreated) {
            onProjectCreated(res.project_id);
          }
          setRunningFullAuto(shouldAutoRun);
          const data = await api.getProject(res.project_id);
          applyProjectData(data);
          await checkPipeline(res.project_id);
        }
        showCopied('manual_prepared');
      }
    } catch (err: any) {
      alert('Lỗi tạo dự án mới: ' + (err.message || err));
    } finally {
      setUploadingNewProduct(false);
    }
  };

  const handlePasteAsNewProject = async () => {
    if (Date.now() - lastPasteTimeRef.current < 800) return;
    lastPasteTimeRef.current = Date.now();
    try {
      setUploadingNewProduct(true);

      // 1. Try browser navigator.clipboard.read() first
      if (navigator.clipboard && 'read' in navigator.clipboard) {
        try {
          const items = await navigator.clipboard.read();
          for (const item of items) {
            const imgType = item.types.find(t => t.startsWith('image/'));
            if (imgType) {
              const blob = await item.getType(imgType);
              const ext = imgType.split('/')[1] || 'png';
              const file = new File([blob], `san_pham_paste.${ext}`, { type: imgType });
              await handleCreateNewProjectWithFile(file);
              return;
            }
          }
        } catch (e_nav) {
          console.debug('navigator.clipboard.read() skipped/denied, falling back to backend clipboard:', e_nav);
        }
      }

      // 2. Direct backend Windows clipboard read
      const shouldAutoRun = true;
      const isAlreadyRunning = Boolean(
        runningFullAuto ||
        sessionState?.running_project_id ||
        sessionState?.batch_state?.active
      );
      const res = await api.quickCreateFromClipboard(shouldAutoRun);
      if (res.success && res.project_id) {
        if (shouldAutoRun) {
          setStudioMode('auto');
          if (activeTab === 'manual_flow') {
            setActiveTab('character');
          }
        }
        if (isAlreadyRunning && shouldAutoRun) {
          await checkPipeline(effectiveId);
          showQueueToast(
            `📥 Đã dán & thêm "${res.name || 'Sản phẩm mới'}" vào Hàng Đợi Sản Xuất!`,
            res.project_id
          );
        } else {
          activeProjectIdRef.current = res.project_id;
          if (onProjectCreated) {
            onProjectCreated(res.project_id);
          }
          setRunningFullAuto(shouldAutoRun);
          const data = await api.getProject(res.project_id);
          applyProjectData(data);
          await checkPipeline(res.project_id);
        }
        showCopied('manual_prepared');
      } else {
        alert(res.message || 'Không thể tạo dự án từ Clipboard.');
      }
    } catch (err: any) {
      alert(err.message || 'Chưa tìm thấy ảnh trong Clipboard! Hãy bấm copy ảnh (Ctrl+C hoặc Win+Shift+S) rồi bấm Dán.');
    } finally {
      setUploadingNewProduct(false);
    }
  };

  const handleQuickNewProjectUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      try {
        if (files.length === 1) {
          await handleCreateNewProjectWithFile(files[0]);
        } else {
          setUploadingNewProduct(true);
          const shouldAutoRun = true;
          const isAlreadyRunning = Boolean(
            runningFullAuto ||
            sessionState?.running_project_id ||
            sessionState?.batch_state?.active
          );
          const batchRes = await api.batchCreateProjects(files, [], shouldAutoRun);
          if (batchRes.success && batchRes.first_project_id) {
            if (shouldAutoRun) {
              setStudioMode('auto');
              if (activeTab === 'manual_flow') {
                setActiveTab('character');
              }
            }
            if (isAlreadyRunning && shouldAutoRun) {
              await checkPipeline(effectiveId);
              showQueueToast(
                `📥 Đã thêm ${files.length} sản phẩm mới vào Hàng Đợi Sản Xuất! Nhấp vào sản phẩm bất kỳ trên Hàng Đợi để xem.`,
                batchRes.first_project_id
              );
            } else {
              activeProjectIdRef.current = batchRes.first_project_id;
              if (onProjectCreated) {
                onProjectCreated(batchRes.first_project_id);
              }
              setRunningFullAuto(shouldAutoRun);
              const data = await api.getProject(batchRes.first_project_id);
              applyProjectData(data);
              await checkPipeline(batchRes.first_project_id);
              showQueueToast(
                `🚀 Đã khởi tạo Hàng Đợi ${files.length} sản phẩm! Bạn có thể nhấp vào từng sản phẩm trên thanh Hàng Đợi để xem riêng.`,
                batchRes.first_project_id
              );
            }
            showCopied('manual_prepared');
          }
        }
      } catch (err: any) {
        alert('Lỗi thêm sản phẩm hàng loạt: ' + (err.message || err));
      } finally {
        setUploadingNewProduct(false);
        e.target.value = '';
      }
    }
  };

  const handleSetPrimaryCharacter = async (assetId: string) => {
    try {
      await api.setPrimaryCharacter(effectiveId, assetId);
      await loadProject(true);
    } catch (e: any) {
      alert(e.message);
    }
  };

  // Handlers for Step 2: Scripts & Prompts
  const handleGenerateScripts = async () => {
    try {
      setGeneratingScripts(true);
      setScriptProgressMsg('Gửi ảnh và thông tin sản phẩm sang Gemini để tạo kịch bản & prompt tạo video...');

      const res = await api.generateScripts(effectiveId);
      if (res.success) {
        await loadProject(true);
      } else if (res.needs_login) {
        alert('Cần đăng nhập Google trên Gemini để tạo kịch bản.');
      }
    } catch (e: any) {
      alert('Lỗi tạo kịch bản: ' + e.message);
    } finally {
      setGeneratingScripts(false);
      setScriptProgressMsg('');
    }
  };

  const handleScriptChange = (optLabel: string, field: string, val: string) => {
    setEditableScripts(prev => {
      const current = prev[optLabel] || {};
      const updated: Partial<ScriptOption> = {
        ...current,
        [field]: val
      };
      // If user edits scene1_dialogue or scene2_dialogue, keep the embedded dialogue inside prompt_veo in sync
      if (field === 'scene1_dialogue' && current.scene1_prompt_veo) {
        const oldDlg = (current.scene1_dialogue || '').trim();
        if (oldDlg && current.scene1_prompt_veo.includes(oldDlg)) {
          updated.scene1_prompt_veo = current.scene1_prompt_veo.replace(oldDlg, val);
        }
      }
      if (field === 'scene2_dialogue' && current.scene2_prompt_veo) {
        const oldDlg = (current.scene2_dialogue || '').trim();
        if (oldDlg && current.scene2_prompt_veo.includes(oldDlg)) {
          updated.scene2_prompt_veo = current.scene2_prompt_veo.replace(oldDlg, val);
        }
      }
      return {
        ...prev,
        [optLabel]: updated
      };
    });
  };

  const handleSaveScript = async (optLabel: string) => {
    const s = editableScripts[optLabel];
    if (!s || !s.id) return;
    try {
      await api.updateScript(s.id, s);
      await loadProject(true);
      showCopied('save_script');
    } catch (e: any) {
      alert('Lỗi lưu kịch bản: ' + e.message);
    }
  };

  const handleSelectScript = async (scriptId: string) => {
    try {
      await api.selectScript(scriptId);
      await loadProject(true);
      setActiveTab('flow');
    } catch (e: any) {
      alert('Lỗi chọn kịch bản: ' + e.message);
    }
  };

  const handleCheckQuality = async (optLabel: string) => {
    const s = editableScripts[optLabel];
    if (!s) return;
    try {
      setCheckingQuality(true);
      const res = await api.checkQuality({
        scene1_dialogue: s.scene1_dialogue || '',
        scene2_dialogue: s.scene2_dialogue || '',
        scene1_prompt: s.scene1_prompt_veo || '',
        scene2_prompt: s.scene2_prompt_veo || '',
        product_name: project?.name || ''
      });
      setQualityResult(res);
      setShowQualityModal(true);
    } catch (e: any) {
      alert('Lỗi kiểm tra chất lượng: ' + e.message);
    } finally {
      setCheckingQuality(false);
    }
  };

  // Handlers for Step 3: Video Generation / Upload / Paste / Drop
  const handleGenerateFastVideo = async (sceneNum: 1 | 2) => {
    try {
      if (sceneNum === 1) setGeneratingFast1(true);
      if (sceneNum === 2) setGeneratingFast2(true);
      setVideoProgressMsg(`Đang tạo Video Cảnh ${sceneNum} siêu tốc 9:16 (2 giây)...`);

      const res = await api.generateFastVideo(effectiveId, sceneNum);
      if (res.success) {
        await loadProject(true);
      }
    } catch (e: any) {
      alert(`Lỗi tạo Video Cảnh ${sceneNum} siêu tốc: ` + e.message);
    } finally {
      if (sceneNum === 1) setGeneratingFast1(false);
      if (sceneNum === 2) setGeneratingFast2(false);
      setVideoProgressMsg('');
    }
  };

  const [switchingFlowAccount, setSwitchingFlowAccount] = useState(false);
  const [switchingMuseAccount, setSwitchingMuseAccount] = useState(false);

  const handleSwitchMuseAccount = async () => {
    try {
      setSwitchingMuseAccount(true);
      await api.logoutMuse();
      if (onRefreshStatus) {
        onRefreshStatus();
      }
      alert('Đã mở cửa sổ đăng nhập Muse AI trên Chrome! Vui lòng hoàn tất đăng nhập để tiếp tục.');
    } catch (e: any) {
      alert('Lỗi mở bảng đăng nhập Muse AI: ' + e.message);
    } finally {
      setSwitchingMuseAccount(false);
    }
  };

  const handleSwitchFlowAccount = async () => {
    try {
      setSwitchingFlowAccount(true);
      await api.logoutFlow();
      if (onRefreshStatus) {
        onRefreshStatus();
      }
      alert(
        'Đã đăng xuất tài khoản cũ và tự động mở nút Đăng nhập tài khoản Google mới trên trình duyệt Chrome!\n\n' +
        'Vui lòng đăng nhập tài khoản Google mới còn tín dụng trên cửa sổ Chrome. Ngay sau khi đăng nhập xong, hệ thống sẽ tự động cập nhật tên tài khoản và chạy tiếp công việc đang dang dở!'
      );
    } catch (e: any) {
      alert('Lỗi mở bảng đổi tài khoản Flow: ' + e.message);
    } finally {
      setSwitchingFlowAccount(false);
    }
  };

  const handleGenerateVideo = async (sceneNum: 1 | 2) => {
    try {
      if (sceneNum === 1) setGeneratingVideo1(true);
      if (sceneNum === 2) setGeneratingVideo2(true);
      setVideoProgressMsg(`Đang mở Google Flow tạo Video Cảnh ${sceneNum}...`);

      const res = await api.generateFlowVideo(effectiveId, sceneNum);
      if (res.success) {
        await loadProject(true);
      } else if (res.out_of_credits) {
        await checkPipeline();
        alert(
          res.message ||
          '⚠️ Tài khoản Google Flow hiện tại đã HẾT TÍN DỤNG!\nHệ thống đã tự động mở trang chọn tài khoản Google mới trên cửa sổ trình duyệt. Vui lòng chọn tài khoản khác còn tín dụng rồi bấm tạo lại.'
        );
      } else if (res.needs_login) {
        alert(
          res.message ||
          'Vui lòng chọn hoặc đăng nhập tài khoản Google trên cửa sổ trình duyệt Flow vừa mở, sau đó bấm tạo lại.'
        );
      } else if (res.manual_required) {
        alert(res.message || `Vui lòng tải video Cảnh ${sceneNum} từ Flow và bấm "Lấy từ Downloads" hoặc dán video vào.`);
      }
    } catch (e: any) {
      alert(`Lỗi tạo Video Cảnh ${sceneNum}: ` + e.message);
    } finally {
      if (sceneNum === 1) setGeneratingVideo1(false);
      if (sceneNum === 2) setGeneratingVideo2(false);
      setVideoProgressMsg('');
    }
  };

  const handleGenerateMuseVideo = async (sceneNum: 1 | 2) => {
    try {
      if (sceneNum === 1) setGeneratingVideo1(true);
      if (sceneNum === 2) setGeneratingVideo2(true);
      setVideoProgressMsg(`Đang mở Muse AI tạo Video Cảnh ${sceneNum}...`);

      const res = await api.generateMuseVideo(effectiveId, sceneNum);
      if (res.success) {
        await loadProject(true);
      } else if (res.needs_login) {
        alert(
          res.message ||
          'Vui lòng đăng nhập tài khoản Muse AI trên cửa sổ trình duyệt Chrome vừa mở, sau đó bấm tạo lại.'
        );
      } else {
        alert(res.message || `Đang xử lý video trên Muse AI.`);
      }
    } catch (e: any) {
      alert(`Lỗi tạo Video Cảnh ${sceneNum} bằng Muse AI: ` + e.message);
    } finally {
      if (sceneNum === 1) setGeneratingVideo1(false);
      if (sceneNum === 2) setGeneratingVideo2(false);
      setVideoProgressMsg('');
    }
  };

  const [pullingMuse, setPullingMuse] = useState(false);
  const handlePullFromMuse = async () => {
    if (!effectiveId) return;
    setPullingMuse(true);
    try {
      const res = await api.pullMuseVideos(effectiveId);
      if (res.success) {
        await loadProject(true);
        if (onRefreshStatus) onRefreshStatus();
        alert(res.message || 'Đã lấy thành công video từ Muse AI!');
      } else {
        alert(res.message || 'Không tìm thấy video nào của sản phẩm này trên Muse AI.');
      }
    } catch (e: any) {
      alert('Lỗi lấy video từ Muse AI: ' + e.message);
    } finally {
      setPullingMuse(false);
    }
  };

  const [importingVideo1, setImportingVideo1] = useState(false);
  const [importingVideo2, setImportingVideo2] = useState(false);

  const handleImportFlowVideo = async (sceneNum: 1 | 2) => {
    try {
      if (sceneNum === 1) setImportingVideo1(true);
      if (sceneNum === 2) setImportingVideo2(true);
      setVideoProgressMsg(`Đang nạp video mới nhất từ thư mục Downloads sang 1080x1920 60fps...`);

      const res = await api.importFlowVideo(effectiveId, sceneNum);
      if (res.success) {
        await loadProject(true);
        showCopied(`import_v${sceneNum}`);
      } else {
        alert(res.message || 'Không tìm thấy video mới trong Downloads.');
      }
    } catch (e: any) {
      alert(`Lỗi nạp video: ` + e.message);
    } finally {
      if (sceneNum === 1) setImportingVideo1(false);
      if (sceneNum === 2) setImportingVideo2(false);
      setVideoProgressMsg('');
    }
  };

  const uploadVideoFileForScene = async (sceneNum: 1 | 2, file: File) => {
    try {
      if (sceneNum === 1) setUploadingVideo1(true);
      if (sceneNum === 2) setUploadingVideo2(true);
      await api.uploadManualVideo(effectiveId, sceneNum, file);
      await loadProject(true);
      showCopied(`upload_v${sceneNum}`);
    } catch (err: any) {
      alert(`Lỗi tải video Cảnh ${sceneNum}: ` + err.message);
    } finally {
      if (sceneNum === 1) setUploadingVideo1(false);
      if (sceneNum === 2) setUploadingVideo2(false);
    }
  };

  const handleManualVideoUpload = async (sceneNum: 1 | 2, e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await uploadVideoFileForScene(sceneNum, e.target.files[0]);
      e.target.value = '';
    }
  };

  const handleDropVideo = async (sceneNum: 1 | 2, e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverScene(null);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      await uploadVideoFileForScene(sceneNum, file);
    }
  };

  const handlePasteVideoEvent = async (sceneNum: 1 | 2, e: React.ClipboardEvent<HTMLDivElement>) => {
    if (Date.now() - lastPasteTimeRef.current < 800) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    lastPasteTimeRef.current = Date.now();
    e.preventDefault();
    e.stopPropagation();
    if (e.clipboardData && e.clipboardData.files && e.clipboardData.files.length > 0) {
      const file = e.clipboardData.files[0];
      if (file.type.startsWith('video/') || file.name.toLowerCase().endsWith('.mp4')) {
        await uploadVideoFileForScene(sceneNum, file);
        return;
      }
    }
    // Otherwise try reading file path from Windows OS clipboard
    await handlePasteClipboardVideoButton(sceneNum);
  };

  const handlePasteClipboardVideoButton = async (sceneNum: 1 | 2) => {
    try {
      if (sceneNum === 1) setPastingVideo1(true);
      if (sceneNum === 2) setPastingVideo2(true);
      const res = await api.pasteClipboardVideo(effectiveId, sceneNum);
      if (res.success) {
        await loadProject(true);
        showCopied(`paste_v${sceneNum}`);
      }
    } catch (e: any) {
      alert(e.message || 'Không tìm thấy file video trong Clipboard. Hãy bấm Ctrl+C vào file video trong máy hoặc dùng nút Chọn File / Kéo thả.');
    } finally {
      if (sceneNum === 1) setPastingVideo1(false);
      if (sceneNum === 2) setPastingVideo2(false);
    }
  };

  const [deletingVideo1, setDeletingVideo1] = useState(false);
  const [deletingVideo2, setDeletingVideo2] = useState(false);
  const [deletingExport, setDeletingExport] = useState(false);
  const [deletingImage, setDeletingImage] = useState<string>('');
  const [pastingImageType, setPastingImageType] = useState<'product' | 'character' | null>(null);

  const handleDeleteSceneVideo = async (sceneNum: 1 | 2) => {
    try {
      if (sceneNum === 1) setDeletingVideo1(true);
      if (sceneNum === 2) setDeletingVideo2(true);
      await api.deleteSceneVideo(effectiveId, sceneNum);
      await loadProject(true);
      showCopied(`del_v${sceneNum}`);
    } catch (e: any) {
      alert(`Lỗi xóa Video Cảnh ${sceneNum}: ` + e.message);
    } finally {
      if (sceneNum === 1) setDeletingVideo1(false);
      if (sceneNum === 2) setDeletingVideo2(false);
    }
  };

  const handleDeleteExportVideo = async () => {
    try {
      setDeletingExport(true);
      await api.deleteExportVideo(effectiveId);
      await loadProject(true);
      showCopied('del_export');
    } catch (e: any) {
      alert('Lỗi xóa video ghép: ' + e.message);
    } finally {
      setDeletingExport(false);
    }
  };

  const handleDeleteImage = async (imageType: 'product' | 'character', assetId?: string) => {
    try {
      setDeletingImage(assetId || imageType);
      await api.deleteProjectImage(effectiveId, imageType, assetId);
      await loadProject(true);
      showCopied(`del_img_${imageType}`);
    } catch (e: any) {
      alert('Lỗi xóa ảnh: ' + e.message);
    } finally {
      setDeletingImage('');
    }
  };

  const handlePasteClipboardImage = async (imageType: 'product' | 'character') => {
    try {
      setPastingImageType(imageType);
      const res = await api.pasteClipboardImage(effectiveId, imageType);
      if (res.success) {
        if (imageType === 'product') {
          setRunningFullAuto(true);
        }
        await loadProject(true);
        await checkPipeline();
        showCopied(`paste_img_${imageType}`);
      }
    } catch (e: any) {
      alert(e.message || 'Không tìm thấy ảnh trong Clipboard! Hãy Copy ảnh (Ctrl+C) rồi bấm Dán Ảnh.');
    } finally {
      setPastingImageType(null);
    }
  };

  const handlePasteImageEvent = async (imageType: 'product' | 'character', e: React.ClipboardEvent<HTMLDivElement>) => {
    if (Date.now() - lastPasteTimeRef.current < 800) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    lastPasteTimeRef.current = Date.now();
    e.preventDefault();
    e.stopPropagation();
    if (e.clipboardData && e.clipboardData.files && e.clipboardData.files.length > 0) {
      const file = e.clipboardData.files[0];
      if (file.type.startsWith('image/')) {
        try {
          setPastingImageType(imageType);
          if (imageType === 'product') {
            await api.uploadProductImage(effectiveId, file);
            setRunningFullAuto(true);
          } else {
            await api.uploadCharacterImage(effectiveId, file);
          }
          await loadProject(true);
          await checkPipeline();
          showCopied(`paste_img_${imageType}`);
        } catch (err: any) {
          alert('Lỗi dán ảnh: ' + err.message);
        } finally {
          setPastingImageType(null);
        }
        return;
      }
    }
    await handlePasteClipboardImage(imageType);
  };

  // Handlers for Step 4: FFmpeg Stitch
  const handleStitch = async () => {
    if (isDuplicateScenes) {
      alert("Cảnh báo: Video Cảnh 1 và Video Cảnh 2 hiện đang trùng lặp (giống hệt nhau). Vui lòng bấm 'Tạo lại Cảnh 2' hoặc 'Lấy Video từ Muse AI' để tách biệt 2 cảnh trước khi ghép!");
      return;
    }
    try {
      setStitching(true);
      const res: any = await api.stitchVideos({
        project_id: effectiveId,
        transition: 'none',
        volume: 1.0
      });
      if (res && res.export) {
        setProject((prev: any) => prev ? { ...prev, export: res.export, status: 'completed' } : prev);
      }
      await loadProject(true);
      showCopied('stitched_ok');
      if (studioMode === 'auto' && activeTab === 'flow') {
        setActiveTab('stitch');
      }
    } catch (e: any) {
      alert('Lỗi ghép video FFmpeg: ' + e.message);
    } finally {
      setStitching(false);
    }
  };

  const handleOpenFolder = async () => {
    try {
      await api.openProjectFolder(effectiveId);
    } catch (e) {
      console.error(e);
    }
  };

  if (loading || !project) {
    return (
      <div className="p-12 flex flex-col items-center justify-center space-y-4">
        <Loader2 className="w-8 h-8 text-pink-500 animate-spin" />
        <div className="text-sm text-slate-400">Đang tải dự án TikTok Affiliate Studio...</div>
      </div>
    );
  }

  // Selected script for Flow & Stitch
  const pName = project?.name || 'Sản phẩm';
  const pBenefits = project?.benefits || 'công dụng vượt trội và tiện ích tối ưu';
  const benefitShort = pBenefits.length > 55 ? pBenefits.slice(0, 52) + '...' : pBenefits;

  const fallbackS1Dialogue = `Các bác đang tìm kiếm giải pháp hoàn hảo cho ${pName}? Đây chính là lựa chọn tuyệt vời nhất. Với công dụng ${benefitShort}, sản phẩm mang lại hiệu quả nhanh chóng, tiện lợi và an tâm tuyệt đối cho các bác mỗi ngày nhé!`;
  const fallbackS2Dialogue = `Thiết kế cao cấp, chứng nhận chất lượng rõ ràng và siêu bền bỉ khi sử dụng. Hôm nay trợ giá cực hời, các bác hãy nhanh tay bấm ngay vào giỏ hàng bên dưới góc trái màn hình để sở hữu liền tay nhé!`;

  const ensurePromptIncludesDialogue = (promptRaw: string, dialogueRaw: string, sceneNum: 1 | 2): string => {
    const cleanPrompt = (promptRaw || '').trim();
    const cleanDlg = (dialogueRaw || '').trim();
    if (!cleanDlg) return cleanPrompt;
    // If prompt already includes dialogue or standard speech clause, return as is!
    if (
      cleanPrompt.includes(cleanDlg) ||
      cleanPrompt.includes(cleanDlg.slice(0, Math.min(28, cleanDlg.length))) ||
      cleanPrompt.includes('Nhân vật nói tiếng Việt')
    ) {
      return cleanPrompt;
    }
    const stripped = cleanPrompt
      .replace(/Khẩu hình miệng khớp 42 từ lời thoại Cảnh [12]\.?/gi, '')
      .trim();
    const wordsCount = cleanDlg.split(/\s+/).filter(Boolean).length;
    return `${stripped} Nhân vật nói tiếng Việt rõ ràng trọn vẹn hết câu trong 10 giây (${wordsCount} từ): "${cleanDlg}" (Không chèn chữ, không phụ đề).`;
  };

  const dynamicFallbackScript = {
    id: project?.scripts?.[0]?.id || 'script_primary',
    option_label: 'A',
    option_title: `Kịch Bản TikTok Affiliate Độc Quyền - ${pName}`,
    hook_concept: `Đánh mạnh vào công dụng & tiện ích của ${pName}`,
    scene1_dialogue: fallbackS1Dialogue,
    scene1_word_count: 42,
    scene1_prompt_veo: ensurePromptIncludesDialogue(
      `Video dọc tỷ lệ 9:16, thời lượng đúng 10 giây, 60fps. Người mẫu nữ Việt Nam 21 tuổi mặc đồng phục thương mại mỉm cười thanh lịch tự nhiên, hai tay cầm ${pName} hướng về máy ảnh, ánh sáng studio 5500K sang trọng. Không text, không đồ họa.`,
      fallbackS1Dialogue,
      1
    ),
    scene2_dialogue: fallbackS2Dialogue,
    scene2_word_count: 42,
    scene2_prompt_veo: ensurePromptIncludesDialogue(
      `Video dọc tỷ lệ 9:16, thời lượng đúng 10 giây, 60fps. Bối cảnh và nhân vật đồng nhất Cảnh 1. Khóa 100% hình dáng bao bì ${pName} ở tiền cảnh không biến dạng. Máy quay tiến chậm lại gần sản phẩm lấy nét cận cảnh. Không text, không đồ họa.`,
      fallbackS2Dialogue,
      2
    )
  };

  const getMediaUrlForProject = (targetProjId?: string, path?: string, defaultFolder: string = 'character') => {
    const pid = targetProjId || project?.id;
    if (!path || !pid) return '';
    const norm = path.replace(/\\/g, '/');
    if (norm.startsWith('http://') || norm.startsWith('https://')) return norm;
    let baseUrl = '';
    const dataIdx = norm.indexOf('/data/');
    if (dataIdx !== -1) {
      baseUrl = norm.substring(dataIdx);
    } else {
      const bareDataIdx = norm.indexOf('data/');
      if (bareDataIdx !== -1) {
        baseUrl = '/' + norm.substring(bareDataIdx);
      } else {
        const filename = norm.split('/').pop() || '';
        if (norm.includes('/product/') || filename.includes('product')) {
          baseUrl = `/data/projects/${pid}/product/${filename}`;
        } else {
          baseUrl = `/data/projects/${pid}/${defaultFolder}/${filename}`;
        }
      }
    }
    return `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}t=${imgCacheKey}`;
  };

  const getMediaUrl = (path?: string, defaultFolder: string = 'character') => {
    return getMediaUrlForProject(project?.id, path, defaultFolder);
  };

  const rawScriptOpt = editableScripts[selectedScriptTab] || project?.scripts?.[0];
  const resolvedS1Dialogue = (rawScriptOpt?.scene1_dialogue && !rawScriptOpt.scene1_dialogue.includes('photo 2026') && !rawScriptOpt.scene1_dialogue.includes('None'))
    ? rawScriptOpt.scene1_dialogue
    : dynamicFallbackScript.scene1_dialogue;
  const resolvedS2Dialogue = (rawScriptOpt?.scene2_dialogue && !rawScriptOpt.scene2_dialogue.includes('photo 2026') && !rawScriptOpt.scene2_dialogue.includes('None'))
    ? rawScriptOpt.scene2_dialogue
    : dynamicFallbackScript.scene2_dialogue;

  const currentScriptOpt = {
    ...dynamicFallbackScript,
    ...(rawScriptOpt || {}),
    scene1_dialogue: resolvedS1Dialogue,
    scene2_dialogue: resolvedS2Dialogue,
    scene1_prompt_veo: ensurePromptIncludesDialogue(
      rawScriptOpt?.scene1_prompt_veo || dynamicFallbackScript.scene1_prompt_veo,
      resolvedS1Dialogue,
      1
    ),
    scene2_prompt_veo: ensurePromptIncludesDialogue(
      rawScriptOpt?.scene2_prompt_veo || dynamicFallbackScript.scene2_prompt_veo,
      resolvedS2Dialogue,
      2
    ),
  };

  const buildCopyPayloadForScene = (sceneNum: 1 | 2): string => {
    const promptPart = ((sceneNum === 1 ? currentScriptOpt.scene1_prompt_veo : currentScriptOpt.scene2_prompt_veo) || '').trim();
    const dialoguePart = ((sceneNum === 1 ? currentScriptOpt.scene1_dialogue : currentScriptOpt.scene2_dialogue) || '').trim();
    return ensurePromptIncludesDialogue(promptPart, dialoguePart, sceneNum);
  };

  const scene1Video = project.videos?.find((v: any) => v.scene_number === 1);
  const scene2Video = project.videos?.find((v: any) => v.scene_number === 2);
  const isDuplicateScenes = Boolean(
    scene1Video &&
    scene2Video &&
    ((scene1Video.file_size && scene2Video.file_size && scene1Video.file_size === scene2Video.file_size) ||
     (scene1Video.video_path && scene2Video.video_path && scene1Video.video_path === scene2Video.video_path))
  );
  const hasBothVideos = Boolean(scene1Video && scene2Video && !isDuplicateScenes);

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Studio Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#232a3b] pb-5">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 rounded-xl bg-[#181d29] border border-[#232a3b] hover:bg-[#232a3b] text-slate-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xl font-bold text-white tracking-tight">{project.name}</h2>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-pink-500/15 text-pink-400 font-bold border border-pink-500/30">
                {project.category}
              </span>
            </div>
            <p className="text-xs text-slate-400">ID: {project.id} &bull; Chế độ: {project.automation_mode.toUpperCase()}</p>
          </div>
        </div>

        {/* Quick actions right */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={handlePasteAsNewProject}
            disabled={uploadingNewProduct}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 via-teal-600 to-cyan-600 hover:from-emerald-600 hover:to-teal-700 text-white text-xs font-extrabold shadow-lg shadow-emerald-500/25 cursor-pointer flex items-center gap-2 transition-all transform hover:-translate-y-0.5 disabled:opacity-50"
            title="Dán ảnh sản phẩm trực tiếp từ Clipboard (Ctrl+V) để tạo dự án mới ngay lập tức"
          >
            {uploadingNewProduct ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <ClipboardPaste className="w-4 h-4" />
            )}
            <span>{uploadingNewProduct ? 'Đang Đọc & Tạo Dự Án Mới...' : '📋 Dán Ảnh Tạo Dự Án Mới (Ctrl+V)'}</span>
          </button>

          <label className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white text-xs font-extrabold shadow-lg shadow-amber-500/25 cursor-pointer flex items-center gap-2 transition-all">
            {uploadingNewProduct ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Upload className="w-4 h-4" />
            )}
            <span>{uploadingNewProduct ? 'Đang Xử Lý...' : '📥 Thêm 1 Hoặc Nhiều Sản Phẩm (Hàng Loạt)'}</span>
            <input type="file" accept="image/*" multiple onChange={handleQuickNewProjectUpload} className="hidden" />
          </label>

          {studioMode === 'auto' && (
            <button
              onClick={handleRunFullAuto}
              disabled={runningFullAuto}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-pink-500 via-rose-600 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white text-xs font-bold shadow-lg shadow-pink-500/25 flex items-center gap-2 transition-all transform hover:-translate-y-0.5 disabled:opacity-50"
            >
              <Sparkles className={`w-4 h-4 ${runningFullAuto ? 'animate-spin' : ''}`} />
              <span>{runningFullAuto ? 'Đang Tự Động Chạy...' : '🚀 BẮT ĐẦU TỰ ĐỘNG TOÀN BỘ'}</span>
            </button>
          )}

          <button
            onClick={handleCloneVideoVariant}
            disabled={cloningVariant || !project?.original_image_path}
            title="Nhân bản video: Giữ sản phẩm, tạo nhân vật mới ở bối cảnh tổng kho xưởng, thoại giá xưởng rẻ nhất ≥ 42 từ và tự động tạo tiếp video 20s mới"
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500 hover:from-amber-600 hover:to-rose-600 text-white text-xs font-black shadow-lg shadow-amber-500/25 flex items-center gap-2 transition-all transform hover:-translate-y-0.5 disabled:opacity-40"
          >
            {cloningVariant ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Đang Nhân Bản...</span>
              </>
            ) : (
              <>
                <Layers className="w-4 h-4" />
                <span>✨ Nhân Bản Video SP (Bản Kho Xưởng)</span>
              </>
            )}
          </button>

          {/* Smart Video Engine Pill: Works if EITHER Muse AI OR Flow is logged in */}
          {museStatus?.logged_in && !flowStatus?.logged_in ? (
            <div className="flex items-center rounded-xl border border-emerald-500/40 bg-[#181d29] overflow-hidden shadow-md">
              <div className="px-3 py-2 text-xs flex items-center gap-1.5 border-r border-emerald-500/30">
                <span className="text-slate-400 font-semibold">🎬 Video AI:</span>
                <span className="font-extrabold text-emerald-300 max-w-[220px] truncate flex items-center gap-1" title={museStatus?.account_display || 'Muse AI đã kết nối'}>
                  <Sparkles className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span>Muse AI (Đã kết nối)</span>
                </span>
              </div>
              <button
                type="button"
                onClick={handleSwitchMuseAccount}
                disabled={switchingMuseAccount}
                className="px-3 py-2 bg-emerald-500/20 hover:bg-emerald-500/35 text-emerald-200 text-xs font-extrabold flex items-center gap-1.5 transition-all"
                title="Đổi tài khoản Muse AI"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${switchingMuseAccount ? 'animate-spin' : ''}`} />
                <span>{switchingMuseAccount ? 'Đang mở...' : '🔄 Đổi TK Muse'}</span>
              </button>
            </div>
          ) : flowStatus?.logged_in && !museStatus?.logged_in ? (
            <div className="flex items-center rounded-xl border border-purple-500/40 bg-[#181d29] overflow-hidden shadow-md">
              <div className="px-3 py-2 text-xs flex items-center gap-1.5 border-r border-purple-500/30">
                <span className="text-slate-400 font-semibold">🎬 Video AI:</span>
                <span className="font-extrabold text-emerald-300 max-w-[220px] truncate flex items-center gap-1" title={flowStatus?.account_display || flowStatus?.account_email || 'Flow đã kết nối'}>
                  <Film className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                  <span>Flow ({flowStatus?.account_display || flowStatus?.account_email || 'Đã kết nối'})</span>
                </span>
              </div>
              <button
                type="button"
                onClick={handleSwitchFlowAccount}
                disabled={switchingFlowAccount}
                className="px-3 py-2 bg-purple-500/20 hover:bg-purple-500/35 text-purple-200 text-xs font-extrabold flex items-center gap-1.5 transition-all"
                title="Đổi tài khoản Google Flow"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${switchingFlowAccount ? 'animate-spin' : ''}`} />
                <span>{switchingFlowAccount ? 'Đang mở...' : '🔄 Đổi TK Flow'}</span>
              </button>
            </div>
          ) : museStatus?.logged_in && flowStatus?.logged_in ? (
            <div className="flex items-center rounded-xl border border-emerald-500/40 bg-[#181d29] overflow-hidden shadow-md">
              <div className="px-3 py-2 text-xs flex items-center gap-1.5 border-r border-emerald-500/30">
                <span className="text-slate-400 font-semibold">🎬 Video AI:</span>
                <span className="font-extrabold text-emerald-300">✅ Cả Muse & Flow sẵn sàng</span>
              </div>
              <button
                type="button"
                onClick={handleSwitchMuseAccount}
                disabled={switchingMuseAccount}
                className="px-2.5 py-2 bg-emerald-500/20 hover:bg-emerald-500/35 text-emerald-200 text-xs font-bold transition-all"
                title="Đổi tài khoản Muse AI"
              >
                Đổi Muse
              </button>
              <button
                type="button"
                onClick={handleSwitchFlowAccount}
                disabled={switchingFlowAccount}
                className="px-2.5 py-2 border-l border-emerald-500/30 bg-purple-500/20 hover:bg-purple-500/35 text-purple-200 text-xs font-bold transition-all"
                title="Đổi tài khoản Flow"
              >
                Đổi Flow
              </button>
            </div>
          ) : (
            <div className="flex items-center rounded-xl border border-amber-500/40 bg-[#181d29] overflow-hidden shadow-md">
              <div className="px-3 py-2 text-xs flex items-center gap-1.5 border-r border-amber-500/30">
                <span className="text-slate-400 font-semibold">🎬 Video AI:</span>
                <span className="font-bold text-amber-300">Đăng nhập 1 trong 2:</span>
              </div>
              <button
                type="button"
                onClick={async () => { await api.connectMuse(); if (onRefreshStatus) onRefreshStatus(); }}
                className="px-2.5 py-2 bg-emerald-500/20 hover:bg-emerald-500/35 text-emerald-300 text-xs font-bold flex items-center gap-1 transition-all"
                title="Đăng nhập tài khoản Muse AI"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Muse AI</span>
              </button>
              <button
                type="button"
                onClick={handleSwitchFlowAccount}
                className="px-2.5 py-2 border-l border-amber-500/30 bg-purple-500/20 hover:bg-purple-500/35 text-purple-300 text-xs font-bold flex items-center gap-1 transition-all"
                title="Đăng nhập tài khoản Google Flow"
              >
                <Film className="w-3.5 h-3.5" />
                <span>Google Flow</span>
              </button>
            </div>
          )}

          {project.export && (
            <button
              onClick={handleOpenFolder}
              className="px-3.5 py-2 rounded-xl bg-[#181d29] hover:bg-[#232a3b] text-slate-300 text-xs font-semibold border border-[#232a3b] flex items-center gap-2 transition-colors"
            >
              <FolderOpen className="w-4 h-4 text-amber-400" />
              <span>Mở Thư Mục Video</span>
            </button>
          )}
          <a
            href={`/api/projects/${project.id}/export-zip`}
            target="_blank"
            rel="noreferrer"
            className="px-3.5 py-2 rounded-xl bg-[#181d29] hover:bg-[#232a3b] text-slate-300 text-xs font-semibold border border-[#232a3b] flex items-center gap-2 transition-colors"
          >
            <Download className="w-4 h-4 text-[#25f4ee]" />
            <span>Sao Lưu ZIP</span>
          </a>
        </div>
      </div>

      {/* =========================================================================
          BANNER 1: UNRECOGNIZED PRODUCT NAME — REQUIRE USER TO INPUT EXACT NAME
          ========================================================================= */}
      {(project.status === 'needs_product_name' ||
        project.name?.includes('Cần nhập tên') ||
        pipelineTask?.status === 'waiting_product_name') && (
        <form
          onSubmit={handleConfirmProductName}
          className="p-5 rounded-2xl bg-gradient-to-r from-amber-500/20 via-orange-500/15 to-rose-500/20 border-2 border-amber-400 shadow-xl space-y-3"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-amber-300 shrink-0 mt-0.5 animate-bounce" />
            <div className="space-y-1 flex-1">
              <div className="text-sm font-black text-white uppercase tracking-wide">
                ⚠️ CHƯA NHẬN DIỆN ĐƯỢC TÊN SẢN PHẨM TRONG ẢNH — VUI LÒNG NHẬP TÊN SẢN PHẨM
              </div>
              <p className="text-xs text-amber-100 leading-relaxed">
                Ảnh sản phẩm này không có chữ bao bì rõ ràng. Để tránh tự ý đặt tên sản phẩm lan man không hợp lý, vui lòng nhập đúng tên sản phẩm bên dưới để AI viết kịch bản 42 từ &amp; Prompt chuẩn xác rồi tự động chạy tiếp!
              </p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-1">
            <input
              type="text"
              value={requiredProductNameInput}
              onChange={(e) => setRequiredProductNameInput(e.target.value)}
              placeholder="Nhập tên sản phẩm chuẩn xác (VD: Máy khoan pin cầm tay Makita, Kem chống nắng Anessa...)"
              className="flex-1 px-4 py-2.5 rounded-xl bg-[#12161f] border-2 border-amber-400/60 text-white text-xs font-bold focus:border-amber-300 focus:outline-none"
              autoFocus
            />
            <button
              type="submit"
              disabled={confirmingProductName || requiredProductNameInput.trim().length < 2}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black text-xs font-black flex items-center justify-center gap-2 shadow-lg disabled:opacity-50"
            >
              {confirmingProductName ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
              <span>✅ Xác Nhận Tên &amp; Viết Prompt Chuẩn Ngay</span>
            </button>
          </div>
        </form>
      )}

      {/* =========================================================================
          BANNER 2: SAVED WORKING SESSION & AUTO-RESUME AFTER FLOW ACCOUNT SWITCH
          ========================================================================= */}
      {(sessionState?.paused_session?.paused ||
        pipelineTask?.message?.toLowerCase().includes('tín dụng') ||
        pipelineTask?.step_name?.toLowerCase().includes('tín dụng') ||
        pipelineTask?.step_name?.toLowerCase().includes('đổi tk') ||
        pipelineTask?.step_name?.toLowerCase().includes('đăng nhập flow')) && (
        <div className="p-4 rounded-2xl bg-gradient-to-r from-red-500/25 via-amber-500/20 to-rose-500/25 border-2 border-red-400 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-amber-300 shrink-0 mt-0.5 animate-bounce" />
            <div className="space-y-1">
              <div className="text-sm font-black text-white uppercase tracking-wide flex items-center gap-2 flex-wrap">
                <span>💾 ĐÃ LƯU PHIÊN LÀM VIỆC — CHỜ ĐỔI TÀI KHOẢN GOOGLE FLOW</span>
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[10px] font-extrabold">
                  TỰ ĐỘNG CHẠY TIẾP SAU KHI ĐĂNG NHẬP
                </span>
              </div>
              <p className="text-xs text-amber-100 leading-relaxed">
                {sessionState?.paused_session?.message ||
                  pipelineTask?.message ||
                  'Tài khoản Google Flow hiện tại đã hết tín dụng. Hệ thống đã lưu phiên làm việc và tự động theo dõi cửa sổ Chrome: ngay khi bạn đăng nhập tài khoản mới xong, công việc đang dang dở sẽ tự động chạy tiếp!'}
              </p>
              <div className="flex items-center gap-4 flex-wrap pt-0.5">
                <div className="text-[11px] font-bold text-white bg-black/30 px-2.5 py-1 rounded-lg border border-white/10">
                  👤 Tài khoản Flow hiện tại:{' '}
                  <span className={flowStatus?.logged_in ? 'text-emerald-300' : 'text-amber-300'}>
                    {flowStatus?.logged_in
                      ? (flowStatus?.account_display || flowStatus?.account_email || 'Đã đăng nhập')
                      : 'Đang chờ đăng nhập tài khoản mới trên Chrome...'}
                  </span>
                </div>
                {sessionState?.paused_project_name && (
                  <div className="text-[11px] text-cyan-300 font-bold">
                    📌 Phiên đang lưu: {sessionState.paused_project_name} (Cảnh {sessionState?.paused_session?.scene_number || 1})
                  </div>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            <button
              type="button"
              onClick={handleSwitchFlowAccount}
              disabled={switchingFlowAccount}
              className="px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-black text-xs font-black flex items-center gap-1.5 shadow-lg"
            >
              <RefreshCw className={`w-4 h-4 ${switchingFlowAccount ? 'animate-spin' : ''}`} />
              <span>🔄 Mở Đăng Nhập Tài Khoản Mới</span>
            </button>
            <button
              type="button"
              onClick={handleResumeSavedSession}
              disabled={resumingSession || runningFullAuto}
              className="px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-black flex items-center gap-1.5 shadow-lg"
            >
              {resumingSession ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              <span>Đã Đổi Xong &rarr; Tiếp Tục Phiên Ngay</span>
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          QUEUE TOAST NOTIFICATION WHEN ADDING MORE PRODUCTS
          ========================================================================= */}
      {queueToast && (
        <div className="p-3.5 rounded-2xl bg-gradient-to-r from-emerald-500/20 via-teal-500/20 to-cyan-500/20 border-2 border-emerald-400/70 shadow-lg flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2.5 text-xs font-extrabold text-emerald-100">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{queueToast.message}</span>
          </div>
          <div className="flex items-center gap-2">
            {queueToast.projectId && queueToast.projectId !== effectiveId && (
              <button
                type="button"
                onClick={() => {
                  const target = queueToast.projectId!;
                  setQueueToast(null);
                  handleSelectProjectInStudio(target);
                }}
                className="px-3 py-1 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black text-[11px] font-black transition-colors"
              >
                👁 Xem dự án vừa thêm
              </button>
            )}
            <button
              type="button"
              onClick={() => setQueueToast(null)}
              className="p-1 rounded-lg text-slate-300 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          BANNER 3: MULTI-PRODUCT BATCH QUEUE PROGRESS (1 IMAGE = 1 20S VIDEO)
          ========================================================================= */}
      {sessionState?.batch_projects && (sessionState.batch_projects.length > 1 || sessionState.batch_state?.active) && (() => {
        const batchList: any[] = sessionState.batch_projects || [];
        const completedCount = batchList.filter(
          (bp: any) =>
            bp.status === 'completed' ||
            bp.has_export ||
            (sessionState.batch_state?.completed_ids || []).includes(bp.id)
        ).length;
        const activeRunId = sessionState.running_project_id || sessionState.batch_state?.current_project_id;
        const runningItem = batchList.find((bp: any) => bp.id === activeRunId);

        return (
          <div className="p-4 rounded-2xl bg-gradient-to-b from-[#181d29] to-[#131722] border-2 border-pink-500/40 shadow-xl space-y-3.5">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 border-b border-[#252d40] pb-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <Sparkles className={`w-4 h-4 text-pink-400 ${activeRunId ? 'animate-spin' : ''}`} />
                  <span className="text-xs font-black text-white uppercase tracking-wider">
                    📦 HÀNG ĐỢI SẢN XUẤT NHIỀU SẢN PHẨM ({completedCount}/{batchList.length} VIDEO 20 GIÂY HOÀN THÀNH)
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 font-bold">
                    Nhấp vào sản phẩm bất kỳ để xem &bull; Giữ nguyên màn hình đang chọn
                  </span>
                </div>
                <div className="text-[11px] text-slate-300 flex items-center gap-2 flex-wrap">
                  {runningItem ? (
                    <span>
                      🤖 Đang sản xuất tự động:{' '}
                      <b className="text-pink-300">{runningItem.name}</b> ({runningItem.step_name || 'Đang xử lý...'} - {runningItem.progress_percent || 15}%)
                    </span>
                  ) : completedCount === batchList.length ? (
                    <span className="text-emerald-300 font-bold">
                      ✅ Đã hoàn thành toàn bộ {batchList.length} sản phẩm trong hàng đợi!
                    </span>
                  ) : (
                    <span>Chọn sản phẩm bên dưới để kiểm tra kịch bản, ảnh nhân vật hoặc tải video.</span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 flex-wrap shrink-0">
                {sessionState.batch_state?.paused_for_login && (
                  <span className="text-[11px] px-2.5 py-1 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold">
                    ⏸ Chờ đổi TK Video AI
                  </span>
                )}
                <button
                  type="button"
                  onClick={handlePasteAsNewProject}
                  disabled={uploadingNewProduct}
                  className="px-3 py-1.5 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-[11px] font-extrabold flex items-center gap-1.5 transition-all"
                  title="Dán thêm ảnh sản phẩm từ Clipboard vào hàng đợi"
                >
                  <ClipboardPaste className="w-3.5 h-3.5" />
                  <span>+ Dán thêm SP (Ctrl+V)</span>
                </button>
                <label className="px-3 py-1.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-[11px] font-extrabold flex items-center gap-1.5 cursor-pointer transition-all">
                  <Upload className="w-3.5 h-3.5" />
                  <span>+ Thêm nhiều SP</span>
                  <input type="file" accept="image/*" multiple onChange={handleQuickNewProjectUpload} className="hidden" />
                </label>
                <button
                  type="button"
                  onClick={handleClearBatchQueue}
                  className="px-2.5 py-1.5 rounded-xl bg-[#232a3b] hover:bg-rose-500/20 text-slate-300 hover:text-rose-300 border border-[#2e374d] text-[11px] font-bold flex items-center gap-1 transition-all"
                  title="Thu gọn danh sách hàng đợi đã hoàn thành"
                >
                  <X className="w-3.5 h-3.5" />
                  <span>Thu gọn</span>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2.5 max-h-[230px] overflow-y-auto pr-1">
              {batchList.map((bp: any, idx: number) => {
                const isViewing = bp.id === effectiveId;
                const isDone =
                  bp.status === 'completed' ||
                  bp.has_export ||
                  (sessionState.batch_state?.completed_ids || []).includes(bp.id);
                const needsName =
                  bp.status === 'needs_product_name' ||
                  bp.task_status === 'waiting_product_name' ||
                  (bp.name || '').includes('Cần nhập tên');
                const isQueued =
                  !isDone &&
                  bp.step_name === 'Đang chờ tới lượt' &&
                  bp.id !== activeRunId;
                const isRunningNow =
                  !isDone &&
                  !isQueued &&
                  (bp.id === activeRunId || bp.task_status === 'running');
                const pct = isDone ? 100 : (bp.progress_percent || (isRunningNow ? 15 : isQueued ? 5 : 0));
                const thumbUrl = getMediaUrlForProject(
                  bp.id,
                  bp.primary_character_image_path || bp.original_image_path,
                  bp.primary_character_image_path ? 'character' : 'product'
                );

                return (
                  <button
                    key={bp.id}
                    type="button"
                    onClick={() => handleSelectProjectInStudio(bp.id)}
                    className={`p-2.5 rounded-xl text-left flex items-center gap-2.5 border-2 transition-all relative overflow-hidden ${
                      isViewing
                        ? 'bg-gradient-to-r from-pink-500/25 via-purple-500/20 to-cyan-500/20 border-pink-400 shadow-lg shadow-pink-500/15 ring-1 ring-pink-400/50'
                        : isRunningNow
                          ? 'bg-[#161c2a] border-cyan-400/70 hover:border-cyan-300'
                          : isDone
                            ? 'bg-emerald-500/10 border-emerald-500/35 hover:border-emerald-400'
                            : needsName
                              ? 'bg-amber-500/15 border-amber-400 animate-pulse'
                              : 'bg-[#12161f] border-[#263044] hover:border-slate-500'
                    }`}
                  >
                    {/* Product / Character Thumbnail */}
                    <div className="w-11 h-14 rounded-lg bg-[#0d1017] border border-white/10 overflow-hidden shrink-0 flex items-center justify-center relative">
                      {thumbUrl ? (
                        <img
                          src={thumbUrl}
                          alt={bp.name}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                      ) : (
                        <ImageIcon className="w-4 h-4 text-slate-500" />
                      )}
                      <span className="absolute top-0.5 left-0.5 px-1 py-0.2 rounded bg-black/80 text-[9px] font-black text-white">
                        #{idx + 1}
                      </span>
                    </div>

                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-xs font-extrabold text-white truncate" title={bp.name}>
                          {bp.name}
                        </span>
                        {isViewing && (
                          <span className="px-1.5 py-0.5 rounded bg-pink-500 text-white text-[9px] font-black shrink-0 uppercase">
                            👁 Đang xem
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-1.5 text-[10px] font-bold">
                        {isDone ? (
                          <span className="text-emerald-300 flex items-center gap-1 truncate">
                            <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                            <span>Hoàn thành Video 20s</span>
                          </span>
                        ) : needsName ? (
                          <span className="text-amber-300 flex items-center gap-1 truncate">
                            <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
                            <span>Cần nhập tên SP</span>
                          </span>
                        ) : isRunningNow ? (
                          <span className="text-cyan-300 flex items-center gap-1 truncate">
                            <Loader2 className="w-3 h-3 text-pink-400 animate-spin shrink-0" />
                            <span className="truncate">{bp.step_name || 'Đang chạy...'} ({pct}%)</span>
                          </span>
                        ) : isQueued ? (
                          <span className="text-indigo-300 flex items-center gap-1 truncate">
                            <RefreshCw className="w-3 h-3 text-indigo-400 shrink-0" />
                            <span>⏳ Chờ tới lượt ({bp.video_count || 0}/2 video)</span>
                          </span>
                        ) : (
                          <span className="text-slate-400 truncate">
                            {bp.step_name || bp.status}
                          </span>
                        )}
                      </div>

                      {/* Mini Progress Bar */}
                      <div className="w-full h-1.5 rounded-full bg-black/40 overflow-hidden">
                        <div
                          className={`h-full transition-all duration-500 ${
                            isDone
                              ? 'bg-emerald-400'
                              : needsName
                                ? 'bg-amber-400'
                                : isRunningNow
                                  ? 'bg-gradient-to-r from-pink-500 to-cyan-400'
                                  : 'bg-indigo-500/60'
                          }`}
                          style={{ width: `${Math.max(5, Math.min(100, pct))}%` }}
                        />
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* =========================================================================
          2 TOP-LEVEL SEPARATE MODE TABS: CHẾ ĐỘ THỦ CÔNG vs CHẾ ĐỘ TỰ ĐỘNG
          ========================================================================= */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-2 rounded-2xl bg-[#12161f] border-2 border-[#232a3b]">
        <button
          type="button"
          onClick={() => handleSwitchStudioMode('manual')}
          className={`p-4 rounded-xl text-left transition-all flex items-center justify-between gap-3 border-2 ${
            studioMode === 'manual'
              ? 'bg-gradient-to-r from-amber-500/20 via-pink-500/15 to-cyan-500/20 border-amber-400 shadow-lg shadow-amber-500/15'
              : 'bg-[#181d29]/60 border-transparent hover:border-[#2a3449] opacity-75 hover:opacity-100'
          }`}
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-md bg-amber-500 text-black text-[11px] font-black uppercase tracking-wider">
                TAB 1 • CHẾ ĐỘ THỦ CÔNG
              </span>
              {studioMode === 'manual' && (
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/40">
                  Đang mở
                </span>
              )}
            </div>
            <div className="text-sm font-extrabold text-white">
              Auto Tạo Ảnh Nhân Vật & Prompt &rarr; Copy Đưa Qua Nền Tảng Khác &rarr; Dán 2 Video Ghép Ngay
            </div>
          </div>
          <Wand2 className={`w-6 h-6 shrink-0 ${studioMode === 'manual' ? 'text-amber-400' : 'text-slate-500'}`} />
        </button>

        <button
          type="button"
          onClick={() => handleSwitchStudioMode('auto')}
          className={`p-4 rounded-xl text-left transition-all flex items-center justify-between gap-3 border-2 ${
            studioMode === 'auto'
              ? 'bg-gradient-to-r from-pink-500/20 via-purple-500/15 to-cyan-500/20 border-pink-500 shadow-lg shadow-pink-500/15'
              : 'bg-[#181d29]/60 border-transparent hover:border-[#2a3449] opacity-75 hover:opacity-100'
          }`}
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-md bg-pink-500 text-white text-[11px] font-black uppercase tracking-wider">
                TAB 2 • CHẾ ĐỘ TỰ ĐỘNG
              </span>
              {studioMode === 'auto' && (
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/40">
                  Đang mở
                </span>
              )}
            </div>
            <div className="text-sm font-extrabold text-white">
              Tự Động Hóa Toàn Bộ A-Z (Gemini + Google Flow Veo 3 + Ghép FFmpeg)
            </div>
          </div>
          <Sparkles className={`w-6 h-6 shrink-0 ${studioMode === 'auto' ? 'text-pink-400' : 'text-slate-500'}`} />
        </button>
      </div>

      {/* Sub-tabs ONLY shown when in TAB 2: CHẾ ĐỘ TỰ ĐỘNG */}
      {studioMode === 'auto' && (
        <>
          {runningFullAuto && (
            <div className="p-4 rounded-2xl bg-gradient-to-r from-pink-500/20 via-purple-500/20 to-cyan-500/20 border-2 border-pink-400/60 shadow-lg flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <Loader2 className="w-6 h-6 text-pink-300 animate-spin shrink-0" />
                <div>
                  <div className="text-sm font-black text-white">
                    🤖 ĐANG CHẠY TỰ ĐỘNG: {pipelineTask?.step_name?.toUpperCase() || 'XỬ LÝ DỰ ÁN'}...
                  </div>
                  <div className="text-xs text-pink-100 mt-0.5">
                    {pipelineTask?.message || 'Đang tự động phân tích ảnh sản phẩm, tạo nhân vật AI, viết prompt và sản xuất video...'}
                  </div>
                </div>
              </div>
              <span className="px-3 py-1 rounded-full bg-pink-500/30 text-pink-200 text-xs font-black border border-pink-400/50">
                {pipelineTask?.progress_percent || 15}%
              </span>
            </div>
          )}

          {!runningFullAuto && pipelineTask?.step_name === 'Đang chờ tới lượt' && project.status !== 'completed' && (
            <div className="p-4 rounded-2xl bg-gradient-to-r from-indigo-500/20 via-cyan-500/15 to-purple-500/20 border-2 border-indigo-400/60 shadow-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <RefreshCw className="w-5 h-5 text-indigo-300 animate-spin shrink-0" />
                <div>
                  <div className="text-sm font-black text-white">
                    ⏳ SẢN PHẨM NÀY ĐANG TRONG HÀNG ĐỢI — CHỜ TỚI LƯỢT SẢN XUẤT TỰ ĐỘNG
                  </div>
                  <div className="text-xs text-indigo-100 mt-0.5">
                    {pipelineTask?.message || 'Hệ thống đang hoàn tất sản phẩm đứng trước trong hàng đợi rồi sẽ tự động chạy sang sản phẩm này.'}
                  </div>
                </div>
              </div>
              {sessionState?.running_project_id && sessionState.running_project_id !== effectiveId && (
                <button
                  type="button"
                  onClick={() => handleSelectProjectInStudio(sessionState.running_project_id)}
                  className="px-3.5 py-2 rounded-xl bg-pink-500 hover:bg-pink-400 text-white text-xs font-black shrink-0 transition-colors"
                >
                  👁 Xem dự án đang chạy
                </button>
              )}
            </div>
          )}

          {/* Interactive Progress Stepper */}
          <div className="bg-[#181d29] border border-[#232a3b] p-3.5 rounded-2xl shadow-lg">
            <div className="flex items-center justify-between overflow-x-auto pb-1 gap-2">
              {steps.map((st, i) => (
                <div key={st.id} className="flex items-center shrink-0">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                        st.done
                          ? 'bg-emerald-500 text-white shadow-md shadow-emerald-500/30'
                          : 'bg-[#12161f] text-slate-500 border border-[#232a3b]'
                      }`}
                    >
                      {st.done ? <Check className="w-3.5 h-3.5" /> : st.id}
                    </div>
                    <span className={`text-xs whitespace-nowrap ${st.done ? 'text-slate-200 font-semibold' : 'text-slate-500'}`}>
                      {st.label}
                    </span>
                  </div>
                  {i < steps.length - 1 && (
                    <div className={`w-6 h-0.5 mx-2 ${st.done ? 'bg-emerald-500/50' : 'bg-[#232a3b]'}`} />
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2 overflow-x-auto border-b border-[#232a3b]">
            <button
              onClick={() => setActiveTab('character')}
              className={`pb-3 px-3 text-sm font-bold flex items-center gap-2 border-b-2 transition-all whitespace-nowrap pt-2 ${
                activeTab === 'character'
                  ? 'border-pink-500 text-pink-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <span className="w-5 h-5 rounded-full bg-pink-500/20 text-pink-400 text-xs flex items-center justify-center">1</span>
              <span>Tạo Nhân Vật AI (Gemini)</span>
            </button>

            <button
              onClick={() => setActiveTab('scripts')}
              className={`pb-3 px-3 text-sm font-bold flex items-center gap-2 border-b-2 transition-all whitespace-nowrap pt-2 ${
                activeTab === 'scripts'
                  ? 'border-purple-500 text-purple-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <span className="w-5 h-5 rounded-full bg-purple-500/20 text-purple-400 text-xs flex items-center justify-center">2</span>
              <span>Kịch Bản & Prompt Video</span>
            </button>

            <button
              onClick={() => setActiveTab('flow')}
              className={`pb-3 px-3 text-sm font-bold flex items-center gap-2 border-b-2 transition-all whitespace-nowrap pt-2 ${
                activeTab === 'flow'
                  ? 'border-cyan-500 text-cyan-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-400 text-xs flex items-center justify-center">3</span>
              <span>Sản Xuất Video (Google Flow)</span>
            </button>

            <button
              onClick={() => setActiveTab('stitch')}
              className={`pb-3 px-3 text-sm font-bold flex items-center gap-2 border-b-2 transition-all whitespace-nowrap pt-2 ${
                activeTab === 'stitch'
                  ? 'border-emerald-500 text-emerald-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs flex items-center justify-center">4</span>
              <span>Ghép Video (FFmpeg)</span>
            </button>
          </div>
        </>
      )}

      {/* =========================================================================
          TAB 1: CHẾ ĐỘ THỦ CÔNG (HOẠT ĐỘNG ĐỘC LẬP HOÀN TOÀN)
          (Auto Tạo Ảnh Nhân Vật & Prompt -> Copy Đưa Qua Nền Tảng Khác -> Dán 2 Video -> Ghép Ngay)
          ========================================================================= */}
      {studioMode === 'manual' && (
        <div className="space-y-8">
          {/* Auto-Generation Live Status Banner */}
          {runningFullAuto ? (
            <div className="p-4 rounded-2xl bg-gradient-to-r from-cyan-500/20 via-pink-500/20 to-amber-500/20 border-2 border-cyan-400/60 shadow-lg flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <Loader2 className="w-6 h-6 text-cyan-300 animate-spin shrink-0" />
                <div>
                  <div className="text-sm font-black text-white">
                    🤖 ĐANG TỰ ĐỘNG NHẬN DIỆN SẢN PHẨM, TẠO ẢNH NHÂN VẬT 9:16 & VIẾT PROMPT (KHÔNG CẦN BẤM)...
                  </div>
                  <div className="text-xs text-cyan-200 mt-0.5">
                    {pipelineTask?.message || 'Đang phân tích ảnh sản phẩm và tạo ảnh nhân vật AI + Prompt 2 cảnh phù hợp với sản phẩm...'}
                  </div>
                </div>
              </div>
              <span className="px-3 py-1 rounded-full bg-cyan-500/30 text-cyan-200 text-xs font-black border border-cyan-400/50">
                {pipelineTask?.progress_percent || 25}%
              </span>
            </div>
          ) : (
            <div className="p-4 rounded-2xl bg-gradient-to-r from-emerald-500/15 via-amber-500/10 to-cyan-500/15 border border-emerald-500/40 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="text-sm font-extrabold text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>ĐÃ TỰ ĐỘNG TẠO ẢNH NHÂN VẬT 9:16 & PROMPT CHUẨN THEO SẢN PHẨM: {project.name.toUpperCase()}</span>
                </div>
                <p className="text-xs text-slate-300">
                  Chỉ cần bấm các nút nổi bật: <b>1. COPY ẢNH NHÂN VẬT</b> &rarr; <b>2. COPY PROMPT CẢNH 1 & CẢNH 2</b> đưa qua nền tảng tạo video &rarr; <b>3. DÁN 2 VIDEO & GHÉP NGAY</b>!
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <a
                  href="https://labs.google/fx/vi/tools/flow"
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 text-xs font-bold border border-cyan-500/40 flex items-center gap-1.5"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Mở Google Flow</span>
                </a>
                <a
                  href="https://dreamina.capcut.com"
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-2 rounded-xl bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 text-xs font-bold border border-purple-500/40 flex items-center gap-1.5"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Mở Dreamina</span>
                </a>
                <a
                  href="https://klingai.com"
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-2 rounded-xl bg-pink-500/20 hover:bg-pink-500/30 text-pink-300 text-xs font-bold border border-pink-500/40 flex items-center gap-1.5"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Mở Kling AI</span>
                </a>
              </div>
            </div>
          )}

          {/* SECTION 1: PRODUCT & AI CHARACTER IMAGE WITH HIGHLIGHTED DOWNLOAD & COPY BUTTONS */}
          <div className="p-6 rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#232a3b] pb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-pink-500 text-white text-xs font-extrabold flex items-center justify-center">1</span>
                  <span>Ảnh Sản Phẩm & Ảnh Nhân Vật AI Đứng Giới Thiệu (Tự Động Tạo Khi Đưa Sản Phẩm Vào)</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Khi bạn đưa ảnh sản phẩm vào, hệ thống <b>tự động tạo ảnh Nhân vật AI 9:16 và viết Prompt theo đúng sản phẩm</b> mà không cần bấm thêm nút.
                </p>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <label className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white text-xs font-black cursor-pointer flex items-center gap-1.5 shadow-lg shadow-amber-500/25">
                  <Upload className="w-4 h-4" />
                  <span>{uploadingNewProduct ? 'Đang tự động xử lý...' : '📥 Đưa Ảnh Sản Phẩm Vào (Tự Động Tạo)'}</span>
                  <input type="file" accept="image/*" onChange={handleReplaceProductUpload} className="hidden" />
                </label>

                <label className="px-3.5 py-2 rounded-xl bg-[#12161f] hover:bg-[#232a3b] text-slate-200 text-xs font-semibold border border-[#232a3b] cursor-pointer flex items-center gap-1.5">
                  <Upload className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Tải ảnh nhân vật riêng</span>
                  <input type="file" accept="image/*" onChange={handleManualCharacterUpload} className="hidden" />
                </label>

                <button
                  onClick={handleGenerateCharacter}
                  disabled={generatingChar}
                  className="px-3.5 py-2 rounded-xl bg-[#12161f] hover:bg-[#232a3b] text-cyan-300 text-xs font-bold border border-cyan-500/30 flex items-center gap-1.5 disabled:opacity-50"
                >
                  {generatingChar ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Đang tạo lại...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Tạo Lại Nhân Vật Bằng Gemini</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Product Name & Key Benefits Quick Input Bar (Auto-Synced, No Click Needed) */}
            <div className="p-4 rounded-xl bg-[#12161f] border border-amber-500/30 grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
              <div className="md:col-span-5 space-y-1">
                <label className="text-[11px] font-bold text-amber-300 flex items-center justify-between">
                  <span>Tên sản phẩm (Đã tự động nhận diện theo ảnh sản phẩm):</span>
                  <span className="text-[10px] text-emerald-400">Tự động cập nhật vào Prompt</span>
                </label>
                <input
                  type="text"
                  value={manualProductName}
                  onChange={(e) => setManualProductName(e.target.value)}
                  placeholder="VD: Ấm Đun Siêu Tốc Inox 1.8L..."
                  className="w-full px-3 py-2 rounded-lg bg-[#181d29] border border-[#232a3b] text-xs font-bold text-white focus:border-amber-400 focus:outline-none"
                />
              </div>
              <div className="md:col-span-7 space-y-1">
                <label className="text-[11px] font-bold text-amber-300 flex items-center justify-between">
                  <span>Công năng & Lợi ích chính của sản phẩm (Đánh mạnh trong lời thoại & Prompt):</span>
                  {preparingManual && <span className="text-[10px] text-cyan-400 animate-pulse">Đang tự động đồng bộ Prompt...</span>}
                </label>
                <input
                  type="text"
                  value={manualProductBenefits}
                  onChange={(e) => setManualProductBenefits(e.target.value)}
                  placeholder="VD: Đun sôi nước cực nhanh trong vài phút, thân inox 304 an toàn sức khỏe, tự ngắt thông minh..."
                  className="w-full px-3 py-2 rounded-lg bg-[#181d29] border border-[#232a3b] text-xs text-white focus:border-amber-400 focus:outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Product Original */}
              <div
                tabIndex={0}
                onPaste={(e) => handlePasteImageEvent('product', e)}
                className="p-4 rounded-xl bg-[#12161f] border border-[#232a3b] focus:border-blue-400 outline-none space-y-3 flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-200 flex items-center gap-2">
                      <ImageIcon className="w-4 h-4 text-blue-400" />
                      <span>Ảnh Sản Phẩm Gốc ({project.name})</span>
                    </span>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handlePasteClipboardImage('product')}
                        disabled={pastingImageType === 'product'}
                        className="px-2 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-[10px] font-bold flex items-center gap-1"
                        title="Dán ảnh sản phẩm từ Clipboard (Ctrl+V)"
                      >
                        <ClipboardPaste className="w-3 h-3" />
                        <span>{copiedId === 'paste_img_product' ? 'Đã Dán!' : 'Dán Ảnh (Ctrl+V)'}</span>
                      </button>
                      {project.original_image_path && (
                        <button
                          type="button"
                          onClick={() => handleDeleteImage('product')}
                          disabled={deletingImage === 'product'}
                          className="px-2 py-1 rounded-lg bg-red-500/20 hover:bg-red-500/35 text-red-300 border border-red-500/40 text-[10px] font-bold flex items-center gap-1 transition-all"
                          title="Xóa ảnh sản phẩm vừa dán / tải lên"
                        >
                          <Trash2 className="w-3 h-3" />
                          <span>Xóa Ảnh</span>
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="w-full h-72 rounded-xl bg-black/60 border border-[#232a3b] overflow-hidden flex items-center justify-center p-2 relative">
                    {project.original_image_path ? (
                      <>
                        <img
                          src={getMediaUrl(project.original_image_path, 'product')}
                          alt="Product"
                          className="w-full h-full object-contain"
                        />
                        <button
                          type="button"
                          onClick={() => handleDeleteImage('product')}
                          disabled={deletingImage === 'product'}
                          className="absolute top-2 right-2 p-2 rounded-xl bg-red-600/90 hover:bg-red-500 text-white shadow-lg flex items-center gap-1 text-[11px] font-bold transition-all"
                          title="Xóa ảnh sản phẩm này"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span>Xóa</span>
                        </button>
                      </>
                    ) : (
                      <div className="text-center space-y-2 p-4">
                        <ImageIcon className="w-8 h-8 text-slate-600 mx-auto" />
                        <div className="text-xs text-slate-400 font-semibold">Chưa có ảnh sản phẩm</div>
                        <div className="text-[11px] text-slate-500">Bấm <b>Dán Ảnh (Ctrl+V)</b> hoặc <b>Đưa Ảnh Sản Phẩm Vào</b></div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2.5 pt-2">
                  <a
                    href={`/api/projects/${project.id}/download-product`}
                    download
                    className="py-3 px-3 rounded-xl bg-[#181d29] hover:bg-[#232a3b] text-white text-xs font-bold border border-[#232a3b] flex items-center justify-center gap-2 transition-all"
                  >
                    <Download className="w-4 h-4 text-blue-400" />
                    <span>Tải Ảnh Sản Phẩm</span>
                  </a>

                  <button
                    type="button"
                    onClick={() => handleCopyImage('product')}
                    className={`py-3 px-3 rounded-xl text-xs font-bold border flex items-center justify-center gap-2 transition-all ${
                      copiedId === 'img_product'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        : 'bg-blue-500/15 hover:bg-blue-500/25 text-blue-300 border-blue-500/30'
                    }`}
                  >
                    {copiedId === 'img_product' ? (
                      <>
                        <Check className="w-4 h-4 text-emerald-400" />
                        <span>Đã Copy Ảnh SP!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-4 h-4 text-blue-400" />
                        <span>Copy Ảnh Sản Phẩm</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* AI Character Image - SUPER HIGHLIGHTED */}
              <div
                tabIndex={0}
                onPaste={(e) => handlePasteImageEvent('character', e)}
                className="p-5 rounded-2xl bg-gradient-to-b from-pink-500/10 via-[#12161f] to-[#12161f] border-2 border-pink-500 outline-none space-y-3 shadow-2xl shadow-pink-500/15"
              >
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="text-xs font-extrabold text-white flex items-center gap-2">
                    <Bot className="w-4 h-4 text-pink-400" />
                    <span>Ảnh Nhân Vật AI Đứng Cùng Sản Phẩm (9:16)</span>
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => handlePasteClipboardImage('character')}
                      disabled={pastingImageType === 'character'}
                      className="px-2 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-[10px] font-bold flex items-center gap-1"
                      title="Dán ảnh nhân vật từ Clipboard (Ctrl+V)"
                    >
                      <ClipboardPaste className="w-3 h-3" />
                      <span>{copiedId === 'paste_img_character' ? 'Đã Dán!' : 'Dán Ảnh (Ctrl+V)'}</span>
                    </button>
                    {project.primary_character_image_path && (
                      <button
                        type="button"
                        onClick={() => handleDeleteImage('character')}
                        disabled={deletingImage === 'character'}
                        className="px-2 py-1 rounded-lg bg-red-500/20 hover:bg-red-500/35 text-red-300 border border-red-500/40 text-[10px] font-bold flex items-center gap-1 transition-all"
                        title="Xóa ảnh nhân vật vừa dán / tạo"
                      >
                        <Trash2 className="w-3 h-3" />
                        <span>Xóa Ảnh</span>
                      </button>
                    )}
                    <span className="text-[10px] px-2.5 py-1 rounded-full bg-amber-500 text-black font-black uppercase tracking-wide shadow">
                      🔥 BƯỚC 1: COPY ẢNH NÀY
                    </span>
                  </div>
                </div>

                <div className="w-full h-72 rounded-xl bg-black/60 border border-pink-500/40 overflow-hidden flex items-center justify-center p-2 relative">
                  {project.primary_character_image_path ? (
                    <>
                      <img
                        src={getMediaUrl(project.primary_character_image_path, 'character')}
                        alt="AI Character"
                        className="w-full h-full object-contain"
                      />
                      <button
                        type="button"
                        onClick={() => handleDeleteImage('character')}
                        disabled={deletingImage === 'character'}
                        className="absolute top-2 right-2 p-2 rounded-xl bg-red-600/90 hover:bg-red-500 text-white shadow-lg flex items-center gap-1 text-[11px] font-bold transition-all"
                        title="Xóa ảnh nhân vật này"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Xóa</span>
                      </button>
                    </>
                  ) : (
                    <div className="text-center space-y-2 text-slate-500 text-xs">
                      <Bot className="w-8 h-8 mx-auto text-slate-600" />
                      <div>Chưa có ảnh nhân vật AI</div>
                      <div className="text-[11px] text-slate-400">Bấm <b>Dán Ảnh (Ctrl+V)</b>, <b>Tải ảnh nhân vật riêng</b> hoặc <b>Tạo Lại Nhân Vật</b></div>
                    </div>
                  )}
                </div>

                {/* EXTRA PROMINENT HIGHLIGHTED DOWNLOAD & COPY BUTTONS FOR CHARACTER IMAGE */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                  <button
                    type="button"
                    onClick={() => handleCopyImage('character')}
                    className={`py-4 px-4 rounded-xl text-sm font-black uppercase tracking-wide flex items-center justify-center gap-2 transition-all transform hover:-translate-y-0.5 ring-2 ${
                      copiedId === 'img_character'
                        ? 'bg-emerald-500 text-white ring-emerald-300 shadow-xl shadow-emerald-500/40'
                        : 'bg-gradient-to-r from-pink-500 via-rose-500 to-amber-500 hover:from-pink-600 hover:to-amber-600 text-white ring-amber-300/80 shadow-xl shadow-pink-500/40'
                    }`}
                  >
                    {copiedId === 'img_character' ? (
                      <>
                        <Check className="w-5 h-5" />
                        <span>ĐÃ COPY ẢNH (CTRL+V)!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-5 h-5" />
                        <span>📋 COPY ẢNH NHÂN VẬT</span>
                      </>
                    )}
                  </button>

                  <a
                    href={`/api/projects/${project.id}/download-character`}
                    download
                    className="py-4 px-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white text-sm font-black uppercase tracking-wide ring-2 ring-cyan-300/70 shadow-xl shadow-cyan-500/30 flex items-center justify-center gap-2 transition-all transform hover:-translate-y-0.5"
                  >
                    <Download className="w-5 h-5" />
                    <span>⬇ TẢI ẢNH NHÂN VẬT</span>
                  </a>
                </div>
              </div>
            </div>
          </div>

          {/* PROMPT TẠO ẢNH NGƯỜI MẪU NỮ CAO CẤP (CHUẨN 9 PHẦN • GEMINI 9:16 8K) */}
          <div className="p-6 rounded-2xl bg-gradient-to-r from-pink-950/30 via-[#181d29] to-purple-950/30 border-2 border-pink-500/70 space-y-4 shadow-2xl shadow-pink-500/15">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#232a3b] pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-pink-500 to-rose-600 flex items-center justify-center text-white shadow-lg shadow-pink-500/30 shrink-0">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-base font-black text-white flex items-center gap-2 flex-wrap">
                    <span>PROMPT TẠO ẢNH NGƯỜI MẪU NỮ ĐỨNG CÙNG SẢN PHẨM (GEMINI 9:16 8K)</span>
                    <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-pink-500/25 text-pink-300 font-extrabold border border-pink-500/50 uppercase tracking-wide">
                      Chuẩn 9 Phần • Khóa 100% Sản Phẩm
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 mt-0.5">
                    Mẫu prompt chuẩn 9 phần độc quyền của bạn: Người mẫu nữ Việt Nam 21 tuổi, showroom thương mại cao cấp, khóa 100% chi tiết sản phẩm, chuẩn tỷ lệ 9:16 siêu nét 8K.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2.5 shrink-0 flex-wrap">
                <button
                  type="button"
                  onClick={() => setShowCharPromptText(!showCharPromptText)}
                  className="px-4 py-3 rounded-xl bg-[#12161f] hover:bg-[#232a3b] text-slate-200 text-xs font-bold border border-[#232a3b] flex items-center gap-2 transition-all shadow"
                >
                  {showCharPromptText ? <EyeOff className="w-4 h-4 text-pink-400" /> : <Eye className="w-4 h-4 text-pink-400" />}
                  <span>{showCharPromptText ? 'Thu gọn Prompt' : '👁 Xem Chi Tiết Prompt 9 Phần'}</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleCopyText(charPromptToUse, 'copy_char_prompt')}
                  className={`py-3.5 px-6 rounded-xl text-xs font-black uppercase tracking-wide flex items-center justify-center gap-2.5 shadow-xl transition-all transform hover:-translate-y-0.5 ring-2 ${
                    copiedId === 'copy_char_prompt'
                      ? 'bg-emerald-500 text-white ring-emerald-300 shadow-emerald-500/40'
                      : 'bg-gradient-to-r from-pink-500 via-rose-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white ring-pink-400/80 shadow-pink-500/35'
                  }`}
                >
                  {copiedId === 'copy_char_prompt' ? (
                    <>
                      <Check className="w-4 h-4" />
                      <span>ĐÃ COPY PROMPT NHÂN VẬT NỮ!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      <span>📋 COPY PROMPT TẠO NHÂN VẬT NỮ</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {showCharPromptText ? (
              <div className="space-y-2">
                <textarea
                  value={charPromptToUse}
                  onChange={(e) => setCustomCharPrompt(e.target.value)}
                  rows={14}
                  className="w-full p-4 rounded-xl bg-[#12161f] border border-pink-500/40 text-xs text-slate-200 font-mono leading-relaxed focus:border-pink-400 focus:outline-none shadow-inner"
                  placeholder="Nội dung prompt tạo ảnh người mẫu nữ 9:16..."
                />
                <div className="flex items-center justify-between text-[11px] text-slate-400 px-1">
                  <span>💡 Bạn có thể trực tiếp sửa prompt này hoặc bấm <b>Copy Prompt Tạo Nhân Vật Nữ</b> để dán vào Gemini.</span>
                  {customCharPrompt && (
                    <button
                      type="button"
                      onClick={() => setCustomCharPrompt('')}
                      className="text-pink-400 hover:text-pink-300 font-bold underline"
                    >
                      Khôi phục mẫu gốc
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div 
                onClick={() => setShowCharPromptText(true)}
                className="p-3.5 rounded-xl bg-[#12161f]/80 border border-dashed border-pink-500/30 hover:border-pink-500/60 cursor-pointer flex items-center justify-between text-xs text-slate-400 transition-all"
              >
                <div className="truncate max-w-2xl font-mono text-[11px] text-slate-300">
                  {charPromptToUse.substring(0, 160)}...
                </div>
                <span className="text-[11px] text-pink-400 font-bold shrink-0 ml-2">Bấm để mở xem toàn bộ 9 phần &rarr;</span>
              </div>
            )}
          </div>

          {/* SECTION 2: DEDICATED VIDEO GENERATION PROMPTS FOR EXTERNAL PLATFORMS (HIGHLIGHTED COPY PROMPT BUTTONS) */}
          <div className="p-6 rounded-2xl bg-[#181d29] border-2 border-purple-500/40 space-y-5 shadow-xl">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#232a3b] pb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-purple-500 text-white text-xs font-extrabold flex items-center justify-center">2</span>
                  <span>Prompt Tạo Video Đã Viết Chuẩn Theo Sản Phẩm: <span className="text-amber-300">{project.name}</span></span>
                </h3>
                <p className="text-xs text-slate-300 mt-0.5">
                  Prompt dưới đây đã được viết tự động bám sát công năng của <b>{project.name}</b> (kèm chuyển động nhân vật + lời thoại ≥ 42 từ nói trọn câu trong 10s). Bấm nút <b>COPY PROMPT</b> bên dưới để dán vào nền tảng tạo video!
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleSaveScript(selectedScriptTab)}
                  className="px-3.5 py-2 rounded-xl bg-[#12161f] hover:bg-[#232a3b] text-slate-200 text-xs font-semibold border border-[#232a3b] flex items-center gap-1.5"
                >
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  <span>{copiedId === 'save_script' ? 'Đã lưu!' : 'Lưu chỉnh sửa'}</span>
                </button>

                <button
                  onClick={handleGenerateScripts}
                  disabled={generatingScripts}
                  className="px-3.5 py-2 rounded-xl bg-[#12161f] hover:bg-[#232a3b] text-purple-300 text-xs font-bold border border-purple-500/30 flex items-center gap-1.5 disabled:opacity-50"
                >
                  {generatingScripts ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Đang viết lại...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Viết Lại Bằng Gemini</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Prompt Card Scene 1 */}
              <div className="p-5 rounded-2xl bg-[#12161f] border-2 border-cyan-500/60 space-y-4 shadow-xl shadow-cyan-500/10">
                <div className="flex items-center justify-between border-b border-[#232a3b] pb-3">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-1 rounded-md bg-cyan-500 text-black text-xs font-black">
                      CẢNH 1 (0s - 10s)
                    </span>
                    <span className="text-xs font-extrabold text-white">Nhân Vật Đứng Giới Thiệu {project.name}</span>
                  </div>
                  <WordCounterBadge text={currentScriptOpt.scene1_dialogue || ''} target={42} />
                </div>

                {/* HIGHLIGHTED COPY PROMPT + DIALOGUE BUTTON AT TOP OF CARD */}
                <button
                  type="button"
                  onClick={() => handleCopyText(buildCopyPayloadForScene(1), 'prompt_s1')}
                  className={`w-full py-4 px-4 rounded-xl text-sm font-black uppercase tracking-wide flex items-center justify-center gap-2.5 ring-2 transition-all transform hover:-translate-y-0.5 ${
                    copiedId === 'prompt_s1'
                      ? 'bg-emerald-500 text-white ring-emerald-300 shadow-xl shadow-emerald-500/40'
                      : 'bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-600 hover:from-cyan-600 hover:to-indigo-700 text-white ring-cyan-300/80 shadow-xl shadow-cyan-500/35'
                  }`}
                >
                  {copiedId === 'prompt_s1' ? (
                    <>
                      <Check className="w-5 h-5" />
                      <span>ĐÃ COPY CẢ PROMPT + LỜI THOẠI CẢNH 1!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-5 h-5" />
                      <span>📋 COPY PROMPT + LỜI THOẠI TẠO VIDEO CẢNH 1</span>
                    </>
                  )}
                </button>

                {/* Dialogue box */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-semibold text-slate-300">Lời thoại Cảnh 1 (≥ 42 từ • Nói trọn câu 10s):</label>
                    <button
                      type="button"
                      onClick={() => handleCopyText(currentScriptOpt.scene1_dialogue || '', 'dlg_s1')}
                      className="text-[11px] text-cyan-400 hover:text-cyan-300 font-bold flex items-center gap-1"
                    >
                      <Copy className="w-3 h-3" />
                      <span>{copiedId === 'dlg_s1' ? 'Đã copy lời thoại!' : 'Copy riêng lời thoại'}</span>
                    </button>
                  </div>
                  <textarea
                    rows={3}
                    value={currentScriptOpt.scene1_dialogue || ''}
                    onChange={(e) => handleScriptChange(selectedScriptTab, 'scene1_dialogue', e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-[#181d29] border border-[#232a3b] text-slate-200 text-xs focus:border-cyan-500 focus:outline-none leading-relaxed"
                  />
                </div>

                {/* Video Prompt box */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => handleCopyText(buildCopyPayloadForScene(1), 'prompt_s1')}
                      className="text-[11px] font-extrabold text-cyan-300 hover:text-cyan-200 flex items-center gap-1.5"
                    >
                      <Copy className="w-3.5 h-3.5 text-cyan-400" />
                      <span>PROMPT TẠO VIDEO CẢNH 1 (Dùng kèm Ảnh Nhân Vật AI - Bấm để Copy cả Thoại + Prompt):</span>
                    </button>
                  </div>
                  <textarea
                    rows={5}
                    value={currentScriptOpt.scene1_prompt_veo || ''}
                    onChange={(e) => handleScriptChange(selectedScriptTab, 'scene1_prompt_veo', e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-[#181d29] border border-cyan-500/40 text-white text-xs focus:border-cyan-400 focus:outline-none leading-relaxed font-mono"
                  />
                </div>

                {/* HIGHLIGHTED COPY PROMPT + DIALOGUE BUTTON AT BOTTOM OF CARD */}
                <button
                  type="button"
                  onClick={() => handleCopyText(buildCopyPayloadForScene(1), 'prompt_s1')}
                  className={`w-full py-3.5 px-4 rounded-xl text-xs font-black uppercase tracking-wide flex items-center justify-center gap-2 ring-2 transition-all ${
                    copiedId === 'prompt_s1'
                      ? 'bg-emerald-500 text-white ring-emerald-300 shadow-lg shadow-emerald-500/30'
                      : 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white ring-cyan-300/70 shadow-lg shadow-cyan-500/25'
                  }`}
                >
                  {copiedId === 'prompt_s1' ? (
                    <>
                      <Check className="w-4 h-4" />
                      <span>ĐÃ COPY CẢ THOẠI + PROMPT TẠO VIDEO CẢNH 1!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      <span>📋 PROMPT TẠO VIDEO CẢNH 1 (COPY CẢ THOẠI + PROMPT)</span>
                    </>
                  )}
                </button>
              </div>

              {/* Prompt Card Scene 2 */}
              <div className="p-5 rounded-2xl bg-[#12161f] border-2 border-pink-500/60 space-y-4 shadow-xl shadow-pink-500/10">
                <div className="flex items-center justify-between border-b border-[#232a3b] pb-3">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-1 rounded-md bg-pink-500 text-white text-xs font-black">
                      CẢNH 2 (10s - 20s)
                    </span>
                    <span className="text-xs font-extrabold text-white">Cận Cảnh Công Năng & Chốt Đơn Giỏ Hàng</span>
                  </div>
                  <WordCounterBadge text={currentScriptOpt.scene2_dialogue || ''} target={42} />
                </div>

                {/* HIGHLIGHTED COPY PROMPT + DIALOGUE BUTTON AT TOP OF CARD */}
                <button
                  type="button"
                  onClick={() => handleCopyText(buildCopyPayloadForScene(2), 'prompt_s2')}
                  className={`w-full py-4 px-4 rounded-xl text-sm font-black uppercase tracking-wide flex items-center justify-center gap-2.5 ring-2 transition-all transform hover:-translate-y-0.5 ${
                    copiedId === 'prompt_s2'
                      ? 'bg-emerald-500 text-white ring-emerald-300 shadow-xl shadow-emerald-500/40'
                      : 'bg-gradient-to-r from-pink-500 via-rose-500 to-amber-500 hover:from-pink-600 hover:to-amber-600 text-white ring-pink-300/80 shadow-xl shadow-pink-500/35'
                  }`}
                >
                  {copiedId === 'prompt_s2' ? (
                    <>
                      <Check className="w-5 h-5" />
                      <span>ĐÃ COPY CẢ PROMPT + LỜI THOẠI CẢNH 2!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-5 h-5" />
                      <span>📋 COPY PROMPT + LỜI THOẠI TẠO VIDEO CẢNH 2</span>
                    </>
                  )}
                </button>

                {/* Dialogue box */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-semibold text-slate-300">Lời thoại Cảnh 2 (≥ 42 từ • Trọn câu 10s & kêu gọi giỏ hàng):</label>
                    <button
                      type="button"
                      onClick={() => handleCopyText(currentScriptOpt.scene2_dialogue || '', 'dlg_s2')}
                      className="text-[11px] text-pink-400 hover:text-pink-300 font-bold flex items-center gap-1"
                    >
                      <Copy className="w-3 h-3" />
                      <span>{copiedId === 'dlg_s2' ? 'Đã copy lời thoại!' : 'Copy riêng lời thoại'}</span>
                    </button>
                  </div>
                  <textarea
                    rows={3}
                    value={currentScriptOpt.scene2_dialogue || ''}
                    onChange={(e) => handleScriptChange(selectedScriptTab, 'scene2_dialogue', e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-[#181d29] border border-[#232a3b] text-slate-200 text-xs focus:border-pink-500 focus:outline-none leading-relaxed"
                  />
                </div>

                {/* Video Prompt box */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => handleCopyText(buildCopyPayloadForScene(2), 'prompt_s2')}
                      className="text-[11px] font-extrabold text-pink-300 hover:text-pink-200 flex items-center gap-1.5"
                    >
                      <Copy className="w-3.5 h-3.5 text-pink-400" />
                      <span>PROMPT TẠO VIDEO CẢNH 2 (Dùng kèm Ảnh Nhân Vật hoặc Ảnh SP - Bấm để Copy cả Thoại + Prompt):</span>
                    </button>
                  </div>
                  <textarea
                    rows={5}
                    value={currentScriptOpt.scene2_prompt_veo || ''}
                    onChange={(e) => handleScriptChange(selectedScriptTab, 'scene2_prompt_veo', e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-[#181d29] border border-pink-500/40 text-white text-xs focus:border-pink-400 focus:outline-none leading-relaxed font-mono"
                  />
                </div>

                {/* HIGHLIGHTED COPY PROMPT + DIALOGUE BUTTON AT BOTTOM OF CARD */}
                <button
                  type="button"
                  onClick={() => handleCopyText(buildCopyPayloadForScene(2), 'prompt_s2')}
                  className={`w-full py-3.5 px-4 rounded-xl text-xs font-black uppercase tracking-wide flex items-center justify-center gap-2 ring-2 transition-all ${
                    copiedId === 'prompt_s2'
                      ? 'bg-emerald-500 text-white ring-emerald-300 shadow-lg shadow-emerald-500/30'
                      : 'bg-gradient-to-r from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 text-white ring-pink-300/70 shadow-lg shadow-pink-500/25'
                  }`}
                >
                  {copiedId === 'prompt_s2' ? (
                    <>
                      <Check className="w-4 h-4" />
                      <span>ĐÃ COPY CẢ THOẠI + PROMPT TẠO VIDEO CẢNH 2!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      <span>📋 PROMPT TẠO VIDEO CẢNH 2 (COPY CẢ THOẠI + PROMPT)</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* SECTION 3: PASTE / DRAG-AND-DROP 2 VIDEOS & 1-CLICK STITCH */}
          <div className="p-6 rounded-2xl bg-[#181d29] border-2 border-emerald-500/40 space-y-6 shadow-xl">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#232a3b] pb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-emerald-500 text-white text-xs font-extrabold flex items-center justify-center">3</span>
                  <span>Dán / Kéo Thả 2 Video Đã Tạo Vào Đây & Ghép Thành 1 Video Hoàn Chỉnh</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Sau khi tạo xong 2 video ở nền tảng ngoài, bạn chỉ cần <b>Kéo thả file video</b>, bấm <b>"Dán Video (Ctrl+V)"</b>, hoặc <b>"Chọn File Video"</b> vào Cảnh 1 và Cảnh 2 rồi bấm <b>GHÉP 2 VIDEO NGAY</b>!
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Drop/Paste Zone Scene 1 */}
              <div
                tabIndex={0}
                onDragOver={(e) => { e.preventDefault(); setDragOverScene(1); }}
                onDragLeave={() => setDragOverScene(null)}
                onDrop={(e) => handleDropVideo(1, e)}
                onPaste={(e) => handlePasteVideoEvent(1, e)}
                className={`p-5 rounded-2xl border-2 transition-all space-y-4 outline-none ${
                  dragOverScene === 1
                    ? 'bg-cyan-500/15 border-cyan-400 shadow-lg shadow-cyan-500/20'
                    : 'bg-[#12161f] border-[#2a3449] hover:border-cyan-500/50 focus:border-cyan-400'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-white flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
                    <span>VIDEO CẢNH 1 (0s - 10s)</span>
                  </span>
                  {scene1Video ? (
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 flex items-center gap-1">
                        <Check className="w-3 h-3" /> ĐÃ NẠP VIDEO CẢNH 1
                      </span>
                      <button
                        type="button"
                        onClick={() => handleDeleteSceneVideo(1)}
                        disabled={deletingVideo1}
                        className="px-2 py-0.5 rounded bg-red-500/20 hover:bg-red-500/35 text-red-300 border border-red-500/40 text-[10px] font-bold flex items-center gap-1 transition-all"
                        title="Xóa Video Cảnh 1 vừa dán / tải lên"
                      >
                        <Trash2 className="w-3 h-3" />
                        <span>Xóa</span>
                      </button>
                    </div>
                  ) : (
                    <span className="text-[10px] text-amber-400 font-semibold">Đang chờ nạp video...</span>
                  )}
                </div>

                {/* Video Preview */}
                <div className="w-full flex justify-center">
                  <div className="w-[210px] h-[372px] rounded-2xl bg-black border-2 border-[#2a3449] overflow-hidden flex items-center justify-center relative">
                    {uploadingVideo1 || pastingVideo1 ? (
                      <div className="text-center space-y-2 p-4">
                        <Loader2 className="w-8 h-8 text-cyan-400 animate-spin mx-auto" />
                        <div className="text-xs text-cyan-300 font-semibold">Đang nạp & chuẩn hóa 60fps...</div>
                      </div>
                    ) : scene1Video ? (
                      <>
                        <video
                          key={`manual-s1-${scene1Video.id || scene1Video.created_at}`}
                          src={`/data/projects/${project.id}/videos/scene1.mp4?v=${encodeURIComponent(scene1Video.id || scene1Video.created_at || '')}`}
                          controls
                          playsInline
                          className="w-full h-full object-cover"
                        />
                        <button
                          type="button"
                          onClick={() => handleDeleteSceneVideo(1)}
                          disabled={deletingVideo1}
                          className="absolute top-2 right-2 p-2 rounded-xl bg-red-600/90 hover:bg-red-500 text-white shadow-lg flex items-center gap-1 text-[11px] font-bold transition-all z-10"
                          title="Xóa Video Cảnh 1 vừa dán / nạp"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span>Xóa Video</span>
                        </button>
                      </>
                    ) : (
                      <div className="text-center p-4 space-y-2">
                        <Upload className="w-10 h-10 text-cyan-400/60 mx-auto" />
                        <div className="text-xs font-bold text-slate-200">Kéo & Thả Video Cảnh 1 Vào Đây</div>
                        <p className="text-[11px] text-slate-400">
                          Hoặc bấm <b>Dán Video (Ctrl+V)</b> / <b>Chọn File</b> bên dưới
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Paste / Upload / Delete Buttons */}
                <div className="grid grid-cols-2 gap-2">
                  <label className="py-2.5 px-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white text-xs font-bold cursor-pointer flex items-center justify-center gap-1.5 shadow-md shadow-cyan-500/20">
                    <Upload className="w-3.5 h-3.5" />
                    <span>Chọn File Video 1</span>
                    <input type="file" accept="video/mp4,video/*" onChange={(e) => handleManualVideoUpload(1, e)} className="hidden" />
                  </label>

                  <button
                    type="button"
                    onClick={() => handlePasteClipboardVideoButton(1)}
                    disabled={pastingVideo1 || uploadingVideo1}
                    className="py-2.5 px-3 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-bold flex items-center justify-center gap-1.5 transition-all"
                    title="Copy file video trong máy tính (Ctrl+C) rồi bấm nút này để dán vào"
                  >
                    <ClipboardPaste className="w-3.5 h-3.5" />
                    <span>{copiedId === 'paste_v1' ? 'Đã Dán Video 1!' : 'Dán Video (Ctrl+V)'}</span>
                  </button>
                </div>

                {scene1Video && (
                  <button
                    type="button"
                    onClick={() => handleDeleteSceneVideo(1)}
                    disabled={deletingVideo1}
                    className="w-full py-2 px-3 rounded-xl bg-red-500/15 hover:bg-red-500/25 text-red-300 border border-red-500/35 text-xs font-bold flex items-center justify-center gap-1.5 transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>{deletingVideo1 ? 'Đang xóa Video Cảnh 1...' : '🗑 Xóa Video Cảnh 1 Vừa Dán / Nạp'}</span>
                  </button>
                )}

                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    onClick={() => handleImportFlowVideo(1)}
                    disabled={importingVideo1}
                    className="text-[11px] text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1"
                  >
                    <Download className="w-3 h-3" />
                    <span>Lấy file .mp4 mới nhất từ Downloads</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleGenerateFastVideo(1)}
                    disabled={generatingFast1}
                    className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1"
                  >
                    <Zap className="w-3 h-3 text-amber-400" />
                    <span>Tạo nhanh từ ảnh (2s)</span>
                  </button>
                </div>
              </div>

              {/* Drop/Paste Zone Scene 2 */}
              <div
                tabIndex={0}
                onDragOver={(e) => { e.preventDefault(); setDragOverScene(2); }}
                onDragLeave={() => setDragOverScene(null)}
                onDrop={(e) => handleDropVideo(2, e)}
                onPaste={(e) => handlePasteVideoEvent(2, e)}
                className={`p-5 rounded-2xl border-2 transition-all space-y-4 outline-none ${
                  dragOverScene === 2
                    ? 'bg-pink-500/15 border-pink-400 shadow-lg shadow-pink-500/20'
                    : 'bg-[#12161f] border-[#2a3449] hover:border-pink-500/50 focus:border-pink-400'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-white flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-pink-400" />
                    <span>VIDEO CẢNH 2 (10s - 20s)</span>
                  </span>
                  {scene2Video ? (
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 flex items-center gap-1">
                        <Check className="w-3 h-3" /> ĐÃ NẠP VIDEO CẢNH 2
                      </span>
                      <button
                        type="button"
                        onClick={() => handleDeleteSceneVideo(2)}
                        disabled={deletingVideo2}
                        className="px-2 py-0.5 rounded bg-red-500/20 hover:bg-red-500/35 text-red-300 border border-red-500/40 text-[10px] font-bold flex items-center gap-1 transition-all"
                        title="Xóa Video Cảnh 2 vừa dán / tải lên"
                      >
                        <Trash2 className="w-3 h-3" />
                        <span>Xóa</span>
                      </button>
                    </div>
                  ) : (
                    <span className="text-[10px] text-amber-400 font-semibold">Đang chờ nạp video...</span>
                  )}
                </div>

                {/* Video Preview */}
                <div className="w-full flex justify-center">
                  <div className="w-[210px] h-[372px] rounded-2xl bg-black border-2 border-[#2a3449] overflow-hidden flex items-center justify-center relative">
                    {uploadingVideo2 || pastingVideo2 ? (
                      <div className="text-center space-y-2 p-4">
                        <Loader2 className="w-8 h-8 text-pink-400 animate-spin mx-auto" />
                        <div className="text-xs text-pink-300 font-semibold">Đang nạp & chuẩn hóa 60fps...</div>
                      </div>
                    ) : scene2Video ? (
                      <>
                        <video
                          key={`manual-s2-${scene2Video.id || scene2Video.created_at}`}
                          src={`/data/projects/${project.id}/videos/scene2.mp4?v=${encodeURIComponent(scene2Video.id || scene2Video.created_at || '')}`}
                          controls
                          playsInline
                          className="w-full h-full object-cover"
                        />
                        <button
                          type="button"
                          onClick={() => handleDeleteSceneVideo(2)}
                          disabled={deletingVideo2}
                          className="absolute top-2 right-2 p-2 rounded-xl bg-red-600/90 hover:bg-red-500 text-white shadow-lg flex items-center gap-1 text-[11px] font-bold transition-all z-10"
                          title="Xóa Video Cảnh 2 vừa dán / nạp"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span>Xóa Video</span>
                        </button>
                      </>
                    ) : (
                      <div className="text-center p-4 space-y-2">
                        <Upload className="w-10 h-10 text-pink-400/60 mx-auto" />
                        <div className="text-xs font-bold text-slate-200">Kéo & Thả Video Cảnh 2 Vào Đây</div>
                        <p className="text-[11px] text-slate-400">
                          Hoặc bấm <b>Dán Video (Ctrl+V)</b> / <b>Chọn File</b> bên dưới
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Paste / Upload / Delete Buttons */}
                <div className="grid grid-cols-2 gap-2">
                  <label className="py-2.5 px-3 rounded-xl bg-gradient-to-r from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 text-white text-xs font-bold cursor-pointer flex items-center justify-center gap-1.5 shadow-md shadow-pink-500/20">
                    <Upload className="w-3.5 h-3.5" />
                    <span>Chọn File Video 2</span>
                    <input type="file" accept="video/mp4,video/*" onChange={(e) => handleManualVideoUpload(2, e)} className="hidden" />
                  </label>

                  <button
                    type="button"
                    onClick={() => handlePasteClipboardVideoButton(2)}
                    disabled={pastingVideo2 || uploadingVideo2}
                    className="py-2.5 px-3 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-bold flex items-center justify-center gap-1.5 transition-all"
                    title="Copy file video trong máy tính (Ctrl+C) rồi bấm nút này để dán vào"
                  >
                    <ClipboardPaste className="w-3.5 h-3.5" />
                    <span>{copiedId === 'paste_v2' ? 'Đã Dán Video 2!' : 'Dán Video (Ctrl+V)'}</span>
                  </button>
                </div>

                {scene2Video && (
                  <button
                    type="button"
                    onClick={() => handleDeleteSceneVideo(2)}
                    disabled={deletingVideo2}
                    className="w-full py-2 px-3 rounded-xl bg-red-500/15 hover:bg-red-500/25 text-red-300 border border-red-500/35 text-xs font-bold flex items-center justify-center gap-1.5 transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>{deletingVideo2 ? 'Đang xóa Video Cảnh 2...' : '🗑 Xóa Video Cảnh 2 Vừa Dán / Nạp'}</span>
                  </button>
                )}

                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    onClick={() => handleImportFlowVideo(2)}
                    disabled={importingVideo2}
                    className="text-[11px] text-pink-400 hover:text-pink-300 font-semibold flex items-center gap-1"
                  >
                    <Download className="w-3 h-3" />
                    <span>Lấy file .mp4 mới nhất từ Downloads</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleGenerateFastVideo(2)}
                    disabled={generatingFast2}
                    className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1"
                  >
                    <Zap className="w-3 h-3 text-amber-400" />
                    <span>Tạo nhanh từ ảnh (2s)</span>
                  </button>
                </div>
              </div>
            </div>

            {/* BIG 1-CLICK MERGE BUTTON */}
            <div className="pt-2">
              <button
                type="button"
                onClick={handleStitch}
                disabled={stitching || !hasBothVideos}
                className="w-full py-4 rounded-2xl bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white text-sm font-black tracking-wide shadow-xl shadow-emerald-500/25 flex items-center justify-center gap-3 transition-all transform hover:-translate-y-0.5 disabled:opacity-40"
              >
                {stitching ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>ĐANG GHÉP NỐI 2 VIDEO CHUẨN TIKTOK 1080x1920 60FPS...</span>
                  </>
                ) : (
                  <>
                    <Combine className="w-5 h-5" />
                    <span>🎬 GHÉP 2 VIDEO LẠI VỚI NHAU NGAY (XUẤT VIDEO HOÀN CHỈNH 60FPS)</span>
                  </>
                )}
              </button>
            </div>

            {/* FINAL STITCHED VIDEO RESULT RIGHT INSIDE MANUAL FLOW */}
            {project.export && !hasBothVideos && (
              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <span>⚠️ Video ghép cũ trước đó không hợp lệ do thiếu Video Cảnh 2. Hệ thống yêu cầu phải có đủ 2 cảnh riêng biệt mới được ghép. Vui lòng tạo Cảnh 2 rồi bấm Ghép lại.</span>
                <button
                  type="button"
                  onClick={handleDeleteExportVideo}
                  disabled={deletingExport}
                  className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold shrink-0 text-xs"
                >
                  Xóa Video Ghép Lỗi
                </button>
              </div>
            )}
            {project.export && hasBothVideos && (
              <div className="p-6 rounded-2xl bg-gradient-to-br from-emerald-950/30 via-[#12161f] to-[#181d29] border-2 border-emerald-500/50 space-y-5">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#232a3b] pb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                      <CheckCircle2 className="w-6 h-6" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-white flex items-center gap-2">
                        <span>Video Hoàn Chỉnh Đã Ghép Xong!</span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-extrabold">
                          1080x1920 • 60 FPS
                        </span>
                      </h4>
                      <p className="text-xs text-slate-400">
                        Tệp: {project.export.file_name} &bull; Thời lượng: {project.export.duration}s
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 flex-wrap">
                    <a
                      href={`/api/ffmpeg/download/${project.id}/${project.export.file_name}`}
                      download
                      className="px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-extrabold flex items-center gap-2 shadow-lg shadow-emerald-500/25 transition-all"
                    >
                      <Download className="w-4 h-4" />
                      <span>TẢI VIDEO THÀNH PHẨM VỀ MÁY</span>
                    </a>

                    <button
                      onClick={handleOpenFolder}
                      className="px-4 py-2.5 rounded-xl bg-[#232a3b] hover:bg-[#2e374d] text-slate-200 text-xs font-semibold flex items-center gap-2"
                    >
                      <FolderOpen className="w-4 h-4 text-amber-400" />
                      <span>Mở Thư Mục</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleDeleteExportVideo}
                      disabled={deletingExport}
                      className="px-4 py-2.5 rounded-xl bg-red-500/20 hover:bg-red-500/35 text-red-300 border border-red-500/40 text-xs font-bold flex items-center gap-1.5 transition-all"
                    >
                      <Trash2 className="w-4 h-4" />
                      <span>{deletingExport ? 'Đang xóa...' : 'Xóa Video Ghép'}</span>
                    </button>
                  </div>
                </div>

                <div className="w-full flex justify-center">
                  <div className="w-[240px] h-[426px] rounded-3xl bg-black border-4 border-emerald-500/40 overflow-hidden shadow-2xl flex items-center justify-center relative">
                    <video
                      key={`export-${project.export.id || project.export.file_name}`}
                      src={`/data/projects/${project.id}/exports/${project.export.file_name}?v=${encodeURIComponent(project.export.id || '')}`}
                      controls
                      playsInline
                      className="w-full h-full object-cover"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 2 SUB-STEP 1: TẠO NHÂN VẬT AI (GEMINI)
          ========================================================================= */}
      {studioMode === 'auto' && activeTab === 'character' && (
        <div className="space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Bot className="w-5 h-5 text-cyan-400" />
                <span>Bước 1: Tạo Nhân Vật AI Thương Mại Đứng Cùng Sản Phẩm (Tỷ lệ 9:16)</span>
              </h3>
              <p className="text-xs text-slate-400">
                Giữ nguyên vẹn 100% đặc điểm nhận diện sản phẩm từ ảnh gốc, có nút Tải về và Copy ảnh trực tiếp vào Clipboard.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <label className="px-4 py-2.5 rounded-xl bg-[#181d29] hover:bg-[#232a3b] text-slate-300 text-xs font-semibold border border-[#232a3b] cursor-pointer flex items-center gap-2">
                <Upload className="w-4 h-4 text-cyan-400" />
                <span>Tải ảnh nhân vật thủ công</span>
                <input type="file" accept="image/*" onChange={handleManualCharacterUpload} className="hidden" />
              </label>

              <button
                onClick={handleGenerateCharacter}
                disabled={generatingChar}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#06b6d4] to-[#3b82f6] hover:from-[#0891b2] hover:to-[#2563eb] text-white text-xs font-bold shadow-lg shadow-cyan-500/20 flex items-center gap-2 transition-all disabled:opacity-50"
              >
                {generatingChar ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Đang tạo nhân vật AI...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>TẠO NHÂN VẬT AI BẰNG GEMINI</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {generatingChar && (
            <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs flex items-center gap-3">
              <Loader2 className="w-4 h-4 animate-spin shrink-0" />
              <div className="flex-1">
                <div className="font-semibold">{charProgressMsg || 'Đang xử lý trên trình duyệt Gemini...'}</div>
              </div>
            </div>
          )}

          {/* PROMPT TẠO ẢNH NGƯỜI MẪU NỮ CAO CẤP (CHUẨN 9 PHẦN • GEMINI 9:16 8K) */}
          <div className="p-6 rounded-2xl bg-gradient-to-r from-pink-950/30 via-[#181d29] to-purple-950/30 border-2 border-pink-500/70 space-y-4 shadow-2xl shadow-pink-500/15">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#232a3b] pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-pink-500 to-rose-600 flex items-center justify-center text-white shadow-lg shadow-pink-500/30 shrink-0">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-base font-black text-white flex items-center gap-2 flex-wrap">
                    <span>PROMPT TẠO ẢNH NGƯỜI MẪU NỮ ĐỨNG CÙNG SẢN PHẨM (GEMINI 9:16 8K)</span>
                    <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-pink-500/25 text-pink-300 font-extrabold border border-pink-500/50 uppercase tracking-wide">
                      Chuẩn 9 Phần • Khóa 100% Sản Phẩm
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 mt-0.5">
                    Mẫu prompt chuẩn 9 phần độc quyền của bạn: Người mẫu nữ Việt Nam 21 tuổi, showroom thương mại cao cấp, khóa 100% chi tiết sản phẩm, chuẩn tỷ lệ 9:16 siêu nét 8K.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2.5 shrink-0 flex-wrap">
                <button
                  type="button"
                  onClick={() => setShowCharPromptText(!showCharPromptText)}
                  className="px-4 py-3 rounded-xl bg-[#12161f] hover:bg-[#232a3b] text-slate-200 text-xs font-bold border border-[#232a3b] flex items-center gap-2 transition-all shadow"
                >
                  {showCharPromptText ? <EyeOff className="w-4 h-4 text-pink-400" /> : <Eye className="w-4 h-4 text-pink-400" />}
                  <span>{showCharPromptText ? 'Thu gọn Prompt' : '👁 Xem Chi Tiết Prompt 9 Phần'}</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleCopyText(charPromptToUse, 'copy_char_prompt_step1')}
                  className={`py-3.5 px-6 rounded-xl text-xs font-black uppercase tracking-wide flex items-center justify-center gap-2.5 shadow-xl transition-all transform hover:-translate-y-0.5 ring-2 ${
                    copiedId === 'copy_char_prompt_step1'
                      ? 'bg-emerald-500 text-white ring-emerald-300 shadow-emerald-500/40'
                      : 'bg-gradient-to-r from-pink-500 via-rose-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white ring-pink-400/80 shadow-pink-500/35'
                  }`}
                >
                  {copiedId === 'copy_char_prompt_step1' ? (
                    <>
                      <Check className="w-4 h-4" />
                      <span>ĐÃ COPY PROMPT NHÂN VẬT NỮ!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      <span>📋 COPY PROMPT TẠO NHÂN VẬT NỮ</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {showCharPromptText ? (
              <div className="space-y-2">
                <textarea
                  value={charPromptToUse}
                  onChange={(e) => setCustomCharPrompt(e.target.value)}
                  rows={14}
                  className="w-full p-4 rounded-xl bg-[#12161f] border border-pink-500/40 text-xs text-slate-200 font-mono leading-relaxed focus:border-pink-400 focus:outline-none shadow-inner"
                  placeholder="Nội dung prompt tạo ảnh người mẫu nữ 9:16..."
                />
                <div className="flex items-center justify-between text-[11px] text-slate-400 px-1">
                  <span>💡 Bạn có thể trực tiếp sửa prompt này hoặc bấm <b>Copy Prompt Tạo Nhân Vật Nữ</b> để dán vào Gemini.</span>
                  {customCharPrompt && (
                    <button
                      type="button"
                      onClick={() => setCustomCharPrompt('')}
                      className="text-pink-400 hover:text-pink-300 font-bold underline"
                    >
                      Khôi phục mẫu gốc
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div 
                onClick={() => setShowCharPromptText(true)}
                className="p-3.5 rounded-xl bg-[#12161f]/80 border border-dashed border-pink-500/30 hover:border-pink-500/60 cursor-pointer flex items-center justify-between text-xs text-slate-400 transition-all"
              >
                <div className="truncate max-w-2xl font-mono text-[11px] text-slate-300">
                  {charPromptToUse.substring(0, 160)}...
                </div>
                <span className="text-[11px] text-pink-400 font-bold shrink-0 ml-2">Bấm để mở xem toàn bộ 9 phần &rarr;</span>
              </div>
            )}
          </div>

          {/* Side-by-Side Images */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Box 1: Original Product Photo */}
            <div
              tabIndex={0}
              onPaste={(e) => handlePasteImageEvent('product', e)}
              className="p-5 rounded-2xl bg-[#181d29] border border-[#232a3b] focus:border-blue-400 outline-none space-y-4"
            >
              <div className="flex items-center justify-between border-b border-[#232a3b] pb-3">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-400" />
                  <span>Ảnh Sản Phẩm Ban Đầu (Gốc)</span>
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => handlePasteClipboardImage('product')}
                    disabled={pastingImageType === 'product'}
                    className="px-2 py-0.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-[10px] font-bold flex items-center gap-1"
                  >
                    <ClipboardPaste className="w-3 h-3" />
                    <span>{copiedId === 'paste_img_product' ? 'Đã Dán!' : 'Dán Ảnh (Ctrl+V)'}</span>
                  </button>
                  {project.original_image_path && (
                    <button
                      type="button"
                      onClick={() => handleDeleteImage('product')}
                      disabled={deletingImage === 'product'}
                      className="px-2 py-0.5 rounded bg-red-500/20 hover:bg-red-500/35 text-red-300 border border-red-500/40 text-[10px] font-bold flex items-center gap-1"
                    >
                      <Trash2 className="w-3 h-3" />
                      <span>Xóa Ảnh</span>
                    </button>
                  )}
                </div>
              </div>

              <div className="w-full h-96 rounded-xl bg-[#12161f] border border-[#232a3b] overflow-hidden flex items-center justify-center relative p-2">
                {project.original_image_path ? (
                  <>
                    <img
                      src={getMediaUrl(project.original_image_path, 'product')}
                      alt="Original"
                      className="w-full h-full object-contain"
                    />
                    <button
                      type="button"
                      onClick={() => handleDeleteImage('product')}
                      disabled={deletingImage === 'product'}
                      className="absolute top-2 right-2 p-2 rounded-xl bg-red-600/90 hover:bg-red-500 text-white shadow-lg flex items-center gap-1 text-[11px] font-bold transition-all"
                      title="Xóa ảnh sản phẩm này"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Xóa</span>
                    </button>
                  </>
                ) : (
                  <div className="text-center space-y-2 text-slate-500 text-xs">
                    <ImageIcon className="w-8 h-8 mx-auto text-slate-600" />
                    <div>Chưa có ảnh sản phẩm</div>
                    <div className="text-[11px] text-slate-500">Bấm "Dán Ảnh (Ctrl+V)" hoặc "Đưa Sản Phẩm Mới Vào"</div>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <a
                  href={`/api/projects/${project.id}/download-product`}
                  download
                  className="py-2.5 px-3 rounded-xl bg-[#12161f] hover:bg-[#232a3b] text-slate-200 text-xs font-bold border border-[#232a3b] flex items-center justify-center gap-2"
                >
                  <Download className="w-4 h-4 text-blue-400" />
                  <span>Tải Ảnh Sản Phẩm</span>
                </a>
                <button
                  type="button"
                  onClick={() => handleCopyImage('product')}
                  className="py-2.5 px-3 rounded-xl bg-[#12161f] hover:bg-[#232a3b] text-slate-200 text-xs font-bold border border-[#232a3b] flex items-center justify-center gap-2"
                >
                  <Copy className="w-4 h-4 text-blue-400" />
                  <span>{copiedId === 'img_product' ? 'Đã Copy Ảnh SP!' : 'Copy Ảnh Sản Phẩm'}</span>
                </button>
              </div>
            </div>

            {/* Box 2: Primary AI Character Photo */}
            <div
              tabIndex={0}
              onPaste={(e) => handlePasteImageEvent('character', e)}
              className="p-5 rounded-2xl bg-[#181d29] border border-[#232a3b] focus:border-pink-400 outline-none space-y-4"
            >
              <div className="flex items-center justify-between border-b border-[#232a3b] pb-3">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-pink-400" />
                  <span>Ảnh Nhân Vật AI Tham Chiếu Chính (9:16)</span>
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => handlePasteClipboardImage('character')}
                    disabled={pastingImageType === 'character'}
                    className="px-2 py-0.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-[10px] font-bold flex items-center gap-1"
                  >
                    <ClipboardPaste className="w-3 h-3" />
                    <span>{copiedId === 'paste_img_character' ? 'Đã Dán!' : 'Dán Ảnh (Ctrl+V)'}</span>
                  </button>
                  {project.primary_character_image_path && (
                    <button
                      type="button"
                      onClick={() => handleDeleteImage('character')}
                      disabled={deletingImage === 'character'}
                      className="px-2 py-0.5 rounded bg-red-500/20 hover:bg-red-500/35 text-red-300 border border-red-500/40 text-[10px] font-bold flex items-center gap-1"
                    >
                      <Trash2 className="w-3 h-3" />
                      <span>Xóa Ảnh</span>
                    </button>
                  )}
                </div>
              </div>

              <div className="w-full h-96 rounded-xl bg-[#12161f] border border-[#232a3b] overflow-hidden flex items-center justify-center relative p-2">
                {project.primary_character_image_path ? (
                  <>
                    <img
                      src={getMediaUrl(project.primary_character_image_path, 'character')}
                      alt="Primary AI Character"
                      className="w-full h-full object-contain"
                      onError={(e) => {
                        if (project.original_image_path) {
                          (e.target as HTMLImageElement).src = getMediaUrl(project.original_image_path, 'product');
                        }
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => handleDeleteImage('character')}
                      disabled={deletingImage === 'character'}
                      className="absolute top-2 right-2 p-2 rounded-xl bg-red-600/90 hover:bg-red-500 text-white shadow-lg flex items-center gap-1 text-[11px] font-bold transition-all"
                      title="Xóa ảnh nhân vật này"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Xóa</span>
                    </button>
                  </>
                ) : (
                  <div className="text-center space-y-2 text-slate-500 text-xs">
                    <Bot className="w-8 h-8 mx-auto text-slate-600" />
                    <div>Chưa có ảnh nhân vật AI</div>
                    <div className="text-[11px] text-slate-500">Bấm "Dán Ảnh (Ctrl+V)" hoặc "Tạo nhân vật AI bằng Gemini" ở trên</div>
                  </div>
                )}
              </div>

              {/* Download & Copy Buttons */}
              <div className="grid grid-cols-2 gap-3">
                <a
                  href={`/api/projects/${project.id}/download-character`}
                  download
                  className="py-2.5 px-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-md"
                >
                  <Download className="w-4 h-4" />
                  <span>TẢI ẢNH NHÂN VẬT</span>
                </a>
                <button
                  type="button"
                  onClick={() => handleCopyImage('character')}
                  className={`py-2.5 px-3 rounded-xl text-xs font-bold flex items-center justify-center gap-2 shadow-md ${
                    copiedId === 'img_character'
                      ? 'bg-emerald-500 text-white'
                      : 'bg-gradient-to-r from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 text-white'
                  }`}
                >
                  <Copy className="w-4 h-4" />
                  <span>{copiedId === 'img_character' ? 'ĐÃ COPY ẢNH (CTRL+V)!' : 'COPY ẢNH NHÂN VẬT'}</span>
                </button>
              </div>
            </div>
          </div>

          {/* History of generated characters (only show if multiple variants exist) */}
          {project.character_images && project.character_images.length > 1 && (
            <div className="p-5 rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-3">
              <h4 className="text-xs font-bold text-white flex items-center gap-2">
                <span>Lịch Sử Các Ảnh Nhân Vật Đã Tạo ({project.character_images.length})</span>
              </h4>

              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3">
                {project.character_images.map((img: Asset) => {
                  const isPrimary = img.file_path === project.primary_character_image_path;
                  const filename = img.file_path.split('\\').pop()?.split('/').pop();

                  return (
                    <div
                      key={img.id}
                      className={`relative rounded-xl overflow-hidden border p-1 bg-[#12161f] space-y-1.5 transition-all ${
                        isPrimary ? 'border-pink-500 shadow-md shadow-pink-500/20' : 'border-[#232a3b] hover:border-slate-500'
                      }`}
                    >
                      <div className="w-full h-36 rounded-lg overflow-hidden bg-black flex items-center justify-center relative">
                        <img
                          src={`/data/projects/${project.id}/character/${filename}`}
                          alt="Char variant"
                          className="w-full h-full object-cover"
                        />
                        <button
                          type="button"
                          onClick={() => handleDeleteImage('character', img.id)}
                          disabled={deletingImage === img.id}
                          className="absolute top-1.5 right-1.5 p-1 rounded-lg bg-red-600/85 hover:bg-red-500 text-white shadow"
                          title="Xóa ảnh nhân vật này"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>

                      <button
                        onClick={() => handleSetPrimaryCharacter(img.id)}
                        className={`w-full py-1 rounded text-[10px] font-bold transition-colors ${
                          isPrimary
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : 'bg-[#232a3b] text-slate-300 hover:text-white'
                        }`}
                      >
                        {isPrimary ? 'Đang dùng' : 'Chọn làm chính'}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="flex justify-end pt-4">
            <button
              onClick={() => setActiveTab('scripts')}
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-600 hover:to-indigo-700 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-purple-500/20"
            >
              <span>Tiếp tục: Sang Bước 2 (Kịch Bản & Prompt Video)</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 2 SUB-STEP 2: KỊCH BẢN & PROMPT TẠO VIDEO RIÊNG (2 CẢNH - 42 TỪ)
          ========================================================================= */}
      {studioMode === 'auto' && activeTab === 'scripts' && (
        <div className="space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <FileText className="w-5 h-5 text-purple-400" />
                <span>Bước 2: Kịch Bản & Prompt Tạo Video Riêng Cho Cảnh 1 & Cảnh 2</span>
              </h3>
              <p className="text-xs text-slate-400">
                Có nút Copy Prompt tạo video riêng cho từng cảnh để bạn đưa qua bất kỳ nền tảng tạo video nào.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => handleCheckQuality(selectedScriptTab)}
                disabled={checkingQuality}
                className="px-3.5 py-2.5 rounded-xl bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 text-xs font-semibold border border-indigo-500/30 flex items-center gap-1.5"
              >
                <ShieldAlert className="w-3.5 h-3.5" />
                <span>Quét Chất Lượng</span>
              </button>

              <button
                onClick={() => handleSaveScript(selectedScriptTab)}
                className="px-4 py-2.5 rounded-xl bg-[#232a3b] hover:bg-[#2e374d] text-white text-xs font-semibold"
              >
                {copiedId === 'save_script' ? '✓ Đã Lưu!' : 'Lưu Thay Đổi'}
              </button>

              <button
                onClick={handleGenerateScripts}
                disabled={generatingScripts}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#8b5cf6] to-[#ec4899] hover:from-[#7c3aed] hover:to-[#db2777] text-white text-xs font-bold shadow-lg shadow-purple-500/20 flex items-center gap-2 disabled:opacity-50"
              >
                {generatingScripts ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Gemini đang viết kịch bản...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>TẠO LẠI KỊCH BẢN & PROMPT (≥42 TỪ • TRỌN CÂU 10S)</span>
                  </>
                )}
              </button>
            </div>
          </div>

          <div className="p-6 rounded-2xl bg-[#181d29] border border-[#232a3b] space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* SCENE 1 */}
              <div className="p-5 rounded-xl bg-[#12161f] border border-[#232a3b] space-y-4">
                <div className="flex items-center justify-between border-b border-[#232a3b] pb-2.5">
                  <span className="text-xs font-bold text-white flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-cyan-400" />
                    <span>CẢNH 1 – HOOK & GIỚI THIỆU SẢN PHẨM (10s)</span>
                  </span>
                  <WordCounterBadge text={currentScriptOpt.scene1_dialogue || ''} target={42} />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-semibold text-slate-300">
                      Lời thoại nhân vật đọc (≥ 42 từ • Nói trọn câu 10s):
                    </label>
                    <button
                      type="button"
                      onClick={() => handleCopyText(currentScriptOpt.scene1_dialogue || '', 'tab2_dlg1')}
                      className="text-[11px] text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1"
                    >
                      <Copy className="w-3 h-3" />
                      <span>{copiedId === 'tab2_dlg1' ? 'Đã Copy!' : 'Copy lời thoại'}</span>
                    </button>
                  </div>
                  <textarea
                    rows={4}
                    value={currentScriptOpt.scene1_dialogue || ''}
                    onChange={(e) => handleScriptChange(selectedScriptTab, 'scene1_dialogue', e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-[#181d29] border border-[#232a3b] text-white text-xs focus:border-cyan-500 focus:outline-none leading-relaxed"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-cyan-300 block">
                    Prompt Tạo Video Cảnh 1 (Copy để đưa qua nền tảng tạo video):
                  </label>
                  <textarea
                    rows={5}
                    value={currentScriptOpt.scene1_prompt_veo || ''}
                    onChange={(e) => handleScriptChange(selectedScriptTab, 'scene1_prompt_veo', e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-[#181d29] border border-[#232a3b] text-white text-xs focus:border-cyan-500 focus:outline-none leading-relaxed font-mono"
                  />
                </div>

                <button
                  type="button"
                  onClick={() => handleCopyText(buildCopyPayloadForScene(1), 'tab2_p1')}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-md"
                >
                  <Copy className="w-4 h-4" />
                  <span>{copiedId === 'tab2_p1' ? '✓ ĐÃ COPY CẢ THOẠI + PROMPT CẢNH 1!' : 'COPY PROMPT + LỜI THOẠI CẢNH 1'}</span>
                </button>
              </div>

              {/* SCENE 2 */}
              <div className="p-5 rounded-xl bg-[#12161f] border border-[#232a3b] space-y-4">
                <div className="flex items-center justify-between border-b border-[#232a3b] pb-2.5">
                  <span className="text-xs font-bold text-white flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-pink-400" />
                    <span>CẢNH 2 – CẬN CẢNH LỢI ÍCH & CHỐT ĐƠN (10s)</span>
                  </span>
                  <WordCounterBadge text={currentScriptOpt.scene2_dialogue || ''} target={42} />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-semibold text-slate-300">
                      Lời thoại nhân vật đọc (≥ 42 từ • Trọn câu 10s & nhắc giỏ hàng):
                    </label>
                    <button
                      type="button"
                      onClick={() => handleCopyText(currentScriptOpt.scene2_dialogue || '', 'tab2_dlg2')}
                      className="text-[11px] text-pink-400 hover:text-pink-300 font-semibold flex items-center gap-1"
                    >
                      <Copy className="w-3 h-3" />
                      <span>{copiedId === 'tab2_dlg2' ? 'Đã Copy!' : 'Copy lời thoại'}</span>
                    </button>
                  </div>
                  <textarea
                    rows={4}
                    value={currentScriptOpt.scene2_dialogue || ''}
                    onChange={(e) => handleScriptChange(selectedScriptTab, 'scene2_dialogue', e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-[#181d29] border border-[#232a3b] text-white text-xs focus:border-pink-500 focus:outline-none leading-relaxed"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-pink-300 block">
                    Prompt Tạo Video Cảnh 2 (Copy để đưa qua nền tảng tạo video):
                  </label>
                  <textarea
                    rows={5}
                    value={currentScriptOpt.scene2_prompt_veo || ''}
                    onChange={(e) => handleScriptChange(selectedScriptTab, 'scene2_prompt_veo', e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-[#181d29] border border-[#232a3b] text-white text-xs focus:border-pink-500 focus:outline-none leading-relaxed font-mono"
                  />
                </div>

                <button
                  type="button"
                  onClick={() => handleCopyText(buildCopyPayloadForScene(2), 'tab2_p2')}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-md"
                >
                  <Copy className="w-4 h-4" />
                  <span>{copiedId === 'tab2_p2' ? '✓ ĐÃ COPY CẢ THOẠI + PROMPT CẢNH 2!' : 'COPY PROMPT + LỜI THOẠI CẢNH 2'}</span>
                </button>
              </div>
            </div>
          </div>

          <div className="flex justify-between items-center gap-3 pt-2 flex-wrap">
            <button
              onClick={() => handleSwitchStudioMode('manual')}
              className="px-4 py-2 rounded-xl bg-[#181d29] hover:bg-[#232a3b] text-slate-400 hover:text-slate-200 border border-[#2b354b] text-xs font-semibold flex items-center gap-2 transition-colors"
            >
              <ClipboardPaste className="w-3.5 h-3.5" />
              <span>Chuyển Sang Tab Thủ Công (Nếu Muốn Copy Dán Tự Do)</span>
            </button>

            <button
              onClick={async () => {
                if (currentScriptOpt.id) {
                  await handleSelectScript(currentScriptOpt.id);
                }
                setActiveTab('flow');
                if (!project?.videos?.some((v: any) => v.scene_number === 1) && !runningFullAuto) {
                  handleGenerateVideo(1);
                }
              }}
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white text-xs font-extrabold flex items-center gap-2 shadow-lg shadow-cyan-500/20"
            >
              <Sparkles className="w-4 h-4" />
              <span>
                {runningFullAuto
                  ? '🤖 Đang Tự Động Sản Xuất Video (Muse / Flow) → Xem Bước 3'
                  : 'Tiếp tục: Sang Bước 3 & Tạo Video (Muse / Flow)'}
              </span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 2 SUB-STEP 3: SẢN XUẤT VIDEO (FLOW & DÁN THỦ CÔNG)
          ========================================================================= */}
      {studioMode === 'auto' && activeTab === 'flow' && (
        <div className="space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-cyan-400" />
                <span>Bước 3: Tạo 2 Video Cảnh (Tự Động Muse AI / Google Flow Hoặc Dán / Tải Thủ Công)</span>
              </h3>
              <p className="text-xs text-slate-400">
                Bạn có thể tự động tạo video với Muse AI / Google Flow, hoặc lấy video đã tạo từ Muse AI về ghép ngay.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handlePullFromMuse}
                disabled={pullingMuse}
                className="px-4 py-2 rounded-xl bg-emerald-600/30 hover:bg-emerald-600/50 border border-emerald-500/40 text-emerald-300 text-xs font-bold flex items-center gap-2 transition-all shadow-lg shadow-emerald-950/40"
                title="Quét tìm và lấy video Cảnh 1 & Cảnh 2 đã tạo trên Muse AI để ghép ngay"
              >
                {pullingMuse ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                    <span>Đang lấy từ Muse AI...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 text-emerald-400" />
                    <span>📥 Lấy Video từ Muse AI &amp; Ghép Ngay</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {(generatingVideo1 || generatingVideo2) && (
            <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs flex items-center gap-3">
              <Loader2 className="w-4 h-4 animate-spin shrink-0" />
              <div>
                <div className="font-semibold">{videoProgressMsg || 'Đang tạo video trên Google Flow...'}</div>
                <div className="text-[11px] text-cyan-400/80">Video hiện tại vẫn được giữ nguyên an toàn trong lúc chờ Flow xử lý.</div>
              </div>
            </div>
          )}

          {isDuplicateScenes && (
            <div className="p-4 rounded-xl bg-amber-500/15 border border-amber-500/40 text-amber-200 text-xs flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-lg shadow-amber-950/30">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
                <div>
                  <div className="font-bold text-amber-300">Phát hiện Video Cảnh 1 và Cảnh 2 trùng lặp (giống hệt nhau)!</div>
                  <div className="text-[11px] text-amber-200/80">Cần có 2 cảnh riêng biệt (Cảnh 1: Nhân vật mở đầu; Cảnh 2: Cận cảnh chi tiết sản phẩm) trước khi ghép video.</div>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => handleDeleteSceneVideo(2)}
                  className="px-3 py-1.5 rounded-lg bg-red-600/30 hover:bg-red-600/50 border border-red-500/40 text-red-200 text-xs font-bold transition-all"
                >
                  Xóa Cảnh 2 Trùng Lặp
                </button>
                <button
                  type="button"
                  onClick={handlePullFromMuse}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600/30 hover:bg-emerald-600/50 border border-emerald-500/40 text-emerald-200 text-xs font-bold transition-all"
                >
                  Quét Lại Muse AI
                </button>
              </div>
            </div>
          )}

          {/* Cards for Video 1 and Video 2 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Card 1: Video 1 - Scene 1 */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOverScene(1); }}
              onDragLeave={() => setDragOverScene(null)}
              onDrop={(e) => handleDropVideo(1, e)}
              onPaste={(e) => handlePasteVideoEvent(1, e)}
              className={`p-6 rounded-2xl bg-[#181d29] border transition-all space-y-5 ${
                dragOverScene === 1 ? 'border-cyan-400 bg-cyan-500/10' : 'border-[#232a3b]'
              }`}
            >
              <div className="flex items-center justify-between border-b border-[#232a3b] pb-3">
                <span className="text-sm font-bold text-white flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
                  <span>VIDEO 1 – CẢNH 1 (Hook & Giới thiệu)</span>
                </span>
                {scene1Video ? (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 font-extrabold border border-cyan-500/30">
                      60 FPS
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 flex items-center gap-1">
                      <Check className="w-3 h-3" /> ĐÃ CÓ VIDEO
                    </span>
                    <button
                      type="button"
                      onClick={() => handleDeleteSceneVideo(1)}
                      disabled={deletingVideo1}
                      className="px-2 py-0.5 rounded bg-red-500/20 hover:bg-red-500/35 text-red-300 border border-red-500/40 text-[10px] font-bold flex items-center gap-1 transition-all"
                      title="Xóa Video Cảnh 1 vừa dán / tạo"
                    >
                      <Trash2 className="w-3 h-3" />
                      <span>Xóa</span>
                    </button>
                  </div>
                ) : (
                  <span className="text-[10px] text-slate-400">Chưa tạo</span>
                )}
              </div>

              {/* Reference Character Image Banner */}
              <div className="flex items-center gap-3 p-2.5 rounded-xl bg-[#12161f] border border-[#232a3b]">
                <img
                  src={getMediaUrl(project?.primary_character_image_path || '')}
                  alt="Ảnh tham chiếu nhân vật AI"
                  className="w-10 h-14 rounded-lg object-cover border border-[#232a3b] shrink-0"
                  onError={(e: any) => { e.target.style.display = 'none'; }}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] text-emerald-400 font-bold flex items-center gap-1">
                    <Check className="w-3 h-3" /> Ảnh nhân vật tham chiếu
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <a
                      href={`/api/projects/${project.id}/download-character`}
                      download
                      className="text-[10px] px-2 py-0.5 rounded bg-[#181d29] hover:bg-[#232a3b] text-cyan-300 border border-[#232a3b] flex items-center gap-1"
                    >
                      <Download className="w-2.5 h-2.5" /> Tải ảnh
                    </a>
                    <button
                      type="button"
                      onClick={() => handleCopyImage('character')}
                      className="text-[10px] px-2 py-0.5 rounded bg-[#181d29] hover:bg-[#232a3b] text-pink-300 border border-[#232a3b] flex items-center gap-1"
                    >
                      <Copy className="w-2.5 h-2.5" /> {copiedId === 'img_character' ? 'Đã Copy!' : 'Copy ảnh'}
                    </button>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleCopyText(buildCopyPayloadForScene(1), 'flow_p1')}
                  className="px-2.5 py-1.5 rounded-lg bg-[#181d29] hover:bg-[#232a3b] text-slate-200 hover:text-white text-[10px] font-semibold border border-[#232a3b] shrink-0 flex items-center gap-1"
                >
                  <Copy className="w-3 h-3 text-cyan-400" />
                  <span>{copiedId === 'flow_p1' ? 'Đã Copy!' : 'Copy Prompt + Thoại'}</span>
                </button>
              </div>

              {/* Video Player */}
              <div className="w-full flex justify-center py-1">
                <div className="w-[215px] h-[382px] sm:w-[225px] sm:h-[400px] rounded-2xl bg-black border-2 border-[#2a3449] overflow-hidden shadow-2xl relative flex items-center justify-center">
                  {scene1Video ? (
                    <>
                      <video
                        key={`scene1-${scene1Video.id || scene1Video.created_at}`}
                        src={`/data/projects/${project.id}/videos/scene1.mp4?v=${encodeURIComponent(scene1Video.id || scene1Video.created_at || '')}`}
                        controls
                        playsInline
                        className="w-full h-full object-cover"
                      />
                      <button
                        type="button"
                        onClick={() => handleDeleteSceneVideo(1)}
                        disabled={deletingVideo1}
                        className="absolute top-2 right-2 p-2 rounded-xl bg-red-600/90 hover:bg-red-500 text-white shadow-lg flex items-center gap-1 text-[11px] font-bold transition-all z-10"
                        title="Xóa Video Cảnh 1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Xóa Video</span>
                      </button>
                    </>
                  ) : (
                    <div className="text-center p-4 space-y-2">
                      <Film className="w-10 h-10 text-slate-600 mx-auto" />
                      <div className="text-xs font-semibold text-slate-300">Kéo thả hoặc Dán Video Cảnh 1</div>
                    </div>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="space-y-2 pt-2">
                <div className="grid grid-cols-2 gap-2">
                  <label className="py-2.5 px-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white text-xs font-bold cursor-pointer flex items-center justify-center gap-1.5 shadow-md">
                    <Upload className="w-3.5 h-3.5" />
                    <span>Chọn Video Cảnh 1</span>
                    <input type="file" accept="video/mp4,video/*" onChange={(e) => handleManualVideoUpload(1, e)} className="hidden" />
                  </label>

                  <button
                    type="button"
                    onClick={() => handlePasteClipboardVideoButton(1)}
                    disabled={pastingVideo1}
                    className="py-2.5 px-3 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-bold flex items-center justify-center gap-1.5"
                  >
                    <ClipboardPaste className="w-3.5 h-3.5" />
                    <span>{copiedId === 'paste_v1' ? 'Đã Dán!' : 'Dán Video (Ctrl+V)'}</span>
                  </button>
                </div>

                {scene1Video && (
                  <button
                    type="button"
                    onClick={() => handleDeleteSceneVideo(1)}
                    disabled={deletingVideo1}
                    className="w-full py-2 px-3 rounded-xl bg-red-500/15 hover:bg-red-500/25 text-red-300 border border-red-500/35 text-xs font-bold flex items-center justify-center gap-1.5 transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>{deletingVideo1 ? 'Đang xóa Video Cảnh 1...' : '🗑 Xóa Video Cảnh 1 Vừa Dán / Nạp'}</span>
                  </button>
                )}

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleImportFlowVideo(1)}
                    disabled={importingVideo1 || generatingVideo1}
                    className="flex-1 py-2 rounded-xl bg-[#12161f] hover:bg-[#232a3b] border border-[#232a3b] text-cyan-300 text-xs font-semibold flex items-center justify-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Lấy từ Downloads</span>
                  </button>

                  <button
                    onClick={() => handleGenerateVideo(1)}
                    disabled={generatingVideo1 || importingVideo1}
                    className="px-3.5 py-2 rounded-xl bg-[#12161f] hover:bg-[#232a3b] border border-[#232a3b] text-slate-300 hover:text-white text-xs font-semibold flex items-center justify-center gap-1.5"
                  >
                    {generatingVideo1 ? <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" /> : <Play className="w-3.5 h-3.5 text-cyan-400" />}
                    <span>Tạo Flow</span>
                  </button>

                  <button
                    onClick={() => handleGenerateMuseVideo(1)}
                    disabled={generatingVideo1 || importingVideo1}
                    className="px-3.5 py-2 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:text-white text-xs font-semibold flex items-center justify-center gap-1.5"
                    title="Tạo video Cảnh 1 bằng Muse AI"
                  >
                    {generatingVideo1 ? <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-400" /> : <Sparkles className="w-3.5 h-3.5 text-emerald-400" />}
                    <span>Tạo Muse AI</span>
                  </button>

                  <button
                    onClick={() => handleGenerateFastVideo(1)}
                    disabled={generatingFast1 || generatingVideo1}
                    className="px-3 py-2 rounded-xl bg-[#12161f] hover:bg-[#232a3b] border border-[#232a3b] text-amber-300 text-xs font-semibold flex items-center gap-1"
                    title="Tạo nhanh chuyển động 60fps từ ảnh"
                  >
                    <Zap className="w-3.5 h-3.5" />
                    <span>2s</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Card 2: Video 2 - Scene 2 */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOverScene(2); }}
              onDragLeave={() => setDragOverScene(null)}
              onDrop={(e) => handleDropVideo(2, e)}
              onPaste={(e) => handlePasteVideoEvent(2, e)}
              className={`p-6 rounded-2xl bg-[#181d29] border transition-all space-y-5 ${
                dragOverScene === 2 ? 'border-pink-400 bg-pink-500/10' : 'border-[#232a3b]'
              }`}
            >
              <div className="flex items-center justify-between border-b border-[#232a3b] pb-3">
                <span className="text-sm font-bold text-white flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-pink-400" />
                  <span>VIDEO 2 – CẢNH 2 (Lợi ích & Cận cảnh SP)</span>
                </span>
                {scene2Video ? (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-pink-500/20 text-pink-400 font-extrabold border border-pink-500/30">
                      60 FPS
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 flex items-center gap-1">
                      <Check className="w-3 h-3" /> ĐÃ CÓ VIDEO
                    </span>
                    <button
                      type="button"
                      onClick={() => handleDeleteSceneVideo(2)}
                      disabled={deletingVideo2}
                      className="px-2 py-0.5 rounded bg-red-500/20 hover:bg-red-500/35 text-red-300 border border-red-500/40 text-[10px] font-bold flex items-center gap-1 transition-all"
                      title="Xóa Video Cảnh 2 vừa dán / tạo"
                    >
                      <Trash2 className="w-3 h-3" />
                      <span>Xóa</span>
                    </button>
                  </div>
                ) : (
                  <span className="text-[10px] text-slate-400">Chưa tạo</span>
                )}
              </div>

              {/* Reference Character Image Banner for Scene 2 */}
              <div className="flex items-center gap-3 p-2.5 rounded-xl bg-[#12161f] border border-[#232a3b]">
                <img
                  src={getMediaUrl(project?.primary_character_image_path || project?.original_image_path || '')}
                  alt="Ảnh nhân vật tham chiếu Cảnh 2"
                  className="w-10 h-14 rounded-lg object-cover border border-[#232a3b] shrink-0"
                  onError={(e: any) => { e.target.style.display = 'none'; }}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] text-pink-400 font-bold flex items-center gap-1">
                    <Check className="w-3 h-3" /> Ảnh nhân vật tham chiếu Cảnh 2
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <a
                      href={project?.primary_character_image_path ? `/api/projects/${project.id}/download-character` : `/api/projects/${project.id}/download-product`}
                      download
                      className="text-[10px] px-2 py-0.5 rounded bg-[#181d29] hover:bg-[#232a3b] text-cyan-300 border border-[#232a3b] flex items-center gap-1"
                    >
                      <Download className="w-2.5 h-2.5" /> Tải ảnh
                    </a>
                    <button
                      type="button"
                      onClick={() => handleCopyImage(project?.primary_character_image_path ? 'character' : 'product')}
                      className="text-[10px] px-2 py-0.5 rounded bg-[#181d29] hover:bg-[#232a3b] text-pink-300 border border-[#232a3b] flex items-center gap-1"
                    >
                      <Copy className="w-2.5 h-2.5" /> {copiedId === 'img_character' || copiedId === 'img_product' ? 'Đã Copy!' : 'Copy ảnh'}
                    </button>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleCopyText(buildCopyPayloadForScene(2), 'flow_p2')}
                  className="px-2.5 py-1.5 rounded-lg bg-[#181d29] hover:bg-[#232a3b] text-slate-200 hover:text-white text-[10px] font-semibold border border-[#232a3b] shrink-0 flex items-center gap-1"
                >
                  <Copy className="w-3 h-3 text-pink-400" />
                  <span>{copiedId === 'flow_p2' ? 'Đã Copy!' : 'Copy Prompt + Thoại'}</span>
                </button>
              </div>

              {/* Video Player */}
              <div className="w-full flex justify-center py-1">
                <div className="w-[215px] h-[382px] sm:w-[225px] sm:h-[400px] rounded-2xl bg-black border-2 border-[#2a3449] overflow-hidden shadow-2xl relative flex items-center justify-center">
                  {scene2Video ? (
                    <>
                      <video
                        key={`scene2-${scene2Video.id || scene2Video.created_at}`}
                        src={`/data/projects/${project.id}/videos/scene2.mp4?v=${encodeURIComponent(scene2Video.id || scene2Video.created_at || '')}`}
                        controls
                        playsInline
                        className="w-full h-full object-cover"
                      />
                      <button
                        type="button"
                        onClick={() => handleDeleteSceneVideo(2)}
                        disabled={deletingVideo2}
                        className="absolute top-2 right-2 p-2 rounded-xl bg-red-600/90 hover:bg-red-500 text-white shadow-lg flex items-center gap-1 text-[11px] font-bold transition-all z-10"
                        title="Xóa Video Cảnh 2"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Xóa Video</span>
                      </button>
                    </>
                  ) : (
                    <div className="text-center p-4 space-y-2">
                      <Film className="w-10 h-10 text-slate-600 mx-auto" />
                      <div className="text-xs font-semibold text-slate-300">Kéo thả hoặc Dán Video Cảnh 2</div>
                    </div>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="space-y-2 pt-2">
                <div className="grid grid-cols-2 gap-2">
                  <label className="py-2.5 px-3 rounded-xl bg-gradient-to-r from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 text-white text-xs font-bold cursor-pointer flex items-center justify-center gap-1.5 shadow-md">
                    <Upload className="w-3.5 h-3.5" />
                    <span>Chọn Video Cảnh 2</span>
                    <input type="file" accept="video/mp4,video/*" onChange={(e) => handleManualVideoUpload(2, e)} className="hidden" />
                  </label>

                  <button
                    type="button"
                    onClick={() => handlePasteClipboardVideoButton(2)}
                    disabled={pastingVideo2}
                    className="py-2.5 px-3 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-bold flex items-center justify-center gap-1.5"
                  >
                    <ClipboardPaste className="w-3.5 h-3.5" />
                    <span>{copiedId === 'paste_v2' ? 'Đã Dán!' : 'Dán Video (Ctrl+V)'}</span>
                  </button>
                </div>

                {scene2Video && (
                  <button
                    type="button"
                    onClick={() => handleDeleteSceneVideo(2)}
                    disabled={deletingVideo2}
                    className="w-full py-2 px-3 rounded-xl bg-red-500/15 hover:bg-red-500/25 text-red-300 border border-red-500/35 text-xs font-bold flex items-center justify-center gap-1.5 transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>{deletingVideo2 ? 'Đang xóa Video Cảnh 2...' : '🗑 Xóa Video Cảnh 2 Vừa Dán / Nạp'}</span>
                  </button>
                )}

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleImportFlowVideo(2)}
                    disabled={importingVideo2 || generatingVideo2}
                    className="flex-1 py-2 rounded-xl bg-[#12161f] hover:bg-[#232a3b] border border-[#232a3b] text-pink-300 text-xs font-semibold flex items-center justify-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Lấy từ Downloads</span>
                  </button>

                  <button
                    onClick={() => handleGenerateVideo(2)}
                    disabled={generatingVideo2 || importingVideo2}
                    className="px-3.5 py-2 rounded-xl bg-[#12161f] hover:bg-[#232a3b] border border-[#232a3b] text-slate-300 hover:text-white text-xs font-semibold flex items-center justify-center gap-1.5"
                  >
                    {generatingVideo2 ? <Loader2 className="w-3.5 h-3.5 animate-spin text-pink-400" /> : <Play className="w-3.5 h-3.5 text-pink-400" />}
                    <span>Tạo Flow</span>
                  </button>

                  <button
                    onClick={() => handleGenerateMuseVideo(2)}
                    disabled={generatingVideo2 || importingVideo2}
                    className="px-3.5 py-2 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:text-white text-xs font-semibold flex items-center justify-center gap-1.5"
                    title="Tạo video Cảnh 2 bằng Muse AI"
                  >
                    {generatingVideo2 ? <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-400" /> : <Sparkles className="w-3.5 h-3.5 text-emerald-400" />}
                    <span>Tạo Muse AI</span>
                  </button>

                  <button
                    onClick={() => handleGenerateFastVideo(2)}
                    disabled={generatingFast2 || generatingVideo2}
                    className="px-3 py-2 rounded-xl bg-[#12161f] hover:bg-[#232a3b] border border-[#232a3b] text-amber-300 text-xs font-semibold flex items-center gap-1"
                    title="Tạo nhanh chuyển động 60fps từ ảnh"
                  >
                    <Zap className="w-3.5 h-3.5" />
                    <span>2s</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Direct Merge & Next Button */}
          <div className="flex flex-col sm:flex-row justify-between items-center gap-3 pt-4 border-t border-[#232a3b]">
            <button
              onClick={handleStitch}
              disabled={stitching || !hasBothVideos}
              className="w-full sm:w-auto px-6 py-3 rounded-xl bg-gradient-to-r from-[#fe2c55] to-[#ff0050] hover:opacity-90 text-white text-xs font-extrabold flex items-center justify-center gap-2 shadow-lg shadow-pink-500/25 disabled:opacity-40"
            >
              {stitching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Combine className="w-4 h-4" />}
              <span>🎬 GHÉP 2 VIDEO LẠI VỚI NHAU NGAY</span>
            </button>

            <button
              onClick={() => setActiveTab('stitch')}
              disabled={!hasBothVideos}
              className="w-full sm:w-auto px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 disabled:opacity-40"
            >
              <span>Sang Bước 4 (Xem & Tải Video Hoàn Chỉnh)</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 2 SUB-STEP 4: GHÉP VIDEO HOÀN CHỈNH BẰNG FFMPEG
          ========================================================================= */}
      {studioMode === 'auto' && activeTab === 'stitch' && (
        <div className="space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <span>Bước 4: Ghép 2 Video Hoàn Chỉnh Bằng FFmpeg (Chuẩn TikTok 9:16 1080p 60fps)</span>
              </h3>
              <p className="text-xs text-slate-400">
                Nối Cảnh 1 và Cảnh 2 thành 1 video hoàn chỉnh, chuẩn hóa độ phân giải 1080x1920 @ 60fps siêu mượt.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handlePullFromMuse}
                disabled={pullingMuse}
                className="px-4 py-2.5 rounded-xl bg-emerald-600/30 hover:bg-emerald-600/50 border border-emerald-500/40 text-emerald-300 text-xs font-bold flex items-center gap-2 transition-all shadow-md"
                title="Lấy video gốc Cảnh 1 & Cảnh 2 từ Muse AI về ghép lại chuẩn 60 FPS"
              >
                {pullingMuse ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                    <span>Đang lấy Muse AI...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 text-emerald-400" />
                    <span>📥 Lấy Video từ Muse AI</span>
                  </>
                )}
              </button>

              <button
                onClick={handleStitch}
                disabled={stitching || !hasBothVideos}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-[#fe2c55] via-[#ff0050] to-[#25f4ee] hover:opacity-90 text-white text-xs font-bold shadow-lg shadow-pink-500/25 flex items-center gap-2 transition-all transform hover:-translate-y-0.5 disabled:opacity-40"
              >
                {stitching ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>FFmpeg đang ghép 60fps...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>{project.export ? 'GHÉP LẠI VIDEO 60FPS' : 'GHÉP VIDEO 60FPS NGAY'}</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Side-by-Side Source Videos */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div
              tabIndex={0}
              onDragOver={(e) => { e.preventDefault(); setDragOverScene(1); }}
              onDragLeave={() => setDragOverScene(null)}
              onDrop={(e) => handleDropVideo(1, e)}
              onPaste={(e) => handlePasteVideoEvent(1, e)}
              className="p-4 rounded-xl bg-[#181d29] border border-[#232a3b] focus:border-cyan-400 outline-none space-y-2"
            >
              <div className="text-xs font-semibold text-slate-300 flex items-center justify-between flex-wrap gap-1.5">
                <span>Cảnh 1 (Video đầu):</span>
                <div className="flex items-center gap-2">
                  <label className="text-[11px] text-cyan-400 hover:underline cursor-pointer flex items-center gap-1">
                    <Upload className="w-3 h-3" /> Đổi Video 1
                    <input type="file" accept="video/mp4,video/*" onChange={(e) => handleManualVideoUpload(1, e)} className="hidden" />
                  </label>
                  <button
                    type="button"
                    onClick={() => handlePasteClipboardVideoButton(1)}
                    disabled={pastingVideo1}
                    className="text-[11px] text-amber-300 hover:text-amber-200 font-bold flex items-center gap-1"
                  >
                    <ClipboardPaste className="w-3 h-3" /> Dán (Ctrl+V)
                  </button>
                  {scene1Video && (
                    <button
                      type="button"
                      onClick={() => handleDeleteSceneVideo(1)}
                      disabled={deletingVideo1}
                      className="text-[11px] text-red-400 hover:text-red-300 font-bold flex items-center gap-1"
                    >
                      <Trash2 className="w-3 h-3" /> Xóa Video 1
                    </button>
                  )}
                </div>
              </div>
              <div className="w-full flex justify-center py-1">
                <div className="w-[140px] h-[248px] rounded-xl bg-black border border-[#2a3449] overflow-hidden flex items-center justify-center relative">
                  {scene1Video ? (
                    <video
                      key={`st-s1-${scene1Video.id || scene1Video.created_at}`}
                      src={`/data/projects/${project.id}/videos/scene1.mp4?v=${encodeURIComponent(scene1Video.id || scene1Video.created_at || '')}`}
                      controls
                      playsInline
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="text-xs text-slate-500 text-center p-2">Chưa có Cảnh 1 (Kéo thả hoặc Dán Ctrl+V)</div>
                  )}
                </div>
              </div>
            </div>

            <div
              tabIndex={0}
              onDragOver={(e) => { e.preventDefault(); setDragOverScene(2); }}
              onDragLeave={() => setDragOverScene(null)}
              onDrop={(e) => handleDropVideo(2, e)}
              onPaste={(e) => handlePasteVideoEvent(2, e)}
              className="p-4 rounded-xl bg-[#181d29] border border-[#232a3b] focus:border-pink-400 outline-none space-y-2"
            >
              <div className="text-xs font-semibold text-slate-300 flex items-center justify-between flex-wrap gap-1.5">
                <span>Cảnh 2 (Video sau):</span>
                <div className="flex items-center gap-2">
                  <label className="text-[11px] text-pink-400 hover:underline cursor-pointer flex items-center gap-1">
                    <Upload className="w-3 h-3" /> Đổi Video 2
                    <input type="file" accept="video/mp4,video/*" onChange={(e) => handleManualVideoUpload(2, e)} className="hidden" />
                  </label>
                  <button
                    type="button"
                    onClick={() => handlePasteClipboardVideoButton(2)}
                    disabled={pastingVideo2}
                    className="text-[11px] text-amber-300 hover:text-amber-200 font-bold flex items-center gap-1"
                  >
                    <ClipboardPaste className="w-3 h-3" /> Dán (Ctrl+V)
                  </button>
                  {scene2Video && (
                    <button
                      type="button"
                      onClick={() => handleDeleteSceneVideo(2)}
                      disabled={deletingVideo2}
                      className="text-[11px] text-red-400 hover:text-red-300 font-bold flex items-center gap-1"
                    >
                      <Trash2 className="w-3 h-3" /> Xóa Video 2
                    </button>
                  )}
                </div>
              </div>
              <div className="w-full flex justify-center py-1">
                <div className="w-[140px] h-[248px] rounded-xl bg-black border border-[#2a3449] overflow-hidden flex items-center justify-center relative">
                  {scene2Video ? (
                    <video
                      key={`st-s2-${scene2Video.id || scene2Video.created_at}`}
                      src={`/data/projects/${project.id}/videos/scene2.mp4?v=${encodeURIComponent(scene2Video.id || scene2Video.created_at || '')}`}
                      controls
                      playsInline
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="text-xs text-slate-500 text-center p-2">Chưa có Cảnh 2 (Kéo thả hoặc Dán Ctrl+V)</div>
                  )}
                </div>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={handleStitch}
            disabled={stitching || !hasBothVideos}
            className="w-full py-4 rounded-2xl bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white text-sm font-black tracking-wide shadow-xl shadow-emerald-500/25 flex items-center justify-center gap-3 transition-all transform hover:-translate-y-0.5 disabled:opacity-40"
          >
            {stitching ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>ĐANG GHÉP NỐI 2 VIDEO CHUẨN TIKTOK 1080x1920 60FPS...</span>
              </>
            ) : (
              <>
                <Combine className="w-5 h-5" />
                <span>🎬 {project.export ? 'GHÉP LẠI 2 VIDEO 60FPS NGAY' : 'GHÉP 2 VIDEO LẠI VỚI NHAU NGAY (1080x1920 60FPS)'}</span>
              </>
            )}
          </button>

          {/* Finished Stitched Video Player */}
          {project.export && !hasBothVideos && (
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg">
              <span>⚠️ Video ghép trước đó không hợp lệ do thiếu Video Cảnh 2. Hệ thống bắt buộc phải có đủ 2 cảnh riêng biệt mới được ghép hoàn chỉnh. Vui lòng tạo Cảnh 2 trước.</span>
              <button
                type="button"
                onClick={handleDeleteExportVideo}
                disabled={deletingExport}
                className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold shrink-0 text-xs"
              >
                Xóa Video Ghép Lỗi
              </button>
            </div>
          )}
          {project.export && hasBothVideos && (
            <div className="p-6 rounded-2xl bg-gradient-to-br from-[#181d29] to-[#12161f] border border-emerald-500/40 space-y-6 shadow-2xl">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#232a3b] pb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                    <CheckCircle2 className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white flex items-center gap-2">
                      <span>Video TikTok Affiliate Hoàn Chỉnh Thành Phẩm</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-extrabold">
                        SẴN SÀNG ĐĂNG TIKTOK (60 FPS)
                      </span>
                    </h4>
                    <p className="text-xs text-slate-400">
                      Tệp: {project.export.file_name} &bull; Thời lượng: {project.export.duration}s &bull; Độ phân giải: {project.export.resolution} &bull; FPS: 60
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 flex-wrap">
                  <a
                    href={`/api/ffmpeg/download/${project.id}/${project.export.file_name}`}
                    download
                    className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold flex items-center gap-2 shadow-md shadow-emerald-500/20 transition-all"
                  >
                    <Download className="w-4 h-4" />
                    <span>Tải Video Thành Phẩm</span>
                  </a>

                  <button
                    onClick={handleOpenFolder}
                    className="px-4 py-2 rounded-xl bg-[#232a3b] hover:bg-[#2e374d] text-slate-200 text-xs font-semibold flex items-center gap-2 transition-colors"
                  >
                    <FolderOpen className="w-4 h-4 text-amber-400" />
                    <span>Mở Thư Mục Windows</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleDeleteExportVideo}
                    disabled={deletingExport}
                    className="px-4 py-2 rounded-xl bg-red-500/20 hover:bg-red-500/35 text-red-300 border border-red-500/40 text-xs font-bold flex items-center gap-1.5 transition-all"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span>{deletingExport ? 'Đang xóa...' : 'Xóa Video Ghép'}</span>
                  </button>
                </div>
              </div>

              <div className="w-full flex justify-center py-2">
                <div className="w-[240px] h-[426px] sm:w-[270px] sm:h-[480px] rounded-3xl bg-black border-4 border-[#2a3449] overflow-hidden shadow-2xl flex items-center justify-center relative">
                  <video
                    key={`export-auto-${project.export.id || project.export.file_name}`}
                    src={`/data/projects/${project.id}/exports/${project.export.file_name}?v=${encodeURIComponent(project.export.id || '')}`}
                    controls
                    playsInline
                    autoPlay
                    className="w-full h-full object-cover"
                  />
                </div>
              </div>

              {/* Callout: Clone Warehouse Video Variant */}
              <div className="p-4 rounded-2xl bg-gradient-to-r from-amber-500/15 via-orange-500/10 to-rose-500/15 border border-amber-500/30 flex flex-col sm:flex-row items-center justify-between gap-4 mt-4">
                <div className="flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/25 border border-amber-500/40 flex items-center justify-center text-amber-300 shrink-0">
                    <Layers className="w-5 h-5" />
                  </div>
                  <div>
                    <h5 className="text-xs font-black text-white flex items-center gap-2">
                      <span>Nhân Bản Thêm Video Mới Cho Sản Phẩm Này?</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-extrabold">BẢN KHO XƯỞNG GIÁ RẺ</span>
                    </h5>
                    <p className="text-[11px] text-slate-300 mt-0.5">
                      Đổi ngay nhân vật AI mới, bối cảnh <strong>Tổng Kho Xưởng Hàng Rẻ Tận Gốc</strong>, kịch bản ≥ 42 từ chuẩn 10s và tự động tạo 2 cảnh mới!
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleCloneVideoVariant}
                  disabled={cloningVariant}
                  className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500 hover:from-amber-600 hover:to-rose-600 text-white text-xs font-black shadow-lg shadow-amber-500/25 flex items-center gap-2 transition-all shrink-0 disabled:opacity-50"
                >
                  {cloningVariant ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Đang nhân bản...</span>
                    </>
                  ) : (
                    <>
                      <Layers className="w-4 h-4" />
                      <span>✨ Nhân Bản Video Mới (Bản Kho Xưởng)</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Quality Scanner Modal */}
      {showQualityModal && qualityResult && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#181d29] border border-[#232a3b] rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#232a3b] pb-3">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-indigo-400" />
                <h3 className="text-sm font-bold text-white">Báo Cáo Kiểm Tra Chất Lượng & Chính Sách</h3>
              </div>
              <button onClick={() => setShowQualityModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex items-center justify-between p-4 rounded-xl bg-[#12161f] border border-[#232a3b]">
              <div>
                <div className="text-xs font-semibold text-slate-300">Điểm Đạt Chuẩn Nội Dung</div>
                <div className="text-[11px] text-slate-400">
                  {qualityResult.score >= 80 ? 'Đạt chuẩn sản xuất video Veo 3' : 'Cần điều chỉnh lại kịch bản'}
                </div>
              </div>
              <div className={`text-2xl font-black ${qualityResult.score >= 80 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {qualityResult.score}/100
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setShowQualityModal(false)}
                className="px-5 py-2 rounded-xl bg-[#232a3b] hover:bg-slate-700 text-white text-xs font-semibold"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

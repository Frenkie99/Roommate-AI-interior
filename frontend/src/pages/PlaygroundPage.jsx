import { useState, useRef, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { Upload, Zap, Download, Send, MessageSquare, Eye, Wand2, Lock } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import Navbar from '../components/Navbar';
import { useChatEngine } from '../chat/useChatEngine';
import { IMAGE_PROMPTS, KNOWLEDGE_PROMPTS, REFINE_PROMPTS } from '../chat/quickPrompts';
import { addDesignHistory } from '../services/historyService';
import { useAuth } from '../context/AuthContext';

// 房间类型映射 v3.0：精简至7个（2026-07-22）
const roomTypes = [
  { id: 'living_room', label: '客厅', labelEn: 'Living Room' },
  { id: 'dining_room', label: '餐厅', labelEn: 'Dining' },
  { id: 'kitchen', label: '厨房', labelEn: 'Kitchen' },
  { id: 'bedroom', label: '卧室', labelEn: 'Bedroom' },
  { id: 'bathroom', label: '卫生间', labelEn: 'Bathroom' },
  { id: 'study', label: '书房', labelEn: 'Study' },
  { id: 'kids_room', label: '儿童房', labelEn: 'Kids' },
];

// 风格映射 v3.0：精简至6个风格（2026-07-22）
const styles = [
  { id: 'modern_luxury', label: '现代轻奢', img: '/styles/现代轻奢.webp' },
  { id: 'chinese_modern', label: '新中式', img: '/styles/新中式.webp' },
  { id: 'aman_style', label: '安缦风', img: '/styles/安缦风.webp' },
  { id: 'wabi_sabi', label: '侘寂风', img: '/styles/侘寂风.webp' },
  { id: 'bohemian', label: '波西米亚', img: '/styles/波西米亚.webp' },
  { id: 'bauhaus_mcm', label: '包豪斯 / 中古风', img: '/styles/包豪斯中古风.webp' },
];

// 后端API地址（生产环境使用相对路径，由Nginx代理）
const API_BASE = '';
const API_TIMEOUT_MS = 300000;

// 匿名会话id：持久化在 localStorage，串联同一人多次操作（无任何身份信息）
const getSessionId = () => {
  let sid = localStorage.getItem('roommate_session_id');
  if (!sid) {
    sid = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem('roommate_session_id', sid);
  }
  return sid;
};

// 点评埋点：发送即忘，失败静默，绝不打扰用户
const sendFeedback = (traceId, action) => {
  if (!traceId) return;
  fetch(`${API_BASE}/api/v1/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trace_id: traceId, action, session_id: getSessionId() }),
  }).catch(() => {});
};

export default function PlaygroundPage() {
  const { user, quota, setQuota, loading: authLoading, openAuth } = useAuth();
  const [selectedRoom, setSelectedRoom] = useState('living_room');
  const [selectedStyle, setSelectedStyle] = useState('aman_style');
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState('');
  const [uploadedImage, setUploadedImage] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [generatedImage, setGeneratedImage] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastTraceId, setLastTraceId] = useState(null);
  const [feedbackGiven, setFeedbackGiven] = useState(null);
  const [notes, setNotes] = useState('');
  const fileInputRef = useRef(null);
  const [isDragover, setIsDragover] = useState(false);
  
  // 精修模式相关状态
  const [viewMode, setViewMode] = useState('preview'); // 'preview' | 'refine'
  const [segmentData, setSegmentData] = useState(null); // SAM分割数据
  const [hoveredMask, setHoveredMask] = useState(null); // 悬停的mask
  const [selectedMask, setSelectedMask] = useState(null); // 选中锁定的mask
  const [isSegmenting, setIsSegmenting] = useState(false); // 分割加载中
  const [displayImage, setDisplayImage] = useState(null); // 当前显示的图片（原图或overlay）
  // 框选模式
  const [isDrawingBox, setIsDrawingBox] = useState(false);
  const [boxStart, setBoxStart] = useState(null);
  const [boxEnd, setBoxEnd] = useState(null);
  const canvasRef = useRef(null);
  const imageContainerRef = useRef(null);
  const chatInputRef = useRef(null);
  const previewPanelRef = useRef(null);

  // 聊天引擎 hook
  const {
    chatMessages, setChatMessages,
    chatInput, setChatInput,
    chatContainerRef,
    sendMessage, sendMessageWithMask,
  } = useChatEngine({
    uploadedFile, generatedImage, selectedMask, viewMode,
    selectedStyle, selectedRoom, styles,
    setIsGenerating, setProgress, setStatusText,
    setGeneratedImage, setSelectedMask, setSelectedStyle, setViewMode,
  });

  // 框选模式 - 按下开始绘制（Pointer 事件：鼠标/触屏/手写笔通用）
  const handlePointerDown = useCallback((e) => {
    if (viewMode !== 'refine' || !generatedImage || isSegmenting) return;

    const img = imageContainerRef.current?.querySelector('img');
    if (!img) return;

    // 捕获指针：手指/鼠标拖出图片范围也能继续收到 move/up
    e.currentTarget.setPointerCapture?.(e.pointerId);

    const imgRect = img.getBoundingClientRect();
    const scaleX = img.naturalWidth / imgRect.width;
    const scaleY = img.naturalHeight / imgRect.height;
    const x = Math.round((e.clientX - imgRect.left) * scaleX);
    const y = Math.round((e.clientY - imgRect.top) * scaleY);

    setIsDrawingBox(true);
    setBoxStart({ x, y, screenX: e.clientX - imgRect.left, screenY: e.clientY - imgRect.top });
    setBoxEnd({ x, y, screenX: e.clientX - imgRect.left, screenY: e.clientY - imgRect.top });
  }, [viewMode, generatedImage, isSegmenting]);

  // 框选模式 - 移动更新框
  const handlePointerMove = useCallback((e) => {
    if (!isDrawingBox || !boxStart) return;

    const img = imageContainerRef.current?.querySelector('img');
    if (!img) return;

    const imgRect = img.getBoundingClientRect();
    const scaleX = img.naturalWidth / imgRect.width;
    const scaleY = img.naturalHeight / imgRect.height;
    const x = Math.round((e.clientX - imgRect.left) * scaleX);
    const y = Math.round((e.clientY - imgRect.top) * scaleY);

    setBoxEnd({ x, y, screenX: e.clientX - imgRect.left, screenY: e.clientY - imgRect.top });
  }, [isDrawingBox, boxStart]);

  // 框选模式 - 松开发送分割请求
  const handlePointerUp = useCallback(async (e) => {
    if (!isDrawingBox || !boxStart || !boxEnd) {
      setIsDrawingBox(false);
      return;
    }
    
    // 检查框是否足够大（至少30像素）
    const width = Math.abs(boxEnd.x - boxStart.x);
    const height = Math.abs(boxEnd.y - boxStart.y);
    
    if (width < 30 || height < 30) {
      // 框太小，忽略
      setIsDrawingBox(false);
      setBoxStart(null);
      setBoxEnd(null);
      return;
    }
    
    setIsSegmenting(true);
    
    try {
      const response = await fetch(generatedImage);
      const blob = await response.blob();
      
      // 只使用框选模式
      const x1 = Math.min(boxStart.x, boxEnd.x);
      const y1 = Math.min(boxStart.y, boxEnd.y);
      const x2 = Math.max(boxStart.x, boxEnd.x);
      const y2 = Math.max(boxStart.y, boxEnd.y);
      
      const formData = new FormData();
      formData.append('image', blob, 'image.jpg');
      formData.append('x1', x1);
      formData.append('y1', y1);
      formData.append('x2', x2);
      formData.append('y2', y2);
      
      const segResponse = await fetch(`${API_BASE}/api/v1/segment/by-box`, {
        method: 'POST',
        body: formData,
      });
      
      const result = await segResponse.json();
      console.log('Segment result:', result);
      
      if (result.code === 0 && result.data?.mask) {
        const maskData = {
          mask: result.data.mask,  // 黑白mask用于inpaint
          overlay: result.data.overlay,  // overlay用于高亮显示
          box: { x1, y1, x2, y2 }
        };
        setSelectedMask(maskData);
        setSegmentData(result.data);
        
        if (chatInputRef.current) {
          chatInputRef.current.focus();
        }
        
        setChatMessages(prev => [...prev, { 
          type: 'ai', 
          text: '✨ 已框选目标家具！请告诉我您想做什么修改？例如：换成现代风沙发、改成绿植、换个颜色...' 
        }]);
      } else {
        throw new Error(result.message || '分割失败');
      }
    } catch (error) {
      console.error('Segment error:', error);
      setChatMessages(prev => [...prev, { 
        type: 'ai', 
        text: `分割失败：${error.message}` 
      }]);
    } finally {
      setIsSegmenting(false);
      setIsDrawingBox(false);
      setBoxStart(null);
      setBoxEnd(null);
    }
  }, [isDrawingBox, boxStart, boxEnd, generatedImage]);

  // 显示overlay高亮图
  useEffect(() => {
    if (selectedMask?.overlay && viewMode === 'refine') {
      // 显示overlay图片（高亮选中物体）
      const prefix = selectedMask.overlay.startsWith('/9j/') ? 'data:image/jpeg;base64,' : 'data:image/png;base64,';
      setDisplayImage(prefix + selectedMask.overlay);
    } else {
      setDisplayImage(null);
    }
  }, [selectedMask, viewMode]);

  // 切换精修模式
  const toggleRefineMode = () => {
    if (viewMode === 'preview') {
      setViewMode('refine');
      setSelectedMask(null);
      setSegmentData(null);
    } else {
      setViewMode('preview');
      setSelectedMask(null);
      setSegmentData(null);
      // 恢复原图
      const imgElement = imageContainerRef.current?.querySelector('img');
      if (imgElement?.dataset.originalSrc) {
        imgElement.src = imgElement.dataset.originalSrc;
        delete imgElement.dataset.originalSrc;
      }
    }
  };

  const handleFileSelect = (file) => {
    if (!file?.type.startsWith('image/')) {
      toast.error('仅支持图片文件（JPG、PNG）');
      return;
    }
    // 后端上传限制 10MB，前端提前拦截，避免提交后才失败
    if (file.size > 10 * 1024 * 1024) {
      toast.error(`图片大小 ${(file.size / 1024 / 1024).toFixed(1)}MB，超过 10MB 限制，请压缩后重新上传`, { duration: 6000 });
      return;
    }
    // 清理旧的 preview URL
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setUploadedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setUploadedImage(file); // 存储 File 对象而非 data URL
  };

  // 组件卸载时清理 preview URL
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragover(false);
    if (e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleGenerate = async () => {
    if (!user) {
      openAuth();
      return;
    }
    if (!quota?.remaining || !quota?.global_remaining) {
      toast.error(quota?.global_remaining === 0 ? '本轮免费体验名额已结束' : '你的免费生图机会已用完');
      return;
    }
    if (!uploadedFile) return;
    // 隐式反馈：拿到过结果又重新生成 = 对上一张不满意的信号
    if (lastTraceId && generatedImage) sendFeedback(lastTraceId, 'regenerate');
    // 移动端是纵向排布，生成按钮在画布上方；不滚过去用户看不到进度，会以为没反应
    if (window.matchMedia('(max-width: 1023px)').matches) {
      previewPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    setIsGenerating(true);
    setGeneratedImage(null);
    setProgress(0);
    setStatusText('正在准备...');

    try {
      // 1. 提交生成任务
      setProgress(10);
      setStatusText('正在上传图片...');

      // 直接使用 File 对象，无需转换
      const formData = new FormData();
      formData.append('image', uploadedFile, uploadedFile.name);
      formData.append('style', selectedStyle);
      formData.append('room_type', selectedRoom);
      formData.append('session_id', getSessionId());
      if (notes) formData.append('custom_prompt', notes);
      
      setProgress(20);
      setStatusText('正在提交生成任务...');
      
      const response = await fetch(`${API_BASE}/api/v1/generate`, {
        method: 'POST',
        body: formData,
        signal: AbortSignal.timeout(API_TIMEOUT_MS),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        if (errorData.data?.quota) setQuota(errorData.data.quota);
        const detail = errorData.detail;
        throw new Error((typeof detail === 'string' ? detail : detail?.message) || errorData.message || errorData.msg || `服务器错误 ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.code !== 0) {
        throw new Error(result.message || result.msg || '生成失败');
      }
      if (result.data?.quota) setQuota(result.data.quota);
      
      // 后端使用generate_and_wait，直接返回结果
      setProgress(90);
      setStatusText('正在加载结果...');
      
      const outputUrls = result.data?.output_urls || [];
      if (outputUrls.length > 0) {
        const generatedImageUrl = outputUrls[0];
        setGeneratedImage(generatedImageUrl);
        setLastTraceId(result.data?.trace_id || null);
        setFeedbackGiven(null);
        addDesignHistory({
          taskId: result.data?.task_id,
          outputUrl: generatedImageUrl,
          style: selectedStyle,
          roomType: selectedRoom,
          prompt: result.data?.prompt || notes,
          source: 'playground',
        });
        setProgress(100);
        setStatusText('生成完成!');
      } else {
        throw new Error('未获取到生成的图片');
      }
      
    } catch (error) {
      console.error('Generate error:', error);
      // statusText 随 isGenerating=false 一起消失，必须用 toast 让用户看到失败原因
      toast.error(`生成失败：${error.message}`, { duration: 6000 });
      setStatusText(`错误: ${error.message}`);
      setProgress(0);
    } finally {
      setIsGenerating(false);
    }
  };

  if (authLoading) {
    return <div className="min-h-screen bg-ivory"><Navbar /><div className="pt-40 text-center text-charcoal/50">正在确认登录状态…</div></div>;
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-ivory">
        <Navbar />
        <main className="flex min-h-screen items-center justify-center px-4 pt-[84px]">
          <div className="luxury-card max-w-md rounded-2xl p-9 text-center">
            <Lock className="mx-auto mb-5 h-10 w-10 text-warm-gold" />
            <h1 className="text-2xl font-semibold text-charcoal">登录后开始设计</h1>
            <p className="mt-3 text-sm leading-6 text-charcoal/60">免费注册即可获得 3 次生图机会，无需手机号或邮箱。</p>
            <button onClick={openAuth} className="gold-gradient mt-7 w-full rounded-lg py-3.5 font-medium text-white">注册 / 登录</button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-ivory">
      <Navbar />
      
      <main className="pt-[84px] min-h-screen">
        {/* 移动端：自然高度、整页滚动；桌面端（lg+）：固定一屏、各栏内部滚动 */}
        <div className="p-4 md:p-6 lg:h-[calc(100vh-84px)] lg:overflow-hidden">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-6 lg:h-full">
            {/* Left Panel: Controls */}
            <div className="lg:col-span-3 lg:overflow-y-auto lg:pr-2 space-y-4 animate-fade-in">
              {/* Upload Area */}
              <div className="luxury-card rounded-lg p-4 lg:p-5">
                <h3 className="font-medium text-charcoal mb-3 flex items-center gap-2">
                  <span className="w-5 h-5 bg-warm-gold/10 rounded-full flex items-center justify-center text-xs text-warm-gold font-bold">1</span>
                  <span>上传房间照片</span>
                </h3>
                {!previewUrl ? (
                  <div 
                    className={`upload-zone rounded-lg p-6 text-center cursor-pointer ${isDragover ? 'dragover' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setIsDragover(true); }}
                    onDragLeave={() => setIsDragover(false)}
                    onDrop={handleDrop}
                  >
                    <input 
                      ref={fileInputRef}
                      type="file" 
                      className="hidden" 
                      accept="image/*"
                      onChange={(e) => e.target.files[0] && handleFileSelect(e.target.files[0])}
                    />
                    <Upload className="w-10 h-10 mx-auto text-warm-gold/40 mb-3" />
                    <p className="text-sm font-medium text-charcoal mb-1">点击或拖拽上传</p>
                    <p className="text-xs text-charcoal/50">支持 JPG、PNG 格式，不大于 10MB</p>
                  </div>
                ) : (
                  <div className="relative">
                    <img src={previewUrl} alt="Preview" className="w-full rounded-lg" />
                    <button 
                      onClick={() => { if (previewUrl) URL.revokeObjectURL(previewUrl); setPreviewUrl(null); setUploadedFile(null); setUploadedImage(null); }}
                      className="absolute top-2 right-2 w-7 h-7 bg-white/90 rounded-full flex items-center justify-center shadow-md hover:bg-white"
                    >
                      <span className="text-charcoal text-sm">×</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Room Type */}
              <div className="luxury-card rounded-lg p-4 lg:p-5">
                <h3 className="font-medium text-charcoal mb-3 flex items-center gap-2">
                  <span className="w-5 h-5 bg-warm-gold/10 rounded-full flex items-center justify-center text-xs text-warm-gold font-bold">2</span>
                  <span>选择房间类型</span>
                </h3>
                <div className="flex flex-wrap gap-2">
                  {roomTypes.map(room => (
                    <button
                      key={room.id}
                      onClick={() => setSelectedRoom(room.id)}
                      className={`room-tag px-3 py-1.5 rounded-sm text-xs font-medium ${selectedRoom === room.id ? 'active' : 'text-charcoal/70'}`}
                    >
                      {room.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Style Selector */}
              <div className="luxury-card rounded-lg p-4 lg:p-5">
                <h3 className="font-medium text-charcoal mb-3 flex items-center gap-2">
                  <span className="w-5 h-5 bg-warm-gold/10 rounded-full flex items-center justify-center text-xs text-warm-gold font-bold">3</span>
                  <span>选择设计风格</span>
                </h3>
                {/* 手机上 3 列：10 个风格从 5 行压到 4 行，少滚约 400px（小卡片仍看得清风格） */}
                <div className="grid grid-cols-3 sm:grid-cols-2 gap-2">
                  {styles.map(style => (
                    <div
                      key={style.id}
                      onClick={() => setSelectedStyle(style.id)}
                      className={`luxury-card cursor-pointer overflow-hidden rounded-lg ${selectedStyle === style.id ? 'selected' : ''}`}
                    >
                      <img src={style.img} alt={style.label} className="w-full aspect-square object-cover" />
                      <div className="p-1.5">
                        <p className="text-xs font-medium">{style.label}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Additional Notes */}
              <div className="luxury-card rounded-lg p-4 lg:p-5">
                <h3 className="font-medium text-charcoal mb-3 flex items-center gap-2">
                  <span className="w-5 h-5 bg-warm-gold/10 rounded-full flex items-center justify-center text-xs text-warm-gold font-bold">4</span>
                  <span>补充说明（可选）</span>
                </h3>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full border border-warm-gold/20 rounded-lg p-2.5 bg-transparent focus:border-warm-gold focus:outline-none transition-colors text-base lg:text-sm resize-none h-16 placeholder:text-charcoal/40"
                  placeholder="描述您的偏好，如：暖色调、自然材质、更多收纳空间..."
                />
              </div>

              {/* Generate Button */}
              <button 
                onClick={handleGenerate}
                disabled={!uploadedFile || isGenerating || !quota?.remaining || !quota?.global_remaining}
                className="w-full gold-gradient text-white py-3 rounded-lg text-sm font-medium tracking-wide hover:opacity-90 transition-opacity shadow-lg flex items-center justify-center gap-2 disabled:opacity-50"
              >
                <Zap className="w-4 h-4" />
                <span>{isGenerating ? '生成中...' : quota?.remaining ? `生成设计方案 · 剩余 ${quota.remaining} 次` : '体验次数已用完'}</span>
              </button>
            </div>

            {/* Center Panel: Preview */}
            {/* 移动端给足高度，否则内部 flex-1 会塌成 0 高；桌面端由父级 h-full 撑开 */}
            <div ref={previewPanelRef} className="lg:col-span-6 flex flex-col animate-fade-in min-h-[70vh] lg:min-h-0" style={{ animationDelay: '0.1s' }}>
              {/* Preview Area */}
              <div className="luxury-card rounded-lg overflow-hidden flex-1 flex flex-col min-h-0">
                <div className="bg-mist/50 p-3 border-b border-warm-gold/10 flex items-center justify-between flex-shrink-0">
                  {/* 模式切换按钮 */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setViewMode('preview')}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                        viewMode === 'preview' 
                          ? 'bg-warm-gold text-white' 
                          : 'bg-white border border-warm-gold/30 text-charcoal hover:border-warm-gold'
                      }`}
                    >
                      <Eye className="w-3.5 h-3.5" />
                      设计预览
                    </button>
                    <button
                      onClick={toggleRefineMode}
                      disabled={!generatedImage}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                        viewMode === 'refine' 
                          ? 'bg-warm-gold text-white' 
                          : 'bg-white border border-warm-gold/30 text-charcoal hover:border-warm-gold disabled:opacity-50 disabled:cursor-not-allowed'
                      }`}
                    >
                      <Wand2 className="w-3.5 h-3.5" />
                      精修模式
                    </button>
                  </div>
                  {generatedImage && (
                    <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => { sendFeedback(lastTraceId, 'satisfied'); setFeedbackGiven('satisfied'); toast.success('感谢反馈！'); }}
                      disabled={!!feedbackGiven}
                      className={`text-xs px-2.5 py-1 border rounded-sm transition-colors flex items-center gap-1 ${
                        feedbackGiven === 'satisfied'
                          ? 'border-warm-gold bg-warm-gold/10 text-charcoal'
                          : 'border-warm-gold/30 text-charcoal hover:border-warm-gold disabled:opacity-40 disabled:cursor-not-allowed'
                      }`}
                    >
                      👍 满意
                    </button>
                    <button
                      onClick={() => { sendFeedback(lastTraceId, 'unsatisfied'); setFeedbackGiven('unsatisfied'); toast('已记录，我们会继续改进', { icon: '🙏' }); }}
                      disabled={!!feedbackGiven}
                      className={`text-xs px-2.5 py-1 border rounded-sm transition-colors flex items-center gap-1 ${
                        feedbackGiven === 'unsatisfied'
                          ? 'border-warm-gold bg-warm-gold/10 text-charcoal'
                          : 'border-warm-gold/30 text-charcoal hover:border-warm-gold disabled:opacity-40 disabled:cursor-not-allowed'
                      }`}
                    >
                      👎 不要了
                    </button>
                    <button
                      onClick={async () => {
                        try {
                          sendFeedback(lastTraceId, 'download');
                          const response = await fetch(generatedImage);
                          const blob = await response.blob();
                          const blobUrl = URL.createObjectURL(blob);
                          const link = document.createElement('a');
                          link.href = blobUrl;
                          link.download = `design_${Date.now()}.jpg`;
                          document.body.appendChild(link);
                          link.click();
                          document.body.removeChild(link);
                          URL.revokeObjectURL(blobUrl);
                        } catch (error) {
                          console.error('下载失败:', error);
                          alert('下载失败，请右键图片另存为');
                        }
                      }}
                      className="text-xs px-2.5 py-1 border border-warm-gold/30 rounded-sm text-charcoal hover:border-warm-gold transition-colors flex items-center gap-1"
                    >
                      <Download className="w-3 h-3" />
                      下载
                    </button>
                    </div>
                  )}
                </div>
                <div className="flex-1 p-4 overflow-auto min-h-0">
                  <div className="min-h-full bg-mist/30 rounded-lg flex flex-col items-center justify-center relative">
                    {/* 生成中状态 - 进度条 */}
                    {isGenerating && (
                      <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/90 rounded-lg z-10">
                        <div className="w-16 h-16 mb-4 relative">
                          <svg className="w-16 h-16 animate-spin" viewBox="0 0 100 100">
                            <circle cx="50" cy="50" r="40" fill="none" stroke="#F5F3EF" strokeWidth="8" />
                            <circle 
                              cx="50" cy="50" r="40" fill="none" stroke="#C4A962" strokeWidth="8"
                              strokeDasharray={`${progress * 2.51} 251`}
                              strokeLinecap="round"
                              transform="rotate(-90 50 50)"
                              style={{ transition: 'stroke-dasharray 0.3s ease' }}
                            />
                          </svg>
                          <span className="absolute inset-0 flex items-center justify-center text-sm font-medium text-warm-gold">
                            {progress}%
                          </span>
                        </div>
                        <p className="text-charcoal font-medium text-sm mb-1">Roommate正在全速生图中···</p>
                        <p className="text-charcoal/50 text-xs">{statusText}</p>
                        
                        {/* 进度条 */}
                        <div className="w-64 h-2 bg-mist rounded-full mt-4 overflow-hidden">
                          <div 
                            className="h-full gold-gradient rounded-full transition-all duration-300 ease-out"
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                      </div>
                    )}
                    
                    {/* 默认空状态 */}
                    {!generatedImage && !isGenerating && (
                      <>
                        <svg className="w-14 h-14 text-warm-gold/20 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                        </svg>
                        <p className="text-charcoal/40 text-sm">上传照片后，AI 生成的设计将在此显示</p>
                      </>
                    )}
                    
                    {/* 生成结果 */}
                    {generatedImage && !isGenerating && (
                      <div
                        ref={imageContainerRef}
                        className={`relative w-full h-full ${viewMode === 'refine' ? 'cursor-crosshair touch-none' : ''}`}
                        onPointerDown={handlePointerDown}
                        onPointerMove={handlePointerMove}
                        onPointerUp={handlePointerUp}
                        onPointerCancel={() => { if (isDrawingBox) { setIsDrawingBox(false); setBoxStart(null); setBoxEnd(null); } }}
                      >
                        <img src={displayImage || generatedImage} alt="Generated Design" className="w-full h-full object-contain rounded-lg select-none" draggable={false} />
                        
                        {/* 框选绘制中的矩形 - 浅蓝色虚线框 */}
                        {isDrawingBox && boxStart && boxEnd && (
                          <div
                            className="absolute border-2 border-dashed pointer-events-none"
                            style={{
                              left: Math.min(boxStart.screenX, boxEnd.screenX),
                              top: Math.min(boxStart.screenY, boxEnd.screenY),
                              width: Math.abs(boxEnd.screenX - boxStart.screenX),
                              height: Math.abs(boxEnd.screenY - boxStart.screenY),
                              borderColor: '#60A5FA',
                              backgroundColor: 'rgba(96, 165, 250, 0.2)'
                            }}
                          />
                        )}
                        
                        {/* 选中区域显示已改为overlay高亮图 */}
                        
                        {/* Canvas遮罩层 - 精修模式下显示 */}
                        {viewMode === 'refine' && (
                          <canvas
                            ref={canvasRef}
                            className="absolute top-0 left-0 w-full h-full pointer-events-none"
                            style={{ mixBlendMode: 'multiply' }}
                          />
                        )}
                        
                        {/* 精修模式提示 */}
                        {viewMode === 'refine' && !selectedMask && !isSegmenting && !isDrawingBox && (
                          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/70 text-white px-4 py-2 rounded-full text-xs">
                            拖动框选要修改的家具
                          </div>
                        )}
                        
                        {/* 分割加载中 - 简洁进度动画 */}
                        {isSegmenting && (
                          <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-lg">
                            <div className="bg-white px-5 py-3 rounded-lg shadow-lg flex items-center gap-3">
                              <div className="w-5 h-5 border-2 border-warm-gold border-t-transparent rounded-full animate-spin"></div>
                              <span className="text-sm text-charcoal">正在识别物体...</span>
                            </div>
                          </div>
                        )}
                        
                        {/* 选中区域提示 */}
                        {selectedMask && viewMode === 'refine' && (
                          <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-warm-gold text-white px-4 py-2 rounded-full text-xs flex items-center gap-2">
                            <Wand2 className="w-3 h-3" />
                            <span className="lg:hidden">已选中区域，请在下方输入修改指令</span>
                            <span className="hidden lg:inline">已选中区域，请在右侧输入修改指令</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>

            </div>

            {/* Right Panel: AI Chat */}
            <div className="lg:col-span-3 animate-fade-in h-[70vh] lg:h-auto min-h-0" style={{ animationDelay: '0.2s' }}>
              <div className="luxury-card rounded-lg overflow-hidden h-full flex flex-col min-h-0">
                <div className="bg-mist/50 p-3 border-b border-warm-gold/10 flex items-center gap-2">
                  <div className="w-7 h-7 bg-warm-gold/10 rounded-full flex items-center justify-center">
                    <MessageSquare className="w-3.5 h-3.5 text-warm-gold" />
                  </div>
                  <div>
                    <h3 className="font-medium text-charcoal text-sm">AI 设计助手</h3>
                    <p className="text-xs text-charcoal/50">{previewUrl ? '与 AI 交流，优化您的设计方案' : '装修知识问答 & 设计助手'}</p>
                  </div>
                </div>

                {/* Chat Messages */}
                <div ref={chatContainerRef} className="chat-container flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
                  {chatMessages.map((msg, index) => (
                    <div key={index} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`flex flex-col ${msg.type === 'user' ? 'items-end' : 'items-start'} max-w-[90%]`}>
                        <div className={`px-3 py-2 rounded-2xl text-xs ${msg.type === 'user' ? 'chat-bubble-user rounded-tr-sm' : 'chat-bubble-ai rounded-tl-sm'}`}>
                          {msg.type === 'ai' ? (
                            <div className="chat-markdown">
                              <ReactMarkdown>{msg.text}</ReactMarkdown>
                            </div>
                          ) : msg.text}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Quick Prompts - 根据上下文显示不同快捷按钮 */}
                <div className="px-3 py-2 border-t border-warm-gold/10 flex-shrink-0">
                  <div className="flex flex-wrap gap-1.5">
                    {viewMode === 'refine' && selectedMask ? (
                      // 精修模式快捷按钮
                      <>
                        {REFINE_PROMPTS.map((item, index) => (
                          <button key={index} onClick={() => sendMessageWithMask(item.prompt)} disabled={isGenerating} className="px-2 py-1 text-xs bg-warm-gold/10 text-charcoal/80 rounded-full hover:bg-warm-gold/20 transition-colors disabled:opacity-50">
                            {item.label}
                          </button>
                        ))}
                        <button onClick={() => setSelectedMask(null)} className="px-2 py-1 text-xs bg-red-100 text-red-600 rounded-full hover:bg-red-200 transition-colors">取消选择</button>
                      </>
                    ) : previewUrl ? (
                      // 有图片时：生成快捷按钮
                      IMAGE_PROMPTS.map((item, index) => (
                        <button key={index} onClick={() => sendMessage(item.prompt)} disabled={isGenerating} className="px-2 py-1 text-xs bg-warm-gold/10 text-charcoal/80 rounded-full hover:bg-warm-gold/20 transition-colors disabled:opacity-50">
                          {item.label}
                        </button>
                      ))
                    ) : (
                      // 无图片时：知识问答快捷按钮
                      KNOWLEDGE_PROMPTS.map((item, index) => (
                        <button key={index} onClick={() => sendMessage(item.prompt)} disabled={isGenerating} className="px-2 py-1 text-xs bg-warm-gold/10 text-charcoal/80 rounded-full hover:bg-warm-gold/20 transition-colors disabled:opacity-50">
                          {item.label}
                        </button>
                      ))
                    )}
                  </div>
                </div>

                {/* Chat Input */}
                <div className="p-3 border-t border-warm-gold/10 flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <input
                      ref={chatInputRef}
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && !isGenerating && (selectedMask ? sendMessageWithMask() : sendMessage())}
                      disabled={isGenerating}
                      /* 移动端字号必须 >=16px，否则 iOS Safari 聚焦时会自动放大整个页面 */
                      className={`flex-1 border rounded-lg px-3 py-2 text-base lg:text-xs focus:outline-none transition-colors disabled:opacity-50 ${
                        selectedMask ? 'border-warm-gold bg-warm-gold/5 focus:border-warm-gold' : 'border-warm-gold/20 focus:border-warm-gold'
                      }`}
                      placeholder={selectedMask ? "描述对选中区域的修改..." : previewUrl ? "描述设计需求或问我装修问题..." : "问我任何装修问题，如：小户型怎么布局？"}
                    />
                    <button
                      onClick={() => selectedMask ? sendMessageWithMask() : sendMessage()}
                      disabled={isGenerating || !chatInput.trim()}
                      className="gold-gradient text-white px-3 py-2 rounded-lg text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

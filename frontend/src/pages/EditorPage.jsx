import { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  MousePointer2, Type, Square, Undo2, Redo2, 
  Download, Sparkles, RefreshCw, Layers, Palette,
  Sofa, Lamp, Image as ImageIcon, X
} from 'lucide-react';
import toast from 'react-hot-toast';
import { segmentByPoint, segmentByText, inpaintRegion, replaceFurniture } from '../services/segmentApi';

const TOOLS = [
  { id: 'point', name: '点击选择', icon: MousePointer2, desc: '点击物体进行分割' },
  { id: 'text', name: '文本选择', icon: Type, desc: '输入物体名称自动分割' },
  { id: 'box', name: '框选', icon: Square, desc: '绘制边界框分割' },
];

const FURNITURE_TYPES = [
  { id: 'sofa', name: '沙发', emoji: '🛋️' },
  { id: 'chair', name: '椅子', emoji: '🪑' },
  { id: 'table', name: '桌子', emoji: '🪵' },
  { id: 'bed', name: '床', emoji: '🛏️' },
  { id: 'lamp', name: '灯具', emoji: '💡' },
  { id: 'cabinet', name: '柜子', emoji: '🗄️' },
];

const DECORATION_TYPES = [
  { id: 'painting', name: '挂画', emoji: '🖼️' },
  { id: 'plant', name: '绿植', emoji: '🌿' },
  { id: 'vase', name: '花瓶', emoji: '🏺' },
  { id: 'curtain', name: '窗帘', emoji: '🪟' },
  { id: 'rug', name: '地毯', emoji: '🧶' },
];

export default function EditorPage() {
  const [image, setImage] = useState(null);
  const [currentTool, setCurrentTool] = useState('point');
  const [masks, setMasks] = useState([]);
  const [selectedMask, setSelectedMask] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [textPrompt, setTextPrompt] = useState('');
  const [replaceType, setReplaceType] = useState('furniture');
  const [selectedItem, setSelectedItem] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  
  const canvasRef = useRef(null);
  const imageRef = useRef(null);

  const handleImageLoad = useCallback((e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setImage({
          file,
          src: event.target.result,
          name: file.name
        });
        setMasks([]);
        setSelectedMask(null);
        setHistory([{ image: event.target.result, masks: [] }]);
        setHistoryIndex(0);
      };
      reader.readAsDataURL(file);
    }
  }, []);

  const handleCanvasClick = useCallback(async (e) => {
    if (!image || currentTool !== 'point' || isProcessing) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = imageRef.current.naturalWidth / rect.width;
    const scaleY = imageRef.current.naturalHeight / rect.height;
    
    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);

    setIsProcessing(true);
    toast.loading('SAM3 正在分割...', { id: 'segment' });

    try {
      const result = await segmentByPoint(image.file, x, y);
      if (result.code === 0 && result.data.masks.length > 0) {
        const newMask = {
          id: Date.now(),
          data: result.data.masks[0],
          box: result.data.boxes[0],
          score: result.data.scores[0],
          point: { x, y }
        };
        setMasks(prev => [...prev, newMask]);
        setSelectedMask(newMask.id);
        toast.success('分割成功', { id: 'segment' });
      } else {
        toast.error('未检测到物体', { id: 'segment' });
      }
    } catch (error) {
      toast.error('分割失败: ' + error.message, { id: 'segment' });
    } finally {
      setIsProcessing(false);
    }
  }, [image, currentTool, isProcessing]);

  const handleTextSegment = useCallback(async () => {
    if (!image || !textPrompt.trim() || isProcessing) return;

    setIsProcessing(true);
    toast.loading('SAM3 正在识别...', { id: 'segment' });

    try {
      const result = await segmentByText(image.file, textPrompt);
      if (result.code === 0 && result.data.masks.length > 0) {
        const newMasks = result.data.masks.map((mask, i) => ({
          id: Date.now() + i,
          data: mask,
          box: result.data.boxes[i],
          score: result.data.scores[i],
          label: textPrompt
        }));
        setMasks(prev => [...prev, ...newMasks]);
        toast.success(`找到 ${newMasks.length} 个 "${textPrompt}"`, { id: 'segment' });
      } else {
        toast.error(`未找到 "${textPrompt}"`, { id: 'segment' });
      }
    } catch (error) {
      toast.error('识别失败: ' + error.message, { id: 'segment' });
    } finally {
      setIsProcessing(false);
    }
  }, [image, textPrompt, isProcessing]);

  const handleReplace = useCallback(async () => {
    if (!image || !selectedMask || !selectedItem || isProcessing) return;

    const mask = masks.find(m => m.id === selectedMask);
    if (!mask) return;

    setIsProcessing(true);
    toast.loading('AI 正在替换...', { id: 'replace' });

    try {
      const result = await replaceFurniture(
        image.file,
        mask.data,
        selectedItem.id,
        'modern'
      );
      
      if (result.code === 0) {
        setImage(prev => ({
          ...prev,
          src: result.data.result_image
        }));
        setMasks([]);
        setSelectedMask(null);
        toast.success('替换成功！', { id: 'replace' });
      } else {
        toast.error(result.message, { id: 'replace' });
      }
    } catch (error) {
      toast.error('替换失败: ' + error.message, { id: 'replace' });
    } finally {
      setIsProcessing(false);
    }
  }, [image, selectedMask, selectedItem, masks, isProcessing]);

  const clearMasks = () => {
    setMasks([]);
    setSelectedMask(null);
  };

  return (
    <div className="pt-20 min-h-screen">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-6">
          {/* Left Toolbar */}
          <div className="w-16 flex flex-col gap-2">
            {TOOLS.map(tool => (
              <button
                key={tool.id}
                onClick={() => setCurrentTool(tool.id)}
                className={`p-3 rounded-xl transition-all ${
                  currentTool === tool.id
                    ? 'bg-primary-600 text-white'
                    : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700'
                }`}
                title={tool.name}
              >
                <tool.icon className="w-5 h-5" />
              </button>
            ))}
            
            <div className="border-t border-neutral-700 my-2" />
            
            <button
              onClick={clearMasks}
              className="p-3 rounded-xl bg-neutral-800 text-neutral-400 hover:bg-neutral-700"
              title="清除选区"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Main Canvas */}
          <div className="flex-1">
            <div className="card-dark p-4">
              {image ? (
                <div className="relative">
                  <div 
                    ref={canvasRef}
                    className="relative cursor-crosshair"
                    onClick={handleCanvasClick}
                  >
                    <img
                      ref={imageRef}
                      src={image.src}
                      alt="Editor"
                      className="w-full rounded-xl"
                    />
                    
                    {/* Mask Overlays */}
                    {masks.map(mask => (
                      <div
                        key={mask.id}
                        className={`absolute inset-0 pointer-events-none transition-opacity ${
                          selectedMask === mask.id ? 'opacity-60' : 'opacity-30'
                        }`}
                        style={{
                          background: selectedMask === mask.id 
                            ? 'rgba(147, 51, 234, 0.5)' 
                            : 'rgba(147, 51, 234, 0.3)'
                        }}
                        onClick={() => setSelectedMask(mask.id)}
                      />
                    ))}

                    {/* Click Points */}
                    {masks.filter(m => m.point).map(mask => (
                      <div
                        key={`point-${mask.id}`}
                        className="absolute w-4 h-4 bg-primary-500 rounded-full border-2 border-white shadow-lg transform -translate-x-1/2 -translate-y-1/2 pointer-events-none"
                        style={{
                          left: `${(mask.point.x / imageRef.current?.naturalWidth) * 100}%`,
                          top: `${(mask.point.y / imageRef.current?.naturalHeight) * 100}%`
                        }}
                      />
                    ))}
                  </div>

                  {isProcessing && (
                    <div className="absolute inset-0 bg-black/50 rounded-xl flex items-center justify-center">
                      <div className="flex flex-col items-center">
                        <div className="w-12 h-12 border-4 border-primary-500/30 border-t-primary-500 rounded-full animate-spin" />
                        <p className="text-white mt-4">AI 处理中...</p>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <label className="flex flex-col items-center justify-center h-96 border-2 border-dashed border-neutral-700 rounded-xl cursor-pointer hover:border-neutral-600 transition-colors">
                  <ImageIcon className="w-16 h-16 text-neutral-600 mb-4" />
                  <p className="text-neutral-400 mb-2">点击上传效果图</p>
                  <p className="text-neutral-500 text-sm">支持 PNG、JPG 格式</p>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleImageLoad}
                    className="hidden"
                  />
                </label>
              )}
            </div>

            {/* Text Prompt (when text tool is selected) */}
            {currentTool === 'text' && image && (
              <div className="mt-4 flex gap-3">
                <input
                  type="text"
                  value={textPrompt}
                  onChange={(e) => setTextPrompt(e.target.value)}
                  placeholder="输入物体名称，如：沙发、椅子、灯..."
                  className="input-luxury flex-1"
                  onKeyDown={(e) => e.key === 'Enter' && handleTextSegment()}
                />
                <button
                  onClick={handleTextSegment}
                  disabled={isProcessing || !textPrompt.trim()}
                  className="btn-primary px-6"
                >
                  识别
                </button>
              </div>
            )}
          </div>

          {/* Right Panel */}
          <div className="w-72 space-y-4">
            {/* Selection Info */}
            <div className="card-dark p-4">
              <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                <Layers className="w-4 h-4" />
                选区信息
              </h3>
              {masks.length > 0 ? (
                <div className="space-y-2">
                  {masks.map((mask, i) => (
                    <div
                      key={mask.id}
                      onClick={() => setSelectedMask(mask.id)}
                      className={`p-3 rounded-lg cursor-pointer transition-colors ${
                        selectedMask === mask.id
                          ? 'bg-primary-600/20 border border-primary-500'
                          : 'bg-neutral-800 hover:bg-neutral-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-neutral-300">
                          {mask.label || `选区 ${i + 1}`}
                        </span>
                        <span className="text-xs text-neutral-500">
                          {(mask.score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-neutral-500 text-sm">
                  {currentTool === 'point' ? '点击图片选择物体' : '使用工具选择物体'}
                </p>
              )}
            </div>

            {/* Replace Options */}
            {selectedMask && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="card-dark p-4"
              >
                <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                  <RefreshCw className="w-4 h-4" />
                  替换为
                </h3>

                {/* Type Tabs */}
                <div className="flex gap-2 mb-4">
                  <button
                    onClick={() => setReplaceType('furniture')}
                    className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
                      replaceType === 'furniture'
                        ? 'bg-primary-600 text-white'
                        : 'bg-neutral-800 text-neutral-400'
                    }`}
                  >
                    <Sofa className="w-4 h-4 inline mr-1" />
                    家具
                  </button>
                  <button
                    onClick={() => setReplaceType('decoration')}
                    className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
                      replaceType === 'decoration'
                        ? 'bg-primary-600 text-white'
                        : 'bg-neutral-800 text-neutral-400'
                    }`}
                  >
                    <Palette className="w-4 h-4 inline mr-1" />
                    装饰
                  </button>
                </div>

                {/* Items Grid */}
                <div className="grid grid-cols-3 gap-2 mb-4">
                  {(replaceType === 'furniture' ? FURNITURE_TYPES : DECORATION_TYPES).map(item => (
                    <button
                      key={item.id}
                      onClick={() => setSelectedItem(item)}
                      className={`p-2 rounded-lg text-center transition-colors ${
                        selectedItem?.id === item.id
                          ? 'bg-primary-600 text-white'
                          : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700'
                      }`}
                    >
                      <div className="text-xl">{item.emoji}</div>
                      <div className="text-xs mt-1">{item.name}</div>
                    </button>
                  ))}
                </div>

                {/* Replace Button */}
                <button
                  onClick={handleReplace}
                  disabled={!selectedItem || isProcessing}
                  className="btn-primary w-full flex items-center justify-center gap-2"
                >
                  <Sparkles className="w-4 h-4" />
                  AI 替换
                </button>
              </motion.div>
            )}

            {/* Download */}
            {image && (
              <button
                onClick={() => {
                  const a = document.createElement('a');
                  a.href = image.src;
                  a.download = `edited-${Date.now()}.png`;
                  a.click();
                }}
                className="btn-secondary w-full flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                下载图片
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

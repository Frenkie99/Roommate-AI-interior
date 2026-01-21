import { useState, useRef, useEffect } from 'react';
import { Upload, Zap, Download, Send, Lightbulb, MessageSquare } from 'lucide-react';
import Navbar from '../components/Navbar';

// 房间类型映射 v2.0：按距离家门口远近排序（玄关→主卧）
const roomTypes = [
  { id: 'entrance', label: '玄关', labelEn: 'Entry' },
  { id: 'living_room', label: '客厅', labelEn: 'Living Room' },
  { id: 'dining_room', label: '餐厅', labelEn: 'Dining' },
  { id: 'kitchen', label: '厨房', labelEn: 'Kitchen' },
  { id: 'balcony', label: '阳台', labelEn: 'Balcony' },
  { id: 'study', label: '书房', labelEn: 'Study' },
  { id: 'bathroom', label: '卫生间', labelEn: 'Bathroom' },
  { id: 'kids_room', label: '儿童房', labelEn: 'Kids' },
  { id: 'bedroom', label: '卧室', labelEn: 'Bedroom' },
  { id: 'master_bedroom', label: '主卧', labelEn: 'Master' },
];

// 风格映射 v2.0：本地代表性图片（/public/styles/）
const styles = [
  { id: 'modern_luxury', label: '现代轻奢', img: '/styles/现代轻奢.png' },
  { id: 'chinese_modern', label: '新中式', img: '/styles/新中式.png' },
  { id: 'american_transitional', label: '美式', img: '/styles/美式.jpg' },
  { id: 'european_neoclassical', label: '欧式', img: '/styles/欧式.png' },
  { id: 'industrial_loft', label: '工业风', img: '/styles/工业风.png' },
  { id: 'natural_wood', label: '原木风', img: '/styles/原木风.png' },
  { id: 'japanese_traditional', label: '日式', img: '/styles/日式.png' },
  { id: 'bohemian', label: '波西米亚', img: '/styles/波西米亚.png' },
  { id: 'bauhaus', label: '包豪斯', img: '/styles/包豪斯.png' },
  { id: 'modern_minimalist', label: '现代简约', img: '/styles/现代简约.png' },
];

// 风格关键词映射（支持泛化识别）
const styleKeywords = {
  modern_luxury: ['轻奢', '现代轻奢', '奢华', 'luxury'],
  chinese_modern: ['中式', '新中式', '中国风', '国风', 'chinese'],
  american_transitional: ['美式', '美国', '美风', 'american'],
  european_neoclassical: ['欧式', '欧洲', '法式', '新古典', '古典', 'european', 'french'],
  industrial_loft: ['工业', '工业风', 'loft', 'industrial', '水泥', '工厂'],
  natural_wood: ['原木', '木质', '自然风', 'japandi', 'wood', '北欧'],
  japanese_traditional: ['日式', '日本', '和风', '日风', 'japanese', '榻榻米'],
  bohemian: ['波西米亚', 'boho', 'bohemian', '波希米亚'],
  bauhaus: ['包豪斯', 'bauhaus'],
  modern_minimalist: ['简约', '极简', 'minimalist', '现代简约', '简洁'],
};

// 从文本中检测风格关键词
const detectStyleFromText = (text) => {
  const lowerText = text.toLowerCase();
  for (const [styleId, keywords] of Object.entries(styleKeywords)) {
    for (const keyword of keywords) {
      if (lowerText.includes(keyword.toLowerCase())) {
        return styleId;
      }
    }
  }
  return null;
};

// 后端API地址（生产环境使用相对路径，由Nginx代理）
const API_BASE = '';

export default function PlaygroundPage() {
  const [selectedRoom, setSelectedRoom] = useState('living_room');
  const [selectedStyle, setSelectedStyle] = useState('modern_minimalist');
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState('');
  const [uploadedImage, setUploadedImage] = useState(null);
  const [generatedImage, setGeneratedImage] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [notes, setNotes] = useState('');
  const [chatMessages, setChatMessages] = useState([
    { type: 'ai', text: '您好！我是您的 AI 设计助手。上传房间照片后，我可以帮您：分析空间结构、推荐配色方案、建议家具布局。有任何问题都可以问我！' }
  ]);
  const [chatInput, setChatInput] = useState('');
  const fileInputRef = useRef(null);
  const chatContainerRef = useRef(null);
  const [isDragover, setIsDragover] = useState(false);

  // 自动滚动到聊天底部
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages]);

  const handleFileSelect = (file) => {
    if (file && file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => setUploadedImage(e.target.result);
      reader.readAsDataURL(file);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragover(false);
    if (e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleGenerate = async () => {
    if (!uploadedImage) return;
    setIsGenerating(true);
    setGeneratedImage(null);
    setProgress(0);
    setStatusText('正在准备...');
    
    try {
      // 1. 提交生成任务
      setProgress(10);
      setStatusText('正在上传图片...');
      
      // 将base64图片转为Blob
      const base64Data = uploadedImage.split(',')[1];
      const blob = await fetch(uploadedImage).then(r => r.blob());
      
      const formData = new FormData();
      formData.append('image', blob, 'upload.jpg');
      formData.append('style', selectedStyle);
      formData.append('room_type', selectedRoom);
      if (notes) formData.append('custom_prompt', notes);
      
      setProgress(20);
      setStatusText('正在提交生成任务...');
      
      const response = await fetch(`${API_BASE}/api/v1/generate`, {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || errorData.msg || `服务器错误 ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.code !== 0) {
        throw new Error(result.message || result.msg || '生成失败');
      }
      
      // 后端使用generate_and_wait，直接返回结果
      setProgress(90);
      setStatusText('正在加载结果...');
      
      const outputUrls = result.data?.output_urls || [];
      if (outputUrls.length > 0) {
        setGeneratedImage(outputUrls[0]);
        setProgress(100);
        setStatusText('生成完成!');
      } else {
        throw new Error('未获取到生成的图片');
      }
      
    } catch (error) {
      console.error('Generate error:', error);
      setStatusText(`错误: ${error.message}`);
      setProgress(0);
    } finally {
      setIsGenerating(false);
    }
  };

  // 预设快捷问题
  const quickPrompts = [
    { label: '再来一张', prompt: '请基于相同的房间结构和视角，生成一个新的设计方案' },
    { label: '换个配色', prompt: '保持当前布局和家具位置，更换不同的配色方案' },
    { label: '换沙发', prompt: '保持房间结构不变，更换不同样式的沙发' },
    { label: '更多绿植', prompt: '保持当前布局，增加更多绿色植物装饰' },
    { label: '暖色调', prompt: '保持当前结构和布局，调整为更温暖的色调' },
    { label: '更简约', prompt: '保持房间结构不变，设计得更加简约现代' },
  ];

  const handleSendChat = async (customPrompt = null) => {
    const messageText = customPrompt || chatInput.trim();
    if (!messageText) return;
    if (!uploadedImage) {
      setChatMessages(prev => [...prev, { type: 'ai', text: '请先上传一张房间照片，我才能为您生成设计方案。' }]);
      return;
    }
    
    // 智能识别风格关键词
    const detectedStyle = detectStyleFromText(messageText);
    let actualStyle = selectedStyle;
    let styleChangeMsg = '';
    
    if (detectedStyle && detectedStyle !== selectedStyle) {
      actualStyle = detectedStyle;
      setSelectedStyle(detectedStyle);  // 同步更新左侧按钮状态
      const styleName = styles.find(s => s.id === detectedStyle)?.label || detectedStyle;
      styleChangeMsg = `（已识别并切换到「${styleName}」风格）`;
    }
    
    // 添加用户消息
    setChatMessages(prev => [...prev, { type: 'user', text: messageText }]);
    setChatInput('');
    
    // 添加AI等待消息
    const waitingMsg = styleChangeMsg 
      ? `${styleChangeMsg} 正在为您生成新的设计方案，请稍候...`
      : '正在为您生成新的设计方案，请稍候...';
    setChatMessages(prev => [...prev, { type: 'ai', text: waitingMsg }]);
    
    // 调用API生成新图片
    setIsGenerating(true);
    setProgress(10);
    setStatusText('正在处理您的需求...');
    
    try {
      const blob = await fetch(uploadedImage).then(r => r.blob());
      const formData = new FormData();
      formData.append('image', blob, 'upload.jpg');
      formData.append('style', actualStyle);  // 使用识别到的风格
      formData.append('room_type', selectedRoom);
      // 将聊天内容作为自定义提示词
      formData.append('custom_prompt', messageText);
      
      setProgress(20);
      setStatusText('AI 正在创作中...');
      
      const response = await fetch(`${API_BASE}/api/v1/generate`, {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        throw new Error(`服务器错误 ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.code !== 0) {
        throw new Error(result.message || '生成失败');
      }
      
      setProgress(90);
      const outputUrls = result.data?.output_urls || [];
      if (outputUrls.length > 0) {
        setGeneratedImage(outputUrls[0]);
        setProgress(100);
        setStatusText('生成完成!');
        // 更新AI回复
        setChatMessages(prev => {
          const newMessages = [...prev];
          newMessages[newMessages.length - 1] = { type: 'ai', text: '已为您生成新的设计方案，请查看预览区域！如需调整，请继续告诉我。' };
          return newMessages;
        });
      } else {
        throw new Error('未获取到生成的图片');
      }
    } catch (error) {
      console.error('Chat generate error:', error);
      setChatMessages(prev => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1] = { type: 'ai', text: `抱歉，生成失败：${error.message}。请重试。` };
        return newMessages;
      });
      setProgress(0);
      setStatusText('');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="min-h-screen bg-ivory">
      <Navbar />
      
      <main className="pt-[84px] min-h-screen">
        <div className="p-6 h-[calc(100vh-84px)] overflow-hidden">
          <div className="grid grid-cols-12 gap-6 h-full">
            {/* Left Panel: Controls */}
            <div className="col-span-3 overflow-y-auto pr-2 space-y-4 animate-fade-in">
              {/* Upload Area */}
              <div className="luxury-card rounded-lg p-5">
                <h3 className="font-medium text-charcoal mb-3 flex items-center gap-2">
                  <span className="w-5 h-5 bg-warm-gold/10 rounded-full flex items-center justify-center text-xs text-warm-gold font-bold">1</span>
                  <span>上传房间照片</span>
                </h3>
                {!uploadedImage ? (
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
                    <p className="text-xs text-charcoal/50">支持 JPG、PNG 格式</p>
                  </div>
                ) : (
                  <div className="relative">
                    <img src={uploadedImage} alt="Preview" className="w-full rounded-lg" />
                    <button 
                      onClick={() => setUploadedImage(null)}
                      className="absolute top-2 right-2 w-7 h-7 bg-white/90 rounded-full flex items-center justify-center shadow-md hover:bg-white"
                    >
                      <span className="text-charcoal text-sm">×</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Room Type */}
              <div className="luxury-card rounded-lg p-5">
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
              <div className="luxury-card rounded-lg p-5">
                <h3 className="font-medium text-charcoal mb-3 flex items-center gap-2">
                  <span className="w-5 h-5 bg-warm-gold/10 rounded-full flex items-center justify-center text-xs text-warm-gold font-bold">3</span>
                  <span>选择设计风格</span>
                </h3>
                <div className="grid grid-cols-2 gap-2">
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
              <div className="luxury-card rounded-lg p-5">
                <h3 className="font-medium text-charcoal mb-3 flex items-center gap-2">
                  <span className="w-5 h-5 bg-warm-gold/10 rounded-full flex items-center justify-center text-xs text-warm-gold font-bold">4</span>
                  <span>补充说明（可选）</span>
                </h3>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full border border-warm-gold/20 rounded-lg p-2.5 bg-transparent focus:border-warm-gold focus:outline-none transition-colors text-sm resize-none h-16 placeholder:text-charcoal/40"
                  placeholder="描述您的偏好，如：暖色调、自然材质、更多收纳空间..."
                />
              </div>

              {/* Generate Button */}
              <button 
                onClick={handleGenerate}
                disabled={!uploadedImage || isGenerating}
                className="w-full gold-gradient text-white py-3 rounded-lg text-sm font-medium tracking-wide hover:opacity-90 transition-opacity shadow-lg flex items-center justify-center gap-2 disabled:opacity-50"
              >
                <Zap className="w-4 h-4" />
                <span>{isGenerating ? '生成中...' : '生成设计方案'}</span>
              </button>
            </div>

            {/* Center Panel: Preview */}
            <div className="col-span-6 flex flex-col animate-fade-in min-h-0" style={{ animationDelay: '0.1s' }}>
              {/* Preview Area */}
              <div className="luxury-card rounded-lg overflow-hidden flex-1 flex flex-col min-h-0">
                <div className="bg-mist/50 p-3 border-b border-warm-gold/10 flex items-center justify-between flex-shrink-0">
                  <h3 className="font-medium text-charcoal text-sm">设计预览</h3>
                  {generatedImage && (
                    <button 
                      onClick={async () => {
                        try {
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
                      <img src={generatedImage} alt="Generated Design" className="w-full h-full object-contain rounded-lg" />
                    )}
                  </div>
                </div>
              </div>

            </div>

            {/* Right Panel: AI Chat */}
            <div className="col-span-3 animate-fade-in min-h-0" style={{ animationDelay: '0.2s' }}>
              <div className="luxury-card rounded-lg overflow-hidden h-full flex flex-col min-h-0">
                <div className="bg-mist/50 p-3 border-b border-warm-gold/10 flex items-center gap-2">
                  <div className="w-7 h-7 bg-warm-gold/10 rounded-full flex items-center justify-center">
                    <MessageSquare className="w-3.5 h-3.5 text-warm-gold" />
                  </div>
                  <div>
                    <h3 className="font-medium text-charcoal text-sm">AI 设计助手</h3>
                    <p className="text-xs text-charcoal/50">与 AI 交流，优化您的设计方案</p>
                  </div>
                </div>

                {/* Chat Messages */}
                <div ref={chatContainerRef} className="chat-container flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
                  {chatMessages.map((msg, index) => (
                    <div key={index} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`px-3 py-2 rounded-2xl max-w-[90%] text-xs ${msg.type === 'user' ? 'chat-bubble-user rounded-tr-sm' : 'chat-bubble-ai rounded-tl-sm'}`}>
                        {msg.text}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Quick Prompts */}
                <div className="px-3 py-2 border-t border-warm-gold/10 flex-shrink-0">
                  <div className="flex flex-wrap gap-1.5">
                    {quickPrompts.map((item, index) => (
                      <button
                        key={index}
                        onClick={() => handleSendChat(item.prompt)}
                        disabled={isGenerating}
                        className="px-2 py-1 text-xs bg-warm-gold/10 text-charcoal/80 rounded-full hover:bg-warm-gold/20 transition-colors disabled:opacity-50"
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Chat Input */}
                <div className="p-3 border-t border-warm-gold/10 flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && !isGenerating && handleSendChat()}
                      disabled={isGenerating}
                      className="flex-1 border border-warm-gold/20 rounded-lg px-3 py-2 text-xs focus:border-warm-gold focus:outline-none transition-colors disabled:opacity-50"
                      placeholder="输入您的设计需求，如：换个颜色、加点装饰..."
                    />
                    <button 
                      onClick={() => handleSendChat()}
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

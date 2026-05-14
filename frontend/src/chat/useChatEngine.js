/**
 * useChatEngine — 聊天状态与逻辑自定义 Hook
 *
 * 从 PlaygroundPage 提取聊天相关的所有状态和处理函数，
 * 使用 routeChatMessage 实现状态优先路由。
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { routeChatMessage } from './chatRouter';
import { getWelcomeMessage } from './quickPrompts';

const API_BASE = '';

// 风格关键词映射
const STYLE_KEYWORDS = {
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

function detectStyleFromText(text) {
  const lower = text.toLowerCase();
  for (const [styleId, keywords] of Object.entries(STYLE_KEYWORDS)) {
    if (keywords.some(kw => lower.includes(kw))) return styleId;
  }
  return null;
}

export function useChatEngine({
  uploadedFile,
  generatedImage,
  selectedMask,
  viewMode,
  selectedStyle,
  selectedRoom,
  styles,
  // 父组件的 state setters（需要写入父组件状态）
  setIsGenerating,
  setProgress,
  setStatusText,
  setGeneratedImage,
  setSelectedMask,
  setSelectedStyle,
}) {
  const [chatMessages, setChatMessages] = useState([
    { type: 'ai', text: getWelcomeMessage(false) }
  ]);
  const [chatInput, setChatInput] = useState('');
  const chatContainerRef = useRef(null);

  // 自动滚动到底部
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages]);

  // 查询知识库
  const queryKnowledgeBase = useCallback(async (message, style, roomType) => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/knowledge/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: message,
          style: style,
          room_type: roomType,
          n_results: 5,
        }),
      });
      if (!response.ok) return null;
      const data = await response.json();
      return data.code === 0 ? data.data : null;
    } catch {
      return null;
    }
  }, []);

  // 处理知识问答路径
  const handleKnowledgeQuery = useCallback(async (messageText) => {
    setChatMessages(prev => [...prev, { type: 'ai', text: '正在思考...' }]);

    const result = await queryKnowledgeBase(messageText, selectedStyle, selectedRoom);

    if (result && result.answer) {
      setChatMessages(prev => {
        const msgs = [...prev];
        msgs[msgs.length - 1] = {
          type: 'ai',
          text: result.answer,
        };
        return msgs;
      });
    } else {
      setChatMessages(prev => {
        const msgs = [...prev];
        msgs[msgs.length - 1] = {
          type: 'ai',
          text: 'AI 助手正在休息中，请稍后再来问我吧～',
        };
        return msgs;
      });
    }
  }, [selectedStyle, selectedRoom, queryKnowledgeBase]);

  // 处理图片生成路径
  const handleGenerate = useCallback(async (messageText) => {
    if (!uploadedFile) {
      setChatMessages(prev => [...prev, {
        type: 'ai',
        text: '请先上传一张房间照片，我才能为您生成设计方案。',
      }]);
      return;
    }

    // 智能识别风格关键词
    const detectedStyle = detectStyleFromText(messageText);
    let actualStyle = selectedStyle;
    let styleChangeMsg = '';

    if (detectedStyle && detectedStyle !== selectedStyle) {
      actualStyle = detectedStyle;
      // 仅本次生成用 detectedStyle，不改写全局 selectedStyle
      const styleName = styles.find(s => s.id === detectedStyle)?.label || detectedStyle;
      styleChangeMsg = `（本次按「${styleName}」风格生成；如需固定切换请点击左侧风格）`;
    }

    const waitingMsg = styleChangeMsg
      ? `${styleChangeMsg} 正在为您生成新的设计方案，请稍候...`
      : '正在为您生成新的设计方案，请稍候...';
    setChatMessages(prev => [...prev, { type: 'ai', text: waitingMsg }]);

    setIsGenerating(true);
    setProgress(10);
    setStatusText('正在处理您的需求...');

    try {
      // 直接使用 File 对象，无需转换
      const formData = new FormData();
      formData.append('image', uploadedFile, uploadedFile.name);
      formData.append('style', actualStyle);
      formData.append('room_type', selectedRoom);
      formData.append('custom_prompt', messageText);

      setProgress(20);
      setStatusText('AI 正在创作中...');

      const response = await fetch(`${API_BASE}/api/v1/generate`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error(`服务器错误 ${response.status}`);

      const result = await response.json();
      if (result.code !== 0) throw new Error(result.message || '生成失败');

      setProgress(90);
      const outputUrls = result.data?.output_urls || [];
      if (outputUrls.length > 0) {
        setGeneratedImage(outputUrls[0]);
        setProgress(100);
        setStatusText('生成完成!');
        setChatMessages(prev => {
          const msgs = [...prev];
          msgs[msgs.length - 1] = {
            type: 'ai',
            text: '已为您生成新的设计方案，请查看预览区域！如需调整，请继续告诉我。',
          };
          return msgs;
        });
      } else {
        throw new Error('未获取到生成的图片');
      }
    } catch (error) {
      console.error('Chat generate error:', error);
      setChatMessages(prev => {
        const msgs = [...prev];
        msgs[msgs.length - 1] = {
          type: 'ai',
          text: `抱歉，生成失败：${error.message}。请重试。`,
        };
        return msgs;
      });
      setProgress(0);
      setStatusText('');
    } finally {
      setIsGenerating(false);
    }
  }, [uploadedFile, selectedStyle, selectedRoom, styles, setIsGenerating, setProgress, setStatusText, setGeneratedImage, setSelectedStyle]);

  // 主发送函数 — 状态优先路由
  const sendMessage = useCallback(async (customPrompt = null) => {
    const messageText = customPrompt || chatInput.trim();
    if (!messageText) return;

    // 添加用户消息
    setChatMessages(prev => [...prev, { type: 'user', text: messageText }]);
    setChatInput('');

    // 路由决策
    const route = routeChatMessage(messageText, {
      hasImage: !!uploadedFile,
      hasMask: !!selectedMask,
      viewMode,
    });

    if (route === 'knowledge') {
      await handleKnowledgeQuery(messageText);
    } else if (route === 'upload_hint') {
      setChatMessages(prev => [...prev, {
        type: 'ai',
        text: '请先上传一张房间照片，我才能为您生成设计方案。',
      }]);
    } else if (route === 'generate') {
      await handleGenerate(messageText);
    }
  }, [chatInput, uploadedFile, selectedMask, viewMode, handleKnowledgeQuery, handleGenerate]);

  // 带 mask 的精修发送
  const sendMessageWithMask = useCallback(async (customPrompt = null) => {
    const messageText = customPrompt || chatInput.trim();
    if (!messageText) return;
    if (!generatedImage) {
      setChatMessages(prev => [...prev, {
        type: 'ai',
        text: '请先生成一张设计图，才能进行精修。',
      }]);
      return;
    }

    setChatMessages(prev => [...prev, { type: 'user', text: messageText }]);
    setChatInput('');

    if (selectedMask && viewMode === 'refine') {
      setChatMessages(prev => [...prev, { type: 'ai', text: '正在对选中区域进行精修，请稍候...' }]);
      setIsGenerating(true);
      setProgress(10);
      setStatusText('正在处理局部修改...');

      try {
        const response = await fetch(generatedImage);
        const blob = await response.blob();

        const formData = new FormData();
        formData.append('image', blob, 'image.jpg');
        formData.append('mask_base64', selectedMask.mask);
        formData.append('prompt', messageText);
        formData.append('strength', 0.85);

        setProgress(30);
        const inpaintResponse = await fetch(`${API_BASE}/api/v1/segment/inpaint`, {
          method: 'POST',
          body: formData,
        });

        const result = await inpaintResponse.json();
        setProgress(90);

        if (result.code === 0 && result.data?.result_image) {
          setGeneratedImage(result.data.result_image);
          setProgress(100);
          setStatusText('精修完成!');
          setChatMessages(prev => {
            const msgs = [...prev];
            msgs[msgs.length - 1] = {
              type: 'ai',
              text: '局部精修完成！如需继续修改，请点击其他区域或描述新的需求。',
            };
            return msgs;
          });
          setSelectedMask(null);
        } else {
          throw new Error(result.message || '精修失败');
        }
      } catch (error) {
        console.error('Inpaint error:', error);
        setChatMessages(prev => {
          const msgs = [...prev];
          msgs[msgs.length - 1] = {
            type: 'ai',
            text: `精修失败：${error.message}。请重试。`,
          };
          return msgs;
        });
        setProgress(0);
      } finally {
        setIsGenerating(false);
      }
    } else {
      // 没有 mask 时走普通发送
      await sendMessage(messageText);
    }
  }, [chatInput, generatedImage, selectedMask, viewMode, sendMessage, setIsGenerating, setProgress, setStatusText, setGeneratedImage, setSelectedMask]);

  return {
    chatMessages,
    setChatMessages,
    chatInput,
    setChatInput,
    chatContainerRef,
    sendMessage,
    sendMessageWithMask,
  };
}

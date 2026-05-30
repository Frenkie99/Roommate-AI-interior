/**
 * useChatEngine — 聊天状态与 Agent 调度 Hook
 *
 * 前端保留上传、预览、精修框选和分割交互；自然语言判断与工具调度交给后端 Agent。
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { getWelcomeMessage } from './quickPrompts';
import { parseAgentResponse } from './agentResponse';

const API_BASE = '';

const DESIGN_ACTION_WORDS = [
  '换', '调整', '变成', '改成', '改为', '增加', '减少', '去掉',
  '生成', '设计', '加', '加点', '加些', '移除', '删除', '更',
  '做', '来一', '配', '放', '摆', '放些',
];
const LOCAL_OBJECT_WORDS = [
  '沙发', '椅子', '桌', '茶几', '床', '柜', '灯', '窗帘', '地毯',
  '绿植', '植物', '挂画', '墙', '背景墙', '吊灯', '区域', '物体', '家具',
];
const LOCAL_POINTER_WORDS = ['把', '将', '这个', '这里', '选中', '局部', '框选', '区域'];

function looksLikeDesignAction(message) {
  return DESIGN_ACTION_WORDS.some(word => message.includes(word));
}

function looksLikeLocalEdit(message) {
  return LOCAL_OBJECT_WORDS.some(word => message.includes(word)) &&
    LOCAL_POINTER_WORDS.some(word => message.includes(word)) &&
    looksLikeDesignAction(message);
}

export function useChatEngine({
  uploadedFile,
  generatedImage,
  selectedMask,
  viewMode,
  selectedStyle,
  selectedRoom,
  setIsGenerating,
  setProgress,
  setStatusText,
  setGeneratedImage,
  setSelectedMask,
  setViewMode,
}) {
  const [chatMessages, setChatMessages] = useState([
    { type: 'ai', text: getWelcomeMessage(false) }
  ]);
  const [chatInput, setChatInput] = useState('');
  const chatContainerRef = useRef(null);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages]);

  const updateLastAssistantMessage = useCallback((text) => {
    setChatMessages(prev => {
      const msgs = [...prev];
      msgs[msgs.length - 1] = { type: 'ai', text };
      return msgs;
    });
  }, []);

  const buildAgentContext = useCallback(() => ({
    has_uploaded_image: !!uploadedFile,
    generated_image: generatedImage,
    view_mode: viewMode,
    has_selected_mask: !!selectedMask,
    style: selectedStyle,
    room_type: selectedRoom,
  }), [uploadedFile, generatedImage, viewMode, selectedMask, selectedStyle, selectedRoom]);

  const appendAgentImages = useCallback(async (formData, messageText, options) => {
    if (options.includeUploadImage && uploadedFile) {
      formData.append('upload_image', uploadedFile, uploadedFile.name);
    }

    if (options.includeCurrentImage && selectedMask && generatedImage && looksLikeDesignAction(messageText)) {
      const response = await fetch(generatedImage);
      const blob = await response.blob();
      formData.append('current_image', blob, 'current-image.jpg');
      formData.append('mask_base64', selectedMask.mask);
    }
  }, [uploadedFile, selectedMask, generatedImage]);

  const applyAgentStatePatch = useCallback((statePatch = {}) => {
    if (Object.prototype.hasOwnProperty.call(statePatch, 'generated_image')) {
      setGeneratedImage(statePatch.generated_image);
    }

    if (
      Object.prototype.hasOwnProperty.call(statePatch, 'selected_mask') &&
      statePatch.selected_mask === null
    ) {
      setSelectedMask(null);
    }
  }, [setGeneratedImage, setSelectedMask]);

  const sendAgentMessage = useCallback(async (customPrompt = null) => {
    const messageText = customPrompt || chatInput.trim();
    if (!messageText) return;

    const userMessage = { type: 'user', text: messageText };
    const history = [...chatMessages, userMessage].slice(-12);
    const isDesignAction = looksLikeDesignAction(messageText);
    const isLocalEditWithoutMask = !!generatedImage && !selectedMask && looksLikeLocalEdit(messageText);
    const likelyRefine = !!selectedMask && isDesignAction;
    const likelyGenerate = !!uploadedFile && isDesignAction && !isLocalEditWithoutMask && !likelyRefine;
    const likelyImageWork = likelyRefine || likelyGenerate;

    setChatMessages(prev => [...prev, userMessage, { type: 'ai', text: '正在处理您的需求...' }]);
    setChatInput('');

    if (likelyImageWork) {
      setIsGenerating(true);
      setProgress(selectedMask ? 20 : 10);
      setStatusText(selectedMask ? '正在准备局部精修...' : '正在准备生成方案...');
    }

    try {
      const formData = new FormData();
      formData.append('message', messageText);
      formData.append('context', JSON.stringify(buildAgentContext()));
      formData.append('history', JSON.stringify(history));
      await appendAgentImages(formData, messageText, {
        includeUploadImage: likelyGenerate,
        includeCurrentImage: likelyRefine,
      });

      if (likelyImageWork) {
        setProgress(selectedMask ? 35 : 20);
        setStatusText(selectedMask ? 'AI 正在局部精修...' : 'AI 正在创作中...');
      }

      const response = await fetch(`${API_BASE}/api/v1/agent/chat`, {
        method: 'POST',
        body: formData,
      });

      const result = await parseAgentResponse(response);

      const data = result.data || {};
      applyAgentStatePatch(data.state_patch);

      if (data.ui_hint === 'refine' && generatedImage && setViewMode) {
        setViewMode('refine');
      }

      if (likelyImageWork) {
        setProgress(100);
        setStatusText(data.action === 'refine_region' ? '精修完成!' : '处理完成!');
      }

      updateLastAssistantMessage(data.assistant_message || '已处理完成。');
    } catch (error) {
      console.error('Agent chat error:', error);
      updateLastAssistantMessage(`抱歉，处理失败：${error.message}。请重试。`);
      setProgress(0);
      setStatusText('');
    } finally {
      if (likelyImageWork) {
        setIsGenerating(false);
      }
    }
  }, [
    chatInput,
    chatMessages,
    selectedMask,
    uploadedFile,
    generatedImage,
    setIsGenerating,
    setProgress,
    setStatusText,
    buildAgentContext,
    appendAgentImages,
    applyAgentStatePatch,
    updateLastAssistantMessage,
    setViewMode,
  ]);

  return {
    chatMessages,
    setChatMessages,
    chatInput,
    setChatInput,
    chatContainerRef,
    sendAgentMessage,
    sendMessage: sendAgentMessage,
    sendMessageWithMask: sendAgentMessage,
  };
}

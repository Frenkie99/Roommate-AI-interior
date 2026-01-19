/**
 * ResultDisplay 组件
 * 用于展示生成的装修效果图
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ReactCompareSlider, ReactCompareSliderImage } from 'react-compare-slider';
import { Download, Maximize2, X, ArrowLeftRight, Image } from 'lucide-react';

export default function ResultDisplay({ result, isGenerating, originalImage }) {
  const [showModal, setShowModal] = useState(false);
  const [viewMode, setViewMode] = useState('compare');

  if (isGenerating) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center">
        <div className="relative">
          <div className="w-20 h-20 rounded-full border-4 border-primary-500/20 border-t-primary-500 animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-12 h-12 rounded-full bg-primary-500/10 animate-pulse" />
          </div>
        </div>
        <p className="text-neutral-400 mt-6 text-center">
          AI 正在生成效果图...<br />
          <span className="text-sm text-neutral-500">预计需要 30-60 秒</span>
        </p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center">
        <div className="w-20 h-20 rounded-2xl bg-neutral-800 flex items-center justify-center mb-4">
          <Image className="w-10 h-10 text-neutral-600" />
        </div>
        <p className="text-neutral-400">
          上传图片并选择风格后<br />
          点击"生成效果图"按钮
        </p>
      </div>
    );
  }

  const handleDownload = async () => {
    try {
      const response = await fetch(result.generatedImage);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `renovation-${Date.now()}.png`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      window.open(result.generatedImage, '_blank');
    }
  };

  return (
    <>
      <div className="flex-1 flex flex-col">
        {/* View Mode Toggle */}
        <div className="flex items-center gap-2 mb-4">
          <button
            onClick={() => setViewMode('compare')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors ${
              viewMode === 'compare' ? 'bg-primary-600 text-white' : 'bg-neutral-800 text-neutral-400 hover:text-white'
            }`}
          >
            <ArrowLeftRight className="w-4 h-4" />
            对比
          </button>
          <button
            onClick={() => setViewMode('result')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors ${
              viewMode === 'result' ? 'bg-primary-600 text-white' : 'bg-neutral-800 text-neutral-400 hover:text-white'
            }`}
          >
            <Image className="w-4 h-4" />
            效果图
          </button>
        </div>

        {/* Image Display */}
        <div className="flex-1 rounded-2xl overflow-hidden bg-neutral-900 relative">
          {viewMode === 'compare' ? (
            <ReactCompareSlider
              itemOne={<ReactCompareSliderImage src={result.originalImage} alt="原图" />}
              itemTwo={<ReactCompareSliderImage src={result.generatedImage} alt="效果图" />}
              className="h-full"
            />
          ) : (
            <img 
              src={result.generatedImage} 
              alt="效果图" 
              className="w-full h-full object-contain"
            />
          )}

          {/* Actions */}
          <div className="absolute bottom-4 right-4 flex gap-2">
            <button
              onClick={() => setShowModal(true)}
              className="p-2.5 rounded-xl bg-black/50 backdrop-blur-sm text-white hover:bg-black/70 transition-colors"
            >
              <Maximize2 className="w-5 h-5" />
            </button>
            <button
              onClick={handleDownload}
              className="p-2.5 rounded-xl bg-primary-600 text-white hover:bg-primary-500 transition-colors"
            >
              <Download className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Fullscreen Modal */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/90 backdrop-blur-xl flex items-center justify-center p-8"
            onClick={() => setShowModal(false)}
          >
            <button className="absolute top-6 right-6 p-2 rounded-full bg-white/10 hover:bg-white/20 text-white">
              <X className="w-6 h-6" />
            </button>
            <img 
              src={result.generatedImage} 
              alt="效果图" 
              className="max-w-full max-h-full object-contain rounded-2xl"
              onClick={(e) => e.stopPropagation()}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

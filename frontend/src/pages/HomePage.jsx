import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, ArrowRight, Zap, Shield, Palette } from 'lucide-react';
import ImageUploader from '../components/ImageUploader';
import StyleSelector from '../components/StyleSelector';
import RoomTypeSelector from '../components/RoomTypeSelector';
import ResultDisplay from '../components/ResultDisplay';
import { generateImage } from '../services/api';
import toast from 'react-hot-toast';

export default function HomePage() {
  const [uploadedImage, setUploadedImage] = useState(null);
  const [selectedStyle, setSelectedStyle] = useState('modern_minimalist');
  const [selectedRoom, setSelectedRoom] = useState('living_room');
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState(null);

  const handleGenerate = useCallback(async () => {
    if (!uploadedImage) {
      toast.error('请先上传毛坯房图片');
      return;
    }

    setIsGenerating(true);
    setResult(null);

    try {
      const response = await generateImage(uploadedImage.file, selectedStyle, selectedRoom);
      if (response.code === 0) {
        setResult({
          originalImage: uploadedImage.preview,
          generatedImage: response.data.output_urls[0],
          style: selectedStyle,
          prompt: response.data.prompt
        });
        toast.success('效果图生成成功！');
      } else {
        toast.error(response.message || '生成失败，请重试');
      }
    } catch (error) {
      toast.error('生成失败：' + (error.message || '网络错误'));
    } finally {
      setIsGenerating(false);
    }
  }, [uploadedImage, selectedStyle, selectedRoom]);

  return (
    <div className="pt-20">
      {/* Hero Section */}
      <section className="relative py-20 lg:py-32 overflow-hidden">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-4xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary-500/10 border border-primary-500/20 text-primary-400 text-sm font-medium mb-6">
                <Sparkles className="w-4 h-4" />
                AI 驱动的智能装修设计
              </span>
            </motion.div>

            <motion.h1 
              className="section-title text-white mb-6"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
            >
              毛坯房秒变
              <span className="text-gradient"> 精装修效果图</span>
            </motion.h1>

            <motion.p 
              className="text-xl text-neutral-400 mb-10 max-w-2xl mx-auto"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              上传一张毛坯房照片，选择您喜欢的装修风格，
              AI 将在数秒内为您呈现专业级精装修效果图
            </motion.p>

            <motion.div 
              className="flex flex-wrap justify-center gap-4"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
            >
              <a href="#generator" className="btn-primary inline-flex items-center gap-2">
                立即体验 <ArrowRight className="w-5 h-5" />
              </a>
              <button className="btn-secondary">
                查看案例
              </button>
            </motion.div>
          </div>

          {/* Features */}
          <motion.div 
            className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-20"
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            {[
              { icon: Zap, title: '秒级生成', desc: 'AI极速渲染，告别漫长等待' },
              { icon: Shield, title: '结构保持', desc: '智能识别并保持原始房间结构' },
              { icon: Palette, title: '多种风格', desc: '9大主流装修风格任您选择' },
            ].map((item, i) => (
              <div key={i} className="card-glass p-6 text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-primary-500/10 mb-4">
                  <item.icon className="w-6 h-6 text-primary-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{item.title}</h3>
                <p className="text-neutral-400 text-sm">{item.desc}</p>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Generator Section */}
      <section id="generator" className="py-20 lg:py-32">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              开始您的 <span className="text-gradient">智能设计</span>
            </h2>
            <p className="text-neutral-400 max-w-xl mx-auto">
              只需三步，即可获得专业级装修效果图
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left: Upload & Settings */}
            <div className="space-y-6">
              <div className="card-dark p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <span className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center text-primary-400 text-sm font-bold">1</span>
                  上传毛坯房图片
                </h3>
                <ImageUploader 
                  onImageUpload={setUploadedImage} 
                  uploadedImage={uploadedImage}
                />
              </div>

              <div className="card-dark p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <span className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center text-primary-400 text-sm font-bold">2</span>
                  选择房间类型
                </h3>
                <RoomTypeSelector 
                  selected={selectedRoom} 
                  onSelect={setSelectedRoom} 
                />
              </div>

              <div className="card-dark p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <span className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center text-primary-400 text-sm font-bold">3</span>
                  选择装修风格
                </h3>
                <StyleSelector 
                  selected={selectedStyle} 
                  onSelect={setSelectedStyle} 
                />
              </div>

              <button 
                className="btn-primary w-full flex items-center justify-center gap-3"
                onClick={handleGenerate}
                disabled={isGenerating || !uploadedImage}
              >
                {isGenerating ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    AI 正在生成中...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    生成效果图
                  </>
                )}
              </button>
            </div>

            {/* Right: Result */}
            <div className="card-dark p-6 min-h-[600px] flex flex-col">
              <h3 className="text-lg font-semibold text-white mb-4">效果预览</h3>
              <ResultDisplay 
                result={result} 
                isGenerating={isGenerating}
                originalImage={uploadedImage?.preview}
              />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

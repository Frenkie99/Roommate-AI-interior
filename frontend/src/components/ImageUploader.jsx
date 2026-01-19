import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, Image as ImageIcon, X } from 'lucide-react';

export default function ImageUploader({ onImageUpload, uploadedImage }) {
  const onDrop = useCallback((acceptedFiles) => {
    const file = acceptedFiles[0];
    if (file) {
      const preview = URL.createObjectURL(file);
      onImageUpload({ file, preview });
    }
  }, [onImageUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.png', '.jpg', '.jpeg'] },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024,
  });

  const handleRemove = (e) => {
    e.stopPropagation();
    onImageUpload(null);
  };

  return (
    <div
      {...getRootProps()}
      className={`
        relative rounded-2xl border-2 border-dashed transition-all duration-300 cursor-pointer
        ${isDragActive 
          ? 'border-primary-500 bg-primary-500/10' 
          : uploadedImage 
            ? 'border-transparent' 
            : 'border-neutral-700 hover:border-neutral-600 bg-neutral-900/50'
        }
      `}
    >
      <input {...getInputProps()} />
      
      <AnimatePresence mode="wait">
        {uploadedImage ? (
          <motion.div
            key="preview"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="relative aspect-video rounded-2xl overflow-hidden"
          >
            <img 
              src={uploadedImage.preview} 
              alt="Preview" 
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
            <button
              onClick={handleRemove}
              className="absolute top-3 right-3 p-2 rounded-full bg-black/50 hover:bg-black/70 text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
            <div className="absolute bottom-3 left-3 text-sm text-white/80">
              点击或拖拽更换图片
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center py-12 px-6"
          >
            <div className={`
              w-16 h-16 rounded-2xl flex items-center justify-center mb-4 transition-colors
              ${isDragActive ? 'bg-primary-500/20' : 'bg-neutral-800'}
            `}>
              {isDragActive ? (
                <Upload className="w-8 h-8 text-primary-400" />
              ) : (
                <ImageIcon className="w-8 h-8 text-neutral-500" />
              )}
            </div>
            <p className="text-neutral-300 font-medium mb-1">
              {isDragActive ? '释放以上传图片' : '拖拽或点击上传毛坯房图片'}
            </p>
            <p className="text-neutral-500 text-sm">
              支持 PNG、JPG 格式，最大 10MB
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

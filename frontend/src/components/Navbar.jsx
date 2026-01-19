import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sparkles, Menu, X } from 'lucide-react';

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-20 items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 group">
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-primary-500 to-pink-500 rounded-xl blur-lg opacity-50 group-hover:opacity-75 transition-opacity" />
              <div className="relative bg-gradient-to-r from-primary-600 to-pink-600 p-2.5 rounded-xl">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
            </div>
            <div>
              <span className="text-xl font-bold text-white">AI 智装</span>
              <span className="hidden sm:inline text-sm text-neutral-400 ml-2">Design Studio</span>
            </div>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-neutral-300 hover:text-white transition-colors">功能特色</a>
            <a href="#styles" className="text-neutral-300 hover:text-white transition-colors">装修风格</a>
            <Link to="/editor" className="text-neutral-300 hover:text-white transition-colors">局部编辑</Link>
            <Link to="/#generator" className="btn-primary text-sm py-3 px-6">
              开始设计
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button 
            className="md:hidden p-2 text-neutral-400 hover:text-white"
            onClick={() => setIsOpen(!isOpen)}
          >
            {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {isOpen && (
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="md:hidden bg-neutral-900/95 backdrop-blur-xl border-t border-neutral-800"
        >
          <div className="px-4 py-6 space-y-4">
            <a href="#features" className="block text-neutral-300 hover:text-white py-2">功能特色</a>
            <a href="#styles" className="block text-neutral-300 hover:text-white py-2">装修风格</a>
            <a href="#pricing" className="block text-neutral-300 hover:text-white py-2">价格方案</a>
            <button className="btn-primary w-full text-sm py-3">开始设计</button>
          </div>
        </motion.div>
      )}
    </nav>
  );
}

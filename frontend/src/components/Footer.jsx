import { Sparkles, Github, Twitter, Mail } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="relative z-10 border-t border-neutral-800 bg-neutral-950/80 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="md:col-span-2">
            <div className="flex items-center gap-3 mb-4">
              <div className="bg-gradient-to-r from-primary-600 to-pink-600 p-2 rounded-xl">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <span className="text-lg font-bold text-white">AI 智装 Design Studio</span>
            </div>
            <p className="text-neutral-400 text-sm max-w-md">
              基于先进AI技术，一键将毛坯房转化为精美装修效果图。
              让您的家居设计梦想触手可及。
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="text-white font-semibold mb-4">产品</h4>
            <ul className="space-y-2 text-sm">
              <li><a href="#" className="text-neutral-400 hover:text-white transition-colors">功能介绍</a></li>
              <li><a href="#" className="text-neutral-400 hover:text-white transition-colors">价格方案</a></li>
              <li><a href="#" className="text-neutral-400 hover:text-white transition-colors">案例展示</a></li>
              <li><a href="#" className="text-neutral-400 hover:text-white transition-colors">API 接口</a></li>
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-4">联系我们</h4>
            <ul className="space-y-2 text-sm">
              <li><a href="#" className="text-neutral-400 hover:text-white transition-colors">帮助中心</a></li>
              <li><a href="#" className="text-neutral-400 hover:text-white transition-colors">商务合作</a></li>
              <li><a href="#" className="text-neutral-400 hover:text-white transition-colors">隐私政策</a></li>
              <li><a href="#" className="text-neutral-400 hover:text-white transition-colors">服务条款</a></li>
            </ul>
          </div>
        </div>

        {/* Bottom */}
        <div className="mt-12 pt-8 border-t border-neutral-800 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-neutral-500 text-sm">
            © 2026 AI智装 Design Studio. All rights reserved.
          </p>
          <div className="flex items-center gap-4">
            <a href="#" className="text-neutral-400 hover:text-white transition-colors">
              <Github className="w-5 h-5" />
            </a>
            <a href="#" className="text-neutral-400 hover:text-white transition-colors">
              <Twitter className="w-5 h-5" />
            </a>
            <a href="#" className="text-neutral-400 hover:text-white transition-colors">
              <Mail className="w-5 h-5" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

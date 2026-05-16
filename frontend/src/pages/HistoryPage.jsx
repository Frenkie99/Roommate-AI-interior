import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Clock, Sparkles, ArrowRight } from 'lucide-react';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';

/**
 * HistoryPage —— 历史记录占位页
 *
 * 历史记录功能尚未接入真实后端（无 /api/v1/history 路由 + 无鉴权体系），
 * 此前的实现是硬编码 Unsplash 图片，用户上传私人户型照后看到的是别人的样张，
 * 既损害信任也违背隐私预期。等鉴权后端 + 历史接口就绪后再恢复真实数据。
 * 详见 issue #49。
 */
export default function HistoryPage() {
  return (
    <div className="min-h-screen bg-ivory flex flex-col">
      <Navbar />

      <main className="flex-1 pt-[84px] flex items-center justify-center px-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="max-w-xl w-full text-center py-16"
        >
          {/* Icon */}
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-warm-gold/10 border border-warm-gold/20 mb-8">
            <Clock className="w-9 h-9 text-warm-gold" strokeWidth={1.5} />
          </div>

          {/* Bilingual title */}
          <h1 className="text-3xl md:text-4xl font-semibold text-charcoal mb-2 tracking-tight">
            敬请期待
          </h1>
          <p className="text-sm uppercase tracking-[0.2em] text-warm-gold/80 mb-8">
            Coming Soon
          </p>

          {/* Explanatory copy */}
          <p className="text-base text-charcoal/70 leading-relaxed mb-3">
            历史记录功能正在开发中。当前生成的设计稿暂未保存到云端。
          </p>
          <p className="text-sm text-charcoal/50 leading-relaxed mb-10">
            History feature is under development. Your generated designs are not yet
            saved to the cloud.
          </p>

          {/* CTA */}
          <Link
            to="/playground"
            className="inline-flex items-center gap-2 gold-gradient text-white px-7 py-3 rounded-sm text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <Sparkles className="w-4 h-4" />
            <span>开始新设计</span>
            <ArrowRight className="w-4 h-4" />
          </Link>

          {/* Secondary note */}
          <p className="text-xs text-charcoal/40 mt-8">
            想第一时间用上这个功能？给我们的 GitHub 仓库点个 Star 关注更新。
          </p>
        </motion.div>
      </main>

      <Footer />
    </div>
  );
}

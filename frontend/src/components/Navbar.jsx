import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X, Globe } from 'lucide-react';
import AuthModal from './AuthModal';

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const [lang, setLang] = useState('zh');
  const [showAuthModal, setShowAuthModal] = useState(false);
  const location = useLocation();

  const toggleLang = () => {
    setLang(lang === 'zh' ? 'en' : 'zh');
  };

  const isActive = (path) => location.pathname === path;

  const t = {
    home: lang === 'zh' ? '首页' : 'Home',
    newDesign: lang === 'zh' ? '新建设计' : 'New Design',
    history: lang === 'zh' ? '历史记录' : 'History',
    pricing: lang === 'zh' ? '定价' : 'Pricing',
    loginSignup: lang === 'zh' ? '登录/注册' : 'Login/Sign Up',
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-white/70 backdrop-blur-xl border-b border-warm-gold/10 h-[84px]">
      <div className="w-full h-full px-4 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center pl-2 flex-1">
          <Link to="/" className="flex items-center gap-3 group">
            <img src="/assets/logo/导航栏logo-抠图.png" alt="Roommate" className="h-14" />
          </Link>
        </div>

        {/* Desktop Nav */}
        <div className="hidden md:flex items-center justify-center gap-10 flex-1">
          <Link 
            to="/" 
            className={`text-sm font-medium transition-colors ${isActive('/') ? 'text-warm-gold' : 'text-charcoal/80 hover:text-warm-gold'}`}
          >
            {t.home}
          </Link>
          <Link 
            to="/playground" 
            className={`text-sm font-medium transition-colors ${isActive('/playground') ? 'text-warm-gold' : 'text-charcoal/80 hover:text-warm-gold'}`}
          >
            {t.newDesign}
          </Link>
          <Link 
            to="/history" 
            className={`text-sm font-medium transition-colors ${isActive('/history') ? 'text-warm-gold' : 'text-charcoal/80 hover:text-warm-gold'}`}
          >
            {t.history}
          </Link>
          <button 
            onClick={() => setShowAuthModal(true)}
            className="text-sm font-medium transition-colors text-charcoal/80 hover:text-warm-gold"
          >
            {t.pricing}
          </button>
        </div>

        {/* Right Actions */}
        <div className="hidden md:flex items-center justify-end gap-5 pr-4 flex-1">
          <button 
            onClick={() => setShowAuthModal(true)}
            className="gold-gradient text-white px-6 py-2.5 rounded-sm text-sm font-medium hover:opacity-90 transition-opacity"
          >
            {t.loginSignup}
          </button>
          <button 
            onClick={toggleLang}
            className="text-sm font-medium text-charcoal/80 hover:text-warm-gold transition-colors flex items-center gap-1.5 border border-warm-gold/30 px-3 py-2 rounded-sm"
          >
            <Globe className="w-4 h-4" />
            <span>{lang === 'zh' ? '中文' : 'EN'}</span>
          </button>
        </div>

        {/* Mobile Menu Button */}
        <button 
          className="md:hidden p-2 text-charcoal hover:text-warm-gold"
          onClick={() => setIsOpen(!isOpen)}
        >
          {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile Menu */}
      {isOpen && (
        <div className="md:hidden bg-white/95 backdrop-blur-xl border-t border-warm-gold/10">
          <div className="px-4 py-6 space-y-4">
            <Link to="/" className="block text-charcoal/80 hover:text-warm-gold py-2" onClick={() => setIsOpen(false)}>{t.home}</Link>
            <Link to="/playground" className="block text-charcoal/80 hover:text-warm-gold py-2" onClick={() => setIsOpen(false)}>{t.newDesign}</Link>
            <Link to="/history" className="block text-charcoal/80 hover:text-warm-gold py-2" onClick={() => setIsOpen(false)}>{t.history}</Link>
            <button onClick={() => { setIsOpen(false); setShowAuthModal(true); }} className="block text-charcoal/80 hover:text-warm-gold py-2 text-left w-full">{t.pricing}</button>
            <div className="pt-4 border-t border-warm-gold/10 space-y-3">
              <button 
                onClick={() => setShowAuthModal(true)}
                className="block w-full gold-gradient text-white text-center py-3 rounded-sm"
              >
                {t.loginSignup}
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Auth Modal */}
      <AuthModal 
        isOpen={showAuthModal} 
        onClose={() => setShowAuthModal(false)} 
      />
    </nav>
  );
}

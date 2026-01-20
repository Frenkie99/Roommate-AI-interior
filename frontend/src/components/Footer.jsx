export default function Footer() {
  return (
    <footer className="bg-charcoal text-ivory py-10 px-8 border-t border-warm-gold/10">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-5">
        <div className="flex items-center">
          <img src="/assets/logo/导航栏logo-抠图.png" alt="Roommate" className="h-10" />
        </div>
        <div className="flex items-center gap-10 text-sm text-ivory/60">
          <a href="#" className="hover:text-warm-gold transition-colors">隐私政策</a>
          <a href="#" className="hover:text-warm-gold transition-colors">服务条款</a>
          <a href="#" className="hover:text-warm-gold transition-colors">联系我们</a>
        </div>
        <p className="text-sm text-ivory/40">© 2025 Roommate. 保留所有权利。</p>
      </div>
    </footer>
  );
}

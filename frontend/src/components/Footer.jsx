export default function Footer() {
  return (
    <footer className="bg-charcoal text-ivory py-10 px-8 border-t border-warm-gold/10">
      <div className="max-w-7xl mx-auto flex flex-col items-center justify-center gap-4">
        <img src="/assets/logo/导航栏logo-抠图.webp" alt="Roommate" className="h-10" loading="lazy" />
        <a
          href="mailto:youchang1999@163.com"
          className="text-sm text-ivory/60 hover:text-warm-gold transition-colors"
        >
          联系我
        </a>
        <p className="text-sm text-ivory/40">© 2025 Roommate. 保留所有权利。</p>
      </div>
    </footer>
  );
}

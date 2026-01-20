import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';

export default function LandingPage() {
  const [sliderPosition, setSliderPosition] = useState(50);
  const sliderRef = useRef(null);
  const isDragging = useRef(false);
  const videoRef = useRef(null);
  const videoSectionRef = useRef(null);
  const hasPlayed = useRef(false);

  const handleMouseDown = () => {
    isDragging.current = true;
  };

  const handleMouseUp = () => {
    isDragging.current = false;
  };

  const handleMouseMove = (e) => {
    if (!isDragging.current || !sliderRef.current) return;
    const rect = sliderRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    setSliderPosition((x / rect.width) * 100);
  };

  useEffect(() => {
    document.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('mousemove', handleMouseMove);
    return () => {
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasPlayed.current && videoRef.current) {
            videoRef.current.play();
            hasPlayed.current = true;
          }
        });
      },
      { threshold: 0.5 }
    );

    if (videoSectionRef.current) {
      observer.observe(videoSectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  const galleryImages = [
    { img: '/assets/gallery/gallery_export/Item_01_Scandinavian_Living_Room_Light_and_Airy.png', label: 'SCANDINAVIAN • LIVING ROOM', title: 'Light & Airy', aspect: 'aspect-2-3', float: 'gallery-float-1' },
    { img: '/assets/gallery/gallery_export/Item_02_Industrial_Bedroom_Urban_Edge.png', label: 'INDUSTRIAL • BEDROOM', title: 'Urban Edge', aspect: 'aspect-3-2', float: 'gallery-float-2' },
    { img: '/assets/gallery/gallery_export/Item_03_Bohemian_Office_Creative_Spirit.png', label: 'BOHEMIAN • OFFICE', title: 'Creative Spirit', aspect: 'aspect-9-16', float: 'gallery-float-3' },
    { img: '/assets/gallery/gallery_export/Item_04_Modern_Kitchen_Clean_Lines.png', label: 'MODERN • KITCHEN', title: 'Clean Lines', aspect: 'aspect-1-1', float: 'gallery-float-4' },
    { img: '/assets/gallery/gallery_export/Item_05_Classic_Bathroom_Timeless_Elegance.png', label: 'CLASSIC • BATHROOM', title: 'Timeless Elegance', aspect: 'aspect-16-9', float: 'gallery-float-5' },
    { img: '/assets/gallery/gallery_export/Item_06_Minimalist_Dining_Pure_Simplicity.png', label: 'MINIMALIST • DINING', title: 'Pure Simplicity', aspect: 'aspect-2-3', float: 'gallery-float-1' },
    { img: '/assets/gallery/gallery_export/Item_07_Japandi_Living_Room_East_Meets_West.png', label: 'JAPANDI • LIVING ROOM', title: 'East Meets West', aspect: 'aspect-3-2', float: 'gallery-float-2' },
    { img: '/assets/gallery/gallery_export/Item_08_Contemporary_Bedroom_Modern_Comfort.png', label: 'CONTEMPORARY • BEDROOM', title: 'Modern Comfort', aspect: 'aspect-9-16', float: 'gallery-float-3' },
    { img: '/assets/gallery/gallery_export/Item_09_Luxury_Living_Room_Opulent_Charm.png', label: 'LUXURY • LIVING ROOM', title: 'Opulent Charm', aspect: 'aspect-1-1', float: 'gallery-float-4' },
    { img: '/assets/gallery/gallery_export/Item_10_Rustic_Kitchen_Natural_Warmth.png', label: 'RUSTIC • KITCHEN', title: 'Natural Warmth', aspect: 'aspect-16-9', float: 'gallery-float-5' },
  ];

  return (
    <div className="min-h-screen">
      <Navbar />
      
      {/* Hero Section */}
      <section id="home" className="h-screen flex items-center px-8 pt-24 pb-8 bg-gradient-to-b from-ivory to-mist hero-bg-pattern relative overflow-hidden">
        {/* Decorative Elements */}
        <div className="absolute top-32 right-16 w-24 h-24 border border-warm-gold/20 rounded-full animate-float" style={{ animationDelay: '0s' }}></div>
        <div className="absolute bottom-24 left-16 w-20 h-20 border border-warm-gold/15 rounded-full animate-float" style={{ animationDelay: '1.5s' }}></div>
        <div className="absolute top-48 left-1/4 w-2 h-2 bg-warm-gold/30 rounded-full animate-float" style={{ animationDelay: '0.5s' }}></div>
        <div className="absolute bottom-32 right-1/4 w-2 h-2 bg-warm-gold/20 rounded-full animate-float" style={{ animationDelay: '1s' }}></div>

        <div className="max-w-7xl mx-auto w-full animate-fade-in">
          <div className="grid lg:grid-cols-12 gap-6 items-center">
            {/* Left: Text Content (5 columns) */}
            <div className="lg:col-span-5 space-y-6 relative">
              <div className="inline-block">
                <p className="text-warm-gold text-xs font-medium tracking-[0.3em] uppercase mb-2">AI-POWERED INTERIOR DESIGN</p>
                <div className="h-px w-12 bg-warm-gold/30"></div>
              </div>
              <h1 className="text-[2.5rem] md:text-[3rem] lg:text-[4rem] font-bold leading-[1.5] hero-text-gradient" style={{ fontFamily: '"Alibaba PuHuiTi", "PingFang SC", "Microsoft YaHei", sans-serif', fontWeight: 700 }}>
                <span>上传毛坯图</span><br/>
                <span className="inline-flex items-center">
                  <span className="text-warm-gold">一键生成</span>
                  <span className="inline-block w-9 h-9 ml-3" style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23C4A962' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z'/%3E%3Cpath d='M13 13l6 6'/%3E%3C/svg%3E\")", backgroundSize: 'contain', backgroundRepeat: 'no-repeat' }}></span>
                </span><br/>
                <span>你的梦中情屋</span>
              </h1>
              <p className="text-base text-charcoal/70 font-light leading-relaxed max-w-md">
                只需 30 秒，AI 将为您的房间打造专属设计方案。
              </p>
              <div className="flex flex-wrap items-center gap-5 pt-2">
                <Link to="/playground" className="inline-flex items-center gap-3 gold-gradient text-white px-10 py-3.5 rounded-sm text-sm font-medium tracking-wide transition-all shadow-lg hover:shadow-xl hover:opacity-90">
                  <span>开始设计</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <span className="text-sm text-charcoal/50 tracking-wide flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122"/>
                  </svg>
                  <span>拖动滑块对比</span>
                </span>
              </div>
            </div>

            {/* Right: Comparison Slider */}
            <div className="lg:col-span-7 relative">
              <div 
                ref={sliderRef}
                className="rounded-lg shadow-2xl relative overflow-hidden cursor-ew-resize select-none"
                onMouseDown={handleMouseDown}
              >
                {/* Before Image (毛坯图) */}
                <div className="relative">
                  <img 
                    src="/assets/hero section/毛坯图.png" 
                    alt="Before" 
                    className="w-full h-[380px] md:h-[420px] lg:h-[450px] object-cover pointer-events-none"
                    draggable="false"
                  />
                  <div className="absolute bottom-5 left-5 bg-black/60 backdrop-blur-sm text-white px-3 py-1.5 rounded-sm text-xs font-medium tracking-wide">
                    改造前
                  </div>
                </div>
                {/* After Image (效果图) - clipped */}
                <div 
                  className="absolute top-0 left-0 w-full h-full overflow-hidden"
                  style={{ clipPath: `inset(0 ${100 - sliderPosition}% 0 0)` }}
                >
                  <img 
                    src="/assets/hero section/效果图.png" 
                    alt="After" 
                    className="w-full h-[380px] md:h-[420px] lg:h-[450px] object-cover pointer-events-none"
                    draggable="false"
                  />
                  <div className="absolute bottom-5 right-5 bg-warm-gold/90 backdrop-blur-sm text-white px-3 py-1.5 rounded-sm text-xs font-medium tracking-wide">
                    改造后
                  </div>
                </div>
                {/* Slider Handle */}
                <div 
                  className="absolute top-0 h-full w-px cursor-ew-resize z-10"
                  style={{ 
                    left: `${sliderPosition}%`,
                    background: 'linear-gradient(180deg, transparent, #C4A962 20%, #C4A962 80%, transparent)'
                  }}
                >
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-11 h-11 bg-white rounded-full flex items-center justify-center shadow-lg border border-warm-gold/30">
                    <svg className="w-5 h-5 text-charcoal" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m6 14l7-7-7-7"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Divider */}
      <div className="section-divider max-w-4xl mx-auto"></div>

      {/* How It Works Section - 左视频右文字布局 */}
      <section id="features" ref={videoSectionRef} className="py-24 px-8 bg-mist">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            {/* Left: Video */}
            <div className="relative rounded-lg overflow-hidden shadow-2xl">
              <video 
                ref={videoRef}
                className="w-full h-auto rounded-lg"
                muted
                playsInline
                controls
                poster="/assets/video/meeting room-1.png"
              >
                <source src="/assets/video/1.mp4" type="video/mp4" />
                您的浏览器不支持视频播放。
              </video>
            </div>

            {/* Right: Text Content */}
            <div className="space-y-6">
              <h2 className="text-3xl md:text-[2rem] lg:text-[2.25rem] font-bold leading-tight text-charcoal" style={{ fontFamily: '"Alibaba PuHuiTi", "PingFang SC", "Microsoft YaHei", sans-serif' }}>
                从毛坯空间到梦想居所的极速进阶
              </h2>
              <p className="text-base text-charcoal/70 leading-relaxed">
                无论是面对原始毛坯房还是初期的施工现场，Roommate都能精准捕捉空间潜能。
              </p>
              <p className="text-base text-charcoal/70 leading-relaxed">
                智能叠加壁纸、地板、家具及氛围灯光，甚至能融入人物角色，从素颜墙体到拎包入住的视觉方案，让空间进化的每一步都极具感染力！
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Gallery Section */}
      <section id="gallery" className="min-h-screen py-16 px-8 bg-ivory flex flex-col justify-center">
        <div className="max-w-7xl mx-auto w-full">
          <div className="text-center mb-12">
            <p className="text-warm-gold text-sm font-medium tracking-[0.3em] uppercase mb-6">Design Gallery</p>
            <h2 className="text-4xl md:text-5xl font-bold" style={{ fontFamily: '"Alibaba PuHuiTi", "PingFang SC", "Microsoft YaHei", sans-serif', fontWeight: 700 }}>精选图库</h2>
          </div>

          {/* Pinterest-style Waterfall Grid */}
          <div className="gallery-waterfall">
            {galleryImages.map((item, index) => (
              <div 
                key={index} 
                className={`gallery-item ${item.aspect} ${item.float}`}
                style={{ animationDelay: `${index * 0.5}s` }}
              >
                <img src={item.img} alt={item.title} className="w-full h-full object-cover" />
                <div className="overlay">
                  <p className="text-xs tracking-wider opacity-80 mb-1">{item.label}</p>
                  <p className="font-serif text-base">{item.title}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section - 黑色背景 */}
      <section className="py-[100px] px-8 bg-obsidian">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-5xl md:text-6xl font-bold text-ivory mb-8 tracking-wide" style={{ fontFamily: '"Alibaba PuHuiTi", "PingFang SC", "Microsoft YaHei", sans-serif', fontWeight: 700 }}>准备好焕新你的空间了吗？</h2>
          <p className="text-lg text-ivory/60 font-light mb-12 max-w-2xl mx-auto">
            加入我们，用 AI 打造理想家居。
          </p>
          <Link to="/playground" className="inline-flex items-center gap-3 gold-gradient text-white px-12 py-5 rounded-sm text-sm font-medium tracking-wide hover:opacity-90 transition-opacity">
            <span>开始您的设计</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      <Footer />
    </div>
  );
}

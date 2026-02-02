import { useState } from 'react';
import { Download, Trash2, Eye, MessageSquare } from 'lucide-react';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';

const designHistory = [
  { id: 1, title: '现代简约客厅', desc: '白色与木质元素的完美结合', style: 'Modern', room: 'Living Room', date: '2025-01-15', img: 'https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=600&h=450&fit=crop' },
  { id: 2, title: '北欧风卧室', desc: '温馨舒适的睡眠空间', style: 'Scandinavian', room: 'Bedroom', date: '2025-01-14', img: 'https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=600&h=450&fit=crop' },
  { id: 3, title: '日式简约厨房', desc: '东方美学与功能性的融合', style: 'Japandi', room: 'Kitchen', date: '2025-01-12', img: 'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=600&h=450&fit=crop' },
  { id: 4, title: '轻奢风客厅', desc: '金属与大理石的奢华质感', style: 'Luxury', room: 'Living Room', date: '2025-01-10', img: 'https://images.unsplash.com/photo-1615529182904-14819c35db37?w=600&h=450&fit=crop' },
];

const chatHistory = [
  { id: 1, title: '现代简约客厅设计咨询', date: '2025-01-15 14:32', msgCount: 12, preview: [
    { type: 'user', text: '我想要一个温馨但不失现代感的客厅' },
    { type: 'ai', text: '我建议采用暖色调的木质家具搭配简洁的线条设计，可以考虑米色沙发配深色茶几...' }
  ]},
  { id: 2, title: '卧室配色方案讨论', date: '2025-01-14 10:15', msgCount: 8, preview: [
    { type: 'user', text: '卧室用什么颜色比较助眠？' },
    { type: 'ai', text: '研究表明，蓝色、绿色和淡紫色等冷色调有助于放松和睡眠...' }
  ]},
  { id: 3, title: '小户型厨房改造建议', date: '2025-01-12 16:45', msgCount: 15, preview: [
    { type: 'user', text: '我的厨房只有5平米，怎么让它看起来更大？' },
    { type: 'ai', text: '小厨房可以通过以下方式扩大视觉空间：1. 使用浅色系橱柜 2. 增加镜面或玻璃元素...' }
  ]},
];

export default function HistoryPage() {
  const [activeTab, setActiveTab] = useState('designs');

  return (
    <div className="min-h-screen bg-ivory">
      <Navbar />
      
      <main className="pt-[84px] min-h-screen">
        {/* Tabs */}
        <div className="bg-white border-b border-warm-gold/10 px-8">
          <div className="max-w-7xl mx-auto flex gap-8">
            <button 
              onClick={() => setActiveTab('designs')}
              className={`py-4 px-2 text-sm font-medium transition-colors ${activeTab === 'designs' ? 'tab-active' : 'text-charcoal/60 hover:text-charcoal'}`}
            >
              生成的设计
            </button>
            <button 
              onClick={() => setActiveTab('chats')}
              className={`py-4 px-2 text-sm font-medium transition-colors ${activeTab === 'chats' ? 'tab-active' : 'text-charcoal/60 hover:text-charcoal'}`}
            >
              对话记录
            </button>
          </div>
        </div>

        {/* Designs Tab Content */}
        {activeTab === 'designs' && (
          <div className="py-10 px-8">
            <div className="max-w-7xl mx-auto">
              {/* Filter Bar */}
              <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
                <div className="flex items-center gap-3">
                  <span className="text-sm text-charcoal/60">筛选:</span>
                  <select className="text-sm border border-warm-gold/30 rounded-sm px-3 py-2 bg-white focus:outline-none focus:border-warm-gold">
                    <option>全部风格</option>
                    <option>现代简约</option>
                    <option>北欧风</option>
                    <option>日式</option>
                  </select>
                  <select className="text-sm border border-warm-gold/30 rounded-sm px-3 py-2 bg-white focus:outline-none focus:border-warm-gold">
                    <option>全部房间</option>
                    <option>客厅</option>
                    <option>卧室</option>
                    <option>厨房</option>
                  </select>
                </div>
                <div className="text-sm text-charcoal/60">
                  共 <span className="font-medium text-charcoal">{designHistory.length}</span> 个设计
                </div>
              </div>

              {/* Design Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {designHistory.map((design, index) => (
                  <div 
                    key={design.id} 
                    className="history-card rounded-lg overflow-hidden animate-fade-in"
                    style={{ animationDelay: `${index * 0.1}s` }}
                  >
                    <div className="relative aspect-[4/3] overflow-hidden">
                      <img src={design.img} alt={design.title} className="w-full h-full object-cover" />
                      <div className="absolute top-3 right-3 bg-white/90 backdrop-blur-sm px-2 py-1 rounded text-xs font-medium text-charcoal">
                        {design.date}
                      </div>
                    </div>
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs px-2 py-0.5 bg-warm-gold/10 text-warm-gold rounded">{design.style}</span>
                        <span className="text-xs px-2 py-0.5 bg-mist text-charcoal/70 rounded">{design.room}</span>
                      </div>
                      <h3 className="font-medium text-charcoal mb-1">{design.title}</h3>
                      <p className="text-xs text-charcoal/50">{design.desc}</p>
                      <div className="flex items-center justify-between mt-4 pt-3 border-t border-warm-gold/10">
                        <button className="text-xs text-warm-gold hover:underline flex items-center gap-1">
                          <Eye className="w-3 h-3" />
                          查看详情
                        </button>
                        <button className="text-xs text-charcoal/50 hover:text-charcoal flex items-center gap-1">
                          <Download className="w-3 h-3" />
                          下载
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Load More */}
              <div className="text-center mt-10">
                <button className="inline-flex items-center gap-2 border border-warm-gold/30 text-charcoal px-6 py-3 rounded-sm text-sm font-medium hover:border-warm-gold hover:text-warm-gold transition-colors">
                  <span>加载更多</span>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Chats Tab Content */}
        {activeTab === 'chats' && (
          <div className="py-10 px-8">
            <div className="max-w-4xl mx-auto space-y-4">
              {chatHistory.map((chat, index) => (
                <div 
                  key={chat.id} 
                  className="history-card rounded-lg p-5 animate-fade-in"
                  style={{ animationDelay: `${index * 0.1}s` }}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="font-medium text-charcoal">{chat.title}</h3>
                      <p className="text-xs text-charcoal/50 mt-1">{chat.date}</p>
                    </div>
                    <span className="text-xs px-2 py-1 bg-warm-gold/10 text-warm-gold rounded">
                      {chat.msgCount} 条消息
                    </span>
                  </div>
                  
                  {/* Chat Preview */}
                  <div className="space-y-3 mb-4">
                    {chat.preview.map((msg, msgIndex) => (
                      <div key={msgIndex} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`px-4 py-2 rounded-2xl max-w-[80%] text-sm ${msg.type === 'user' ? 'chat-bubble-user rounded-tr-sm' : 'chat-bubble-ai rounded-tl-sm'}`}>
                          {msg.text}
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  <div className="flex items-center justify-between pt-3 border-t border-warm-gold/10">
                    <button className="text-sm text-warm-gold hover:underline flex items-center gap-1">
                      <MessageSquare className="w-4 h-4" />
                      查看完整对话
                    </button>
                    <button className="text-sm text-charcoal/50 hover:text-red-500 transition-colors flex items-center gap-1">
                      <Trash2 className="w-4 h-4" />
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}

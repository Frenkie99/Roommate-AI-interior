import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Download, Eye, ImageOff, Trash2 } from 'lucide-react';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';
import { deleteDesignHistory, getDesignHistory } from '../services/historyService';

const STYLE_LABELS = {
  modern_minimalist: '现代简约',
  scandinavian: '北欧风格',
  chinese_modern: '新中式',
  light_luxury: '轻奢风格',
  modern_luxury: '现代轻奢',
  japanese_wood: '日式原木',
  japanese_traditional: '日式',
  industrial: '工业风',
  industrial_loft: '工业风',
  american_country: '美式田园',
  american_transitional: '美式',
  french_romantic: '法式浪漫',
  mediterranean: '地中海',
  european_neoclassical: '欧式',
  natural_wood: '原木风',
  bohemian: '波西米亚',
  bauhaus: '包豪斯',
};

const ROOM_LABELS = {
  entrance: '玄关',
  living_room: '客厅',
  dining_room: '餐厅',
  kitchen: '厨房',
  balcony: '阳台',
  study: '书房',
  bathroom: '卫生间',
  kids_room: '儿童房',
  bedroom: '卧室',
  master_bedroom: '主卧',
};

const SOURCE_LABELS = {
  home: '首页生成',
  playground: '工作台生成',
  agent: 'AI 助手生成',
};

function getLabel(labels, value, fallback) {
  if (!value) return fallback;
  return labels[value] || value;
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '未知时间';

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function buildOptions(history, field, labels) {
  const values = [...new Set(history.map((item) => item[field]).filter(Boolean))];
  return values.map((value) => ({
    value,
    label: getLabel(labels, value, value),
  }));
}

function getCardTitle(record) {
  const room = getLabel(ROOM_LABELS, record.roomType, '空间');
  const style = getLabel(STYLE_LABELS, record.style, 'AI 设计');
  return `${room} · ${style}`;
}

function getPromptPreview(prompt) {
  if (!prompt) return '暂无补充说明';
  return prompt.length > 52 ? `${prompt.slice(0, 52)}...` : prompt;
}

export default function HistoryPage() {
  const [history, setHistory] = useState(() => getDesignHistory());
  const [styleFilter, setStyleFilter] = useState('');
  const [roomFilter, setRoomFilter] = useState('');

  const styleOptions = useMemo(
    () => buildOptions(history, 'style', STYLE_LABELS),
    [history],
  );
  const roomOptions = useMemo(
    () => buildOptions(history, 'roomType', ROOM_LABELS),
    [history],
  );

  const filteredHistory = useMemo(() => history.filter((record) => {
    const matchesStyle = !styleFilter || record.style === styleFilter;
    const matchesRoom = !roomFilter || record.roomType === roomFilter;
    return matchesStyle && matchesRoom;
  }), [history, roomFilter, styleFilter]);

  const handleDelete = (id) => {
    deleteDesignHistory(id);
    setHistory(getDesignHistory());
  };

  const handleDownload = async (record) => {
    try {
      const response = await fetch(record.outputUrl);
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = `${record.id || 'design'}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(blobUrl);
    } catch (error) {
      window.open(record.outputUrl, '_blank', 'noopener,noreferrer');
    }
  };

  const hasHistory = history.length > 0;
  const hasFilteredHistory = filteredHistory.length > 0;

  return (
    <div className="min-h-screen bg-ivory">
      <Navbar />

      <main className="pt-[84px] min-h-screen">
        <div className="bg-white border-b border-warm-gold/10 px-8">
          <div className="max-w-7xl mx-auto py-4">
            <h1 className="text-lg font-medium text-charcoal">生成的设计</h1>
            <p className="text-sm text-charcoal/50 mt-1">
              当前浏览器保存的真实生成记录
            </p>
          </div>
        </div>

        <div className="py-10 px-8">
          <div className="max-w-7xl mx-auto">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-sm text-charcoal/60">筛选</span>
                <select
                  value={styleFilter}
                  onChange={(event) => setStyleFilter(event.target.value)}
                  className="text-sm border border-warm-gold/30 rounded-sm px-3 py-2 bg-white focus:outline-none focus:border-warm-gold"
                >
                  <option value="">全部风格</option>
                  {styleOptions.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
                <select
                  value={roomFilter}
                  onChange={(event) => setRoomFilter(event.target.value)}
                  className="text-sm border border-warm-gold/30 rounded-sm px-3 py-2 bg-white focus:outline-none focus:border-warm-gold"
                >
                  <option value="">全部房间</option>
                  {roomOptions.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div className="text-sm text-charcoal/60">
                共 <span className="font-medium text-charcoal">{filteredHistory.length}</span> 个设计
              </div>
            </div>

            {!hasHistory && (
              <div className="history-card rounded-lg px-6 py-16 text-center">
                <ImageOff className="w-12 h-12 mx-auto text-warm-gold/40 mb-4" />
                <h2 className="text-lg font-medium text-charcoal mb-2">暂无历史记录</h2>
                <p className="text-sm text-charcoal/50 mb-6">
                  生成成功后的设计图会自动保存在这里，方便本次浏览器继续查看。
                </p>
                <Link
                  to="/playground"
                  className="inline-flex items-center justify-center gold-gradient text-white px-5 py-2.5 rounded-sm text-sm font-medium hover:opacity-90 transition-opacity"
                >
                  去生成设计图
                </Link>
              </div>
            )}

            {hasHistory && !hasFilteredHistory && (
              <div className="history-card rounded-lg px-6 py-12 text-center">
                <ImageOff className="w-10 h-10 mx-auto text-warm-gold/40 mb-4" />
                <h2 className="text-base font-medium text-charcoal mb-2">没有符合筛选条件的记录</h2>
                <p className="text-sm text-charcoal/50">调整风格或房间筛选后再查看。</p>
              </div>
            )}

            {hasFilteredHistory && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {filteredHistory.map((record, index) => (
                  <div
                    key={record.id}
                    className="history-card rounded-lg overflow-hidden animate-fade-in"
                    style={{ animationDelay: `${Math.min(index, 8) * 0.05}s` }}
                  >
                    <div className="relative aspect-[4/3] overflow-hidden bg-mist">
                      <img
                        src={record.outputUrl}
                        alt={getCardTitle(record)}
                        className="w-full h-full object-cover"
                      />
                      <div className="absolute top-3 right-3 bg-white/90 backdrop-blur-sm px-2 py-1 rounded text-xs font-medium text-charcoal">
                        {formatDate(record.createdAt)}
                      </div>
                    </div>
                    <div className="p-4">
                      <div className="flex flex-wrap items-center gap-2 mb-2">
                        <span className="text-xs px-2 py-0.5 bg-warm-gold/10 text-warm-gold rounded">
                          {getLabel(STYLE_LABELS, record.style, '未知风格')}
                        </span>
                        <span className="text-xs px-2 py-0.5 bg-mist text-charcoal/70 rounded">
                          {getLabel(ROOM_LABELS, record.roomType, '未知房间')}
                        </span>
                      </div>
                      <h3 className="font-medium text-charcoal mb-1">{getCardTitle(record)}</h3>
                      <p className="text-xs text-charcoal/50 min-h-[32px]">
                        {getPromptPreview(record.prompt)}
                      </p>
                      <p className="text-xs text-charcoal/40 mt-2">
                        {getLabel(SOURCE_LABELS, record.source, '生成记录')}
                      </p>
                      <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-warm-gold/10">
                        <button
                          type="button"
                          onClick={() => window.open(record.outputUrl, '_blank', 'noopener,noreferrer')}
                          className="text-xs text-warm-gold hover:underline flex items-center justify-center gap-1"
                        >
                          <Eye className="w-3 h-3" />
                          查看
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDownload(record)}
                          className="text-xs text-charcoal/60 hover:text-charcoal flex items-center justify-center gap-1"
                        >
                          <Download className="w-3 h-3" />
                          下载
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(record.id)}
                          className="text-xs text-charcoal/50 hover:text-red-500 transition-colors flex items-center justify-center gap-1"
                        >
                          <Trash2 className="w-3 h-3" />
                          删除
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}

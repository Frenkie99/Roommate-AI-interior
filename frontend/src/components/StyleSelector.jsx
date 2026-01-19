/**
 * StyleSelector 组件
 * 用于选择装修风格
 */

import React from 'react';
import { motion } from 'framer-motion';
import clsx from 'clsx';

const STYLES = [
  { id: 'modern_minimalist', name: '现代简约', emoji: '🏢', color: 'from-gray-400 to-gray-600' },
  { id: 'scandinavian', name: '北欧风格', emoji: '🌲', color: 'from-blue-300 to-teal-400' },
  { id: 'chinese_modern', name: '新中式', emoji: '🏮', color: 'from-red-400 to-amber-500' },
  { id: 'light_luxury', name: '轻奢风格', emoji: '✨', color: 'from-amber-300 to-yellow-500' },
  { id: 'japanese_wood', name: '日式原木', emoji: '🎋', color: 'from-amber-600 to-orange-400' },
  { id: 'industrial', name: '工业风', emoji: '🔩', color: 'from-slate-500 to-zinc-600' },
  { id: 'american_country', name: '美式田园', emoji: '🌻', color: 'from-green-400 to-emerald-500' },
  { id: 'french_romantic', name: '法式浪漫', emoji: '🌹', color: 'from-pink-400 to-rose-500' },
  { id: 'mediterranean', name: '地中海', emoji: '🌊', color: 'from-cyan-400 to-blue-500' },
];

export default function StyleSelector({ selected, onSelect }) {
  return (
    <div className="grid grid-cols-3 gap-3">
      {STYLES.map((style) => (
        <motion.button
          key={style.id}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => onSelect(style.id)}
          className={clsx(
            'relative p-4 rounded-xl text-center transition-all duration-200',
            selected === style.id
              ? 'bg-gradient-to-br ' + style.color + ' text-white shadow-lg'
              : 'bg-neutral-800/50 hover:bg-neutral-800 text-neutral-300'
          )}
        >
          <div className="text-2xl mb-1">{style.emoji}</div>
          <div className="text-xs font-medium">{style.name}</div>
          {selected === style.id && (
            <motion.div
              layoutId="styleIndicator"
              className="absolute inset-0 rounded-xl border-2 border-white/30"
              transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }}
            />
          )}
        </motion.button>
      ))}
    </div>
  );
}

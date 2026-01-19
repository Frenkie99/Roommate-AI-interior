/**
 * ProgressBar 组件
 * 用于显示图片生成进度
 */

import React from 'react';

const ProgressBar = ({ progress = 0 }) => {
  // TODO: 实现进度条逻辑
  return (
    <div className="progress-bar">
      <div className="progress" style={{ width: `${progress}%` }}></div>
    </div>
  );
};

export default ProgressBar;

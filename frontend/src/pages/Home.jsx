/**
 * Home 页面
 * 主页面，包含图片上传、风格选择和结果展示
 */

import React from 'react';
import ImageUploader from '../components/ImageUploader';
import StyleSelector from '../components/StyleSelector';
import ResultDisplay from '../components/ResultDisplay';

const Home = () => {
  return (
    <div className="home-page">
      <h1>AI 毛坯房精装修效果图生成器</h1>
      <ImageUploader />
      <StyleSelector />
      <ResultDisplay />
    </div>
  );
};

export default Home;

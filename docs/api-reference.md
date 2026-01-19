# API 接口文档

> AI 毛坯房精装修效果图生成器 - API Reference

## 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **Content-Type**: `multipart/form-data` (上传) / `application/json` (其他)

---

## 外部API: Grsai Nano Banana

本项目使用 **Grsai Nano Banana API** 进行图片生成。

| 配置项 | 值 |
|-------|---|
| API地址(海外) | https://grsaiapi.com |
| API地址(国内) | https://grsai.dakka.com.cn |
| 绘画接口 | POST /v1/draw/nano-banana |
| 结果查询 | POST /v1/draw/result |

### 支持的模型

| 模型ID | 说明 |
|-------|------|
| nano-banana-fast | 快速生成 |
| nano-banana | 标准模型（默认） |
| nano-banana-pro | 专业版，支持1K/2K/4K |
| nano-banana-pro-vt | 专业增强版 |
| nano-banana-pro-cl | 色彩增强版 |
| nano-banana-pro-vip | VIP版，支持1K/2K |
| nano-banana-pro-4k-vip | 4K专享版 |

---

## 接口列表

### 1. 生成装修效果图（同步）

```
POST /api/v1/generate
```

**请求参数 (multipart/form-data):**

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| image | File | 是 | 毛坯房图片(PNG/JPG) |
| style | String | 是 | 装修风格ID |
| room_type | String | 否 | 房间类型 |
| custom_prompt | String | 否 | 自定义提示词 |
| aspect_ratio | String | 否 | 输出比例(默认auto) |
| image_size | String | 否 | 输出大小(1K/2K/4K) |

**响应示例:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "xxx",
    "status": "succeeded",
    "input_image": "20250119_160000_abc12345_input.jpg",
    "output_urls": ["https://..."],
    "style": "modern_minimalist",
    "prompt": "..."
  }
}
```

### 2. 生成装修效果图（异步）

```
POST /api/v1/generate-async
```

立即返回任务ID，需轮询获取结果。参数同上。

### 3. 查询任务状态

```
GET /api/v1/task/{task_id}
```

**响应示例:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "xxx",
    "status": "succeeded",
    "progress": 100,
    "results": [{"url": "https://...", "content": "..."}]
  }
}
```

### 4. 获取装修风格列表

```
GET /api/v1/styles
```

### 5. 获取模型列表

```
GET /api/v1/models
```

---

## 装修风格

| ID | 名称 | 说明 |
|----|-----|------|
| modern_minimalist | 现代简约 | 线条简洁、色彩素雅 |
| scandinavian | 北欧风格 | 清新自然、原木元素 |
| chinese_modern | 新中式 | 传统与现代融合 |
| light_luxury | 轻奢风格 | 精致细节、金属点缀 |
| japanese_wood | 日式原木 | 简约禅意、自然材质 |
| industrial | 工业风 | 裸露砖墙、金属管道 |
| american_country | 美式田园 | 温馨浪漫、柔和色调 |

---

## 输出比例

支持: `auto`, `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `5:4`, `4:5`, `21:9`

# 提示词模块文档 v3.0

本文件夹包含发送给 Nano Banana API 的系统提示词配置。

## v3.0 优化更新

基于专业审核建议，本版本进行了以下核心优化：

| 优化项 | 说明 |
|--------|------|
| **色彩冲突管理** | 用户指定色调时自动剔除预设冲突色彩词 |
| **渲染词优化** | 移除 octane render 等渲染引擎词汇，使用建筑摄影词汇 |
| **结构词精简** | 使用 `preserving spatial architecture` 等专业建筑术语 |
| **材质反射率** | 新增 texture 字段描述表面特性（漫反射/高光等） |
| **动态相机** | 支持 wide/standard/portrait 三种相机预设 |
| **色彩变量插槽** | 支持暖色调/冷色调/中性色调/莫兰迪色等预设 |

---

## 当前提示词结构

提示词采用**6层分层架构**，按权重优先级组合：

### 1. 核心意图层 (Core Intent) - 权重1.3
- 房间类型描述
- 装修风格核心特征

### 2. 结构约束层 (Structure Constraints) - 权重1.5
- `preserving original room structure and wall positions`
- `consistent room geometry`
- `consistent camera viewpoint and perspective`

### 3. 用户色调层 (User Color Tone) - 优先于预设
- 检测用户输入的色调关键词
- 自动插入对应色彩提示词和光照补充

### 4. 风格细节层 (Style Details)
- 材质描述（含反射率特性）
- 色彩方案（自动过滤与用户色调冲突的部分）
- 家具配置
- 光照氛围

### 5. 质量与摄影层 (Quality & Photography)
- 建筑摄影词汇（非渲染引擎）
- 动态相机预设
- 构图要求

### 6. 用户自定义层 (Custom)
- 用户补充说明

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `styles.md` | 装修风格提示词库 |
| `rooms.md` | 房间类型提示词库 |
| `structure.md` | 结构保持提示词 |
| `quality.md` | 质量与渲染提示词 |
| `negative.md` | 负向提示词 |

---

## 权重语法

使用 Stable Diffusion 的权重语法：`(text:weight)`

| 权重等级 | 数值 | 用途 |
|----------|------|------|
| CRITICAL | 1.5 | 关键约束（如结构保持） |
| HIGH | 1.3 | 高优先级（如核心风格） |
| MEDIUM | 1.1 | 中等优先级 |
| NORMAL | 1.0 | 默认权重 |

---

## 示例输出 (v3.0)

**输入**：
- 房间类型：客厅 (living_room)
- 装修风格：现代简约 (modern_minimalist)
- 用户补充：暖色调
- 相机预设：standard

**正向提示词**：
```
(spacious living room:1.3), (modern minimalist interior design:1.3), (preserving original room structure and wall positions:1.5), (consistent room geometry:1.5), (consistent camera viewpoint and perspective:1.5), warm color palette, creamy tones, amber accents, soft warm glow, (high-end materials:1.1), glass, polished concrete, minimal oak wood textures, smooth matte surfaces, diffuse reflection, subtle specular highlights, clean-lined low-profile furniture, modular sofa, geometric coffee table, warm golden sunlight, soft amber lighting, sofa set, coffee table, TV console, armchairs, area rug, window treatments, focal wall, hidden storage, potted plants, minimal sculptural decor, photorealistic architecture photography, ultra-detailed textures, highly realistic, 35mm lens, natural perspective, minimal distortion, professional architectural photography, eye-level view, straight-on shot, natural lighting, cinematic lighting, 8k resolution, 暖色调
```

**负向提示词**：
```
(deforming walls, moving windows, changing room layout, structural alterations, altered ceiling height:1.5), low quality, blurry, grainy, noise, unrealistic lighting, distorted perspective, fish-eye lens, warped walls, bent lines, (cgi, 3d render, cartoon, illustration:1.1), watermark, human, person, pets, floating furniture, merging textures, duplicate objects
```

**v3.0 优化亮点**：
1. ✅ 检测到用户色调"暖色调" → 自动插入 `warm color palette, creamy tones, amber accents`
2. ✅ 自动跳过预设颜色（避免冷暖冲突）
3. ✅ 光照替换为 `warm golden sunlight, soft amber lighting`
4. ✅ 使用建筑摄影词汇，移除 `octane render`
5. ✅ 结构约束使用专业术语 `preserving spatial architecture`

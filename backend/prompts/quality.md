# 质量与摄影提示词 v3.0

## v3.0 优化说明

基于专业建议，本版本进行了以下核心优化：
- **移除渲染引擎词汇**：`octane render` 会带来"渲染感"，不利于照片级真实
- **使用建筑摄影词汇**：更接近真实摄影效果
- **动态相机预设**：根据原图透视情况选择合适的镜头

---

## 基础真实感

使用摄影词汇而非渲染词汇：

```
photorealistic architecture photography, ultra-detailed textures, highly realistic
```

---

## 动态相机预设

根据原图透视情况选择：

| 预设 | 适用场景 | 提示词 |
|------|----------|--------|
| **wide** | 大空间、全景 | `16mm wide angle lens, expansive view` |
| **standard** | 标准房间 | `35mm lens, natural perspective, minimal distortion` |
| **portrait** | 小空间、特写 | `50mm lens, eye-level view, straight-on shot` |

---

## 构图与视角

减少边缘畸变：

```
professional architectural photography, eye-level view, straight-on shot
```

---

## 光照质量

替代渲染引擎词汇：

```
natural lighting, cinematic lighting, 8k resolution
```

---

## 质量级别

| 级别 | 包含内容 |
|------|----------|
| **high** | 真实感 + 动态相机 + 构图 + 光照 |
| **medium** | 真实感 + 构图 |
| **low** | professional interior photo |

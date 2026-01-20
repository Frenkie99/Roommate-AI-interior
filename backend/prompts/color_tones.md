# 色彩变量插槽 v3.0

## 功能说明

当用户在补充说明中输入色调关键词时，系统会：
1. **自动检测**色调关键词
2. **插入**对应的色彩提示词和光照补充
3. **过滤**风格预设中与用户色调冲突的颜色词

---

## 支持的色调预设

### 1. 暖色调

| 属性 | 值 |
|------|-----|
| **关键词** | 暖色、暖调、warm、温暖 |
| **色彩提示** | `warm color palette, creamy tones, amber accents, soft warm glow` |
| **光照补充** | `warm golden sunlight, soft amber lighting` |
| **冲突过滤** | cool, cold, blue tones, gray |

---

### 2. 冷色调

| 属性 | 值 |
|------|-----|
| **关键词** | 冷色、冷调、cool、清冷 |
| **色彩提示** | `cool color palette, icy blue tones, silver accents, crisp cool light` |
| **光照补充** | `cool daylight, blue hour lighting` |
| **冲突过滤** | warm, golden, amber, yellow |

---

### 3. 中性色调

| 属性 | 值 |
|------|-----|
| **关键词** | 中性、neutral、灰调 |
| **色彩提示** | `neutral color palette, balanced tones, understated elegance` |
| **光照补充** | `balanced natural lighting` |
| **冲突过滤** | 无 |

---

### 4. 莫兰迪色

| 属性 | 值 |
|------|-----|
| **关键词** | 莫兰迪、morandi、高级灰 |
| **色彩提示** | `morandi color palette, muted dusty tones, sophisticated gray undertones` |
| **光照补充** | `soft diffused lighting, gentle shadows` |
| **冲突过滤** | vibrant, saturated, bright colors |

---

## 工作原理

```python
# 1. 检测用户输入
user_input = "暖色调，更多收纳空间"
detected_tone = detect_color_tone(user_input)  # 返回 "暖色调"

# 2. 插入色彩提示词
color_prompt = COLOR_TONE_MAPPINGS["暖色调"]["prompt"]
# → "warm color palette, creamy tones, amber accents, soft warm glow"

# 3. 替换风格光照
lighting_addon = COLOR_TONE_MAPPINGS["暖色调"]["lighting_addon"]
# → "warm golden sunlight, soft amber lighting"

# 4. 过滤冲突颜色
style_colors = "white, gray, beige, blue tones"
filtered = filter_conflicting_colors(style_colors, "暖色调")
# → "white, beige" (移除了 gray, blue tones)
```

---

## 扩展建议

如需添加新的色调预设，请在 `prompt_builder.py` 的 `COLOR_TONE_MAPPINGS` 中添加：

```python
"新色调名称": {
    "keywords": ["关键词1", "关键词2"],
    "prompt": "色彩提示词",
    "lighting_addon": "光照补充词",
    "conflicts": ["冲突词1", "冲突词2"]
}
```

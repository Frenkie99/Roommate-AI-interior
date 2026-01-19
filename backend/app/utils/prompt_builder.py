"""
Prompt 构建工具 - 提示词工程核心模块 v2.0
负责构建高质量的装修效果图生成提示词

优化原则（基于Prompt Engineering最佳实践）：
1. 权重优先 - 核心意图置于Prompt前部，确保模型优先理解
2. 结构锁定 - 使用权重语法强调空间结构不可变
3. 光影耦合 - 每种风格配备专属光照预设
4. Token高效 - 剔除同义词冗余，每词贡献唯一语义
5. 正负协同 - 正向提示词与负向提示词成对输出
"""

from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass


# ============================================================================
# 权重配置
# 用于强调关键提示词的重要性
# ============================================================================

@dataclass
class PromptWeight:
    """提示词权重配置"""
    CRITICAL = 1.5      # 关键约束（如结构保持）
    HIGH = 1.3          # 高优先级（如核心风格）
    MEDIUM = 1.1        # 中等优先级
    NORMAL = 1.0        # 默认权重


def apply_weight(text: str, weight: float = 1.0) -> str:
    """
    应用权重到提示词
    支持 Stable Diffusion 的 (text:weight) 语法
    """
    if weight == 1.0:
        return text
    return f"({text}:{weight})"


# ============================================================================
# 结构识别与遵循提示词（带权重）
# 确保AI理解并保持原始房间结构 - 这是最关键的约束
# ============================================================================

STRUCTURE_PRESERVATION_PROMPTS = {
    "core": apply_weight("keep exact same room structure", PromptWeight.CRITICAL),
    "walls": apply_weight("maintain original wall positions and angles", PromptWeight.CRITICAL),
    "windows": apply_weight("preserve window locations sizes and shapes", PromptWeight.HIGH),
    "doors": apply_weight("keep door positions unchanged", PromptWeight.HIGH),
    "perspective": apply_weight("same camera angle and viewpoint", PromptWeight.HIGH),
    "proportions": "maintain spatial proportions and ceiling height",
}

# 简化版结构提示（用于Token受限场景）
STRUCTURE_COMPACT = apply_weight(
    "keep exact room layout, same walls windows doors perspective", 
    PromptWeight.CRITICAL
)


# ============================================================================
# 装修风格提示词库
# 每个风格包含：核心特征、材质、色彩、家具、氛围
# ============================================================================

STYLE_PROMPTS: Dict[str, Dict] = {
    "modern_minimalist": {
        "name": "现代简约",
        "core": apply_weight("modern minimalist interior", PromptWeight.HIGH),
        "materials": "glass, polished concrete, smooth surfaces",
        "colors": "white, gray, beige, black accents",
        "furniture": "clean-lined furniture, low-profile sofa, geometric shapes",
        "lighting": "recessed LED lighting, natural daylight, soft ambient glow",
        "details": "hidden storage, potted plants, minimal decor"
    },
    "scandinavian": {
        "name": "北欧风格",
        "core": apply_weight("scandinavian nordic interior", PromptWeight.HIGH),
        "materials": "light oak wood, wool textiles, linen, rattan",
        "colors": "white walls, light wood, soft pastels, muted blue",
        "furniture": "danish modern furniture, organic curves, functional design",
        "lighting": "large windows, bright diffused daylight, warm pendant lights",
        "details": "sheepskin throws, candles, indoor plants, woven baskets"
    },
    "chinese_modern": {
        "name": "新中式",
        "core": apply_weight("modern chinese oriental interior", PromptWeight.HIGH),
        "materials": "dark walnut, bamboo, silk fabric, lacquered wood",
        "colors": "deep red, black, gold accents, jade green, ivory",
        "furniture": "ming-style chairs, low tea table, screen dividers, symmetrical",
        "lighting": "paper lantern glow, warm ambient light, accent spotlights",
        "details": "calligraphy art, porcelain vases, bonsai, traditional patterns"
    },
    "light_luxury": {
        "name": "轻奢风格",
        "core": apply_weight("light luxury elegant interior", PromptWeight.HIGH),
        "materials": "marble, velvet, brass, leather, crystal",
        "colors": "champagne gold, dusty pink, navy blue, cream white",
        "furniture": "tufted sofa, designer pieces, sculptural furniture",
        "lighting": "crystal chandelier, golden wall sconces, dramatic highlights",
        "details": "metallic accents, art deco elements, fresh flowers"
    },
    "japanese_wood": {
        "name": "日式原木",
        "core": apply_weight("japanese wabi-sabi interior", PromptWeight.HIGH),
        "materials": "hinoki wood, cedar, tatami, shoji paper, stone",
        "colors": "warm wood tones, off-white, beige, earth tones",
        "furniture": "low furniture, floor seating, built-in storage, futon",
        "lighting": "soft diffused natural light, paper lanterns, warm indirect glow",
        "details": "sliding shoji doors, ikebana arrangement, ceramic pottery"
    },
    "industrial": {
        "name": "工业风",
        "core": apply_weight("industrial loft interior", PromptWeight.HIGH),
        "materials": "exposed brick, raw concrete, metal pipes, reclaimed wood",
        "colors": "gray, rust orange, black, dark brown, metallic",
        "furniture": "metal frame furniture, leather sofa, industrial shelving",
        "lighting": "edison bulbs, exposed track lighting, hard directional light",
        "details": "exposed ductwork, vintage signage, large factory windows"
    },
    "american_country": {
        "name": "美式田园",
        "core": apply_weight("american farmhouse country interior", PromptWeight.HIGH),
        "materials": "distressed wood, cotton fabric, painted furniture, ceramic",
        "colors": "warm white, sage green, dusty blue, butter yellow",
        "furniture": "overstuffed sofa, farmhouse table, windsor chairs",
        "lighting": "warm golden sunlight, rustic lanterns, soft lamplight",
        "details": "floral patterns, gingham, mason jars, quilts"
    },
    "french_romantic": {
        "name": "法式浪漫",
        "core": apply_weight("french provincial romantic interior", PromptWeight.HIGH),
        "materials": "ornate moldings, gilded frames, toile fabric, marble",
        "colors": "blush pink, lavender, cream white, powder blue, gold",
        "furniture": "louis xvi chairs, tufted upholstery, antique mirrors",
        "lighting": "crystal chandelier, soft romantic glow, candlelight ambiance",
        "details": "fresh roses, ornate frames, lace curtains"
    },
    "mediterranean": {
        "name": "地中海风格",
        "core": apply_weight("mediterranean coastal interior", PromptWeight.HIGH),
        "materials": "terracotta tiles, wrought iron, stucco walls, ceramic",
        "colors": "ocean blue, turquoise, white, terracotta, olive green",
        "furniture": "rustic wood furniture, arched details, mosaic patterns",
        "lighting": "bright mediterranean sunlight, warm golden hour glow",
        "details": "potted herbs, blue pottery, arched doorways"
    },
}


# ============================================================================
# 房间类型提示词库
# 针对不同功能空间的专业描述
# ============================================================================

ROOM_TYPE_PROMPTS: Dict[str, Dict] = {
    "living_room": {
        "name": "客厅",
        "space": apply_weight("spacious living room", PromptWeight.HIGH),
        "furniture": "sofa set, coffee table, TV console, armchairs",
        "features": "area rug, window treatments, focal wall"
    },
    "bedroom": {
        "name": "卧室",
        "space": apply_weight("cozy bedroom", PromptWeight.HIGH),
        "furniture": "bed with headboard, nightstands, wardrobe",
        "features": "soft bedding, window curtains, accent wall"
    },
    "master_bedroom": {
        "name": "主卧",
        "space": apply_weight("luxurious master bedroom suite", PromptWeight.HIGH),
        "furniture": "king bed, nightstands, seating area, vanity",
        "features": "walk-in closet, chandelier, large windows"
    },
    "kitchen": {
        "name": "厨房",
        "space": apply_weight("modern kitchen", PromptWeight.HIGH),
        "furniture": "cabinetry, kitchen island, bar stools",
        "features": "countertops, backsplash, range hood, pendant lights"
    },
    "dining_room": {
        "name": "餐厅",
        "space": apply_weight("elegant dining room", PromptWeight.HIGH),
        "furniture": "dining table, upholstered chairs, sideboard",
        "features": "chandelier, centerpiece, wall art"
    },
    "bathroom": {
        "name": "卫生间",
        "space": apply_weight("modern spa bathroom", PromptWeight.HIGH),
        "furniture": "vanity cabinet, mirror, storage",
        "features": "rainfall shower, elegant fixtures, tile work"
    },
    "study": {
        "name": "书房",
        "space": apply_weight("home office study room", PromptWeight.HIGH),
        "furniture": "executive desk, ergonomic chair, bookshelves",
        "features": "task lighting, built-in shelving, window view"
    },
    "kids_room": {
        "name": "儿童房",
        "space": apply_weight("playful children bedroom", PromptWeight.HIGH),
        "furniture": "child bed, toy storage, desk area",
        "features": "colorful accents, creative wall art, soft rugs"
    },
    "balcony": {
        "name": "阳台",
        "space": apply_weight("outdoor balcony terrace", PromptWeight.HIGH),
        "furniture": "outdoor seating, planters, small table",
        "features": "potted plants, string lights, outdoor rug"
    },
    "entrance": {
        "name": "玄关",
        "space": apply_weight("welcoming entryway foyer", PromptWeight.HIGH),
        "furniture": "console table, shoe cabinet, coat hooks",
        "features": "mirror, pendant light, decorative accents"
    },
}


# ============================================================================
# 图片质量与渲染提示词（针对2025+模型优化）
# ============================================================================

QUALITY_PROMPTS = {
    # 基础真实感（替代过时的4K/high resolution）
    "realism": "photographic realism, hyper-realistic textures, true-to-life materials",
    # 专业相机参数（更具体的描述）
    "camera": "shot on Canon EOS R5, 16mm wide angle lens, f/8 aperture, ISO 100",
    # 构图与视角
    "composition": "professional architectural photography, perfect composition, eye-level view",
    # 渲染质量
    "render": "octane render, ray traced global illumination, physically based rendering",
}

# ============================================================================
# 负向提示词（增强结构保护）
# ============================================================================

NEGATIVE_PROMPTS = {
    # 结构变形限制（新增！关键改进）
    "structure": apply_weight(
        "changing floor plan, moving windows, altered ceiling height, different room layout, modified wall positions, changed door locations",
        PromptWeight.CRITICAL
    ),
    # 质量问题
    "quality": "low quality, blurry, pixelated, grainy, jpeg artifacts, noise",
    # 透视变形
    "distortion": "distorted perspective, warped walls, bent lines, impossible architecture, fisheye distortion",
    # 风格排除
    "style": "cartoon, anime, illustration, painting, sketch, 3d render, cgi, artificial looking",
    # 内容排除
    "content": "watermark, signature, text, logo, human, person, people, animals, pets",
    # 生成错误
    "errors": "duplicate objects, floating furniture, disconnected elements, merged objects",
}


# ============================================================================
# 提示词构建函数（优化版 v2.0）
# 基于Prompt Engineering最佳实践重构
# ============================================================================

@dataclass
class PromptResult:
    """提示词构建结果，包含正向和负向提示词"""
    positive: str
    negative: str
    
    def to_dict(self) -> Dict[str, str]:
        return {"prompt": self.positive, "negative_prompt": self.negative}


def build_prompt(
    style: str,
    room_type: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    preserve_structure: bool = True,
    quality_level: str = "high",
    compact_mode: bool = False
) -> str:
    """
    构建完整的装修效果图生成提示词（优化版）
    
    优化策略：
    1. 核心意图前置 - 房间类型和风格放在最前，确保模型优先理解
    2. 结构约束紧随 - 紧跟核心意图，确保布局不偏移
    3. 细节填充 - 材质、色彩、家具等细节
    4. 质量收尾 - 渲染和相机参数放在最后
    
    Args:
        style: 装修风格ID
        room_type: 房间类型ID
        custom_prompt: 用户自定义提示词
        preserve_structure: 是否强调保持原始结构
        quality_level: 质量级别 (high/medium/low)
        compact_mode: 紧凑模式，用于Token受限场景
    
    Returns:
        优化后的完整提示词
    """
    
    # ===== 第1层：核心意图 (Core Intent) - 权重最高 =====
    core_parts = []
    
    # 房间类型（如果有）
    if room_type and room_type in ROOM_TYPE_PROMPTS:
        room_info = ROOM_TYPE_PROMPTS[room_type]
        core_parts.append(room_info["space"])
    
    # 装修风格核心
    if style in STYLE_PROMPTS:
        style_info = STYLE_PROMPTS[style]
        core_parts.append(style_info["core"])
    
    # ===== 第2层：结构约束 (Structure Constraints) - 紧随其后 =====
    structure_parts = []
    if preserve_structure:
        if compact_mode:
            structure_parts.append(STRUCTURE_COMPACT)
        else:
            structure_parts.append(STRUCTURE_PRESERVATION_PROMPTS["core"])
            structure_parts.append(STRUCTURE_PRESERVATION_PROMPTS["walls"])
            structure_parts.append(STRUCTURE_PRESERVATION_PROMPTS["perspective"])
    
    # ===== 第3层：风格细节 (Style Details) =====
    detail_parts = []
    if style in STYLE_PROMPTS:
        style_info = STYLE_PROMPTS[style]
        detail_parts.append(style_info["materials"])
        detail_parts.append(style_info["colors"])
        detail_parts.append(style_info["furniture"])
        # 添加风格专属光照
        detail_parts.append(style_info["lighting"])
    
    # 房间家具和特征
    if room_type and room_type in ROOM_TYPE_PROMPTS:
        room_info = ROOM_TYPE_PROMPTS[room_type]
        detail_parts.append(room_info["furniture"])
        detail_parts.append(room_info["features"])
    
    # 风格装饰细节
    if style in STYLE_PROMPTS:
        detail_parts.append(STYLE_PROMPTS[style]["details"])
    
    # ===== 第4层：质量与渲染 (Quality & Rendering) =====
    quality_parts = []
    if quality_level == "high":
        quality_parts.append(QUALITY_PROMPTS["realism"])
        quality_parts.append(QUALITY_PROMPTS["camera"])
        quality_parts.append(QUALITY_PROMPTS["composition"])
        quality_parts.append(QUALITY_PROMPTS["render"])
    elif quality_level == "medium":
        quality_parts.append(QUALITY_PROMPTS["realism"])
        quality_parts.append(QUALITY_PROMPTS["composition"])
    else:
        quality_parts.append("professional interior photo")
    
    # ===== 第5层：用户自定义 (Custom) =====
    custom_parts = []
    if custom_prompt:
        # 清理用户输入，移除可能破坏结构的特殊字符
        cleaned_prompt = custom_prompt.replace("(", "").replace(")", "").replace(":", " ")
        custom_parts.append(cleaned_prompt)
    
    # ===== 按权重顺序组合 =====
    all_parts = core_parts + structure_parts + detail_parts + quality_parts + custom_parts
    
    # 过滤空值并组合
    filtered_parts = [p.strip() for p in all_parts if p and p.strip()]
    full_prompt = ", ".join(filtered_parts)
    
    # 清理多余空格
    full_prompt = " ".join(full_prompt.split())
    
    return full_prompt


def build_prompt_pair(
    style: str,
    room_type: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    preserve_structure: bool = True,
    quality_level: str = "high"
) -> PromptResult:
    """
    构建正向和负向提示词对（推荐使用）
    
    在实际生产环境中，正负提示词必须成对传递给推理API。
    此函数确保两者协同工作。
    
    Args:
        style: 装修风格ID
        room_type: 房间类型ID
        custom_prompt: 用户自定义提示词
        preserve_structure: 是否强调保持原始结构
        quality_level: 质量级别
    
    Returns:
        PromptResult 包含正向和负向提示词
    """
    positive = build_prompt(
        style=style,
        room_type=room_type,
        custom_prompt=custom_prompt,
        preserve_structure=preserve_structure,
        quality_level=quality_level
    )
    
    negative = get_negative_prompt(include_structure=preserve_structure)
    
    return PromptResult(positive=positive, negative=negative)


def get_negative_prompt(include_structure: bool = True) -> str:
    """
    获取负面提示词，避免生成不需要的内容
    
    Args:
        include_structure: 是否包含结构保护的负向提示词
    
    Returns:
        负面提示词字符串
    """
    negative_parts = []
    
    # 结构保护放在最前面（如果需要）
    if include_structure:
        negative_parts.append(NEGATIVE_PROMPTS["structure"])
    
    # 其他负向提示词
    negative_parts.append(NEGATIVE_PROMPTS["quality"])
    negative_parts.append(NEGATIVE_PROMPTS["distortion"])
    negative_parts.append(NEGATIVE_PROMPTS["style"])
    negative_parts.append(NEGATIVE_PROMPTS["content"])
    negative_parts.append(NEGATIVE_PROMPTS["errors"])
    
    return ", ".join(negative_parts)


def get_style_info(style: str) -> Optional[Dict]:
    """
    获取指定风格的详细信息
    
    Args:
        style: 风格ID
    
    Returns:
        风格信息字典，如果不存在则返回None
    """
    return STYLE_PROMPTS.get(style)


def get_room_info(room_type: str) -> Optional[Dict]:
    """
    获取指定房间类型的详细信息
    
    Args:
        room_type: 房间类型ID
    
    Returns:
        房间信息字典，如果不存在则返回None
    """
    return ROOM_TYPE_PROMPTS.get(room_type)


def list_available_styles() -> List[Dict]:
    """
    获取所有可用的装修风格列表
    
    Returns:
        风格列表
    """
    return [
        {"id": style_id, "name": info["name"], "core": info["core"]}
        for style_id, info in STYLE_PROMPTS.items()
    ]


def list_available_room_types() -> List[Dict]:
    """
    获取所有可用的房间类型列表
    
    Returns:
        房间类型列表
    """
    return [
        {"id": room_id, "name": info["name"], "space": info["space"]}
        for room_id, info in ROOM_TYPE_PROMPTS.items()
    ]

"""
Prompt 构建工具 - 提示词工程核心模块 v4.0 (Gemini 3 / Nano Banana 专用)
负责构建高质量的装修效果图生成提示词

设计原则（针对 Gemini 3 多模态模型优化）：
1. 指令优先 (Instruction-Based) - 使用完整句子定义物理约束
2. 否定语义集成 (Integrated Negation) - 在正向指令中包含否定逻辑
3. 物理锚点定义 (Physical Anchoring) - 明确定义不可变量
4. 无需负向提示词 - Gemini 原生不支持 negative prompt
"""

from typing import Optional, Dict, List
from dataclasses import dataclass


# ============================================================================
# 结构约束指令库 v4.0 - 描述性指令模式
# 使用自然语言指令而非标签+权重
# ============================================================================

STRUCTURE_CONSTRAINTS = {
    # A. 建筑骨架层 (Architectural Skeleton)
    "skeleton": "The architectural skeleton and structural layout must remain strictly unchanged.",
    "walls": "Do not add, remove, or shift any load-bearing walls or partitions.",
    "openings": "Maintain the exact coordinates, shapes, and dimensions of all window apertures and door openings.",
    "boundaries": "Ensure the intersection lines between walls, floor, and ceiling are fixed as per the original image.",
    "height": "Preserve the original floor-to-ceiling height without any structural modification.",
    # B. 摄影与透视层 (Perspective & Optics)
    "viewpoint": "Lock the camera at the original eye-level viewpoint and maintain identical vanishing points.",
    "perspective": "Apply strict linear perspective; all vertical and horizontal architectural lines must be perfectly straight.",
}

# 完整结构约束模板（推荐用于复杂毛坯图）
STRUCTURE_TEMPLATE_FULL = """CRITICAL STRUCTURAL CONSTRAINTS (MUST FOLLOW STRICTLY):
1. WINDOWS: The exact size, position, and proportions of ALL windows in the input image MUST be preserved. Do NOT enlarge, shrink, move, or change the shape of any window. The window-to-wall ratio must remain identical.
2. WALLS: The original wall positions, room geometry, and all architectural openings are fixed and must not be altered.
3. FLOOR PLAN: Maintain the exact floor plan, ceiling height, and room dimensions.
4. CAMERA: The camera perspective, focal length, and vanishing points must remain 100% consistent with the input image.
5. FOCUS: Do not perform any structural remodeling. Focus ONLY on surface materials, lighting, furniture, and decoration."""

# 紧凑版结构约束（用于 Token 受限场景）
STRUCTURE_TEMPLATE_COMPACT = "Keep all walls, windows, doors, and ceiling height exactly as shown. Do not add or remove any architectural elements."

# 全局结构约束导出（供 llm_client.py 引用）
GLOBAL_STRUCTURE_CONSTRAINTS = STRUCTURE_TEMPLATE_FULL


# ============================================================================
# 装修风格提示词库 v2.0 (Gemini 3 Optimized)
# 每个风格包含：设计逻辑、核心、材质、色彩、家具、光照、细节
# ============================================================================

STYLE_PROMPTS: Dict[str, Dict] = {
    "modern_luxury": {
        "name": "现代轻奢",
        "logic": "强调材质的对比（哑光 vs 亮光）与精致的金属点缀",
        "vibe": "Sophisticated, refined, and high-end with a sense of understated elegance",
        "core": "sophisticated modern luxury interior",
        "materials": "calacatta marble, brushed brass accents, leather upholstery, glossy finishes, velvet texture",
        "colors": "warm greige, champagne gold, ivory white, deep navy contrast, metallic highlights",
        "furniture": "italian designer furniture, tufted sofa, sleek metal legs, marble coffee table",
        "lighting": "ambient linear LED strips, crystal chandelier, warm accent lighting, layered illumination",
        "details": "art deco elements, gold rimmed decor, geometric carpets, high-end finishing"
    },
    "chinese_modern": {
        "name": "新中式",
        "logic": "去除传统繁复，强调对称性、留白与深色木作的质感",
        "vibe": "Serene, balanced, and culturally rooted with modern simplicity",
        "core": "contemporary chinese zen interior",
        "materials": "dark walnut wood, natural silk, brass details, ink-wash painting textures, stone",
        "colors": "dark wood tones, off-white background, cinnabar red accents, jade green, gold",
        "furniture": "ming-style minimalist chairs, symmetrical layout, round-backed armchairs, solid wood console",
        "lighting": "soft diffused lantern effect, hidden strip lighting, warm atmosphere, focused spotlights on art",
        "details": "bonsai pine, calligraphy art, porcelain vases, circular moon gate motifs, symmetry"
    },
    "american_transitional": {
        "name": "美式风格",
        "logic": "强调线条感（护墙板）和体量感大的舒适家具",
        "vibe": "Warm, inviting, and comfortable with classic American charm",
        "core": "modern american transitional interior",
        "materials": "wainscoting wall panels, dark oak flooring, linen fabric, brass hardware, crown molding",
        "colors": "warm neutral tones, navy blue, sage green, cream white, antique brass",
        "furniture": "large comfortable fabric sofa, leather armchairs, solid wood coffee table, shaker style cabinets",
        "lighting": "warm floor lamps, wall sconces, brass pendant lights, cozy inviting atmosphere",
        "details": "decorative pillows, area rugs, framed artworks, fireplace mantel, books"
    },
    "european_neoclassical": {
        "name": "欧式风格",
        "logic": "侧重于石膏线条、鱼骨拼地板和优雅的比例",
        "vibe": "Elegant, timeless, and romantically European with classical proportions",
        "core": "neoclassical european interior",
        "materials": "intricate wall moldings (boiserie), herringbone wood floor, marble fireplace, plaster relief",
        "colors": "creamy white, beige, pastel tones, gold leaf accents, light grey",
        "furniture": "curved elegant furniture, velvet upholstery, carved wood details, cabriole legs",
        "lighting": "crystal chandelier, natural window light, bright and airy, romantic glow",
        "details": "ornate mirrors, oil paintings, floral arrangements, crown molding details, curtains"
    },
    "industrial_loft": {
        "name": "工业风",
        "logic": "暴露的结构美学，引入微水泥等现代材质，减少脏旧感",
        "vibe": "Raw, edgy, and urban with refined industrial aesthetics",
        "core": "modern industrial loft interior",
        "materials": "exposed concrete walls, micro-cement floor, black steel, red brick, distressed leather",
        "colors": "cement gray, matte black, rust orange, dark wood, metallic silver",
        "furniture": "iron frame furniture, chesterfield leather sofa, raw wood tables, open shelving",
        "lighting": "edison bulbs, track lighting, cold daylight, dramatic shadows, metal pendant lights",
        "details": "exposed ductwork, pipes, vintage factory decor, large metal windows, concrete texture"
    },
    "natural_wood": {
        "name": "原木风",
        "logic": "现代极简与自然的结合，强调大面积浅色木饰面",
        "vibe": "Warm, organic, and naturally calming with Scandinavian influences",
        "core": "warm minimalist natural wood interior",
        "materials": "light ash wood, matte micro-cement, cotton linen, rattan, travertine stone",
        "colors": "warm white, beige, light wood tones, cream, earth tones",
        "furniture": "curved wooden furniture, boucle sofa, low profile designs, organic shapes",
        "lighting": "soft sunlight, warm ambient glow, paper lamps, natural atmosphere",
        "details": "dried flowers, ceramic vases, minimal decor, sheer curtains, wood grain texture"
    },
    "japanese_traditional": {
        "name": "日式",
        "logic": "严格遵循传统日式元素，如榻榻米、障子门，强调低矮重心",
        "vibe": "Zen, tranquil, and authentically Japanese with mindful simplicity",
        "core": "authentic japanese ryokan style interior",
        "materials": "tatami mats, shoji screens (rice paper), cedar wood (sugi), bamboo, clay walls",
        "colors": "natural wood color, straw yellow, matcha green, white, charcoal gray",
        "furniture": "low wooden tables (chabudai), floor cushions (zabuton), futon, built-in storage",
        "lighting": "diffused soft light, andon lamps, natural daylight filtering through paper, zen atmosphere",
        "details": "ikebana flower arrangement, hanging scrolls, sliding doors, tea set, minimalism"
    },
    "bohemian": {
        "name": "波西米亚",
        "logic": "繁复的纹理叠加、植物、编织物和自由奔放的色彩",
        "vibe": "Free-spirited, eclectic, and artistically layered with global influences",
        "core": "eclectic bohemian chic interior",
        "materials": "macrame, rattan, persian rugs, velvet, layered textiles, natural wood",
        "colors": "terracotta, emerald green, mustard yellow, warm earth tones, vibrant patterns",
        "furniture": "peacock chairs, low sofas, poufs, vintage wooden pieces, hanging chairs",
        "lighting": "fairy lights, warm bulb string lights, moroccan lanterns, cozy warm glow",
        "details": "many indoor plants, woven wall hangings, ethnic patterns, cluttercore aesthetic, baskets"
    },
    "bauhaus": {
        "name": "包豪斯",
        "logic": "形式追随功能，使用钢管家具、三原色点缀和几何抽象感",
        "vibe": "Functional, geometric, and artistically modernist with primary color accents",
        "core": "bauhaus modernist interior",
        "materials": "tubular steel (chrome), glass, plywood, leather, smooth plaster",
        "colors": "white background, black lines, primary colors accents (red, yellow, blue)",
        "furniture": "tubular steel chairs (cantilever), functional modular furniture, geometric forms",
        "lighting": "spherical glass lamps, adjustable metal desk lamps, bright distinct lighting",
        "details": "geometric abstract art, clean lines, lack of ornamentation, industrial precision, grid layout"
    },
    "modern_minimalist": {
        "name": "现代简约",
        "logic": "少即是多，利用留白（Negative Space）和隐藏式设计",
        "vibe": "Clean, airy, and architecturally pure with intentional negative space",
        "core": "ultra-modern minimalist interior",
        "materials": "matte white surfaces, self-leveling cement, glass, anodized aluminum",
        "colors": "monochromatic white, cool gray, black contrasts, neutral palette",
        "furniture": "blocky geometric furniture, hidden handle cabinets, sharp lines, suspended furniture",
        "lighting": "linear recessed lights, hidden light troughs, cool natural light, shadowless illumination",
        "details": "decluttered space, hidden storage, negative space, no visible wires, architectural purity"
    },
}

# ============================================================================
# 房间类型提示词库 v2.0 (Gemini 3 Spatial Edition)
# 每个房间包含：空间逻辑、核心、硬装、家具、软装
# ============================================================================

ROOM_TYPE_PROMPTS: Dict[str, Dict] = {
    "living_room": {
        "name": "客厅",
        "logic": "强调视觉重心（通常是电视墙或景观窗）与围合感的平衡",
        "core": "spacious open-plan living room with balanced layout",
        "hardscape": "Ceiling: suspended gypsum ceiling with hidden cove lighting, modern track lights. Walls: textured feature wall (TV background), neutral painted side walls.",
        "furniture": "Layout: L-shaped modular sofa arrangement, low-profile marble coffee table, single lounge chair. Items: slim media console, side tables.",
        "softscape": "large geometric area rug defining the seating zone, floor-to-ceiling sheer curtains, minimal abstract art, indoor potted tree"
    },
    "bedroom": {
        "name": "卧室",
        "logic": "强调舒适性与私密性，避免视线直冲床头",
        "core": "cozy and serene bedroom sanctuary",
        "hardscape": "Ceiling: flat clean ceiling with soft perimeter lighting. Walls: upholstered or wood-paneled headboard wall, warm neutral wall paint.",
        "furniture": "Layout: double bed centered against the main wall. Items: symmetrical nightstands, floating wall shelves, sliding door wardrobe to save space.",
        "softscape": "layered high-thread-count bedding, blackout curtains, soft bedside pendant lights, plush bedside rug"
    },
    "master_bedroom": {
        "name": "主卧",
        "logic": "强调套房感和功能分区（睡眠区+休闲区/梳妆区）",
        "core": "luxurious master bedroom suite with functional zoning",
        "hardscape": "Ceiling: intricate multi-level ceiling design, central statement chandelier. Walls: decorative molding (wainscoting) or wallpaper, bookmatched stone accents.",
        "furniture": "Layout: King-size bed with bench at foot, separate seating corner with armchairs. Items: vanity dresser, walk-in closet visibility.",
        "softscape": "premium velvet bedding, double-layer drapery, architectural wall sconces, art gallery wall, fresh flowers"
    },
    "kitchen": {
        "name": "厨房",
        "logic": "强调洗-切-炒动线和材质的高级感（反光与哑光的对比）",
        "core": "modern gourmet kitchen with ergonomic workflow",
        "hardscape": "Ceiling: moisture-resistant smooth ceiling, recessed downlights. Walls: marble or ceramic tile backsplash, easy-clean surfaces.",
        "furniture": "Layout: U-shaped or galley layout with central kitchen island (if space permits). Items: sleek handle-less cabinetry, integrated appliances (fridge, oven), bar stools.",
        "softscape": "under-cabinet LED strip lighting, designer faucet, organized countertop accessories, fruit bowl"
    },
    "dining_room": {
        "name": "餐厅",
        "logic": "强调聚餐氛围，灯光必须压低并聚焦于桌面",
        "core": "elegant formal dining room atmosphere",
        "hardscape": "Ceiling: decorative ceiling medallion or defined dining zone ceiling. Walls: textured wallpaper or wood veneer buffet wall.",
        "furniture": "Layout: large dining table centered under light. Items: upholstered dining chairs, sideboard console for storage, wine display cabinet.",
        "softscape": "low-hanging statement pendant light (focus on table), table centerpiece (vase/candles), wall art mirror to expand space"
    },
    "bathroom": {
        "name": "卫生间",
        "logic": "强调干湿分离（Wet/Dry separation）和洁净感",
        "core": "modern spa-like bathroom retreat",
        "hardscape": "Ceiling: waterproof ceiling with ventilation shadow gaps. Walls: floor-to-ceiling large format porcelain tiles, shower niche.",
        "furniture": "Layout: floating vanity unit (wall-mounted). Items: frameless glass shower enclosure, freestanding bathtub (optional), smart toilet.",
        "softscape": "backlit smart mirror, chrome or matte black fixtures, rolled clean towels, ambient waterproof lighting"
    },
    "study": {
        "name": "书房",
        "logic": "强调专注度，收纳系统要像展示柜一样有设计感",
        "core": "productive home office and creative studio",
        "hardscape": "Ceiling: acoustic treatment or simple flat ceiling. Walls: built-in floor-to-ceiling bookshelves, sound-absorbing felt panels.",
        "furniture": "Layout: desk facing the window or room center. Items: large executive desk, ergonomic office chair, reading nook armchair.",
        "softscape": "professional desk lamp, organized books, cable management, blinds for light control"
    },
    "kids_room": {
        "name": "儿童房",
        "logic": "强调安全性、趣味性和可成长性（留出活动空间）",
        "core": "playful and imaginative children's room",
        "hardscape": "Ceiling: creative lighting (cloud/star shape) or colorful paint. Walls: half-wall paint, chalkboard wall or washable wallpaper.",
        "furniture": "Layout: zoned for sleep and play. Items: bunk bed or house-frame bed, low-height storage bins, study desk.",
        "softscape": "soft non-slip play rug, colorful scatter cushions, whimsical wall decals, warm night light"
    },
    "balcony": {
        "name": "阳台",
        "logic": "强调室内空间的延伸，模糊室内外界限",
        "core": "relaxing outdoor balcony garden oasis",
        "hardscape": "Ceiling: wooden slat ceiling or weather-resistant paint. Walls: vertical garden wall or outdoor screen.",
        "furniture": "Layout: corner seating arrangement. Items: weather-resistant rattan chairs, small round coffee table.",
        "softscape": "potted plants varying in height, string lights, outdoor waterproof rug, glass railing visualization"
    },
    "entrance": {
        "name": "玄关",
        "logic": "第一印象，强调收纳的隐蔽性和照明的仪式感",
        "core": "welcoming entryway foyer with smart storage",
        "hardscape": "Ceiling: recessed spotlight focusing on decor. Walls: full-length mirror, decorative wall hooks or paneling.",
        "furniture": "Layout: clear passage width. Items: slim console table, built-in shoe cabinet (floor-to-ceiling).",
        "softscape": "decorative tray for keys, sculptural vase, warm entry light, durable runner rug"
    },
}


# ============================================================================
# 图片质量提示词 v4.0
# 使用建筑摄影词汇实现照片级真实
# ============================================================================

QUALITY_PROMPTS = {
    "realism": "photorealistic architecture photography, ultra-detailed textures, highly realistic",
    "camera": "shot on Canon EOS R5, 16mm f/8, depth of field",
    "composition": "professional architectural photography, eye-level view, straight-on shot",
    "lighting": "natural lighting, cinematic lighting, 8k resolution",
}


# ============================================================================
# 提示词构建函数 v4.0 - Gemini 3 描述性指令模式
# 无需负向提示词，使用自然语言指令
# ============================================================================

@dataclass
class PromptResult:
    """提示词构建结果（v4.0 仅包含 prompt，无 negative_prompt）"""
    prompt: str
    
    def to_dict(self) -> Dict[str, str]:
        return {"prompt": self.prompt}


def build_prompt(
    style: str,
    room_type: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    preserve_structure: bool = True,
    compact_mode: bool = False
) -> str:
    """
    构建完整的装修效果图生成提示词 v4.0 (Gemini 3 优化版)
    
    设计原则：
    1. 角色设定 - 以专业建筑可视化引擎的身份执行
    2. 任务定义 - 明确说明是将毛坯房装修为某种风格
    3. 结构约束 - 使用描述性指令锁定建筑骨架
    4. 风格细节 - 包含材质、色彩、家具、光照、软装
    5. 房间细节 - 包含硬装、家具布局、软装
    
    Args:
        style: 装修风格ID
        room_type: 房间类型ID
        custom_prompt: 用户自定义提示词
        preserve_structure: 是否强调保持原始结构
        compact_mode: 紧凑模式，用于Token受限场景
    
    Returns:
        优化后的完整提示词
    """
    
    prompt_parts = []
    
    # ===== 角色与任务定义 =====
    style_name = STYLE_PROMPTS.get(style, {}).get("name", style)
    room_name = ROOM_TYPE_PROMPTS.get(room_type, {}).get("name", room_type) if room_type else "room"
    
    prompt_parts.append(f"Act as a professional architectural visualization engine.")
    prompt_parts.append(f"Task: Renovate the provided raw {room_name} into a {style_name} interior.")
    
    # ===== 结构约束（最高优先级）=====
    if preserve_structure:
        if compact_mode:
            prompt_parts.append(STRUCTURE_TEMPLATE_COMPACT)
        else:
            prompt_parts.append(STRUCTURE_TEMPLATE_FULL)
    
    # ===== 风格细节 =====
    if style in STYLE_PROMPTS:
        style_info = STYLE_PROMPTS[style]
        prompt_parts.append(f"STYLE SPECIFICATIONS:")
        prompt_parts.append(f"Core aesthetic: {style_info['core']}")
        prompt_parts.append(f"Materials: {style_info['materials']}")
        prompt_parts.append(f"Color palette: {style_info['colors']}")
        prompt_parts.append(f"Furniture: {style_info['furniture']}")
        prompt_parts.append(f"Lighting: {style_info['lighting']}")
        prompt_parts.append(f"Details: {style_info['details']}")
    
    # ===== 房间细节 =====
    if room_type and room_type in ROOM_TYPE_PROMPTS:
        room_info = ROOM_TYPE_PROMPTS[room_type]
        prompt_parts.append(f"ROOM SPECIFICATIONS:")
        prompt_parts.append(f"Space type: {room_info['core']}")
        prompt_parts.append(f"Hardscape: {room_info['hardscape']}")
        prompt_parts.append(f"Furniture layout: {room_info['furniture']}")
        prompt_parts.append(f"Soft furnishings: {room_info['softscape']}")
    
    # ===== 质量要求 =====
    prompt_parts.append(f"QUALITY REQUIREMENTS:")
    prompt_parts.append(f"{QUALITY_PROMPTS['realism']}, {QUALITY_PROMPTS['composition']}, {QUALITY_PROMPTS['lighting']}")
    
    # ===== 用户自定义 =====
    if custom_prompt:
        prompt_parts.append(f"ADDITIONAL REQUIREMENTS: {custom_prompt}")
    
    # 组合为完整提示词
    full_prompt = "\n".join(prompt_parts)
    
    return full_prompt


def build_prompt_simple(
    style: str,
    room_type: Optional[str] = None,
    custom_prompt: Optional[str] = None
) -> str:
    """
    构建简化版提示词（用于 Token 受限场景）
    
    Args:
        style: 装修风格ID
        room_type: 房间类型ID
        custom_prompt: 用户自定义提示词
    
    Returns:
        简化版提示词
    """
    parts = []
    
    # 风格核心
    if style in STYLE_PROMPTS:
        parts.append(STYLE_PROMPTS[style]["core"])
        parts.append(STYLE_PROMPTS[style]["materials"])
        parts.append(STYLE_PROMPTS[style]["furniture"])
    
    # 房间核心
    if room_type and room_type in ROOM_TYPE_PROMPTS:
        parts.append(ROOM_TYPE_PROMPTS[room_type]["core"])
    
    # 结构约束（紧凑版）
    parts.append(STRUCTURE_TEMPLATE_COMPACT)
    
    # 质量
    parts.append(QUALITY_PROMPTS["realism"])
    
    # 用户自定义
    if custom_prompt:
        parts.append(custom_prompt)
    
    return ", ".join(parts)


def build_prompt_v2(
    style: str,
    room_type: Optional[str] = None,
    llm_analysis: Optional[Dict] = None,
    custom_prompt: Optional[str] = None
) -> str:
    """
    构建增强版提示词 v2.0 - 支持接收 LLM 分析结果
    
    混合架构：
    - 结构约束：始终使用静态模板（最高优先级）
    - 风格/材质：使用专业库（确保质量下限）
    - 空间分析：来自 LLM 的动态感知（增强灵活性）
    
    Args:
        style: 装修风格ID
        room_type: 房间类型ID
        llm_analysis: LLM 分析结果字典
        custom_prompt: 用户自定义需求
    
    Returns:
        完整的增强版提示词
    """
    prompt_parts = []
    
    # ===== 1. 角色定义 =====
    prompt_parts.append("## ROLE: Professional Architectural Renderer")
    
    style_info = STYLE_PROMPTS.get(style, {})
    style_name = style_info.get("name", style)
    room_name = ROOM_TYPE_PROMPTS.get(room_type, {}).get("name", room_type) if room_type else "room"
    
    prompt_parts.append(f"Task: Transform this raw {room_name} into a {style_name} interior.")
    
    # ===== 2. 结构约束（最高优先级，不可覆盖）=====
    prompt_parts.append(GLOBAL_STRUCTURE_CONSTRAINTS)
    
    # ===== 3. LLM 空间分析（动态感知）=====
    if llm_analysis:
        room_analysis = llm_analysis.get("room_analysis", {})
        design_rec = llm_analysis.get("design_recommendations", {})
        
        if room_analysis:
            physical_features = room_analysis.get("space_description", "") or room_analysis.get("physical_features", "")
            if physical_features:
                prompt_parts.append(f"## SPACE CONTEXT: {physical_features}")
        
        if design_rec:
            design_intent = []
            if design_rec.get("layout_suggestion"):
                design_intent.append(f"Layout: {design_rec['layout_suggestion']}")
            if design_rec.get("furniture_placement"):
                design_intent.append(f"Furniture: {design_rec['furniture_placement']}")
            if design_rec.get("color_scheme"):
                design_intent.append(f"Colors: {design_rec['color_scheme']}")
            if design_intent:
                prompt_parts.append(f"## DESIGN LOGIC: {'; '.join(design_intent)}")
    
    # ===== 4. 风格材质库（确保质量下限）=====
    if style_info:
        prompt_parts.append(f"## ATMOSPHERE: {style_info.get('vibe', '')}")
        prompt_parts.append(f"## MATERIAL & FINISHES: {style_info.get('materials', '')}")
        prompt_parts.append(f"## LIGHTING SCHEME: {style_info.get('lighting', '')}")
        prompt_parts.append(f"## COLOR PALETTE: {style_info.get('colors', '')}")
        prompt_parts.append(f"## FURNITURE STYLE: {style_info.get('furniture', '')}")
    
    # ===== 5. 房间细节 =====
    if room_type and room_type in ROOM_TYPE_PROMPTS:
        room_info = ROOM_TYPE_PROMPTS[room_type]
        prompt_parts.append(f"## ROOM LAYOUT: {room_info.get('furniture', '')}")
        prompt_parts.append(f"## SOFT FURNISHINGS: {room_info.get('softscape', '')}")
    
    # ===== 6. 用户自定义需求 =====
    if custom_prompt:
        prompt_parts.append(f"## USER REQUIREMENTS: {custom_prompt}")
    
    # ===== 7. 质量要求 =====
    prompt_parts.append(f"## QUALITY: {QUALITY_PROMPTS['realism']}, {QUALITY_PROMPTS['camera']}, {QUALITY_PROMPTS['lighting']}")
    
    return "\n\n".join(prompt_parts)


def build_prompt_result(
    style: str,
    room_type: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    preserve_structure: bool = True,
    compact_mode: bool = False
) -> PromptResult:
    """
    构建提示词结果对象（推荐使用）- v4.0
    
    Args:
        style: 装修风格ID
        room_type: 房间类型ID
        custom_prompt: 用户自定义提示词
        preserve_structure: 是否强调保持原始结构
        compact_mode: 紧凑模式
    
    Returns:
        PromptResult 对象
    """
    prompt = build_prompt(
        style=style,
        room_type=room_type,
        custom_prompt=custom_prompt,
        preserve_structure=preserve_structure,
        compact_mode=compact_mode
    )
    
    return PromptResult(prompt=prompt)


def get_style_info(style: str) -> Optional[Dict]:
    """获取指定风格的详细信息"""
    return STYLE_PROMPTS.get(style)


def get_room_info(room_type: str) -> Optional[Dict]:
    """获取指定房间类型的详细信息"""
    return ROOM_TYPE_PROMPTS.get(room_type)


def list_available_styles() -> List[Dict]:
    """获取所有可用的装修风格列表"""
    return [
        {"id": style_id, "name": info["name"], "core": info["core"], "logic": info.get("logic", "")}
        for style_id, info in STYLE_PROMPTS.items()
    ]


def list_available_room_types() -> List[Dict]:
    """获取所有可用的房间类型列表"""
    return [
        {"id": room_id, "name": info["name"], "core": info["core"], "logic": info.get("logic", "")}
        for room_id, info in ROOM_TYPE_PROMPTS.items()
    ]

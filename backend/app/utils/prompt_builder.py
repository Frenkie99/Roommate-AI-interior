"""
Prompt 构建工具 - 提示词工程核心模块 v4.0 (API易平台 Gemini 专用)
负责构建高质量的装修效果图生成提示词

设计原则（针对 Gemini 3 多模态模型优化）：
1. 指令优先 (Instruction-Based) - 使用完整句子定义物理约束
2. 否定语义集成 (Integrated Negation) - 在正向指令中包含否定逻辑
3. 物理锚点定义 (Physical Anchoring) - 明确定义不可变量
4. 无需负向提示词 - Gemini 原生不支持 negative prompt
"""

from typing import Any, Optional, Dict, List
from dataclasses import dataclass
import json
from pathlib import Path


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
    "aman_style": {
        "name": "安缦风",
        "logic": "度假酒店式的静谧奢华，强调天然材质肌理、低矮体量与留白",
        "vibe": "Serene, resort-like quiet luxury with Japandi restraint and organic warmth",
        "core": "Aman resort-inspired tranquil luxury interior with organic minimalism",
        "materials": "warm micro-cement, textured art paint, wood veneer from light oak to deep walnut, matte neutral stone, handcrafted ceramics",
        "colors": "cream, off-white, warm greige base (60%), natural wood tones (25%), matte black and dark bronze accents (15%)",
        "furniture": "low-profile grounded seating with rounded organic forms, boucle and linen upholstery, solid wood pieces with chunky cylindrical legs",
        "lighting": "architectural concealed lighting at 2700K-3000K, cove strips, shelf lighting, frameless recessed spots, sculptural diffused floor lamps",
        "details": "handcrafted ceramic vessels, linen textiles, negative space as design element, wood grain texture, quiet zen compositions"
    },
    "wabi_sabi": {
        "name": "侘寂风",
        "logic": "接受不完美与无常之美，强调自然材料的原始肌理与时间痕迹",
        "vibe": "Quiet, imperfect, and deeply grounded — beauty in impermanence and weathered authenticity",
        "core": "wabi-sabi interior celebrating natural imperfection and patina",
        "materials": "hand-troweled clay plaster walls, reclaimed solid wood with visible grain and knots, raw stone (river rock and unpolished slate), hand-thrown ceramic, tsuchi-kabe (earth wall), oxidized iron",
        "colors": "warm ash grey, bone white, raw umber, faded indigo, moss green, sun-bleached beige — all muted, no synthetic saturation",
        "furniture": "low-slung solid wood pieces with visible joinery, organic irregular forms, weathered timber benches, hand-built shelving, floor cushions (zabuton), pieces that show maker's marks",
        "lighting": "single-source warm light (2700K max), washi paper lamps casting diffused shadows, candlelight pools, strong light-shadow contrast (komorebi), negative space in darkness",
        "details": "kintsugi-repaired ceramics, dried branches in rough clay vessels, hand-woven hemp textiles, visible wood knots and cracks celebrated, emptiness as a design element, moss and stone compositions"
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
    "bauhaus_mcm": {
        "name": "包豪斯 / 中古风",
        "logic": "包豪斯的功能主义骨架 + 中古现代主义的有机温暖，几何秩序中嵌入自然材质",
        "vibe": "Intellectual warmth — rigorous geometry softened by aged wood, patinated leather, and lived-in comfort",
        "core": "bauhaus principles fused with mid-century modern organic warmth",
        "materials": "teak and walnut (oil-finished, not lacquered), tubular chrome steel, molded bent plywood (Eames-era shells), saddle leather, spun fiberglass, nubby wool textiles, smooth matte plaster walls",
        "colors": "warm walnut brown base (60%), parchment white (25%), burnt orange / mustard yellow / avocado green as controlled accents (15% total), matte black for structural lines only",
        "furniture": "iconic mid-century silhouettes — low-profile teak credenzas with tapered legs, cantilevered chrome chairs, molded plywood lounge shells, kidney-shaped coffee tables, floating storage units, furniture raised on slender legs for visual lightness",
        "lighting": "arc floor lamps with brass domes, spherical rice-paper pendants (Noguchi-style), adjustable-angle task lighting, warm 2700K throughout, distinct light pools defining functional zones",
        "details": "abstract expressionist prints in simple frames, sunburst wall clocks, ceramic vessels with matte glazes, vintage glassware, negative space between furniture groupings, every object has a function"
    },
}

# ============================================================================
# 旧风格 ID 迁移映射（风格精简/改名后，兼容老用户缓存与历史记录里的旧值）
# 改名类映射到继任风格；彻底删除类映射到当前默认风格 aman_style
# ============================================================================

LEGACY_STYLE_ID_MAP: Dict[str, str] = {
    "natural_wood": "aman_style",            # 2026-07-31 原木风更名为安缦风
    "japanese_traditional": "wabi_sabi",     # v3.0 日式更名为侘寂风
    "bauhaus": "bauhaus_mcm",                # v3.0 包豪斯并入包豪斯/中古风
    "modern_minimalist": "aman_style",       # v3.0 已删除 → 默认风格
    "european_neoclassical": "aman_style",   # v3.0 已删除 → 默认风格
    "industrial_loft": "aman_style",         # v3.0 已删除 → 默认风格
    "american_transitional": "aman_style",   # v3.0 已删除 → 默认风格
}

DEFAULT_STYLE = "aman_style"


def resolve_style_id(style: Optional[str]) -> str:
    """把旧风格 ID 重映射到现行 ID；未知值原样返回（由调用方校验）"""
    if not style:
        return DEFAULT_STYLE
    return LEGACY_STYLE_ID_MAP.get(style, style)


# ============================================================================
# 提取产物接入（scripts/extract_style_prompts.py 的多图交集运算结果）
# 四段式提取结果覆盖手写版的 materials/colors/lighting/furniture 四个字段，
# 其余字段（name/logic/vibe/core/details）保持手写。JSON 缺失时静默使用手写版。
# ============================================================================

_EXTRACTED_STYLE_JSON = (
    Path(__file__).resolve().parents[2]
    / "prompts" / "prompt_data_preparation" / "style_prompts.json"
)

_FOUR_PART_TO_STYLE_FIELD = {
    "MATERIAL_AND_FINISHES": "materials",
    "COLOR_PALETTE": "colors",
    "LIGHTING_SCHEME": "lighting",
    "FURNITURE_STYLE": "furniture",
}


def _apply_extracted_style_prompts() -> None:
    """用提取的四段式风格描述覆盖 STYLE_PROMPTS 对应字段"""
    if not _EXTRACTED_STYLE_JSON.exists():
        return
    try:
        data = json.loads(_EXTRACTED_STYLE_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    for style_id, extracted in data.items():
        if style_id not in STYLE_PROMPTS or not isinstance(extracted, dict):
            continue
        for src_field, dst_field in _FOUR_PART_TO_STYLE_FIELD.items():
            value = extracted.get(src_field)
            if value:
                STYLE_PROMPTS[style_id][dst_field] = value


_apply_extracted_style_prompts()

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
    [已废弃] 请使用 build_prompt_v2
    保留此函数仅为了兼容旧测试用例和备用回退
    
    原始功能：构建完整的装修效果图生成提示词 v4.0 (Gemini 3 优化版)
    
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
    custom_prompt: Optional[str] = None,
    preserve_structure: bool = True,
    compact_mode: bool = False
) -> str:
    """
    构建增强版提示词 v2.0 - 支持接收 LLM 分析结果
    
    混合架构：
    - 结构约束：可选开关（默认开启，最高优先级）
    - 风格/材质：使用专业库（确保质量下限）
    - 空间分析：来自 LLM 的动态感知（增强灵活性）
    - 排他性逻辑：LLM 建议优先于静态模板
    
    Args:
        style: 装修风格ID
        room_type: 房间类型ID
        llm_analysis: LLM 分析结果字典
        custom_prompt: 用户自定义需求
        preserve_structure: 是否保持原始结构（默认True）
        compact_mode: 紧凑模式（Token受限场景）
    
    Returns:
        完整的增强版提示词
    """
    # 处理默认值，避免后续大量 if 嵌套
    if llm_analysis is None:
        llm_analysis = {}
    
    prompt_parts = []
    
    # ===== 1. 角色定义 =====
    style_info = STYLE_PROMPTS.get(style, {})
    style_name = style_info.get("name", style)
    room_name = ROOM_TYPE_PROMPTS.get(room_type, {}).get("name", room_type) if room_type else "room"
    
    prompt_parts.append("## ROLE: Professional Architectural Renderer")
    prompt_parts.append(f"Task: Transform this raw {room_name} into a {style_name} interior.")
    
    # ===== 2. 氛围定调（优先级最高，让模型先理解“感觉”）=====
    if style_info and style_info.get('vibe'):
        prompt_parts.append(f"## ATMOSPHERE & VIBE: {style_info.get('vibe')}")
    
    # ===== 3. 结构约束（可选开关）=====
    if preserve_structure:
        if compact_mode:
            prompt_parts.append(STRUCTURE_TEMPLATE_COMPACT)
        else:
            prompt_parts.append(GLOBAL_STRUCTURE_CONSTRAINTS)
    
    # ===== 4. LLM 空间分析（动态感知）=====
    room_analysis = llm_analysis.get("room_analysis", {})
    design_rec = llm_analysis.get("design_recommendations", {})
    
    # 标记是否有 LLM 提供的布局建议（用于排他性逻辑）
    has_dynamic_layout = bool(design_rec.get("layout_suggestion") or design_rec.get("furniture_placement"))
    has_dynamic_colors = bool(design_rec.get("color_scheme"))
    
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
        if design_rec.get("lighting_design"):
            design_intent.append(f"Lighting: {design_rec['lighting_design']}")
        if design_intent:
            prompt_parts.append(f"## DESIGN LOGIC (AI Analysis): {'; '.join(design_intent)}")
    
    # ===== 5. 风格材质库（确保质量下限）=====
    if style_info:
        # ATMOSPHERE 已在前面定调，这里不再重复
        prompt_parts.append(f"## MATERIAL & FINISHES: {style_info.get('materials', '')}")
        prompt_parts.append(f"## LIGHTING SCHEME: {style_info.get('lighting', '')}")
        # 颜色：如果 LLM 提供了配色建议，降级静态库
        if not has_dynamic_colors:
            prompt_parts.append(f"## COLOR PALETTE: {style_info.get('colors', '')}")
        prompt_parts.append(f"## FURNITURE STYLE: {style_info.get('furniture', '')}")
    
    # ===== 6. 房间细节（排他性逻辑）=====
    if room_type and room_type in ROOM_TYPE_PROMPTS:
        room_info = ROOM_TYPE_PROMPTS[room_type]
        # 布局：只有当 LLM 没有提供布局建议时，才使用静态模板兜底
        if not has_dynamic_layout:
            prompt_parts.append(f"## ROOM LAYOUT (Standard): {room_info.get('furniture', '')}")
        # 软装通常可以叠加
        prompt_parts.append(f"## SOFT FURNISHINGS: {room_info.get('softscape', '')}")
    
    # ===== 7. 用户自定义需求 =====
    if custom_prompt:
        prompt_parts.append(f"## USER REQUIREMENTS: {custom_prompt}")
    
    # ===== 8. 质量要求 =====
    if compact_mode:
        prompt_parts.append(f"## QUALITY: {QUALITY_PROMPTS['realism']}")
    else:
        prompt_parts.append(f"## QUALITY: {QUALITY_PROMPTS['realism']}, {QUALITY_PROMPTS['camera']}, {QUALITY_PROMPTS['lighting']}")
    
    return "\n\n".join(prompt_parts)


def normalize_llm_analysis(llm_analysis: Any) -> tuple[Dict, bool]:
    """规范化 LLM 空间分析，避免异常类型进入提示词构建器。

    返回 ``(normalized, is_valid)``。允许 room_analysis 或
    design_recommendations 只返回其中一部分，但至少需要一个非空字典。
    未识别的顶层字段会保留，便于兼容后续扩展。
    """
    if not isinstance(llm_analysis, dict):
        return {}, False

    normalized = dict(llm_analysis)
    has_valid_section = False
    for key in ("room_analysis", "design_recommendations"):
        section = llm_analysis.get(key)
        if isinstance(section, dict):
            normalized[key] = section
            has_valid_section = has_valid_section or bool(section)
        else:
            normalized[key] = {}

    return normalized, has_valid_section


def llm_analysis_has_prompt_context(llm_analysis: Dict) -> bool:
    """判断 v2 是否会把分析内容真正写入最终提示词。"""
    room_analysis = llm_analysis.get("room_analysis", {})
    design_rec = llm_analysis.get("design_recommendations", {})

    room_context = (
        room_analysis.get("space_description")
        or room_analysis.get("physical_features")
    )
    design_context = any(
        design_rec.get(key)
        for key in (
            "layout_suggestion",
            "furniture_placement",
            "color_scheme",
            "lighting_design",
        )
    )
    return bool(room_context or design_context)


def build_prompt_result(
    style: str,
    room_type: Optional[str] = None,
    llm_analysis: Optional[Dict] = None,
    custom_prompt: Optional[str] = None,
    preserve_structure: bool = True,
    compact_mode: bool = False
) -> PromptResult:
    """
    构建提示词结果对象（v4.0 混合架构版）
    
    优先使用 build_prompt_v2 逻辑，支持 LLM 分析结果注入
    
    Args:
        style: 装修风格ID
        room_type: 房间类型ID
        llm_analysis: LLM 分析结果字典（可选）
        custom_prompt: 用户自定义提示词
        preserve_structure: 是否强调保持原始结构
        compact_mode: 紧凑模式
    
    Returns:
        PromptResult 对象
    """
    prompt = build_prompt_v2(
        style=style,
        room_type=room_type,
        llm_analysis=llm_analysis,
        custom_prompt=custom_prompt,
        preserve_structure=preserve_structure,
        compact_mode=compact_mode
    )
    
    return PromptResult(prompt=prompt)


# ============================================================================
# v3.0 提示词引擎 — 指令优先 + 压缩关键词 + LLM 分析主导
# 核心思路: "告诉模型做什么"而非"描述风格长什么样"
# ============================================================================

# 从长段落提取关键词的填充词黑名单
_COMPRESSION_FILLER = [
    "A rich interplay of", "The design language emphasizes", "A layered",
    "philosophy focusing on", "Extensive use of", "The defining characteristic is",
    "Primary architectural surfaces", "Primary surfaces feature", "Dominant surfaces feature",
    "Secondary applications involve", "Accent elements consist of",
    "A warm, calming neutral palette", "A highly organic and neutral scheme",
    "Base foundation of", "Dominant use of", "Design language emphasizes",
    "The design language features", "Characterized by", "focusing on", "applied to",
    "are extensively used for", "cover general wall areas", "features highly textured",
    "is supplemented by", "utilizing", "employing", "constituting",
    "making up about", "accounting for the remaining",
    "It features", "The overall aesthetic is",
    "Primary seating volumes are", "Supporting surfaces frequently utilize",
    "Standalone accent pieces often exhibit",
    "Hard surface pieces and storage units are constructed from",
    "Seating and sleeping surfaces are typically",
    "Seating categories are generous and",
    "Surface elements (tables, consoles, plinths) are typically",
    "Large upholstered pieces are",
    "Freestanding wooden or stone elements feature",
    "Seating elements frequently utilize",
    "Storage and surface units are typically",
    "Profiles are generally",
    "The design language emphasizes",
    "frequently accented by", "often layered with", "often incorporating",
    "often resting on", "with visible", "alongside", "alongside dramatic",
    "introduced through", "providing linear definition",
]

def _compress_text(text: str) -> str:
    """Compress verbose architectural description into keyword-dense instruction."""
    import re
    result = text

    # 1. Remove filler phrases
    for filler in _COMPRESSION_FILLER:
        result = result.replace(filler, "")

    # 2. Remove percentage notations (the model doesn't need them)
    result = re.sub(r'Dominant\s*\(\d+%\):\s*', '', result)
    result = re.sub(r'Secondary\s*\(\d+%\):\s*', '', result)
    result = re.sub(r'Accent\s*\(\d+%\):\s*', '', result)
    result = re.sub(r'Base foundation of\s*', '', result)

    # 3. Remove orphaned adjectives and fix grammar
    result = re.sub(r'\bdominates\b', '', result)
    result = re.sub(r'\bis\s+extensively\s+used\b', '', result)
    result = re.sub(r'\bare\s+extensively\s+used\b', '', result)

    # 4. Clean up whitespace and punctuation
    result = re.sub(r'\s{2,}', ' ', result)
    result = re.sub(r',\s*,', ',', result)
    result = re.sub(r'^\s*[.,;:]\s*', '', result)  # leading punctuation
    result = re.sub(r'\s+[.,;:]', '.', result)      # space before punctuation
    result = re.sub(r'\.{2,}', '.', result)          # multiple periods
    result = re.sub(r'^\s*,?\s*', '', result)
    result = re.sub(r'\s*,?\s*$', '', result)

    # 5. If still too long, take first 2-3 sentences
    sentences = [s.strip() for s in result.split('.') if s.strip() and len(s.strip()) > 5]
    if len(sentences) > 3:
        result = '. '.join(sentences[:3]) + '.'
    else:
        result = '. '.join(sentences) + '.'

    return result.strip(' .')


def build_prompt_v3(
    style: str,
    room_type: Optional[str] = None,
    llm_analysis: Optional[Dict] = None,
    custom_prompt: Optional[str] = None,
    preserve_structure: bool = True,
) -> str:
    """
    v3.0 指令优先提示词引擎

    与 v2 的核心区别：
    1. LLM 空间分析放在最前面（让模型先理解"这个房间长什么样"）
    2. 风格关键词经过压缩（去论文腔，变指令式）
    3. 房间布局和家具位置精确描述
    4. 总长度控制在 ~200 词以内
    """
    if llm_analysis is None:
        llm_analysis = {}

    style_info = STYLE_PROMPTS.get(style, {})
    style_name = style_info.get("name", style)
    room_info = ROOM_TYPE_PROMPTS.get(room_type, {})
    room_name = room_info.get("name", room_type) if room_type else "room"

    room_analysis = llm_analysis.get("room_analysis", {})
    design_rec = llm_analysis.get("design_recommendations", {})

    parts = []

    # ===== 1. 任务指令（一句） =====
    vibe = style_info.get('vibe', '')
    parts.append(f"Transform this {room_name} into a {style_name} interior. {vibe}")

    # ===== 2. LLM 空间感知（优先）=====
    if room_analysis:
        spatial = room_analysis.get("space_description", "") or room_analysis.get("physical_features", "")
        if spatial:
            parts.append(f"ROOM CONTEXT: {spatial}")

    if design_rec:
        rec_parts = []
        if design_rec.get("layout_suggestion"):
            rec_parts.append(f"Layout: {design_rec['layout_suggestion']}")
        if design_rec.get("furniture_placement"):
            rec_parts.append(f"Furniture: {design_rec['furniture_placement']}")
        if design_rec.get("lighting_design"):
            rec_parts.append(f"Lighting: {design_rec['lighting_design']}")
        if design_rec.get("color_scheme"):
            rec_parts.append(f"Colors: {design_rec['color_scheme']}")
        if rec_parts:
            parts.append("DESIGN PLAN: " + "; ".join(rec_parts))

    # ===== 3. 压缩风格关键词 =====
    if style_info:
        materials = _compress_text(style_info.get('materials', ''))
        colors = _compress_text(style_info.get('colors', ''))
        lighting = _compress_text(style_info.get('lighting', ''))
        furniture = _compress_text(style_info.get('furniture', ''))

        if materials:
            parts.append(f"MATERIALS: {materials}")
        if colors:
            parts.append(f"COLORS: {colors}")
        if lighting:
            parts.append(f"LIGHTING: {lighting}")
        if furniture:
            parts.append(f"FURNITURE: {furniture}")

    # ===== 4. 房间特定布局（仅当 LLM 未提供时使用）=====
    has_dynamic_layout = bool(design_rec.get("layout_suggestion") or design_rec.get("furniture_placement"))
    if room_info and not has_dynamic_layout:
        parts.append(f"LAYOUT: {room_info.get('furniture', '')}")
        parts.append(f"SOFT FURNISHINGS: {room_info.get('softscape', '')}")

    # ===== 5. 结构约束 =====
    if preserve_structure:
        parts.append("CONSTRAINTS: Keep all walls, windows, doors, and ceiling height exactly as shown. Do not remodel.")

    # ===== 6. 用户需求 =====
    if custom_prompt:
        parts.append(f"REQUIREMENTS: {custom_prompt}")

    # ===== 7. 质量 =====
    parts.append("QUALITY: photorealistic architectural photography, 8k resolution, natural lighting, ultra-detailed textures")

    return "\n\n".join(parts)


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

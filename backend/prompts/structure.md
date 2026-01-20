# 结构保持提示词规范 v4.0 (Gemini 3 / Nano Banana 专用)

本模块专为 **Roommate** AI 装修产品设计，鉴于 Nano Banana (Gemini 3) 模型具备极强的多模态推理能力，本规范弃用传统的"标签+权重"模式，转而采用**描述性指令（Descriptive Instructions）**与**逻辑约束**模式。

## 1. 核心设计原则

* **指令优先 (Instruction-Based)**：利用 Gemini 3 的自然语言理解能力，通过完整句子定义物理约束，而非离散的单词。
* **否定语义集成 (Integrated Negation)**：直接在正向指令中包含否定逻辑（如 "do not move"），无需依赖独立的 Negative Prompt 字段。
* **物理锚点定义 (Physical Anchoring)**：明确定义"不可变量（Immutables）"，引导模型在推理阶段锁定建筑骨架。

---

## 2. 结构约束指令库

### A. 建筑骨架层 (Architectural Skeleton)
**目的**：锁定房间物理边界，防止空间重组。

| 模块 | 核心指令 (Core Instructions) | 逻辑说明 |
| :--- | :--- | :--- |
| **整体结构** | `The architectural skeleton and structural layout must remain strictly unchanged.` | 定义全屋轮廓为刚性框架。 |
| **墙体约束** | `Do not add, remove, or shift any load-bearing walls or partitions.` | 明确禁止对墙体进行增删改。 |
| **开口对齐** | `Maintain the exact coordinates, shapes, and dimensions of all window apertures and door openings.` | **关键**：防止门窗位移或变形。 |
| **边界锁定** | `Ensure the intersection lines between walls, floor, and ceiling are fixed as per the original image.` | 锁定三维空间交界线，维持空间进深。 |
| **层高保持** | `Preserve the original floor-to-ceiling height without any structural modification.` | 防止虚构吊顶改变原有空间感。 |

### B. 摄影与透视层 (Perspective & Optics)
**目的**：确保渲染图与原图观察点重合，消除视觉偏差。

| 模块 | 核心指令 (Core Instructions) | 逻辑说明 |
| :--- | :--- | :--- |
| **视点固定** | `Lock the camera at the original eye-level viewpoint and maintain identical vanishing points.` | 确保透视关系与原图完全一致。 |
| **线性一致** | `Apply strict linear perspective; all vertical and horizontal architectural lines must be perfectly straight.` | 纠正广角畸变，确保线条横平竖直。 |

---

## 3. 集成提示词模板 (Prompt Templates)

建议将以下文本置于 System Prompt 或 User Prompt 的前段作为最高优先级指令。

### 方案一：完整推理版 (推荐用于复杂毛坯图)
适用于 Nano Banana Pro，利用其长文本推理能力。

```text
Act as a professional architectural visualization engine. 
Task: Renovate the provided raw room into a [Style] interior.
CRITICAL STRUCTURAL CONSTRAINTS:
1. The original wall positions, room geometry, and window apertures are fixed and must not be altered.
2. Maintain the exact floor plan and ceiling height.
3. The camera perspective, focal length, and vanishing points must remain 100% consistent with the input image.
4. Do not perform any structural remodeling; focus solely on surface materials, lighting, and furniture.
```

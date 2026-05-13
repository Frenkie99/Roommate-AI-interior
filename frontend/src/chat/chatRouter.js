/**
 * 聊天消息路由器 — 基于上下文状态的确定性路由
 *
 * 路由优先级：
 * 1. 精修模式 + mask → inpaint
 * 2. 无图片 → knowledge（无条件）
 * 3. 有图片 + 问句 → knowledge
 * 4. 有图片 + 设计动词 → generate
 * 5. 兜底 → knowledge（安全默认）
 */

// 设计指令动词 —— 表示"修改/生成这张图"
const DESIGN_ACTION_VERBS = [
  '换', '调整', '变成', '改成', '改为', '增加', '减少', '去掉',
  '生成', '设计', '加点', '加些', '移除', '删除', '更', '弄',
  '做', '来一', '配', '放', '摆', '放些',
];

// 问句模式 —— 即使有图片也应走问答
const QUESTION_PATTERNS = [
  '什么', '如何', '怎么', '为什么', '建议', '推荐',
  '哪些', '区别', '优缺点', '怎么样', '好不好',
  '注意', '预算', '适合', '选择', '吗', '呢',
];

/**
 * 根据消息内容和上下文决定路由目标
 * @param {string} message - 用户输入的消息
 * @param {{ hasImage: boolean, hasMask: boolean, viewMode: string }} context
 * @returns {'inpaint' | 'generate' | 'knowledge'}
 */
export function routeChatMessage(message, { hasImage, hasMask, viewMode }) {
  // 优先级1：精修模式 + 选中 mask → 局部修改
  if (hasMask && viewMode === 'refine') return 'inpaint';

  // 优先级2：无图片 → 无条件走知识问答
  if (!hasImage) return 'knowledge';

  // 优先级3：有图片 + 是问句 → 知识问答
  if (QUESTION_PATTERNS.some(p => message.includes(p))) return 'knowledge';

  // 优先级4：有图片 + 含设计动词 → 图片生成
  if (DESIGN_ACTION_VERBS.some(v => message.includes(v))) return 'generate';

  // 兜底：安全默认走知识问答
  return 'knowledge';
}

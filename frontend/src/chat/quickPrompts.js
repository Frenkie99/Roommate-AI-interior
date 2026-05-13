/**
 * 聊天快捷按钮数据 — 根据上下文切换
 */

// 有图片时的生成快捷按钮
export const IMAGE_PROMPTS = [
  { label: '再来一张', prompt: '请基于相同的房间结构和视角，生成一个新的设计方案' },
  { label: '换个配色', prompt: '保持当前布局和家具位置，更换不同的配色方案' },
  { label: '换沙发', prompt: '保持房间结构不变，更换不同样式的沙发' },
  { label: '更多绿植', prompt: '保持当前布局，增加更多绿色植物装饰' },
  { label: '暖色调', prompt: '保持当前结构和布局，调整为更温暖的色调' },
  { label: '更简约', prompt: '保持房间结构不变，设计得更加简约现代' },
];

// 无图片时的知识问答快捷按钮
export const KNOWLEDGE_PROMPTS = [
  { label: '客厅怎么布局？', prompt: '客厅怎么布局比较好？' },
  { label: '小户型收纳', prompt: '小户型有什么收纳技巧？' },
  { label: '风格怎么选？', prompt: '什么装修风格适合小空间？' },
  { label: '装修预算', prompt: '装修预算怎么算？' },
  { label: '材料怎么选？', prompt: '装修材料怎么选比较环保？' },
  { label: '配色建议', prompt: '装修配色有什么建议？' },
];

// 精修模式快捷按钮
export const REFINE_PROMPTS = [
  { label: '换沙发', prompt: '换成现代风格的沙发' },
  { label: '换绿植', prompt: '换成绿色植物' },
  { label: '换颜色', prompt: '换成蓝色' },
  { label: '移除', prompt: '移除这个物体' },
];

/**
 * 根据上下文返回合适的欢迎语
 * @param {boolean} hasImage - 是否已上传图片
 * @returns {string}
 */
export function getWelcomeMessage(hasImage) {
  if (hasImage) {
    return '您好！我是您的 AI 设计助手。您可以描述设计需求让我生成新方案，也可以问我任何装修相关的问题。';
  }
  return '您好！我是您的 AI 装修顾问。您可以问我任何装修相关的问题，也可以上传房间照片让我帮您生成设计方案。';
}

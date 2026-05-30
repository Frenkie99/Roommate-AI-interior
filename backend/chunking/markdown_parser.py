"""
Markdown 层级分块器
将装修知识大全按标题层级拆分为语义完整的 chunks
"""

import re
from typing import List, Dict


# 关键词 → topic 标签映射
TOPIC_KEYWORDS = {
    "预算": ["预算", "价格", "费用", "报价", "成本", "省钱", "省钱"],
    "风格": ["风格", "简约", "北欧", "中式", "美式", "轻奢", "工业", "日式", "法式"],
    "水电": ["水电", "水路", "电路", "管线", "防水", "电线", "水管"],
    "瓷砖": ["瓷砖", "铺贴", "空鼓", "美缝", "地砖", "墙砖"],
    "家具": ["家具", "沙发", "床", "衣柜", "餐桌", "橱柜", "茶几"],
    "环保": ["环保", "甲醛", "TVOC", "检测", "E0", "E1", "无醛"],
    "验收": ["验收", "检查", "标准", "合格", "不合格"],
    "合同": ["合同", "报价单", "增项", "闭口", "签约"],
    "施工": ["施工", "工期", "进度", "工人", "项目经理"],
    "软装": ["软装", "窗帘", "灯具", "地毯", "装饰", "挂画", "绿植"],
    "色彩": ["色彩", "配色", "色温", "色调", "颜色"],
    "收纳": ["收纳", "储物", "整理", "柜子", "置物"],
    "设计": ["设计", "设计师", "方案", "图纸", "户型"],
    "装修公司": ["装修公司", "装企", "施工队", "半包", "全包", "清包"],
}


def extract_topics(text: str) -> str:
    """从文本中自动提取 topic 关键词标签"""
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            topics.append(topic)
    return ",".join(topics)


class MarkdownChunker:
    """将 Markdown 文档按标题层级拆分为语义 chunks"""

    def __init__(self, min_chunk_size: int = 200, max_chunk_size: int = 3000):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def parse(self, content: str, source: str = "装修知识大全.md") -> List[Dict]:
        """
        解析 markdown 并返回 chunks 列表

        每个 chunk 包含:
        - id: 层级路径 ID
        - content: 带上下文前缀的文本内容
        - metadata: {part, section, subsection, topic, doc_type, source, char_count}
        """
        lines = content.split("\n")
        sections = self._split_by_headings(lines)
        chunks = []

        for section in sections:
            part = section.get("part", "")
            sec_title = section.get("section", "")
            sub_title = section.get("subsection", "")
            body = section.get("body", "").strip()

            if not body or len(body) < 50:
                continue

            # 生成 chunk ID
            chunk_id = self._make_id(part, sec_title, sub_title)

            # 构建上下文前缀
            prefix = self._make_prefix(part, sec_title, sub_title)
            full_content = f"{prefix}\n\n{body}" if prefix else body

            # 提取 topic
            topic = extract_topics(full_content)

            chunks.append({
                "id": chunk_id,
                "content": full_content,
                "metadata": {
                    "part": part,
                    "section": sec_title,
                    "subsection": sub_title,
                    "topic": topic,
                    "doc_type": "knowledge",
                    "source": source,
                    "char_count": len(full_content),
                },
            })

        # 后处理：合并超短 chunk、拆分超长 chunk
        chunks = self._post_process(chunks)
        return chunks

    def _split_by_headings(self, lines: List[str]) -> List[Dict]:
        """按标题行切分，构建 section 列表"""
        result = []
        current_part = ""
        current_section = ""
        current_subsection = ""
        body_lines = []
        in_references = False

        for line in lines:
            # 跳过参考资料部分
            if "参考资料" in line and line.strip().startswith("**"):
                in_references = True
                continue
            if in_references:
                continue

            # 检测标题层级
            if line.startswith("## ") and not line.startswith("### "):
                # 保存之前的 section
                if body_lines:
                    result.append({
                        "part": current_part,
                        "section": current_section,
                        "subsection": current_subsection,
                        "body": "\n".join(body_lines),
                    })
                    body_lines = []

                title = line[3:].strip()
                # 判断是"第X部分"还是其他二级标题
                if title.startswith("第") and "部分" in title:
                    current_part = title
                    current_section = ""
                    current_subsection = ""
                elif title == "核心摘要与建议":
                    current_part = "核心摘要"
                    current_section = "核心摘要与建议"
                    current_subsection = ""
                else:
                    current_section = title
                    current_subsection = ""

            elif line.startswith("### ") and not line.startswith("#### "):
                # 保存之前的 section
                if body_lines:
                    result.append({
                        "part": current_part,
                        "section": current_section,
                        "subsection": current_subsection,
                        "body": "\n".join(body_lines),
                    })
                    body_lines = []

                current_section = line[4:].strip()
                current_subsection = ""

            elif line.startswith("#### "):
                # 保存之前的 section
                if body_lines:
                    result.append({
                        "part": current_part,
                        "section": current_section,
                        "subsection": current_subsection,
                        "body": "\n".join(body_lines),
                    })
                    body_lines = []

                current_subsection = line[5:].strip()

            else:
                body_lines.append(line)

        # 保存最后一个 section
        if body_lines and not in_references:
            result.append({
                "part": current_part,
                "section": current_section,
                "subsection": current_subsection,
                "body": "\n".join(body_lines),
            })

        return result

    def _post_process(self, chunks: List[Dict]) -> List[Dict]:
        """后处理：合并超短 chunk、拆分超长 chunk"""
        if not chunks:
            return chunks

        result = []
        for chunk in chunks:
            content = chunk["content"]
            char_count = len(content)

            if char_count > self.max_chunk_size:
                # 超长 chunk 按段落拆分
                sub_chunks = self._split_long_chunk(chunk)
                result.extend(sub_chunks)
            elif char_count < self.min_chunk_size and result:
                # 超短 chunk 合并到前一个
                prev = result[-1]
                prev["content"] += "\n\n" + content
                prev["metadata"]["char_count"] = len(prev["content"])
                # 合并 topic
                prev_topics = set(prev["metadata"]["topic"].split(","))
                new_topics = set(chunk["metadata"]["topic"].split(","))
                merged = prev_topics | new_topics
                prev["metadata"]["topic"] = ",".join(t for t in merged if t)
            else:
                result.append(chunk)

        return result

    def _split_long_chunk(self, chunk: Dict) -> List[Dict]:
        """将超长 chunk 按段落拆分为多个子 chunk"""
        content = chunk["content"]
        paragraphs = re.split(r"\n{2,}", content)
        sub_chunks = []
        current_text = ""
        part_idx = 1

        for para in paragraphs:
            if len(current_text) + len(para) > self.max_chunk_size and current_text:
                sub_id = f"{chunk['id']}_p{part_idx}"
                sub_chunks.append({
                    "id": sub_id,
                    "content": current_text.strip(),
                    "metadata": {
                        **chunk["metadata"],
                        "char_count": len(current_text.strip()),
                    },
                })
                part_idx += 1
                current_text = para
            else:
                current_text += "\n\n" + para if current_text else para

        if current_text.strip():
            sub_id = f"{chunk['id']}_p{part_idx}" if part_idx > 1 else chunk["id"]
            sub_chunks.append({
                "id": sub_id,
                "content": current_text.strip(),
                "metadata": {
                    **chunk["metadata"],
                    "char_count": len(current_text.strip()),
                },
            })

        return sub_chunks if sub_chunks else [chunk]

    def _make_id(self, part: str, section: str, subsection: str) -> str:
        """从标题文本生成 chunk ID"""
        # 提取编号如 "1.1", "2.3.1"
        sec_num = ""
        sub_num = ""
        if section:
            m = re.match(r"(\d+(?:\.\d+)*)", section)
            if m:
                sec_num = m.group(1)
        if subsection:
            m = re.match(r"(\d+(?:\.\d+)*)", subsection)
            if m:
                sub_num = m.group(1)

        if sub_num:
            return f"sec_{sub_num.replace('.', '_')}"
        if sec_num:
            return f"sec_{sec_num.replace('.', '_')}"
        # 无编号的用标题哈希
        import hashlib
        key = (part + section + subsection)[:50]
        return f"sec_{hashlib.md5(key.encode()).hexdigest()[:8]}"

    def _make_prefix(self, part: str, section: str, subsection: str) -> str:
        """构建上下文前缀"""
        parts = ["装修知识"]
        if part and part != "核心摘要":
            parts.append(part)
        if section:
            parts.append(section)
        if subsection:
            parts.append(subsection)
        if len(parts) <= 1:
            return ""
        return "[" + " > ".join(parts) + "]"

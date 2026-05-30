"""
初始化知识库 - 将装修知识分块后向量化存入 ChromaDB
运行此脚本将项目中的装修知识导入到Chroma向量数据库
"""

import sys
import os
from pathlib import Path

# Windows控制台编码设置
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.knowledge_service import knowledge_service
from app.utils.prompt_builder import STYLE_PROMPTS, ROOM_TYPE_PROMPTS
from chunking.markdown_parser import MarkdownChunker


def init_from_prompt_builder():
    """将现有的风格和房间描述转换为知识库 chunks"""
    documents = []
    metadatas = []
    ids = []

    # 添加风格知识
    print("📋 正在导入装修风格知识...")
    for style_id, style_info in STYLE_PROMPTS.items():
        doc = f"""[装修知识 > 装修风格 > {style_info['name']}]

# 装修风格：{style_info['name']}

## 设计逻辑
{style_info.get('logic', '暂无说明')}

## 核心描述
{style_info['core']}

## 材质搭配
{style_info['materials']}

## 色彩方案
{style_info['colors']}

## 家具特点
{style_info['furniture']}

## 照明设计
{style_info['lighting']}

## 细节装饰
{style_info['details']}"""

        documents.append(doc)
        metadatas.append({
            "part": "装修风格",
            "section": style_info['name'],
            "subsection": "",
            "topic": f"风格,{style_info['name']}",
            "doc_type": "style",
            "style_id": style_id,
            "source": "prompt_builder.py",
            "char_count": len(doc),
        })
        ids.append(f"style_{style_id}")

    print(f"✅ 已添加 {len(STYLE_PROMPTS)} 个装修风格")

    # 添加房间类型知识
    print("\n📋 正在导入房间类型知识...")
    for room_id, room_info in ROOM_TYPE_PROMPTS.items():
        doc = f"""[装修知识 > 房间类型 > {room_info['name']}]

# 房间类型：{room_info['name']}

## 设计逻辑
{room_info.get('logic', '暂无说明')}

## 空间定义
{room_info['core']}

## 硬装要点
{room_info['hardscape']}

## 家具布局
{room_info['furniture']}

## 软装搭配
{room_info['softscape']}"""

        documents.append(doc)
        metadatas.append({
            "part": "房间类型",
            "section": room_info['name'],
            "subsection": "",
            "topic": f"房间,{room_info['name']}",
            "doc_type": "room_type",
            "room_type": room_id,
            "source": "prompt_builder.py",
            "char_count": len(doc),
        })
        ids.append(f"room_{room_id}")

    print(f"✅ 已添加 {len(ROOM_TYPE_PROMPTS)} 个房间类型")
    return documents, metadatas, ids


def init_from_markdown():
    """从 knowledge_base 目录加载 Markdown 文件并分块"""
    knowledge_base_dir = project_root / "knowledge_base"

    if not knowledge_base_dir.exists():
        print(f"⚠️  知识库目录不存在: {knowledge_base_dir}")
        return [], [], []

    md_files = list(knowledge_base_dir.rglob("*.md"))
    if not md_files:
        print(f"⚠️  在 {knowledge_base_dir} 中未找到 Markdown 文件")
        return [], [], []

    print(f"📚 找到 {len(md_files)} 个 Markdown 文件")

    chunker = MarkdownChunker(min_chunk_size=200, max_chunk_size=3000)
    all_documents = []
    all_metadatas = []
    all_ids = []

    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            chunks = chunker.parse(content, source=md_file.name)
            print(f"✅ {md_file.name}: {len(chunks)} 个 chunks")

            for chunk in chunks:
                all_documents.append(chunk["content"])
                all_metadatas.append(chunk["metadata"])
                all_ids.append(chunk["id"])

        except Exception as e:
            print(f"❌ 加载文件失败 {md_file}: {e}")

    return all_documents, all_metadatas, all_ids


def main():
    """主函数"""
    print("=" * 60)
    print("🏠 AI装修知识库初始化工具 (v2.0)")
    print("=" * 60)

    # 检查知识库状态
    stats = knowledge_service.get_collection_stats()
    print(f"\n📊 当前知识库状态:")
    print(f"   - 文档数: {stats['total_documents']}")
    print(f"   - 状态: {stats['status']}")

    if stats['total_documents'] > 0:
        print("\n⚠️  知识库已有数据")
        choice = input("是否要重置并重新初始化？(yes/no): ").strip().lower()
        if choice not in ['yes', 'y']:
            print("❌ 取消初始化")
            return

        print("🔄 正在重置知识库...")
        knowledge_service.reset_collection()

    print("\n🚀 开始初始化知识库...\n")

    # 1. 从 prompt_builder 导入
    pb_docs, pb_metas, pb_ids = init_from_prompt_builder()

    # 2. 从 Markdown 文件导入（分块）
    md_docs, md_metas, md_ids = init_from_markdown()

    # 合并所有文档
    all_docs = pb_docs + md_docs
    all_metas = pb_metas + md_metas
    all_ids = pb_ids + md_ids

    if not all_docs:
        print("\n❌ 没有可导入的文档")
        return

    # 3. 批量向量化并存入
    print(f"\n💾 正在向量化并保存 {len(all_docs)} 个文档到 ChromaDB...")
    success = knowledge_service.add_documents(
        documents=all_docs,
        metadatas=all_metas,
        ids=all_ids
    )

    if success:
        print(f"\n🎉 成功初始化知识库！")
        stats = knowledge_service.get_collection_stats()
        print(f"📊 总计: {stats['total_documents']} 条知识")
        print(f"📁 数据保存在: {project_root}/data/chroma/")
    else:
        print("\n❌ 初始化失败，请检查错误信息")

    print("\n" + "=" * 60)
    print("✅ 初始化完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

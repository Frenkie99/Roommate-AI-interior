"""
初始化知识库 - 将现有prompt_builder内容转换为向量库
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


def init_from_prompt_builder():
    """将现有的风格和房间描述转换为知识库"""

    documents = []
    metadatas = []
    ids = []

    # 添加风格知识
    print("📋 正在导入装修风格知识...")
    for style_id, style_info in STYLE_PROMPTS.items():
        doc = f"""# 装修风格：{style_info['name']}

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
            "category": "style",
            "style": style_id,
            "source": "prompt_builder.py",
            "name": style_info['name']
        })
        ids.append(f"style_{style_id}")

    print(f"✅ 已添加 {len(STYLE_PROMPTS)} 个装修风格")

    # 添加房间类型知识
    print("\n📋 正在导入房间类型知识...")
    for room_id, room_info in ROOM_TYPE_PROMPTS.items():
        doc = f"""# 房间类型：{room_info['name']}

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
            "category": "room_type",
            "room_type": room_id,
            "source": "prompt_builder.py",
            "name": room_info['name']
        })
        ids.append(f"room_{room_id}")

    print(f"✅ 已添加 {len(ROOM_TYPE_PROMPTS)} 个房间类型")

    # 添加到向量库
    print("\n💾 正在向量化并保存到Chroma数据库...")
    success = knowledge_service.add_documents(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

    if success:
        print(f"\n🎉 成功初始化知识库！")
        print(f"📊 总计添加 {len(documents)} 条知识")
        print(f"📁 数据保存在: {project_root}/data/chroma/")

        # 显示统计信息
        stats = knowledge_service.get_collection_stats()
        print(f"\n📈 知识库统计:")
        print(f"   - 总文档数: {stats['total_documents']}")
        print(f"   - 集合名称: {stats['collection_name']}")
        print(f"   - 状态: {stats['status']}")
    else:
        print("\n❌ 初始化失败，请检查错误信息")


def init_from_markdown_files():
    """从knowledge_base目录加载Markdown文件"""

    knowledge_base_dir = project_root / "knowledge_base"

    if not knowledge_base_dir.exists():
        print(f"⚠️  知识库目录不存在: {knowledge_base_dir}")
        print("💡 提示: 请将装修知识.md文件放入该目录")
        return

    # 查找所有Markdown文件
    md_files = list(knowledge_base_dir.rglob("*.md"))

    if not md_files:
        print(f"⚠️  在 {knowledge_base_dir} 中未找到Markdown文件")
        return

    print(f"📚 找到 {len(md_files)} 个Markdown文件")
    documents = []
    metadatas = []
    ids = []

    for md_file in md_files:
        try:
            # 读取文件内容
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取相对路径作为分类
            rel_path = md_file.relative_to(knowledge_base_dir)
            category = str(rel_path.parent).replace('\\', '/')

            # 生成文档ID
            doc_id = category.replace('/', '_') + '_' + md_file.stem

            documents.append(content)
            metadatas.append({
                "category": category,
                "source": f"knowledge_base/{rel_path}",
                "filename": md_file.name
            })
            ids.append(doc_id)

            print(f"✅ 已加载: {rel_path}")

        except Exception as e:
            print(f"❌ 加载文件失败 {md_file}: {e}")

    if documents:
        print(f"\n💾 正在向量化 {len(documents)} 个文档...")
        success = knowledge_service.add_documents(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        if success:
            print(f"✅ 成功添加 {len(documents)} 个文档到知识库")
        else:
            print("❌ 添加文档失败")


def main():
    """主函数"""
    print("=" * 60)
    print("🏠 AI装修知识库初始化工具")
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

    # 1. 从prompt_builder导入
    init_from_prompt_builder()

    # 2. 从Markdown文件导入（如果有）
    init_from_markdown_files()

    print("\n" + "=" * 60)
    print("✅ 初始化完成！")
    print("=" * 60)
    print("\n💡 提示:")
    print("   - 知识库数据已保存到: backend/data/chroma/")
    print("   - 重启服务后即可使用知识问答功能")
    print("   - 可以通过 /api/v1/knowledge/stats 查看知识库状态")


if __name__ == "__main__":
    main()

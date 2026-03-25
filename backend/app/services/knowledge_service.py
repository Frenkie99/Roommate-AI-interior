"""
知识库服务 - RAG查询核心
提供装修知识的向量检索和智能问答功能
"""

import os
from typing import List, Dict, Optional
from chromadb import PersistentClient
from chromadb.config import Settings


class KnowledgeService:
    """装修知识库服务 - 基于Chroma向量数据库的RAG实现"""

    def __init__(self, persist_directory: str = "./data/chroma"):
        """
        初始化知识库服务

        Args:
            persist_directory: Chroma数据库持久化目录
        """
        # 确保数据目录存在
        os.makedirs(persist_directory, exist_ok=True)

        # 初始化Chroma客户端（持久化模式）
        self.chroma_client = PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,  # 关闭匿名遥测
                allow_reset=True
            )
        )

        # 获取或创建集合
        self.collection = self.chroma_client.get_or_create_collection(
            name="renovation_knowledge",
            metadata={"hnsw:space": "cosine", "description": "装修设计知识库"}
        )

    async def query(
        self,
        question: str,
        style: Optional[str] = None,
        room_type: Optional[str] = None,
        n_results: int = 5
    ) -> Dict:
        """
        查询装修知识库

        Args:
            question: 用户问题
            style: 可选的风格过滤条件
            room_type: 可选的房间类型过滤条件
            n_results: 返回结果数量

        Returns:
            {
                "answer": "AI生成的回答",
                "sources": ["来源1", "来源2"],
                "relevant_docs": [...],
                "context_used": "使用的上下文"
            }
        """
        # 1. 构建过滤条件
        where = {}
        if style:
            where["style"] = style
        if room_type:
            where["room_type"] = room_type

        # 2. 向量检索
        try:
            results = self.collection.query(
                query_texts=[question],
                n_results=n_results,
                where=where if where else None
            )
        except Exception as e:
            # 如果查询失败（如知识库为空），返回空结果
            return {
                "answer": "知识库尚未初始化，请先运行初始化脚本。",
                "sources": [],
                "relevant_docs": [],
                "context_used": ""
            }

        # 3. 检查是否有结果
        if not results or not results['documents'] or not results['documents'][0]:
            return {
                "answer": "未找到相关知识。请尝试其他问题或联系管理员扩充知识库。",
                "sources": [],
                "relevant_docs": [],
                "context_used": ""
            }

        # 4. 构建上下文
        context_parts = []
        sources = []
        relevant_docs = []

        for i, doc in enumerate(results['documents'][0]):
            context_parts.append(f"[知识{i+1}] {doc}")
            relevant_docs.append(doc)

            # 提取来源（优先使用metadata中的source，否则使用ID）
            if results['metadatas'] and results['metadatas'][0]:
                source = results['metadatas'][0][i].get('source', '知识库')
            else:
                source = "知识库"
            sources.append(source)

        context = "\n\n".join(context_parts)

        return {
            "answer": "",  # 将由调用方使用LLM生成
            "sources": list(set(sources)),  # 去重
            "relevant_docs": relevant_docs,
            "context_used": context
        }

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict],
        ids: List[str]
    ) -> bool:
        """
        批量添加文档到知识库

        Args:
            documents: 文档内容列表
            metadatas: 元数据列表
            ids: 文档ID列表

        Returns:
            是否添加成功
        """
        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            return True
        except Exception as e:
            print(f"添加文档失败: {e}")
            return False

    def get_collection_stats(self) -> Dict:
        """获取知识库统计信息"""
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "collection_name": "renovation_knowledge",
                "status": "ok" if count > 0 else "empty"
            }
        except Exception as e:
            return {
                "total_documents": 0,
                "collection_name": "renovation_knowledge",
                "status": f"error: {e}"
            }

    def reset_collection(self) -> bool:
        """清空并重新创建集合（用于重置知识库）"""
        try:
            self.chroma_client.delete_collection("renovation_knowledge")
            self.collection = self.chroma_client.create_collection(
                name="renovation_knowledge",
                metadata={"hnsw:space": "cosine", "description": "装修设计知识库"}
            )
            return True
        except Exception as e:
            print(f"重置集合失败: {e}")
            return False


# 全局知识库服务实例
knowledge_service = KnowledgeService()

"""
重排序模块
使用 bge-reranker-v2-m3 对检索结果进行精排
"""

import os
from typing import List, Dict

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


class Reranker:
    """CrossEncoder 重排序器"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 5,
        content_key: str = "content"
    ) -> List[Dict]:
        """对文档列表重排序，返回 top_k 个最相关结果"""
        if not documents:
            return []

        pairs = [(query, doc[content_key]) for doc in documents]
        scores = self.model.predict(pairs)

        scored_docs = list(zip(scores, documents))
        scored_docs.sort(key=lambda x: x[0], reverse=True)

        return [doc for _, doc in scored_docs[:top_k]]


# 全局实例（延迟加载）
_reranker_instance = None


def get_reranker() -> Reranker:
    """获取全局重排序器实例"""
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = Reranker()
    return _reranker_instance

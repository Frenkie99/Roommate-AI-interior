"""
中文 Embedding 适配层
使用 BAAI/bge-base-zh-v1.5 模型，为 ChromaDB 提供中文语义向量化
"""

import os
from typing import List, Dict, Any

# 设置 HuggingFace 镜像（国内网络环境）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


class ChineseEmbeddingFunction:
    """ChromaDB 兼容的中文 embedding 函数"""

    def __init__(self, model_name: str = "BAAI/bge-base-zh-v1.5"):
        from sentence_transformers import SentenceTransformer
        self._model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.query_instruction = "为这个句子生成表示以用于检索相关文章："

    def name(self) -> str:
        """ChromaDB 1.5+ 要求的标识方法"""
        return self._model_name

    def __call__(self, input: List[str]) -> List[List[float]]:
        """ChromaDB 调用此方法进行 embedding"""
        embeddings = self.model.encode(input, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, input: List[str]) -> List[List[float]]:
        """查询时加指令前缀，提升检索效果"""
        texts = [self.query_instruction + t for t in input]
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def get_config(self) -> Dict[str, Any]:
        """返回序列化配置"""
        return {"model_name": self._model_name}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "ChineseEmbeddingFunction":
        """从配置构建实例"""
        return ChineseEmbeddingFunction(model_name=config.get("model_name", "BAAI/bge-base-zh-v1.5"))

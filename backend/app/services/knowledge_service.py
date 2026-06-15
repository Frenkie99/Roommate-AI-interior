"""
知识库服务 - RAG查询核心
混合检索 (向量 + BM25) + 重排序
"""

import logging
import os
import sys
import math
import re
from typing import List, Dict, Optional
from chromadb import PersistentClient
from chromadb.config import Settings

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def _tokenize_chinese(text: str) -> List[str]:
    """中文分词（jieba 精确模式 + 单字 fallback）"""
    try:
        import jieba
        return [w for w in jieba.cut(text) if len(w.strip()) > 0]
    except ImportError:
        # jieba 未安装时用简单字符切分
        return list(text)


class KnowledgeService:
    """装修知识库服务 - 混合检索 + 重排序"""

    def __init__(self, persist_directory: str = "./data/chroma"):
        self._initialized = False
        self._init_error = None
        self._bm25 = None
        self._bm25_ids = []
        self._bm25_docs = []
        self._bm25_metas = []

        # 低内存模式开关：设 ENABLE_KNOWLEDGE_BASE=false 时不加载 embedding 模型，
        # 知识问答自动降级为纯 LLM 兜底（main.py 的 lifespan 已处理此降级）。
        # 适用于 ~1GB 内存的小服务器，避免 SentenceTransformer 占用 ~470MB 触发 OOM。
        if os.getenv("ENABLE_KNOWLEDGE_BASE", "true").strip().lower() not in ("true", "1", "yes"):
            self._init_error = "knowledge base disabled (low-memory mode)"
            logger.warning("知识库已禁用 (ENABLE_KNOWLEDGE_BASE=false)，问答降级为 LLM 兜底")
            return

        try:
            os.makedirs(persist_directory, exist_ok=True)

            self.chroma_client = PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            from embedding.chinese_embedding import ChineseEmbeddingFunction
            ef = ChineseEmbeddingFunction()

            try:
                self.collection = self.chroma_client.get_or_create_collection(
                    name="renovation_knowledge",
                    metadata={"hnsw:space": "cosine", "description": "装修设计知识库"},
                    embedding_function=ef
                )
            except ValueError:
                self.chroma_client.delete_collection("renovation_knowledge")
                self.collection = self.chroma_client.create_collection(
                    name="renovation_knowledge",
                    metadata={"hnsw:space": "cosine", "description": "装修设计知识库"},
                    embedding_function=ef
                )

            self._initialized = True
        except Exception as e:
            self._init_error = str(e)
            logger.error(f"知识库初始化失败: {e}，将降级为 LLM 兜底模式")

    def _ensure_bm25_index(self):
        """确保 BM25 索引已构建"""
        if self._bm25 is not None:
            return

        from rank_bm25 import BM25Okapi

        count = self.collection.count()
        if count == 0:
            self._bm25 = BM25Okapi([])
            return

        # 从 ChromaDB 加载所有文档
        all_docs = self.collection.get(limit=count)
        self._bm25_ids = all_docs['ids']
        self._bm25_docs = all_docs['documents']
        self._bm25_metas = all_docs['metadatas']

        # 分词
        tokenized = [_tokenize_chinese(doc) for doc in self._bm25_docs]
        self._bm25 = BM25Okapi(tokenized)

    def _bm25_search(self, query: str, top_k: int = 20) -> List[Dict]:
        """BM25 关键词检索"""
        self._ensure_bm25_index()

        if not self._bm25_docs:
            return []

        tokens = _tokenize_chinese(query)
        scores = self._bm25.get_scores(tokens)

        # 取 top_k
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for idx, score in ranked:
            results.append({
                "id": self._bm25_ids[idx],
                "content": self._bm25_docs[idx],
                "metadata": self._bm25_metas[idx],
                "bm25_score": float(score),
                "bm25_rank": len(results) + 1,
            })
        return results

    @staticmethod
    def _build_where_filter(style: Optional[str], room_type: Optional[str]) -> Optional[Dict]:
        filters: List[Dict] = []
        if style:
            filters.append({"style": style})
        if room_type:
            filters.append({"room_type": room_type})

        if not filters:
            return None
        if len(filters) == 1:
            return filters[0]
        return {"$and": filters}

    @staticmethod
    def _match_metadata(metadata: Dict, style: Optional[str], room_type: Optional[str]) -> bool:
        if style and metadata.get("style") != style:
            return False
        if room_type and metadata.get("room_type") != room_type:
            return False
        return True

    def _vector_search(
        self,
        query: str,
        top_k: int = 20,
        where: Optional[Dict] = None
    ) -> List[Dict]:
        """向量语义检索"""
        query_kwargs = {
            "query_texts": [query],
            "n_results": min(top_k, self.collection.count()),
        }
        if where is not None:
            query_kwargs["where"] = where

        results = self.collection.query(**query_kwargs)

        if not results or not results['documents'] or not results['documents'][0]:
            return []

        docs = []
        for i, doc in enumerate(results['documents'][0]):
            metadata = results['metadatas'][0][i] if results['metadatas'] else {}
            distance = results['distances'][0][i] if results.get('distances') else None
            docs.append({
                "id": results['ids'][0][i],
                "content": doc,
                "metadata": metadata,
                "vector_distance": distance,
                "vector_rank": i + 1,
            })
        return docs

    def _rrf_fusion(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict],
        k: int = 60
    ) -> List[Dict]:
        """Reciprocal Rank Fusion 融合两路检索结果"""
        # 构建 id -> doc 映射
        doc_map = {}

        # 向量检索分数
        for doc in vector_results:
            doc_id = doc['id']
            rrf_score = 1.0 / (k + doc['vector_rank'])
            doc_map[doc_id] = {**doc, 'rrf_score': rrf_score}

        # BM25 检索分数（累加）
        for doc in bm25_results:
            doc_id = doc['id']
            rrf_score = 1.0 / (k + doc['bm25_rank'])
            if doc_id in doc_map:
                doc_map[doc_id]['rrf_score'] += rrf_score
                doc_map[doc_id]['bm25_score'] = doc['bm25_score']
            else:
                doc_map[doc_id] = {**doc, 'rrf_score': rrf_score}

        # 按 RRF 分数排序
        fused = sorted(doc_map.values(), key=lambda x: x['rrf_score'], reverse=True)
        return fused

    def _build_source_path(self, metadata: Dict) -> str:
        """构建层级来源路径"""
        source_path = metadata.get('source', '知识库')
        if metadata.get('part'):
            source_path += f" > {metadata['part']}"
        if metadata.get('section'):
            source_path += f" > {metadata['section']}"
        if metadata.get('subsection'):
            source_path += f" > {metadata['subsection']}"
        return source_path

    async def query(
        self,
        question: str,
        style: Optional[str] = None,
        room_type: Optional[str] = None,
        n_results: int = 5
    ) -> Dict:
        """
        混合检索 + 重排序

        Pipeline:
        1. 向量检索 top-20
        2. BM25 检索 top-20
        3. RRF 融合
        4. Reranker 重排序取 top-n_results
        """
        if not self._initialized:
            return self._empty_result(
                f"知识库未初始化: {self._init_error}",
                error="not_initialized",
            )

        try:
            count = self.collection.count()
            if count == 0:
                return self._empty_result(
                    "知识库为空，请先运行初始化脚本。",
                    error="empty_collection",
                )

            retrieve_k = min(20, count)
            where_filter = self._build_where_filter(style, room_type)

            # Step 1 + 2: 双路检索
            vector_results = self._vector_search(
                question,
                top_k=retrieve_k,
                where=where_filter,
            )
            bm25_results = self._bm25_search(question, top_k=retrieve_k)
            if style or room_type:
                bm25_results = [
                    result for result in bm25_results
                    if self._match_metadata(result.get("metadata") or {}, style, room_type)
                ]

            # Step 3: RRF 融合
            fused = self._rrf_fusion(vector_results, bm25_results)
            fused = fused[:retrieve_k]

            # Step 4: 重排序
            try:
                from embedding.reranker import get_reranker
                reranker = get_reranker()
                reranked = reranker.rerank(question, fused, top_k=n_results)
            except Exception:
                # 重排序器不可用时，直接用 RRF 排序结果
                logger.exception("重排序器不可用，回退到 RRF 排序")
                reranked = fused[:n_results]

        except ValueError:
            logger.exception("知识库检索参数不合法")
            return self._empty_result("检索参数不合法", error="invalid_query")
        except Exception:
            logger.exception("知识库检索内部错误")
            return self._empty_result("检索失败", error="internal")

        if not reranked:
            return self._empty_result("未找到相关知识。")

        # 构建结构化上下文
        context_parts = []
        sources = []
        relevant_docs = []

        for i, doc in enumerate(reranked):
            metadata = doc.get('metadata', {})
            source_path = self._build_source_path(metadata)

            context_parts.append(f"--- 知识片段 {i+1} ---\n来源: {source_path}\n{doc['content']}")
            sources.append(source_path)
            relevant_docs.append({
                "content": doc['content'],
                "metadata": metadata,
                "distance": doc.get('vector_distance'),
                "rrf_score": doc.get('rrf_score'),
            })

        context = "\n\n".join(context_parts)

        return {
            "answer": "",
            "sources": list(dict.fromkeys(sources)),
            "relevant_docs": relevant_docs,
            "context_used": context
        }

    def _empty_result(self, message: str = "", error: Optional[str] = None) -> Dict:
        result = {
            "answer": message,
            "sources": [],
            "relevant_docs": [],
            "context_used": ""
        }
        if error is not None:
            result["error"] = error
        return result

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict],
        ids: List[str]
    ) -> bool:
        """批量添加文档到知识库"""
        try:
            batch_size = 50
            for i in range(0, len(documents), batch_size):
                end = min(i + batch_size, len(documents))
                self.collection.add(
                    documents=documents[i:end],
                    metadatas=metadatas[i:end],
                    ids=ids[i:end]
                )
            # 新增文档后重置 BM25 索引
            self._bm25 = None
            return True
        except Exception as e:
            print(f"添加文档失败: {e}")
            return False

    def get_collection_stats(self) -> Dict:
        """获取知识库统计信息"""
        if not self._initialized:
            return {
                "total_documents": 0,
                "collection_name": "renovation_knowledge",
                "status": f"uninitialized: {self._init_error}"
            }
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

    def document_exists(self, doc_id: str) -> bool:
        """检查文档是否已存在"""
        try:
            result = self.collection.get(ids=[doc_id])
            return len(result['ids']) > 0
        except Exception:
            return False

    def reset_collection(self) -> bool:
        """清空并重新创建集合"""
        try:
            self.chroma_client.delete_collection("renovation_knowledge")
            from embedding.chinese_embedding import ChineseEmbeddingFunction
            ef = ChineseEmbeddingFunction()
            self.collection = self.chroma_client.create_collection(
                name="renovation_knowledge",
                metadata={"hnsw:space": "cosine", "description": "装修设计知识库"},
                embedding_function=ef
            )
            self._bm25 = None
            return True
        except Exception as e:
            print(f"重置集合失败: {e}")
            return False


knowledge_service = KnowledgeService()

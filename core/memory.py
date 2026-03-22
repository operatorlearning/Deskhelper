# -*- coding: utf-8 -*-
"""
记忆系统 - ChromaDB 向量数据库 + RAG
支持：短期对话记忆、长期用户偏好记忆、语义检索
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional

from loguru import logger


class MemorySystem:
    """
    双层记忆架构：
    - 短期记忆：当前会话对话历史（列表）
    - 长期记忆：ChromaDB向量存储，跨会话持久化
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self._collection = None
        self._embedder = None
        self._short_term: List[Dict] = []  # 短期对话历史
        self._max_short_term = 20           # 最大短期记忆条数

    def _init_db(self):
        """初始化ChromaDB"""
        if self._collection is not None:
            return
        logger.info("初始化 ChromaDB 向量记忆系统...")
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path=self.cfg.persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = client.get_or_create_collection(
            name=self.cfg.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.success(f"ChromaDB 初始化完成，集合: {self.cfg.collection_name}")

    def _get_embedder(self):
        """获取嵌入模型（懒加载）"""
        if self._embedder is not None:
            return self._embedder
        logger.info(f"加载嵌入模型: {self.cfg.embedding_model}")
        from sentence_transformers import SentenceTransformer
        self._embedder = SentenceTransformer(self.cfg.embedding_model)
        logger.success("嵌入模型加载完成")
        return self._embedder

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """文本向量化"""
        embedder = self._get_embedder()
        embeddings = embedder.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    # ========== 短期记忆（对话历史）==========

    def add_message(self, role: str, content: str):
        """
        添加对话消息到短期记忆
        Args:
            role: 'user' | 'assistant' | 'system'
            content: 消息内容
        """
        self._short_term.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        # 超出上限时，保留最新的
        if len(self._short_term) > self._max_short_term:
            self._short_term = self._short_term[-self._max_short_term:]

    def get_conversation_history(self, n: int = 10) -> List[Dict]:
        """获取最近n条对话历史（格式适配LangChain）"""
        recent = self._short_term[-n:]
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def clear_short_term(self):
        """清空短期记忆"""
        self._short_term.clear()
        logger.info("短期记忆已清空")

    # ========== 长期记忆（ChromaDB向量存储）==========

    def remember(
        self,
        content: str,
        memory_type: str = "general",
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        存储长期记忆
        Args:
            content: 记忆内容
            memory_type: 类型标签 (preference/task/fact/general)
            metadata: 额外元数据
        Returns:
            记忆ID
        """
        self._init_db()
        mem_id = str(uuid.uuid4())
        meta = {
            "type": memory_type,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {}),
        }
        embedding = self._embed([content])
        self._collection.add(
            ids=[mem_id],
            embeddings=embedding,
            documents=[content],
            metadatas=[meta],
        )
        logger.debug(f"存储长期记忆 [{memory_type}]: {content[:50]}...")
        return mem_id

    def recall(
        self,
        query: str,
        top_k: Optional[int] = None,
        memory_type: Optional[str] = None,
    ) -> List[Dict]:
        """
        语义检索相关记忆（RAG）
        Args:
            query: 查询文本
            top_k: 返回条数
            memory_type: 按类型过滤
        Returns:
            [{"content": str, "score": float, "metadata": dict}]
        """
        self._init_db()
        k = top_k or self.cfg.top_k
        query_embedding = self._embed([query])

        where = {"type": memory_type} if memory_type else None
        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=min(k, max(1, self._collection.count())),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        memories = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                memories.append({
                    "content": doc,
                    "score": float(1 - dist),  # cosine相似度
                    "metadata": meta,
                })
        logger.debug(f"记忆检索 '{query[:30]}...' 找到 {len(memories)} 条")
        return memories

    def recall_as_context(self, query: str) -> str:
        """
        检索记忆并格式化为上下文字符串（用于RAG注入提示词）
        """
        memories = self.recall(query)
        if not memories:
            return ""
        lines = ["【相关记忆】"]
        for i, m in enumerate(memories, 1):
            lines.append(f"{i}. [{m['metadata'].get('type', 'general')}] {m['content']}")
        return "\n".join(lines)

    def remember_preference(self, preference: str):
        """存储用户偏好"""
        self.remember(preference, memory_type="preference")

    def remember_task_result(self, task: str, result: str):
        """存储任务执行结果"""
        content = f"任务: {task}\n结果: {result}"
        self.remember(content, memory_type="task")

    def get_all_memories(self) -> List[Dict]:
        """获取所有长期记忆"""
        self._init_db()
        results = self._collection.get(include=["documents", "metadatas"])
        memories = []
        for doc, meta in zip(results["documents"], results["metadatas"]):
            memories.append({"content": doc, "metadata": meta})
        return memories

    def delete_memory(self, mem_id: str):
        """删除指定记忆"""
        self._init_db()
        self._collection.delete(ids=[mem_id])
        logger.info(f"已删除记忆: {mem_id}")

    def get_memory_count(self) -> int:
        """获取长期记忆总数"""
        self._init_db()
        return self._collection.count()

    def export_memories(self, output_path: str):
        """导出所有记忆到JSON文件"""
        memories = self.get_all_memories()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(memories, f, ensure_ascii=False, indent=2)
        logger.info(f"记忆已导出到: {output_path}")


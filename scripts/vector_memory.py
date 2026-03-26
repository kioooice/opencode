#!/usr/bin/env python3
"""
Vector Memory System - HNSW + SQLite
基于 ruflo RuVector 设计理念，适配 opencode 本地使用
"""

import json
import os
import sys
import sqlite3
import hashlib
import math
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# 基础路径
MEMORY_DIR = Path(__file__).parent.parent / "memory"
VECTOR_DIR = MEMORY_DIR / ".vectors"
DB_PATH = VECTOR_DIR / "memory.db"


class SimpleEmbedder:
    """简化版嵌入器 - 字符 n-gram + 词级特征混合"""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _char_ngrams(self, text: str, n: int = 2) -> List[str]:
        """提取字符 n-grams（中文逐字，英文逐词内 n-gram）"""
        import re

        # 分离中英文
        chars = []
        eng_buf = []
        for ch in text.lower():
            if "\u4e00" <= ch <= "\u9fff":
                if eng_buf:
                    chars.append("".join(eng_buf))
                    eng_buf = []
                chars.append(ch)
            elif ch.isalnum():
                eng_buf.append(ch)
            else:
                if eng_buf:
                    chars.append("".join(eng_buf))
                    eng_buf = []
        if eng_buf:
            chars.append("".join(eng_buf))

        # 生成 n-grams
        ngrams = []
        for i in range(len(chars) - n + 1):
            ngrams.append(tuple(chars[i : i + n]))
        return ngrams

    def _word_ngrams(self, text: str) -> List[str]:
        """提取单词/中文字符作为 unigram"""
        import re

        return re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", text.lower())

    def _hash_to_idx(self, feature: str, offset: int = 0) -> int:
        """稳定哈希映射"""
        h = hashlib.md5(feature.encode("utf-8")).digest()
        return (int.from_bytes(h[:4], "little") + offset) % self.dim

    def embed(self, text: str) -> List[float]:
        """生成文本嵌入向量 - 混合字符 bigram + unigram"""
        vector = [0.0] * self.dim

        # Unigram 特征（权重 1.0）
        for word in self._word_ngrams(text):
            idx = self._hash_to_idx(word, offset=0)
            vector[idx] += 1.0

        # Bigram 特征（权重 1.5，更强的局部匹配信号）
        for ng in self._char_ngrams(text, n=2):
            feature = "|".join(ng)
            idx = self._hash_to_idx(feature, offset=128)  # 偏移避免冲突
            vector[idx] += 1.5

        # Trigram 特征（权重 0.8）
        for ng in self._char_ngrams(text, n=3):
            feature = "|".join(ng)
            idx = self._hash_to_idx(feature, offset=256)
            vector[idx] += 0.8

        # 归一化
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    def similarity(self, v1: List[float], v2: List[float]) -> float:
        """余弦相似度"""
        if len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)


class VectorDB:
    """向量数据库 - SQLite + 内存 HNSW 索引"""

    def __init__(self):
        self.embedder = SimpleEmbedder()
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row

        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                namespace TEXT DEFAULT 'default',
                embedding BLOB,
                metadata TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                accessed_at TEXT DEFAULT (datetime('now')),
                access_count INTEGER DEFAULT 0,
                importance REAL DEFAULT 0.5
            );
            
            CREATE INDEX IF NOT EXISTS idx_namespace ON memories(namespace);
            CREATE INDEX IF NOT EXISTS idx_key ON memories(key);
            CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance);
        """)
        self.conn.commit()

    def _vector_to_blob(self, vector: List[float]) -> bytes:
        """向量转二进制"""
        import struct

        return struct.pack(f"{len(vector)}f", *vector)

    def _blob_to_vector(self, blob: bytes) -> List[float]:
        """二进制转向量"""
        import struct

        dim = len(blob) // 4
        return list(struct.unpack(f"{dim}f", blob))

    def store(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        metadata: Optional[Dict] = None,
        importance: float = 0.5,
    ) -> str:
        """存储记忆"""
        # 生成 ID
        id_str = hashlib.md5(f"{namespace}:{key}".encode()).hexdigest()

        # 生成嵌入向量
        embedding = self.embedder.embed(value)
        embedding_blob = self._vector_to_blob(embedding)

        metadata_json = json.dumps(metadata or {})

        self.conn.execute(
            """
            INSERT OR REPLACE INTO memories 
            (id, key, value, namespace, embedding, metadata, importance, accessed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
            (id_str, key, value, namespace, embedding_blob, metadata_json, importance),
        )

        self.conn.commit()
        return id_str

    def search(
        self,
        query: str,
        namespace: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict]:
        """语义搜索"""
        query_embedding = self.embedder.embed(query)

        # 获取候选记忆
        if namespace:
            rows = self.conn.execute(
                "SELECT * FROM memories WHERE namespace = ?", (namespace,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM memories").fetchall()

        # 计算相似度
        results = []
        for row in rows:
            if row["embedding"]:
                memory_embedding = self._blob_to_vector(row["embedding"])
                score = self.embedder.similarity(query_embedding, memory_embedding)

                if score >= min_score:
                    results.append(
                        {
                            "id": row["id"],
                            "key": row["key"],
                            "value": row["value"],
                            "namespace": row["namespace"],
                            "score": score,
                            "metadata": json.loads(row["metadata"]),
                            "importance": row["importance"],
                        }
                    )

        # 更新访问计数
        for r in results[:top_k]:
            self.conn.execute(
                "UPDATE memories SET access_count = access_count + 1, accessed_at = datetime('now') WHERE id = ?",
                (r["id"],),
            )
        self.conn.commit()

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def retrieve(self, key: str, namespace: str = "default") -> Optional[Dict]:
        """按 key 精确获取"""
        row = self.conn.execute(
            "SELECT * FROM memories WHERE key = ? AND namespace = ?", (key, namespace)
        ).fetchone()

        if row:
            self.conn.execute(
                "UPDATE memories SET access_count = access_count + 1, accessed_at = datetime('now') WHERE id = ?",
                (row["id"],),
            )
            self.conn.commit()
            return {
                "id": row["id"],
                "key": row["key"],
                "value": row["value"],
                "namespace": row["namespace"],
                "metadata": json.loads(row["metadata"]),
                "importance": row["importance"],
            }
        return None

    def list_all(self, namespace: Optional[str] = None) -> List[Dict]:
        """列出所有记忆"""
        if namespace:
            rows = self.conn.execute(
                "SELECT * FROM memories WHERE namespace = ? ORDER BY importance DESC",
                (namespace,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM memories ORDER BY namespace, importance DESC"
            ).fetchall()

        return [
            {
                "id": row["id"],
                "key": row["key"],
                "value": row["value"][:100] + "..."
                if len(row["value"]) > 100
                else row["value"],
                "namespace": row["namespace"],
                "importance": row["importance"],
                "access_count": row["access_count"],
            }
            for row in rows
        ]

    def index_files(self):
        """索引 memory 目录下的文件"""
        indexed = 0
        for md_file in MEMORY_DIR.rglob("*.md"):
            if ".vectors" in str(md_file):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                if content.strip():
                    relative_path = str(md_file.relative_to(MEMORY_DIR))
                    self.store(
                        key=relative_path,
                        value=content[:2000],  # 限制长度
                        namespace="files",
                        metadata={"path": relative_path},
                        importance=0.3,
                    )
                    indexed += 1
            except Exception as e:
                print(f"Warning: Failed to index {md_file}: {e}")
        return indexed

    def status(self) -> Dict:
        """获取状态"""
        total = self.conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        namespaces = self.conn.execute(
            "SELECT namespace, COUNT(*) as count FROM memories GROUP BY namespace"
        ).fetchall()

        return {
            "total_memories": total,
            "namespaces": {row["namespace"]: row["count"] for row in namespaces},
            "db_path": str(DB_PATH),
            "db_size": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
        }

    def delete(self, key: str, namespace: str = "default") -> bool:
        """删除记忆"""
        cursor = self.conn.execute(
            "DELETE FROM memories WHERE key = ? AND namespace = ?", (key, namespace)
        )
        self.conn.commit()
        return cursor.rowcount > 0


def main():
    db = VectorDB()

    if len(sys.argv) < 2:
        print("Usage: vector_memory.py <command> [args]")
        print("Commands:")
        print("  index          - Index memory directory files")
        print("  search <query> - Search memories")
        print("  store <key> <value> [namespace] - Store memory")
        print("  retrieve <key> [namespace] - Retrieve memory by key")
        print("  list [namespace] - List memories")
        print("  status         - Show status")
        print("  delete <key> [namespace] - Delete memory")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "index":
        count = db.index_files()
        print(f"Indexed {count} files")

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: vector_memory.py search <query> [--namespace NS] [--top-k N]")
            sys.exit(1)

        query = sys.argv[2]
        namespace = None
        top_k = 5

        # 解析参数
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--namespace" and i + 1 < len(sys.argv):
                namespace = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--top-k" and i + 1 < len(sys.argv):
                top_k = int(sys.argv[i + 1])
                i += 2
            else:
                i += 1

        results = db.search(query, namespace=namespace, top_k=top_k)

        if results:
            for r in results:
                print(f"[{r['score']:.3f}] {r['key']}")
                print(f"  {r['value'][:200]}")
                print()
        else:
            print("No results found")

    elif cmd == "store":
        if len(sys.argv) < 4:
            print("Usage: vector_memory.py store <key> <value> [namespace]")
            sys.exit(1)

        key = sys.argv[2]
        value = sys.argv[3]
        namespace = sys.argv[4] if len(sys.argv) > 4 else "default"

        id_str = db.store(key, value, namespace)
        print(f"Stored: {id_str}")

    elif cmd == "retrieve":
        if len(sys.argv) < 3:
            print("Usage: vector_memory.py retrieve <key> [namespace]")
            sys.exit(1)

        key = sys.argv[2]
        namespace = sys.argv[3] if len(sys.argv) > 3 else "default"

        result = db.retrieve(key, namespace)
        if result:
            print(f"Key: {result['key']}")
            print(f"Value: {result['value']}")
            print(f"Namespace: {result['namespace']}")
            print(f"Importance: {result['importance']}")
        else:
            print("Not found")

    elif cmd == "list":
        namespace = sys.argv[2] if len(sys.argv) > 2 else None
        items = db.list_all(namespace)

        for item in items:
            print(
                f"[{item['namespace']}] {item['key']} (importance: {item['importance']:.2f}, access: {item['access_count']})"
            )

    elif cmd == "status":
        status = db.status()
        print(f"Total memories: {status['total_memories']}")
        print(f"DB size: {status['db_size'] / 1024:.1f} KB")
        print("Namespaces:")
        for ns, count in status["namespaces"].items():
            print(f"  {ns}: {count}")

    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("Usage: vector_memory.py delete <key> [namespace]")
            sys.exit(1)

        key = sys.argv[2]
        namespace = sys.argv[3] if len(sys.argv) > 3 else "default"

        if db.delete(key, namespace):
            print(f"Deleted: {key}")
        else:
            print("Not found")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

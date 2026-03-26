#!/usr/bin/env python3
"""
Self-Learning System - EWC++ 防遗忘机制
基于 ruflo RuVector 设计，适配 opencode 本地使用
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# 基础路径
MEMORY_DIR = Path(__file__).parent.parent / "memory"
VECTOR_DIR = MEMORY_DIR / ".vectors"
LEARNING_DB = VECTOR_DIR / "learning.json"


class Pattern:
    """学习模式"""

    def __init__(
        self,
        id: str,
        content: str,
        pattern_type: str,
        importance: float = 0.5,
        protected: bool = False,
    ):
        self.id = id
        self.content = content
        self.pattern_type = pattern_type  # success, failure, neutral
        self.importance = importance
        self.protected = protected
        self.created_at = datetime.now().isoformat()
        self.last_used = datetime.now().isoformat()
        self.use_count = 0
        self.success_count = 0
        self.failure_count = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "pattern_type": self.pattern_type,
            "importance": self.importance,
            "protected": self.protected,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Pattern":
        p = cls(
            id=data["id"],
            content=data["content"],
            pattern_type=data["pattern_type"],
            importance=data.get("importance", 0.5),
            protected=data.get("protected", False),
        )
        p.created_at = data.get("created_at", p.created_at)
        p.last_used = data.get("last_used", p.last_used)
        p.use_count = data.get("use_count", 0)
        p.success_count = data.get("success_count", 0)
        p.failure_count = data.get("failure_count", 0)
        return p


class EWCLearning:
    """EWC++ 学习系统"""

    # EWC++ 参数
    SUCCESS_BOOST = 0.05  # 成功模式重要性增加
    FAILURE_PENALTY = 0.025  # 失败模式重要性减少
    DECAY_RATE = 0.01  # 衰减率
    PROTECTED_DECAY = 0.005  # 受保护模式衰减率（更慢）
    MIN_IMPORTANCE = 0.1  # 最小重要性阈值
    MAX_PATTERNS = 1000  # 最大模式数量

    def __init__(self):
        self.patterns: Dict[str, Pattern] = {}
        self._load()

    def _load(self):
        """加载学习数据"""
        if LEARNING_DB.exists():
            try:
                data = json.loads(LEARNING_DB.read_text(encoding="utf-8"))
                for item in data.get("patterns", []):
                    p = Pattern.from_dict(item)
                    self.patterns[p.id] = p
            except Exception as e:
                print(f"Warning: Failed to load learning data: {e}")

    def _save(self):
        """保存学习数据"""
        VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "patterns": [p.to_dict() for p in self.patterns.values()],
            "updated_at": datetime.now().isoformat(),
        }
        LEARNING_DB.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _generate_id(self, content: str) -> str:
        """生成模式 ID"""
        import hashlib

        return hashlib.md5(content.encode()).hexdigest()[:12]

    def learn(self, content: str, outcome: str, context: Optional[str] = None) -> str:
        """
        学习新模式

        Args:
            content: 模式内容
            outcome: success 或 failure
            context: 可选上下文

        Returns:
            模式 ID
        """
        id_str = self._generate_id(content)

        if id_str in self.patterns:
            # 更新现有模式
            pattern = self.patterns[id_str]
            pattern.use_count += 1
            pattern.last_used = datetime.now().isoformat()

            if outcome == "success":
                pattern.success_count += 1
                pattern.importance = min(1.0, pattern.importance + self.SUCCESS_BOOST)
            elif outcome == "failure":
                pattern.failure_count += 1
                pattern.importance = max(
                    self.MIN_IMPORTANCE, pattern.importance - self.FAILURE_PENALTY
                )

            # 更新类型
            if pattern.success_count > pattern.failure_count * 2:
                pattern.pattern_type = "success"
            elif pattern.failure_count > pattern.success_count * 2:
                pattern.pattern_type = "failure"
            else:
                pattern.pattern_type = "neutral"
        else:
            # 创建新模式
            pattern = Pattern(
                id=id_str,
                content=content,
                pattern_type=outcome,
                importance=0.6 if outcome == "success" else 0.4,
            )
            self.patterns[id_str] = pattern

        self._save()
        return id_str

    def protect(self, pattern_id: str) -> bool:
        """保护重要模式（减缓衰减）"""
        if pattern_id in self.patterns:
            self.patterns[pattern_id].protected = True
            self.patterns[pattern_id].importance = min(
                1.0, self.patterns[pattern_id].importance + 0.1
            )
            self._save()
            return True
        return False

    def unprotect(self, pattern_id: str) -> bool:
        """取消保护"""
        if pattern_id in self.patterns:
            self.patterns[pattern_id].protected = False
            self._save()
            return True
        return False

    def decay(self, days: int = 7):
        """
        时间衰减 - EWC++ 核心机制

        长期未用的模式重要性会降低，但受保护的模式衰减更慢
        """
        now = datetime.now()
        decayed = 0

        for pattern in self.patterns.values():
            last_used = datetime.fromisoformat(pattern.last_used)
            days_unused = (now - last_used).days

            if days_unused > days:
                # 计算衰减量
                decay_amount = self.DECAY_RATE * (days_unused - days)
                if pattern.protected:
                    decay_amount *= (
                        self.PROTECTED_DECAY / self.DECAY_RATE
                    )  # 受保护模式衰减更慢

                pattern.importance = max(
                    self.MIN_IMPORTANCE, pattern.importance - decay_amount
                )
                decayed += 1

        if decayed > 0:
            self._save()

        return decayed

    def cleanup(self, max_patterns: Optional[int] = None):
        """
        清理低重要性模式

        当模式数量超过阈值时，删除重要性最低的未保护模式
        """
        max_count = max_patterns or self.MAX_PATTERNS

        if len(self.patterns) <= max_count:
            return 0

        # 按重要性排序，排除受保护的
        unprotected = [(pid, p) for pid, p in self.patterns.items() if not p.protected]
        unprotected.sort(key=lambda x: x[1].importance)

        # 删除低重要性的
        to_delete = len(self.patterns) - max_count
        deleted = 0

        for pid, _ in unprotected[:to_delete]:
            del self.patterns[pid]
            deleted += 1

        if deleted > 0:
            self._save()

        return deleted

    def consolidate(self) -> Dict:
        """
        整合学习成果

        执行衰减 + 清理，返回统计信息
        """
        before_count = len(self.patterns)

        # 执行衰减
        decayed = self.decay()

        # 清理低重要性
        cleaned = self.cleanup()

        # 统计
        stats = {
            "before": before_count,
            "after": len(self.patterns),
            "decayed": decayed,
            "cleaned": cleaned,
            "protected": sum(1 for p in self.patterns.values() if p.protected),
            "success_patterns": sum(
                1 for p in self.patterns.values() if p.pattern_type == "success"
            ),
            "failure_patterns": sum(
                1 for p in self.patterns.values() if p.pattern_type == "failure"
            ),
        }

        return stats

    def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_importance: float = 0.0,
        limit: int = 50,
    ) -> List[Dict]:
        """获取模式列表"""
        results = []

        for pattern in self.patterns.values():
            if pattern_type and pattern.pattern_type != pattern_type:
                continue
            if pattern.importance < min_importance:
                continue

            results.append(pattern.to_dict())

        # 按重要性排序
        results.sort(key=lambda x: x["importance"], reverse=True)
        return results[:limit]

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索模式（简单关键词匹配）"""
        query_lower = query.lower()
        results = []

        for pattern in self.patterns.values():
            if query_lower in pattern.content.lower():
                results.append(
                    {
                        **pattern.to_dict(),
                        "relevance": 1.0
                        if query_lower == pattern.content.lower()
                        else 0.5,
                    }
                )

        results.sort(key=lambda x: (x["relevance"], x["importance"]), reverse=True)
        return results[:limit]

    def get_stats(self) -> Dict:
        """获取统计信息"""
        if not self.patterns:
            return {
                "total": 0,
                "protected": 0,
                "success": 0,
                "failure": 0,
                "neutral": 0,
                "avg_importance": 0,
                "max_importance": 0,
                "total_uses": 0,
            }

        patterns = list(self.patterns.values())
        return {
            "total": len(patterns),
            "protected": sum(1 for p in patterns if p.protected),
            "success": sum(1 for p in patterns if p.pattern_type == "success"),
            "failure": sum(1 for p in patterns if p.pattern_type == "failure"),
            "neutral": sum(1 for p in patterns if p.pattern_type == "neutral"),
            "avg_importance": sum(p.importance for p in patterns) / len(patterns),
            "max_importance": max(p.importance for p in patterns),
            "total_uses": sum(p.use_count for p in patterns),
        }


def main():
    learner = EWCLearning()

    if len(sys.argv) < 2:
        print("Usage: self_learning.py <command> [args]")
        print("Commands:")
        print("  learn <content> <success|failure> - Learn a pattern")
        print("  patterns [--type TYPE] [--min-importance N] - List patterns")
        print("  search <query> - Search patterns")
        print("  protect <id> - Protect a pattern")
        print("  unprotect <id> - Unprotect a pattern")
        print("  consolidate - Run consolidation (decay + cleanup)")
        print("  stats - Show statistics")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "learn":
        if len(sys.argv) < 4:
            print("Usage: self_learning.py learn <content> <success|failure>")
            sys.exit(1)

        content = sys.argv[2]
        outcome = sys.argv[3]

        if outcome not in ("success", "failure"):
            print("Outcome must be 'success' or 'failure'")
            sys.exit(1)

        id_str = learner.learn(content, outcome)
        print(f"Learned: {id_str} ({outcome})")

    elif cmd == "patterns":
        pattern_type = None
        min_importance = 0.0

        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--type" and i + 1 < len(sys.argv):
                pattern_type = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--min-importance" and i + 1 < len(sys.argv):
                min_importance = float(sys.argv[i + 1])
                i += 2
            else:
                i += 1

        patterns = learner.get_patterns(pattern_type, min_importance)

        if not patterns:
            print("No patterns found")
        else:
            for p in patterns:
                protected = " [PROTECTED]" if p["protected"] else ""
                print(
                    f"[{p['id']}] {p['pattern_type']} - importance: {p['importance']:.2f}{protected}"
                )
                print(f"  {p['content'][:100]}")
                print(
                    f"  Uses: {p['use_count']}, Success: {p['success_count']}, Failure: {p['failure_count']}"
                )
                print()

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: self_learning.py search <query>")
            sys.exit(1)

        query = sys.argv[2]
        results = learner.search(query)

        if results:
            for r in results:
                print(
                    f"[{r['id']}] {r['pattern_type']} - importance: {r['importance']:.2f}"
                )
                print(f"  {r['content'][:100]}")
                print()
        else:
            print("No results found")

    elif cmd == "protect":
        if len(sys.argv) < 3:
            print("Usage: self_learning.py protect <id>")
            sys.exit(1)

        pattern_id = sys.argv[2]
        if learner.protect(pattern_id):
            print(f"Protected: {pattern_id}")
        else:
            print("Pattern not found")

    elif cmd == "unprotect":
        if len(sys.argv) < 3:
            print("Usage: self_learning.py unprotect <id>")
            sys.exit(1)

        pattern_id = sys.argv[2]
        if learner.unprotect(pattern_id):
            print(f"Unprotected: {pattern_id}")
        else:
            print("Pattern not found")

    elif cmd == "consolidate":
        stats = learner.consolidate()
        print("Consolidation complete:")
        print(f"  Patterns: {stats['before']} → {stats['after']}")
        print(f"  Decayed: {stats['decayed']}")
        print(f"  Cleaned: {stats['cleaned']}")
        print(f"  Protected: {stats['protected']}")
        print(f"  Success patterns: {stats['success_patterns']}")
        print(f"  Failure patterns: {stats['failure_patterns']}")

    elif cmd == "stats":
        stats = learner.get_stats()
        print(f"Total patterns: {stats['total']}")
        print(f"Protected: {stats['protected']}")
        print(f"Success: {stats['success']}")
        print(f"Failure: {stats['failure']}")
        print(f"Neutral: {stats['neutral']}")
        print(f"Average importance: {stats['avg_importance']:.3f}")
        print(f"Max importance: {stats['max_importance']:.3f}")
        print(f"Total uses: {stats['total_uses']}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

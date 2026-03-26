#!/usr/bin/env python3
"""
Session End Hook - 会话结束时自动执行
整合自学习 + 向量索引更新
"""

import sys
from pathlib import Path

# 基础路径
SCRIPTS_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPTS_DIR.parent / "memory"

# 导入模块
sys.path.insert(0, str(SCRIPTS_DIR))
from vector_memory import VectorDB
from auto_learn import AutoLearner


def run_session_end():
    """会话结束处理"""
    print("=" * 50)
    print("Session End Processing")
    print("=" * 50)

    results = {"learning": None, "indexing": None, "consolidation": None}

    # 1. 自动学习
    print("\n[1/3] Auto Learning...")
    try:
        learner = AutoLearner()
        learning_result = learner.run(days=1, dry_run=False)
        results["learning"] = learning_result
        print(
            f"  ✓ Learned {learning_result['total_learned']} patterns from {learning_result['files_processed']} files"
        )
    except Exception as e:
        print(f"  ✗ Learning failed: {e}")

    # 2. 向量索引更新
    print("\n[2/3] Vector Index Update...")
    try:
        db = VectorDB()
        indexed = db.index_files()
        results["indexing"] = indexed
        print(f"  ✓ Indexed {indexed} files")
    except Exception as e:
        print(f"  ✗ Indexing failed: {e}")

    # 3. 整合学习成果
    print("\n[3/3] Consolidation...")
    try:
        from self_learning import EWCLearning

        learner = EWCLearning()
        stats = learner.consolidate()
        results["consolidation"] = stats
        print(f"  ✓ Patterns: {stats['before']} → {stats['after']}")
        print(f"  ✓ Protected: {stats['protected']}")
    except Exception as e:
        print(f"  ✗ Consolidation failed: {e}")

    print("\n" + "=" * 50)
    print("Session End Complete")
    print("=" * 50)

    return results


def main():
    if "--dry-run" in sys.argv:
        print("Dry run mode - no changes will be made")
        return

    run_session_end()


if __name__ == "__main__":
    main()

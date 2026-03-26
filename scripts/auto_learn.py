#!/usr/bin/env python3
"""
Auto Learning - 从经历中自动提取学习模式
基于 ruflo ReasoningBank 设计，适配 opencode 本地使用
"""

import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

# 基础路径
MEMORY_DIR = Path(__file__).parent.parent / "memory"
EXPERIENCES_DIR = MEMORY_DIR / "experiences"

# 导入学习系统
sys.path.insert(0, str(Path(__file__).parent))
from self_learning import EWCLearning


class PatternExtractor:
    """模式提取器"""

    # 成功模式关键词
    SUCCESS_PATTERNS = [
        (r"(?:成功|完成|搞定|解决|实现|部署)(?:了)?(.{5,50})", "achievement"),
        (r"(?:学到|发现|记住|明白)(?:了)?(?:：|:)?(.{5,100})", "learning"),
        (r"(?:最佳实践|建议|推荐|注意)(?:：|:)?(.{5,100})", "best_practice"),
        (r"(?:设置|安装|配置)(?:好?了?)?(?:：|:)?(.{5,80})", "setup"),
        (r"(?:优化|改进|提升)(?:了)?(.{5,50})", "optimization"),
    ]

    # 失败模式关键词
    FAILURE_PATTERNS = [
        (r"(?:错误|失败|问题|bug|issue)(?:：|:)?(.{5,100})", "error"),
        (r"(?:原因|因为|由于|导致)(?:：|:)?(.{5,100})", "cause"),
        (r"(?:不要|避免|注意|小心)(?:：|:)?(.{5,100})", "warning"),
        (r"(?:坑|陷阱|踩过)(?:：|:)?(.{5,80})", "pitfall"),
    ]

    def extract_success_patterns(self, text: str) -> List[Tuple[str, str]]:
        """提取成功模式"""
        patterns = []
        for regex, category in self.SUCCESS_PATTERNS:
            matches = re.finditer(regex, text, re.IGNORECASE)
            for match in matches:
                content = match.group(1).strip()
                if len(content) > 5:
                    patterns.append((f"[{category}] {content}", "success"))
        return patterns

    def extract_failure_patterns(self, text: str) -> List[Tuple[str, str]]:
        """提取失败模式"""
        patterns = []
        for regex, category in self.FAILURE_PATTERNS:
            matches = re.finditer(regex, text, re.IGNORECASE)
            for match in matches:
                content = match.group(1).strip()
                if len(content) > 5:
                    patterns.append((f"[{category}] {content}", "failure"))
        return patterns

    def extract_all(self, text: str) -> List[Tuple[str, str]]:
        """提取所有模式"""
        return self.extract_success_patterns(text) + self.extract_failure_patterns(text)


class AutoLearner:
    """自动学习器"""

    def __init__(self):
        self.extractor = PatternExtractor()
        self.learner = EWCLearning()

    def process_file(self, file_path: Path, dry_run: bool = False) -> Dict:
        """处理单个文件"""
        if not file_path.exists():
            return {"error": f"File not found: {file_path}"}

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return {"error": f"Failed to read {file_path}: {e}"}

        patterns = self.extractor.extract_all(content)

        results = {
            "file": str(file_path),
            "patterns_found": len(patterns),
            "learned": 0,
            "skipped": 0,
        }

        if not dry_run:
            for pattern_content, outcome in patterns:
                self.learner.learn(pattern_content, outcome)
                results["learned"] += 1
        else:
            results["skipped"] = len(patterns)
            results["patterns"] = patterns

        return results

    def process_days(self, days: int = 1, dry_run: bool = False) -> List[Dict]:
        """处理最近 N 天的经历"""
        results = []
        today = datetime.now()

        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = EXPERIENCES_DIR / f"{date_str}.md"

            if file_path.exists():
                result = self.process_file(file_path, dry_run)
                results.append(result)

        return results

    def run(self, days: int = 1, dry_run: bool = False) -> Dict:
        """运行自动学习"""
        results = self.process_days(days, dry_run)

        summary = {
            "files_processed": len(results),
            "total_patterns": sum(r.get("patterns_found", 0) for r in results),
            "total_learned": sum(r.get("learned", 0) for r in results),
            "total_skipped": sum(r.get("skipped", 0) for r in results),
            "details": results,
        }

        # 运行整合
        if not dry_run:
            consolidation = self.learner.consolidate()
            summary["consolidation"] = consolidation

        return summary


def main():
    dry_run = False
    days = 1

    # 解析参数
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--dry-run":
            dry_run = True
            i += 1
        elif sys.argv[i] == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    learner = AutoLearner()
    summary = learner.run(days=days, dry_run=dry_run)

    print(f"Auto Learning {'(DRY RUN)' if dry_run else ''}")
    print(f"Files processed: {summary['files_processed']}")
    print(f"Patterns found: {summary['total_patterns']}")

    if dry_run:
        print(f"Would learn: {summary['total_skipped']} patterns")
        for detail in summary["details"]:
            if "patterns" in detail:
                print(f"\n{detail['file']}:")
                for content, outcome in detail["patterns"]:
                    print(f"  [{outcome}] {content[:80]}")
    else:
        print(f"Patterns learned: {summary['total_learned']}")
        if "consolidation" in summary:
            c = summary["consolidation"]
            print(f"\nConsolidation:")
            print(f"  Total patterns: {c['after']}")
            print(f"  Protected: {c['protected']}")
            print(f"  Success: {c['success_patterns']}")
            print(f"  Failure: {c['failure_patterns']}")


if __name__ == "__main__":
    main()

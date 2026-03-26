#!/bin/bash
# memory-sync.sh - 增量同步 memory/ 目录
# 用法: bash scripts/memory-sync.sh [commit message]

set -e
cd "$(git rev-parse --show-toplevel)"

MSG="${1:-sync: memory update}"

# 只暂存 memory/ 相关变更
git add memory/

# 检查是否有变更
if git diff --cached --quiet; then
    echo "memory/ 无变更，跳过"
    exit 0
fi

# 提交并推送
git commit -m "$MSG"
git push origin main

echo "memory/ 同步完成"

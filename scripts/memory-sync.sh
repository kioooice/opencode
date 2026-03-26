#!/bin/bash
# memory-sync.sh - 推送 memory/ 到远程
# 用法: bash scripts/memory-sync.sh [commit message]

set -e
cd "$(git rev-parse --show-toplevel)"

MSG="${1:-sync: memory update}"

# 检查是否有未解决的冲突
if git ls-files -u | grep -q .; then
    echo "错误：存在未解决的合并冲突，请先手动解决"
    git ls-files -u
    exit 1
fi

# 只暂存 memory/ 相关变更
git add memory/

# 检查是否有变更
if git diff --cached --quiet -- memory/; then
    echo "memory/ 无变更，跳过"
    exit 0
fi

# 提交并推送
git commit -m "$MSG"
git push origin main

echo "memory/ 已推送到远程"

#!/bin/bash
# setup.sh - 另一台电脑首次运行
# 用法: bash scripts/setup.sh

set -e
cd "$(git rev-parse --show-toplevel)"

echo "=== opencode 快速同步设置 ==="

# 1. 确保 git 配置正确
git config --local core.autocrlf input
git config --local core.compression 9
git config --local pack.compression 9

# 2. 确保 .gitattributes 生效
git checkout HEAD -- .gitattributes 2>/dev/null || true

# 3. 拉取最新 memory/
echo "拉取 memory/..."
git fetch origin main
git checkout origin/main -- memory/ .gitattributes scripts/

# 4. 创建必要目录
mkdir -p memory/.vectors memory/episodic/hot memory/episodic/warm memory/working memory/archive

echo ""
echo "=== 完成 ==="
echo "现在可以使用："
echo "  bash scripts/mem-pull.sh    - 拉取最新记忆"
echo "  bash scripts/memory-sync.sh - 推送记忆变更"
echo "  bash scripts/memory-sync.sh \"说明\" - 带说明推送"

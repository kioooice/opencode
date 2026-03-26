#!/bin/bash
# mem-pull.sh - 从远程拉取最新 memory/
# 换电脑时先执行这个

set -e
cd "$(git rev-parse --show-toplevel)"

echo "拉取远程变更..."
git fetch origin main

# 只合并 memory/ 目录的变更
echo "合并 memory/ 变更..."
git checkout origin/main -- memory/

echo "memory/ 已同步到最新"

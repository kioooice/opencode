#!/bin/bash
# mem-pull.sh - 从远程拉取 memory/，自动处理冲突
# 策略：冲突文件保留两边内容，人工后续整理

set -e
cd "$(git rev-parse --show-toplevel)"

echo "=== memory/ 双向同步 ==="

# 1. 暂存本地未提交的 memory 变更
git add memory/

# 2. 如果有本地变更，先提交
if ! git diff --cached --quiet -- memory/; then
    echo "提交本地 memory 变更..."
    git commit -m "sync: local memory before pull"
fi

# 3. 拉取远程
echo "拉取远程..."
git fetch origin main

# 4. 检查是否有冲突
MERGE_BASE=$(git merge-base HEAD origin/main)
REMOTE_TREE=$(git rev-parse origin/main:memory/ 2>/dev/null || echo "")
LOCAL_TREE=$(git rev-parse HEAD:memory/ 2>/dev/null || echo "")

if [ "$REMOTE_TREE" = "$LOCAL_TREE" ]; then
    echo "无冲突，已是最新"
    exit 0
fi

# 5. 尝试合并，检测冲突
echo "合并远程 memory/..."
if git merge origin/main --no-edit -m "merge: memory sync" 2>/dev/null; then
    echo "=== 合并成功，无冲突 ==="
    exit 0
fi

# 6. 有冲突，处理冲突文件
echo ""
echo "=== 检测到冲突，自动保留两边内容 ==="
echo ""

CONFLICTS=$(git diff --name-only --diff-filter=U -- memory/)
CONFLICT_COUNT=0

for file in $CONFLICTS; do
    CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
    echo "处理冲突: $file"

    # 保存远程版本
    REMOTE_VER=$(git show "origin/main:$file" 2>/dev/null || echo "")
    LOCAL_VER=$(git show "HEAD:$file" 2>/dev/null || echo "")

    # 合并策略：本地在前，远程在后，用分隔符标记
    MERGED="$LOCAL_VER

---
## [冲突合并] 远程版本 ($(date +%Y-%m-%d\ %H:%M))
---

$REMOTE_VER"

    # 写入合并后的内容
    echo "$MERGED" > "$file"

    git add "$file"
done

# 7. 完成合并
git commit --no-edit -m "merge: 解决 memory/ 冲突 ($CONFLICT_COUNT 个文件)"

echo ""
echo "=== 完成 ==="
echo "冲突文件已保留两边内容，请手动整理以下文件："
for file in $CONFLICTS; do
    echo "  - $file"
done

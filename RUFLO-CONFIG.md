# Ruflo 参考配置

Python 脚本是独立工具，命令行直接调用，不依赖 opencode 配置。

## 向量记忆系统

```bash
PY="/c/Users/Administrator/AppData/Local/Programs/Python/Python314/python.exe"
$PY scripts/vector_memory.py index          # 索引 memory/ 目录
$PY scripts/vector_memory.py search "查询"   # 语义搜索
$PY scripts/vector_memory.py store "key" "value" "namespace"  # 存储
$PY scripts/vector_memory.py status         # 查看状态
```

## 自学习系统（EWC++）

```bash
PY="/c/Users/Administrator/AppData/Local/Programs/Python/Python314/python.exe"
$PY scripts/self_learning.py learn "模式" success   # 学习成功模式
$PY scripts/self_learning.py learn "模式" failure   # 学习失败教训
$PY scripts/self_learning.py patterns               # 查看所有模式
$PY scripts/self_learning.py consolidate            # 整合（衰减+清理）
$PY scripts/self_learning.py stats                  # 统计
```

## 自动学习

```bash
PY="/c/Users/Administrator/AppData/Local/Programs/Python/Python314/python.exe"
$PY scripts/auto_learn.py              # 从今天经历学习
$PY scripts/auto_learn.py --days 3     # 从近 3 天学习
$PY scripts/auto_learn.py --dry-run    # 预览不执行
$PY scripts/session_end_hook.py        # 会话结束自动处理
```

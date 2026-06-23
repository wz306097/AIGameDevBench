# Benchmark Testcases

每个子目录是一个 testcase:在一个游戏 repo 的某个基线 commit 上,给 AI 一个任务,
用一个**冻结的黄金验证器**给结果打分。设计目标:不动手必须 0 分,正确改动满分。

## 目录格式

```
bench-0001-attack-buff/
  testcase.toml        # 必需:manifest
  expected.json        # py_config 用
  expected_delta.json  # py_tscn_diff 用(配 baseline/<scene>.tscn)
  arch_rules.json      # py_gdscript_ast 用
  verifier.gd          # godot_scenetree / visual_static / interaction_routing 用
  fix.diff             # 可选:已知正确改动,用于自测验证器
```

### testcase.toml

```toml
[testcase]
id = "bench-0001-attack-buff"
category = "intent_translation"   # 见下方五类
baseline_ref = "<源 repo 的 commit SHA>"   # runner 用 git worktree checkout 这个点
source_repo = "godot-creature-sim"          # 可选,仅记录
task = "用自然语言写清要 AI 做什么"

[verifier]
type = "py_config"     # 见下方验证器类型
entry = "expected.json"

[scoring]
mode = "fields"        # checkpoints | fields | tristate | weighted
```

### 五个 category

| category | 含义 | 典型验证器 |
|---|---|---|
| `behavior_logic` | 运行时行为对不对 | `godot_scenetree` |
| `intent_translation` | 把自然语言意图翻成正确数值/配置 | `py_config` |
| `precise_edit` | 精确改动且无副作用 | `py_tscn_diff` |
| `architecture` | 代码结构/依赖约束 | `py_gdscript_ast` |
| `visual_audio` | 视觉/布局 | `visual_static` |

### 六个验证器类型

**纯 Python(无需 Godot)**
- `py_config` — 读 `expected.json`,在 `files_glob` 命中的配置里按 `aliases` 找字段,
  比对 `expected`(数值用 `tol`)。`must_differ_from_base=true` 时,值等于 `base` 判失败
  (防止"照抄基线"骗分)。
- `py_tscn_diff` — 读 `expected_delta.json` + `baseline/<scene>.tscn`,对比工作区场景的
  增删节点/改属性。三态打分:缺意图改动→fail,有意图但有副作用→partial,干净命中→pass。
- `py_gdscript_ast` — 读 `arch_rules.json`,对 `target_files` 跑规则
  (`forbid_import_glob` / `forbid_hardcoded_res_path` / `require_extends`),
  每违反一条扣 `weight`,score = max(0, 100 - 扣分)/100。

**需要 Godot 在 PATH 上**
- `godot_scenetree` / `visual_static` / `interaction_routing` — 把 `verifier.gd`
  (`extends SceneTree`)注入工作区跑 headless,脚本 print 出
  `{"assertions":[{"name","pass"}]}`,据此打分,跑完删除临时脚本。

## 怎么跑

> runner 用 `git worktree` checkout `baseline_ref`,所以**必须在目标游戏 repo 内执行**。

```bash
TCDIR='C:\path\to\testcases'   # Windows 原生路径;git-bash 的 /c/... 会被 Click 判为不存在

# 列出
aigdbench list --testcases-dir "$TCDIR"

# 基线对照:noop 什么都不改 -> 必须 fail / 0.00
aigdbench run --testcases-dir "$TCDIR" --testcase bench-0001-attack-buff --driver noop

# 回放正确改动:patch 应用 fix.diff -> pass / 1.00
aigdbench run --testcases-dir "$TCDIR" --testcase bench-0001-attack-buff \
  --driver patch --patch bench-0001-attack-buff/fix.diff
```

测真实 AI:让它在 `baseline_ref` 状态完成 `task` → `git diff > ai.diff` →
`--driver patch --patch ai.diff` 出分(真实 harness driver 是后续工作)。

## 示例:bench-0001-attack-buff

`intent_translation` + `py_config`,纯 Python 可跑。任务是"精英怪攻击力比基础 50 高 20%",
黄金答案 60。最小 demo repo(`data/elite.json` 里 `attack:50`)实跑结果:

| driver | status | score |
|---|---|---|
| noop | fail | 0.00 |
| patch (fix.diff) | pass | 1.00 |

## 注意

- 入口脚本 `aigdbench` 若不在 PATH,用
  `python -c "from aigamedevbench.cli import main; main([...])"` 调。
- `--testcases-dir` 传 Windows 原生路径(`C:\...`)。

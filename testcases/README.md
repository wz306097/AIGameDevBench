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

执行起点取决于 testcase 的 `source_kind`:

- `folder` 型(从 GameDevBench 导入的 `gdb-task_*`):**自包含,任意目录都能跑**。runner
  把 `baseline/` 拷进临时区、`git init`,资源导入(`godot --import`)由 runner 自动完成。
- `git` 型:runner 用 `git worktree` checkout `baseline_ref`,所以**必须在目标游戏 repo 内执行**。

需要 Godot 的验证器(`godot_scene_assert` 等)要求 `godot` 在 PATH 上(或用 `--godot-binary` 指定)。

```bash
TCDIR='C:\Users\WinterZhao\Codes\AIGameDevBench\testcases'   # Windows 原生路径;git-bash 的 /c/... 会被 Click 判为不存在

# 列出
aigdbench list --testcases-dir "$TCDIR"

# 基线对照:noop 什么都不改 -> 必须 fail / 0.00
aigdbench run --testcases-dir "$TCDIR" --testcase gdb-task_0002 --driver noop

# 回放正确改动:patch 应用 fix.diff -> pass / 1.00
aigdbench run --testcases-dir "$TCDIR" --testcase gdb-task_0002 \
  --driver patch --patch testcases/gdb-task_0002/fix.diff
```

### 三种 driver

| `--driver` | 作用 | 必带参数 |
|---|---|---|
| `noop` | 什么都不改,基线对照(应得 0) | — |
| `patch` | 应用一个现成的 diff(回放正确改动或离线评一个 AI 的产出) | `--patch <file>` |
| `command` | 在工作区内调用任意命令行 harness 现场完成任务 | `--harness-cmd '<模板>'` |

`--driver command` 用占位符把任务交给 harness:`{task}`(任务原文,单参数)、
`{task_file}`(工作区里的 `TASK.md` 路径)、`{workspace}`(工作区路径)。命令模板用
`shlex` 切分,**不经过 shell**(无注入风险),Windows 路径用正斜杠。例如:

```bash
aigdbench run --testcases-dir "$TCDIR" --testcase gdb-task_0002 \
  --driver command --harness-cmd 'codex exec --cd {workspace} {task}' \
  --timeout 600 --log-dir harness-logs --report report.json
```

> harness **不要 commit** 自己的改动:runner 用 `git status --porcelain` 检测变化,
> 一旦 commit,工作区就"干净"了 → 检测不到改动 → 0 分。改完留在工作区即可。

离线评一个 AI:让它在起点状态完成 `task` → `git diff > ai.diff` →
`--driver patch --patch ai.diff` 出分。

## 示例:gdb-task_0002

`behavior_logic` + `godot_scene_assert`,folder 型(自包含,需要 Godot)。任务是让子弹
命中敌人时推进任务、命中后自我移除、离屏 50 像素自我移除。verifier 逐 checkpoint 打分
(4 个断言)。实跑结果:

| driver | status | score |
|---|---|---|
| noop | fail | 0.00 |
| patch (fix.diff) | pass | 1.00 |

## 注意

- 入口脚本 `aigdbench` 若不在 PATH,用
  `python -c "from aigamedevbench.cli import main; main()"` 后接同样的子命令/参数调用,
  或先 `pip install -e .`。
- `--testcases-dir` 传 Windows 原生路径(`C:\...`),不要用 git-bash 的 `/c/...`。

## 两种起点形态(source_kind)

| source_kind | 起点 | 谁用 |
|---|---|---|
| `git`(默认) | 源 repo 的一个 commit,runner 用 `git worktree` checkout | 原生 testcase,必须在目标游戏 repo 内跑 |
| `folder` | testcase 自带的 `baseline/` 子目录(自包含 Godot 项目),runner 拷进临时区并 `git init` | 从 GameDevBench 导入的任务,可独立跑(无需在游戏 repo 内) |

## 从 GameDevBench 导入任务(folder + godot_scene_assert)

GameDevBench 每个 task 是自包含项目 + 一个黄金验证器(`scenes/test.tscn` + `scripts/test.gd`,
打印 `VALIDATION_PASSED/FAILED`)。导入脚本把它转成本仓的 folder-type testcase:

```
gdb-task_0002/
  testcase.toml          # source_kind="folder", verifier.type="godot_scene_assert"
  baseline/              # 起点项目(已剔除 test.* / .godot / 嵌套重复目录 / 泄答案的 *.md+task_config.json)
  verifier_scene.tscn    # 由 test.tscn 改来,脚本路径换成占位符 __VERIFIER_GD__
  verifier.gd            # 由 test.gd 转译:extends Node,逐 checkpoint 打印 {"assertions":[...]}
  fix.diff               # baseline → ground-truth 的 diff,自测用
```

**为什么 verifier 走场景模式而非 `--script`**:被测代码常用 autoload 单例全局名
(如 `QuestManager.progress_quest(...)`)。`--script`(`extends SceneTree`)模式下 autoload
不加载,全局名无法解析。`godot_scene_assert` 用 `godot --headless --path <ws> <scene>` 跑场景,
让 autoload 生效。

导入:

```bash
python scripts/import_gamedevbench.py --gdb ../GameDevBench --out testcases --tasks task_0002 task_0003
```

脚本会跳过 `requires_display` 任务(首批只接 headless 可验证的纯代码/gameplay 逻辑)。
`test.gd → verifier.gd` 默认产单 checkpoint 兜底;要逐断言部分得分需手工拆分
(见 `gdb-task_0002/verifier.gd` 的多 checkpoint 范例)。

> 注意:GameDevBench 的起点 task 可能本身是"部分错误的实现",baseline 已满足了某些
> checkpoint(如 task_0002 原本已有离屏移除 + UI label),导致 `noop` 在 checkpoints 模式下
> 不是干净的 0 分。**两条硬不变量:`noop → 0.00` 且 `patch fix.diff → 1.00`**。导入后务必
> 两个都自测;若 noop 非 0,需把那些非区分性行为从 baseline 移除、并相应重生 `fix.diff`
> (gdb-task_0002 即按此修正:删掉 baseline 的离屏块 + 去掉 UI label checkpoint)。

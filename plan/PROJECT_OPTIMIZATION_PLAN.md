# TRPGdice-Complete 项目优化方案

最后更新：2026-05-10

本文档说明我建议如何继续优化整个项目。它不是单次改动清单，而是后续几轮开发的路线图。目标是：在不破坏现有功能的前提下，让插件主体和 `log-painter` 都变得更清晰、可验证、可维护、方便继续加功能。

## 一、总体目标

### 1. 稳定优先

这个项目已经有不少可用功能，尤其是骰点、角色卡、日志、log-painter 之间已经形成了实际工作流。因此后续优化不能以“重写”为主，而应该以“小步收口”为主：

- 每次只改一个明确边界。
- 每次改完都能验证。
- 每次都记录到 `diff/`。
- 不删除现有功能。
- 不做无法回滚的大范围格式化。

### 2. 降低 `main.py` 负担

`main.py` 仍然承担过多职责：

- AstrBot 命令注册。
- 命令参数拆解。
- 业务流程编排。
- 消息发送。
- 日志记录。
- 部分角色卡逻辑。
- 部分 CoC 检定逻辑。

最终目标不是让 `main.py` 消失，而是让它变成“命令入口和编排层”。真正的业务规则应该在 `component/` 下。

### 3. 让数据结构显式化

目前很多功能靠文本拼接和临时字段工作。例如检定结果、日志消息、角色卡属性、OB 标记、log-painter 的 `LogItem` 都有类似问题。

后续应逐步引入明确的数据对象：

- 检定结果对象。
- 日志消息对象。
- 角色卡对象。
- 预览项对象。
- 导入/导出格式对象。

这样日志统计、log-painter 过滤、对抗检定、角色卡导入导出都会更容易做。

### 4. 保持 AstrBot 插件框架兼容

所有重构都应尊重 AstrBot 插件结构：

- `main.py` 保留插件注册和命令入口。
- 命令函数保持异步行为。
- 不破坏 `filter.command`、`command_group`、`event_message_type` 的使用方式。
- 不引入复杂运行时依赖。

## 二、当前项目分区

### 插件主体

当前较清晰的结构已经初步建立：

- `component/roll/`
  - 掷骰表达式、命令解析、骰点执行。
- `component/coc/`
  - CoC 规则、SAN、检定扩展入口。
- `component/pc/`
  - 角色卡存储、展示、名片、模板。
- `component/logs/`
  - 日志存储、导出、统计、OB 标记。
- `component/combat/`
  - 先攻管理。
- `component/common/`
  - 输出、通用工具。

这条路是对的。后续应该继续沿着这个方向拆，而不是再把逻辑塞回 `main.py`。

### log-painter

`log-painter` 目前风险更高。它的问题不是“某几个 bug”，而是整体边界混乱：

- `main.vue` 和 `template.vue` 两个超大组件高度重复。
- 解析、预览、导出、角色管理、颜色管理全部混在 Vue 文件里。
- importer 架构存在但基本未启用。
- JSON 会先转为文本，再重新解析。
- 类型定义跟实际字段脱节。

所以 `log-painter` 不应直接大拆。它需要先建立安全验证，再逐步收口数据流。

## 三、总体优化原则

### 1. 先文档，后代码

对高风险区域，先写清楚：

- 现状。
- 数据流。
- 依赖关系。
- 风险点。
- 验收方式。

已经有：

- `TODO_MD.md`
- `LOG_PAINTER_AUDIT.md`

后续如果要动大模块，最好也先写局部设计文档。

### 2. 先边界，后抽象

不要为了“好看”提前抽象。只有当一段逻辑已经有明确职责时才抽出模块。

例如：

- 日志统计已经可以抽成 `component/logs/stats.py`。
- 群名片格式已经可以抽成 `component/pc/nick.py`。
- log-painter 的 JSON 加载可以先抽成 loader，再考虑 importer 架构。

### 3. 先验证，后重构

每一阶段至少要有一种验证：

- Python：`python -m compileall -q main.py component`
- 解析器：小型 smoke test。
- 日志：构造临时日志会话测试。
- 前端：`npm run build` 或至少 `vue-tsc`。
- log-painter：手动用样例日志打开页面验证。

### 4. 不碰无关功能

当前用户要求的核心范围是：

- CoC。
- Log。
- 角色卡。
- log-painter。

DND、牌堆、自定义回复、机器人管理等先不主动整理。

## 四、阶段计划

## 阶段 0：建立安全网

### 目标

在继续改代码前，先确保每次改动都能被快速验证。

### 要做的事

1. 建立样例数据目录，例如：
   - `tests/fixtures/logs/`
   - `tests/fixtures/cards/`

2. 准备样例日志：
   - 普通对话日志。
   - 包含骰点的日志。
   - 包含图片的日志。
   - 包含 OB 的日志。
   - 包含 SAN 变化的日志。

3. 建立最小 Python smoke tests：
   - 命令解析。
   - 日志创建/暂停/恢复/导出。
   - OB toggle。
   - 角色卡读写。

4. 为 log-painter 准备手动验收清单：
   - 页面能打开。
   - `?file=xxx.json` 能加载。
   - 角色列表正确。
   - 图片能显示/隐藏。
   - OB 能识别。
   - Word 导出不崩。

### 验收标准

- 能一条命令跑 Python 基础检查。
- 至少有 3 份固定样例日志。
- 每次改动前后都能用同一批样例验证。

## 阶段 1：继续瘦身插件主体

### 目标

让 `main.py` 进一步变成命令入口，把业务规则迁移到 `component/`。

### 要做的事

1. 抽出消息发送辅助函数。

当前多个函数手写：

- reply。
- at。
- send_group_msg。
- send_private_msg。
- save_log。

建议新增：

- `component/common/messaging.py`

负责：

- 构造群回复。
- 构造私聊。
- 统一保存骰点日志。

2. 抽出 CoC 检定服务。

建议新增：

- `component/coc/check_service.py`

负责：

- `.ra` / `.rc` 统一入口。
- 技能值解析。
- 难度修正。
- 奖惩骰。
- 暗骰。
- 对抗。

`main.py` 只负责拿 event、调用 service、发消息。

3. 抽出日志命令服务。

建议新增：

- `component/logs/commands.py` 或 `component/logs/service.py`

负责：

- log new/on/off/end/get/export/stat。
- ob add/del/list/clear/toggle。

4. 抽出角色卡命令服务。

建议新增：

- `component/pc/service.py`

负责：

- `.pc` 系列。
- `.st` 系列。
- `.sn` 系列。

这一步不要一次性做完，可以先从 `.sn`、`.st show`、`.pc show` 这种低风险展示逻辑开始。

### 验收标准

- `main.py` 行数下降。
- 命令行为不变。
- `python -m compileall -q main.py component` 通过。
- 关键命令 smoke test 通过。

## 阶段 2：补齐 CoC 规则能力

### 目标

让 CoC 功能从“能用”变成“语义明确、可扩展”。

### 要做的事

1. 明确 `.ra` 与 `.rc` 差异。

当前 `.rc` 只是入口，实际仍接近 `.ra`。需要明确：

- `.ra` 是房规检定。
- `.rc` 是规则书检定。
- 大成功/大失败规则如何不同。
- 奖惩骰是否一致。
- 成功等级如何计算。

2. 结构化检定结果。

建议定义：

- `CheckResult`
- `RollDetail`
- `SuccessLevel`

这样日志统计可以直接统计成功/失败，而不是从文本里猜。

3. 完善对抗检定。

当前 `.rav/.rcv` 是基础版。后续应支持：

- `@目标`。
- 双方从角色卡取技能值。
- 双方不同技能。
- 平局规则配置。
- 对抗结果结构化。

4. 完善暗骰。

当前暗骰结果发给发起者。后续应支持：

- 发给 KP。
- 发给指定 QQ。
- 群内只提示“已暗骰”。
- 日志中记录是否公开。

5. SAN 流程增强。

建议逐步实现：

- 大额 SAN 损失自动提示临时疯狂。
- 可选自动执行 `.ti`。
- 记录疯狂状态。
- 在日志中记录 SAN 变化。

### 验收标准

- `.ra` 和 `.rc` 行为差异有文档。
- 检定结果可被日志统计使用。
- 对抗检定支持至少一种 @ 目标形式。

## 阶段 3：角色卡管理增强

### 目标

让角色卡从“JSON 存储 + 命令修改”升级为“可导入、可同步、可恢复”的角色卡系统。

### 要做的事

1. 拆分 `component/pc/store.py`。

当前 `store.py` 仍有较多职责：

- 文件路径。
- 绑定。
- 读写。
- 同义词同步。
- 派生属性。
- 跨群同步。
- 成长。

建议拆成：

- `paths.py`
- `binding.py`
- `repository.py`
- `sync.py`
- `derived.py`
- `growth.py`
- `importers/`
- `exporters/`

2. 支持更宽松 `.st` 输入。

优先支持：

- `.st 属性=值`
- `.st 属性:值`
- `.st 属性 值`
- `.st <角色名>-属性值...`

3. 模板一键录入。

当前 `.st 模板` 只输出模板。下一步应支持：

- 用户复制模板。
- 填数值。
- 一次性录入。

4. 角色卡导入导出。

优先级：

- 当前 JSON。
- 纯文本卡。
- 海豹格式。
- Dice! 格式。

5. 名片系统完善。

当前 `.sn coc/cocL/none/off` 是基础版。后续：

- `.sn expr <表达式>`。
- `.sn off` 持久关闭自动名片更新。
- `.sn mode <模式>` 持久化默认模式。

6. 备份恢复。

建议新增：

- `.pc backup`
- `.pc restore`
- 自动保存历史版本。

### 验收标准

- `store.py` 职责明显减少。
- 角色卡读写行为不变。
- 至少支持一种外部格式导入。
- `.st` 新格式有 smoke test。

## 阶段 4：日志系统增强

### 目标

让日志系统从“记录消息”升级为“可统计、可管理、可导出”的日志系统。

### 要做的事

1. 清理测试分支。

`component/logs/store.py` 中仍存在特殊群号逻辑。应改为：

- 测试 fixture。
- 或配置项。
- 或直接删除。

2. 扩展统计。

依赖结构化检定结果后，可以统计：

- 成功/失败次数。
- 大成功/大失败次数。
- 技能使用次数。
- SAN 损失。
- HP/SAN/MP 变化。
- 发言排行。
- OB 发言数。

3. 日志权限。

需要设计：

- 谁能开始/结束日志。
- 谁能删除日志。
- 谁能导出日志。
- KP/管理员如何识别。

4. 文件发送和分享。

`.log export` 目前只返回文件名。后续可以：

- 直接发送文件。
- 返回下载 URL。
- 上传到公共染色器。
- 生成永久分享链接。

5. 日志管理后台。

后续可以做 Web 管理：

- 按群查看日志。
- 搜索。
- 删除。
- 导出。
- 修复损坏日志。

### 验收标准

- 日志特殊测试分支清理。
- `.log stat` 有更多结构化统计。
- 权限策略写入文档并实现基础检查。

## 阶段 5：log-painter 安全收口

### 目标

不大拆页面，先让数据流可控、字段不丢、功能可验证。

### 要做的事

1. 建立 log-painter 样例和验收。

样例至少包括：

- 标准插件 JSON。
- 图片。
- OB。
- 骰点。
- 场外发言。

2. 修后端配置。

当前缺少 `backend/config.yaml`。建议：

- 提供 `config.example.yaml`。
- 如果没有配置，默认指向插件导出目录。
- 启动时输出清晰错误。

3. 清理无效 router。

`router/index.ts` 指向不存在的 `JsonEditor.vue`。需要确认：

- 如果不用 router，删除或归档。
- 如果要用 router，补齐入口。

4. 补齐类型。

先只补类型，不改行为：

- `LogItem.images`
- `LogItem.date`
- `LogItem.time`
- `LogItem.is_comment`
- `LogItem.isObserver`
- `LogItem.role`
- `LogItem.messageSanitized`
- `LogItem.who`

5. 抽出 JSON 加载。

从 `main.vue` 抽：

- `src/logManager/loaders/pluginJsonLoader.ts`

目标：

- 请求文件。
- 校验格式。
- 标准化字段。
- 保留结构化信息。

6. 抽出预览构建。

从 `main.vue` / `template.vue` 抽：

- `src/logManager/preview/buildPreviewItems.ts`

目标：

- 统一图片处理。
- 统一场外过滤。
- 统一命令过滤。
- 统一 OB 过滤。
- 统一 @ 替换。

7. 实现 OB 过滤 UI。

加一个开关：

- 隐藏 OB 发言。

并让预览和导出共用同一过滤逻辑。

8. 确认 `template.vue` 用途。

如果不用：

- 标记 legacy。
- 不再维护。
- 后续删除。

如果用：

- 抽共享 composable，避免双份逻辑继续分裂。

9. 恢复 importer 架构。

先实现：

- plugin JSON importer。
- edit log importer。

再考虑：

- QQ export。
- SealDice。
- FVTT。

未实现的 importer 不应该静默返回空，应明确报“不支持”。

### 验收标准

- `npm run build` 通过。
- 样例 JSON 能加载。
- OB 过滤可用。
- 图片显示/隐藏可用。
- `main.vue` 行数开始下降。
- `template.vue` 是否使用有明确结论。

## 阶段 6：逐步清理中文乱码和文案

### 目标

不是盲目转码，而是让用户可见文案、注释、配置逐步恢复正常。

### 要做的事

1. 优先修用户可见文案。

- `component/config.yaml`
- 帮助文本。
- 错误提示。
- log-painter UI 标签。

2. 再修注释。

只在改到对应模块时顺手修，不单独做全项目注释清洗。

3. 避免全文件重编码。

之前检查结果是 UTF-8 可读，很多乱码来自历史文本内容或 PowerShell 显示问题。不要做不可控的批量转码。

### 验收标准

- 用户看到的命令输出不乱码。
- log-painter 页面主要按钮不乱码。
- 不引入 YAML 解析错误。

## 五、建议的近期执行顺序

我建议接下来按这个顺序做：

1. 为 log-painter 准备样例日志和验收清单。
2. 实现 log-painter 的 OB 过滤开关。
3. 修复 log-painter 后端配置缺失问题。
4. 补齐 `LogItem` 类型。
5. 抽出插件 JSON loader。
6. 抽出预览构建函数。
7. 回到插件主体，拆 CoC 检定 service。
8. 明确 `.ra` / `.rc` 规则差异。
9. 改进 `.st` 录入格式。
10. 扩展 `.log stat`。

这个顺序的理由是：

- log-painter 当前最脆，先补安全网和最小功能。
- OB 刚在插件侧实现，马上在 log-painter 侧闭环收益最高。
- JSON loader 和 preview builder 是后续拆大组件的前置条件。
- CoC 和角色卡的增强依赖结构化结果，放在日志链路收口之后更稳。

## 六、哪些事暂时不要做

短期不建议：

- 一次性重写 log-painter。
- 一次性删除 `template.vue`。
- 一次性把 store 改成 Pinia。
- 一次性重写所有 importer。
- 全项目批量格式化。
- 全项目批量“修乱码”。
- 在没有样例日志的情况下重构预览和导出。

## 七、每次改动的固定流程

后续每次动代码建议固定这样做：

1. 说明本轮只改什么。
2. 先读相关文件。
3. 小范围修改。
4. 运行对应验证。
5. 更新 `TODO_MD.md` 或相关文档。
6. 写入 `diff/` 日志。
7. 汇报：
   - 改了什么。
   - 没改什么。
   - 怎么验证。
   - 剩余风险。

## 八、判断成功的标准

长期来看，优化成功不是“文件看起来漂亮”，而是这些指标改善：

- `main.py` 行数明显下降。
- `component/` 每个模块职责清楚。
- 新增命令不需要大量修改 `main.py`。
- log-painter 不再通过大组件维护所有逻辑。
- 插件 JSON 字段能稳定传到预览和导出。
- OB、图片、骰点、场外发言等过滤逻辑统一。
- 常见功能有 smoke test 或样例验收。
- 用户可见文案基本无乱码。

这套方案的核心是：先把系统变得可验证，再让它变得好看。否则在当前状态下直接大拆，很容易把能用的功能拆坏。

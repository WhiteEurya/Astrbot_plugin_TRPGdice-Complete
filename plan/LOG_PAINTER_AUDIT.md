# Log Painter Audit

最后更新：2026-05-10

本文档是 `log-painter` 的只读审计结果，用于后续重构和补功能前建立安全边界。本轮没有改动业务代码。

## 总体判断

`log-painter` 目前属于“功能可以跑一部分，但结构高度脆弱”的状态。真正高风险不在单个函数写得复杂，而在几个问题叠加：

- 两个超大 Vue 单文件组件承担了几乎全部 UI、解析、预览、导出、角色管理逻辑。
- `main.vue` 和 `template.vue` 近似重复，但能力不完全一致，后续修 bug 很容易只修一份。
- `logManager/importers/` 目录里多数 importer 是占位实现，但主流程又没有真正使用这些 importer。
- 数据结构主要靠 `any`、运行时补字段和字符串约定维持。
- 后端、前端路由、导出目录配置存在明显未收口问题。
- 当前缺少自动化验证，任何改动都需要手动打开页面测试。

结论：不建议直接“大重构”。应先补测试/样例、收口数据流，再做小步拆分。

## 项目结构

### 后端

- `log-painter/backend/main.py`
  - FastAPI 服务。
  - 提供 `/export` 和 `/export/{file_name}`。
  - 只负责返回 JSON 文件或空 JSON。

- `log-painter/backend/config.py`
  - 读取 `log-painter/backend/config.yaml`。
  - 当前仓库中未发现 `config.yaml`，因此后端直接启动大概率会失败。

### 前端入口

- `log-painter/frontend/src/main.ts`
  - 创建 Vue app。
  - 注册 Naive UI 组件。

- `log-painter/frontend/src/App.vue`
  - 直接渲染 `components/main.vue`。
  - 没有使用 router-view。

- `log-painter/frontend/src/router/index.ts`
  - 指向 `@/components/JsonEditor.vue`。
  - 当前未发现 `JsonEditor.vue`。
  - 该 router 目前看起来没有被 `main.ts` 挂载，属于残留或未完成代码。

### 前端核心文件

- `components/main.vue`
  - 约 1633 行。
  - 当前实际入口。
  - 同时负责 UI 布局、URL 加载、日志解析触发、角色列表、颜色、预览、导出、过滤器、Word 导出等。

- `components/template.vue`
  - 约 1601 行。
  - 与 `main.vue` 高度相似。
  - 有一些 `main.vue` 没有或实现不同的导出函数。
  - 当前未确认是否仍被实际使用。

- `logManager/logManager.ts`
  - 当前解析核心。
  - 直接内置 QQ 风格日志解析。
  - `importers` 数组保留为空，外部 importer 基本未进入主流程。

- `utils/index.ts`
  - 消息格式化工具。
  - 包含图片处理、场外过滤、命令过滤、ID 处理、@ 替换、HTML 转义。

- `store.ts`
  - 伪 store / 轻量 reactive 状态。
  - 不是 Pinia，但部分代码仍按 Pinia 风格兼容。

## 当前数据流

### 从插件导出 JSON 到前端

1. 插件 `.log end` 或 `.log get` 导出 JSON 到 `data/group_logs/exports/`。
2. 插件返回 URL，通常形如 `/?file=<group>_<session>.json`。
3. 前端 `main.vue` 在 `onMounted()` 读取 URL 参数 `file`。
4. `loadJsonFile(fileName)` 请求 `/export/{fileName}`。
5. Vite dev server 通过 `/export` proxy 转发到 FastAPI。
6. FastAPI 从 `EXPORT_ROOT` 读取 JSON 文件。
7. 前端把 JSON items 转换成“QQ 两行日志文本”。
8. 转换后的文本写入 `text.value`。
9. `watch(text)` 触发 `logMan.syncChange()`。
10. `logManager.parse()` 再把文本解析回 `LogItem[]`。
11. `buildPcList()` 从 `LogItem[]` 构建左侧角色列表。
12. `showPreview()` / `getPreviewText()` 生成预览数据。

### 关键问题

这一链路有一次明显的“JSON -> 文本 -> 再解析回 JSON-like item”的绕路。它能兼容手工编辑文本，但也导致：

- 插件导出的结构化字段可能丢失或变形。
- `isDice`、`isObserver`、`role`、`images` 等字段需要在多处手工转存。
- 后续扩展字段会很容易漏传。
- 解析和预览之间的职责边界不清楚。

## 已实现能力

- 读取 URL 参数中的 JSON 文件。
- 从 FastAPI `/export/{file}` 加载日志。
- 将插件 JSON 转为聊天文本。
- 实时解析编辑器文本。
- 生成角色列表。
- 角色颜色分配和预览染色。
- 基础预览。
- BBS/TRG 预览入口存在，但目前更像调试视图。
- 过滤表情/图片、场外发言、具体时间、日期、账号等选项。
- 下载原始文本。
- Word 导出逻辑存在。
- CodeMirror 编辑器封装。
- 图片 URL 拼接到消息后。
- 初步识别 OB 字段，并可把角色 role 标成 `OB`。

## 明显未完成或疑似失效功能

### 后端启动配置

- `backend/config.py` 强依赖 `backend/config.yaml`。
- 当前仓库未发现该文件。
- 如果没有外部部署时补这个文件，FastAPI 后端会启动失败。

### Router 残留

- `router/index.ts` 引用 `@/components/JsonEditor.vue`。
- 当前未发现该文件。
- `main.ts` 也未挂载 router。
- 这块应确认是废弃代码还是未来入口。

### Importer 系统基本未启用

- `logManager.importers = []`。
- `QQExportLogImporter`、`SealDiceLogImporter`、`FvttLogImporter`、`DiceKokonaLogImporter`、`RenderedLogImporter`、`SinaNyaLogImporter` 都是 `check() => false`、返回空 items。
- `EditLogImporter` 有实际实现，但主流程不是通过统一 importer 管线调用。

### Exporter 系统不完整

- `utils/exporter.ts` 中 `exportFileQQ()`、`exportFileIRC()` 是空函数。
- `EditLogExporter` 只能导出 `<nickname> message` 这种编辑文本。
- Word 导出逻辑主要散落在 `main.vue` / `template.vue`。

### `main.vue` / `template.vue` 重复

- 两个文件都超过 1600 行。
- 大量函数名和逻辑重复：`buildPcList`、`loadJsonFile`、`showPreview`、颜色逻辑、角色重命名、导出相关。
- 两者导出能力不完全一致。
- 很容易出现“一个页面修了，另一个没修”的问题。

### 类型系统基本失效

- 大量 `(it as any)`、`any`、`@ts-ignore`。
- `LogItem` 实际运行字段远多于类型定义，例如 `date`、`time`、`role`、`is_comment`、`images`、`messageSanitized`、`who`。
- `CharItem.role` 之前是固定联合类型，现在为了 OB 放宽成 `string`，说明角色枚举需要正式设计。

### 调试代码未清理

- `main.vue` / `template.vue` 中存在大量 `console.log`、`console.warn`、`console.error`。
- 包括 `[TEST] 请求 JSON`、`[parsed] rebuild pcList`、`curItems` 等调试输出。

### OB 功能只完成数据标记

- 后端导出的 JSON 已有 `isObserver` / `observer` / `role: OB`。
- 前端角色列表可标出 `OB`。
- 但 UI 中还没有明确的“隐藏 OB 发言”开关。
- 预览过滤函数还没有统一使用 `isObserver`。

### 图片处理不完整

- `msgImageFormat(item, options, htmlText = false)` 只有 `htmlText=true` 才会拼 `<img>`。
- 当前部分调用传的是 `i.message` 而不是整个 item，可能导致 images 没有进入预览。
- `loadJsonFile()` 会把 images 拼成 `[image:url]` 文本，但预览 HTML 渲染是否一致需要测试。

### 预览模式仍是半成品

- `preview-bbs.vue` 和 `preview-trg.vue` 基本只是 `JSON.stringify(previewItems)`。
- 它们不是最终格式化输出。

### 颜色映射策略不一致

- 注释说希望以 `IMUserId || name` 或复合键区分。
- `buildPcList()` 当前用 `name.trim()` 作为 key。
- `preview-main.vue` 优先用 `name + IMUserId` 查找，失败后按 name。
- 这会导致同名/改名/同 ID 不同名时行为不稳定。

### 文本解析链路风险

- `LogManager.parse()` 只内置 QQ 两行格式：
  - `name(id) yyyy/MM/dd HH:mm:ss`
  - 后续行为内容
- 插件 JSON 先被转成这种格式再解析。
- 如果 nickname 包含括号、时间格式变化、Bot ID 变化，解析可能失败。

## 高风险文件

### 不建议直接大改

- `log-painter/frontend/src/components/main.vue`
- `log-painter/frontend/src/components/template.vue`
- `log-painter/frontend/src/logManager/logManager.ts`

原因：它们承担了太多职责，而且互相依赖隐式字段。直接拆容易导致页面白屏、预览不刷新、颜色丢失、导出错位。

### 可小步改动

- `log-painter/frontend/src/logManager/types.ts`
  - 可以逐步补齐字段类型。

- `log-painter/frontend/src/utils/index.ts`
  - 可以单独修过滤函数、图片函数。

- `log-painter/frontend/src/logManager/importers/*.ts`
  - 可以逐个补 importer，但要先接入统一选择流程。

- `log-painter/backend/main.py`
  - 可补错误日志、配置默认值、健康检查。

## 建议的安全重构路线

### 第 0 步：先建立样例和手动验收清单

不要先拆代码。先准备 3 到 5 个样例日志：

- 插件导出的标准 JSON。
- 包含图片的 JSON。
- 包含 OB 的 JSON。
- 包含骰点结果的 JSON。
- 一份手工 QQ 导出文本。

验收清单：

- 页面能打开。
- URL `?file=xxx.json` 能加载。
- 左侧角色列表正确。
- 颜色修改后预览立即刷新。
- 图片显示/隐藏符合预期。
- 场外发言过滤符合预期。
- OB 能被识别。
- 原始文本导出可用。
- Word 导出可用。

### 第 1 步：补齐类型，不改行为

- 扩展 `LogItem`：
  - `date`
  - `time`
  - `images`
  - `is_comment`
  - `isObserver`
  - `observer`
  - `role`
  - `who`
  - `messageSanitized`

- 定义 `RoleType`：
  - `主持人`
  - `角色`
  - `骰子`
  - `隐藏`
  - `OB`
  - `dice`

目标：减少 `as any`，但不重写逻辑。

### 第 2 步：收口 JSON 加载

把 `loadJsonFile()` 从 `main.vue` 抽成一个单独模块，例如：

- `src/logManager/loaders/pluginJsonLoader.ts`

职责：

- 校验文件名。
- 请求 `/export/{file}`。
- 标准化 items。
- 保留 `isDice`、`isObserver`、`images` 等结构化字段。

短期仍可输出当前文本格式，但要把结构化字段保存在可追踪位置。

### 第 3 步：抽出预览构建

把 `showPreview()` / `getPreviewText()` 相关逻辑抽到：

- `src/logManager/preview/buildPreviewItems.ts`

目标：

- 输入 `LogItem[]`、`pcList`、`exportOptions`。
- 输出 `PreviewItem[]`。
- 统一处理图片、命令隐藏、场外过滤、OB 过滤。

### 第 4 步：处理 OB UI

在过滤选项中新增：

- `filterObservers`

逻辑：

- 如果 `filterObservers` 为 true，跳过 `item.isObserver === true` 的消息。
- 预览和导出都使用同一套过滤函数。

### 第 5 步：合并 `main.vue` 和 `template.vue`

先确认 `template.vue` 是否被路由或构建引用。

如果未使用：

- 标记为 legacy。
- 不再往里面加功能。
- 后续删除前先保留一版备份说明。

如果仍使用：

- 抽共享 composable：
  - `useLogLoading`
  - `usePreview`
  - `useRoleList`
  - `useExport`

不要一次性把两个大文件合并。

### 第 6 步：恢复 importer 架构

定义统一接口：

- `check(textOrData): boolean`
- `parse(input): TextInfo`

然后逐个实现：

- plugin JSON importer
- EditLog importer
- QQ export importer
- SealDice importer

未实现的 importer 不应静默返回空，应明确标记 unsupported。

## 功能缺口清单

### 高优先级

- 后端 `config.yaml` 缺失时的默认配置或清晰错误说明。
- Router 残留清理。
- OB 隐藏过滤开关。
- 图片预览链路修正。
- `main.vue` / `template.vue` 使用关系确认。
- 删除或收敛调试 `console.log`。

### 中优先级

- 补齐 `LogItem` 类型。
- 统一颜色 key 策略。
- 抽出 `loadJsonFile()`。
- 抽出预览构建逻辑。
- 让插件 JSON 直接走结构化 importer。
- Word 导出逻辑从 Vue 文件中抽出。

### 低优先级

- 实现 QQ/SealDice/FVTT 等 importer。
- 完成 BBS/TRG 预览格式。
- 远程分享/上传功能。
- 角色列表高级编辑和持久化。

## 不建议现在做的事

- 不要直接格式化 `main.vue` / `template.vue` 全文件。
- 不要一次性迁移到 Pinia。
- 不要一次性替换 LogManager。
- 不要在没有样例日志的情况下重写 importer。
- 不要先改 UI 视觉结构，当前最大风险是数据流而不是样式。

## 下一步建议

最稳的下一步是实现“低风险可见收益”的 OB 过滤：

1. 在 `store.exportOptions` 或 `previewFilters` 中加入 `filterObservers`。
2. 在预览构建时过滤 `item.isObserver`。
3. 在导出时复用同一过滤逻辑。
4. 用一份包含 OB 的插件 JSON 手动验证。

这一步改动范围小，能检验我们刚才加的 OB 标记是否在 log-painter 里真正有用。

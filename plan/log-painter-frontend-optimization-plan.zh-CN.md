# log-painter 前端优化计划

最后更新：2026-05-12

这份文档是 `log-painter/frontend` 的中文优化计划。目标不是立刻重写前端，而是在不破坏现有染色器工作流的前提下，把当前混在大组件里的逻辑逐步拆出来，让后续修 bug、加 OB 过滤、图片预览、导出格式和多 importer 都能有稳定落点。

## 当前判断

`log-painter/frontend` 是一个 Vite + Vue 3 项目，主要依赖 Naive UI 和 CodeMirror。

当前实际入口是：

- `src/main.ts` 创建 Vue app。
- `src/App.vue` 直接渲染 `components/main.vue`。
- `src/router/index.ts` 虽然存在，但没有被挂载，而且引用了不存在的 `components/JsonEditor.vue`。

也就是说，现在真正跑起来的是 `main.vue`，router 基本属于残留或半成品代码。

## 主要问题

### 1. `main.vue` 太大

`src/components/main.vue` 大约 1633 行，承担了太多职责：

- 页面布局
- 左侧角色列表
- 角色改名
- 角色颜色管理
- CodeMirror 编辑器状态
- URL 参数读取
- 后端 JSON 加载
- 日志文本转换
- 触发解析
- 构建预览数据
- 预览过滤
- 原始文本导出
- Word / HTML 导出
- 深色模式和大量样式

这导致任何小改动都容易牵动整页。比如只想修 OB 过滤，也会碰到预览、导出、角色列表和 `store`。

### 2. `template.vue` 和 `main.vue` 高度重复

`src/components/template.vue` 大约 1601 行，和 `main.vue` 很像，但不是完全一致。

风险在于：

- 修 `main.vue` 时容易忘记 `template.vue`。
- 两边导出函数和预览行为已经有差异。
- 很难判断哪个是正本、哪个是旧稿。

目前看 `App.vue` 只使用 `main.vue`，所以建议先把 `template.vue` 标成 legacy，不再往里面加新功能。等确认一轮后再考虑删除或归档。

### 3. 数据流绕了一圈

现在的核心链路大致是：

1. 插件导出 JSON。
2. 前端通过 `/export/{file}` 加载 JSON。
3. 前端把 JSON 转成类似 QQ 导出的纯文本。
4. `LogManager.parse()` 再把纯文本解析回 `LogItem[]`。
5. 预览和导出再基于 `LogItem[]` 工作。

这个链路最大的问题是结构化字段容易丢。

例如：

- `images`
- `isObserver`
- `observer`
- `role`
- `isDice`
- 骰点元信息
- 时间、日期、账号

这些字段原本在 JSON 里很清楚，但转成文本再解析后，必须靠额外拼接或猜测恢复。后续越加功能，越容易出现“预览有、导出没有”或“导出有、过滤没有”的问题。

### 4. 预览、过滤、导出逻辑重复

现在相关逻辑散在多个地方：

- `showPreview()`
- `getPreviewText()`
- `cmContent` 的 computed
- `preview-main.vue`
- `preview-bbs.vue`
- `preview-trg.vue`
- Word / HTML 导出函数
- `utils/index.ts` 里的若干格式化函数

同一个需求可能要改很多处。比如“隐藏 OB 发言”应该同时影响预览和导出，但当前没有一个统一过滤入口。

### 5. 类型定义落后于运行时数据

`logManager/types.ts` 里的 `LogItem` 很薄，但实际代码里大量使用额外字段：

- `date`
- `time`
- `images`
- `is_comment`
- `isObserver`
- `observer`
- `role`
- `who`
- `messageSanitized`

所以代码里出现了很多 `(it as any)`。这不是单纯“不好看”，而是会让字段丢失、拼错、逻辑分叉都躲过 TypeScript。

### 6. 颜色 key 策略不统一

当前不同位置的角色颜色匹配策略不一致：

- 有的地方只按 `name`
- 有的地方按 `IMUserId`
- 有的地方尝试 `name + IMUserId`
- 失败后又 fallback 到 `name`

这会导致同名角色、改名、同 QQ 多角色时颜色不稳定。

建议统一成一个 helper，例如：

```ts
colorKey = `${IMUserId || 'noid'}#${nickname || name}`
```

然后所有角色列表、预览、导出都走同一个 key。

### 7. importer/exporter 架构存在但没有真正收口

`logManager/importers/` 目录存在多个 importer，但主流程没有真正使用 importer registry。

同时：

- `logManager.importers = []`
- 多个 importer 是占位实现
- `exportFileQQ()` / `exportFileIRC()` 是空函数
- Word 导出逻辑主要还在 Vue 大组件里

这说明项目已经有“想做架构”的痕迹，但还没有真正形成边界。

## 对照海豹在线染色器后的能力缺口

参考对象主要是海豹官网、海豹手册和海豹更新日志里公开描述的在线日志着色器能力。它们提到的核心能力包括：骰子日志可直接导出到配套着色网站；在线编辑、着色后导出 doc；提供多套着色方案并支持用户自己配色；支持 QQ 格式和塔骰格式文本粘贴导入；海豹日志会自动上传；支持论坛代码和回声工坊导出；较新版本还强调日志导出筛选、性能优化、预览颜色生成优化、特殊符号预览修复，以及论坛代码/回声工坊导出行粘连修复。

对照我们当前 `log-painter`，缺口如下。

### 1. 导入格式支持不足

我们当前主流程基本只稳定覆盖两类输入：

- 插件侧导出的 JSON。
- 类 QQ 两行一条的文本格式。

但海豹公开说明里至少提到：

- 海豹自用 Log。
- QQ 格式。
- 塔骰格式。
- 其他骰系 log 转换格式。

我们仓库里虽然有 `QQExportLogImporter`、`SealDiceLogImporter`、`FvttLogImporter`、`DiceKokonaLogImporter`、`RenderedLogImporter`、`SinaNyaLogImporter` 等文件，但多数并没有进入主流程，部分还是占位实现。

需要补的能力：

- 明确支持“粘贴全文后自动识别格式”。
- 实现 SealDice / 塔骰 / QQ 至少三种 importer。
- 未支持格式要给明确错误，不要静默空结果。
- 插件 JSON 应作为一等 importer，而不是先转文本再解析。

### 2. 着色方案能力不足

海豹官网提到有多套着色方案，也鼓励用户自己配色。

我们现在主要是：

- 角色颜色自动生成。
- 单个角色手动改色。
- 刷新颜色。

缺少：

- 预设主题/色板。
- 色板保存和恢复。
- 一键切换方案。
- 导入/导出配色方案。
- 按角色身份分配颜色策略，例如 KP、PC、NPC、骰子、OB。
- 颜色冲突检测，例如相邻角色颜色太接近。

这块不影响核心链路，但会影响“在线染色器”的完整体验。

### 3. 导出格式明显不足

海豹公开描述中明确提到 doc 导出、论坛代码、回声工坊导出。

我们现在已有：

- 原始文本下载。
- HTML/Word 相关逻辑雏形。
- BBS/TRG 预览入口。

但问题是：

- Word 导出逻辑还散在 Vue 大组件里。
- BBS/TRG 预览更像调试视图，不是稳定格式。
- 没有明确的“论坛代码导出”成品能力。
- 没有“回声工坊导出”成品能力。
- 导出和预览不一定共用同一套过滤逻辑。
- 图片、OB、场外、账号、时间等字段是否进入导出不稳定。

需要补的导出目标：

- doc / docx。
- HTML。
- 论坛 BBCode。
- 回声工坊兼容格式。
- 纯文本。
- 可选 JSON 再导出，方便二次处理。

### 4. 筛选能力不完整

海豹更新日志提到日志导出升级补齐筛选与性能优化。

我们现在已有一些过滤开关：

- 表情/图片。
- 场外发言。
- 具体时间。
- 日期。
- 账号。

但还不完整：

- 没有稳定的 OB 隐藏开关。
- 没有按角色隐藏。
- 没有按身份隐藏，例如骰子、KP、OB、旁白。
- 没有按消息类型隐藏，例如指令、骰点、图片、纯文本。
- 没有按时间段筛选。
- 没有“预览和导出共用筛选”的强约束。

这应该成为近期重点，因为筛选是日志清理的核心功能。

### 5. 在线编辑体验不足

海豹手册描述的是“可以实时编辑的跑团日志”。

我们虽然有 CodeMirror，但编辑体验还停留在基础文本框增强：

- 没有格式识别状态提示。
- 没有导入错误定位。
- 没有按消息块折叠/跳转。
- 没有角色定位。
- 没有搜索/替换 UI。
- 没有撤销友好的结构化编辑。
- 预览模式和编辑模式耦合较重。

后续可以把编辑器从“纯文本编辑”升级成“日志块编辑”，但这要在 parser 和类型稳定之后再做。

### 6. 自动上传和分享链路不足

海豹公开说明里提到日志会自动上传到在线染色器，省去手动发送日志文件。

我们当前插件侧已经能导出 JSON 并返回 `?file=...` 形式的链接，但还比较粗：

- 后端配置缺失时容易失败。
- 没有日志列表页。
- 没有访问过期/权限/密码策略。
- 没有跨群或历史日志选择。
- 没有重新分享、复制链接、下载源文件的一体化流程。

这块属于后端和前端协作，不建议先做大功能，但至少要把当前 `/export/{file}` 的配置、错误提示和加载状态补齐。

### 7. 性能和大日志能力不明

海豹更新日志多次提到日志、染色器性能优化。

我们当前有几个潜在性能问题：

- 编辑器每次变更会 debounce 后全量重新解析。
- JSON 会转文本再重新解析。
- `main.vue` 中预览构建和颜色匹配可能重复遍历。
- 大量 `v-for` 预览没有虚拟列表。
- 大日志下 Word/HTML 生成可能阻塞主线程。

需要后续验证：

- 1 万行日志是否可编辑。
- 5 万行日志是否可预览。
- 图片较多时是否卡顿。
- 导出 Word 是否会冻结页面。

### 8. 特殊符号和行粘连问题需要加入验收

海豹更新日志提到过：

- 特殊符号在预览中正确显示。
- 论坛代码和回声工坊导出解决行粘连。
- 回复他人发言不应误判为场外发言。

这些点对我们也很重要。当前计划里的 fixtures 应新增：

- 含 `< > & " '` 的文本。
- 含中英文括号的场外发言。
- 含回复/引用的消息。
- 连续多行消息。
- 空行和仅图片消息。
- BBCode 敏感字符。

否则后续做 BBS/回声工坊导出时很容易踩同样的问题。

## 优化原则

1. 不要一上来重写整个前端。
2. 先建立样例和验收清单，再拆逻辑。
3. 每次只抽一个边界，保证行为可回归。
4. 优先抽纯函数：加载、标准化、过滤、预览构建、颜色 key。
5. 先承认 `main.vue` 是当前正本，`template.vue` 暂时视为旧稿。
6. 中文乱码不要全仓库盲目批量修，先修用户可见文案。

## 目标结构

短期建议拆成：

- `components/main.vue`
  - 只保留页面组装和少量状态连接。

- `components/sidebar/RoleList.vue`
  - 角色列表、颜色点、改名、删除角色。

- `components/sidebar/LogActions.vue`
  - 下载原始文件、下载 Word、刷新、清空等操作入口。

- `components/editor/LogEditor.vue`
  - CodeMirror 包装和预览模式切换。

- `logManager/loaders/pluginJsonLoader.ts`
  - 负责从后端加载插件 JSON，并标准化字段。

- `logManager/filters/filterLogItems.ts`
  - 统一处理图片隐藏、场外发言隐藏、时间隐藏、账号隐藏、OB 隐藏。

- `logManager/preview/buildPreviewItems.ts`
  - 输入 `LogItem[]`、角色列表、过滤选项，输出预览用数据。

- `logManager/colors/colorKey.ts`
  - 统一角色颜色 key。

- `logManager/importers/`
  - 真正接入 importer registry，至少覆盖插件 JSON、QQ、SealDice/海豹、塔骰。

- `logManager/exporters/`
  - 输出纯文本、HTML、doc/docx、BBCode、回声工坊格式。

- `logManager/types.ts`
  - 补齐真实运行时字段。

## 分阶段计划

### 第 0 阶段：先建立安全网

先不要拆大组件。

要先准备几份固定样例：

- 标准插件 JSON
- 带图片的 JSON
- 带 OB 发言的 JSON
- 带骰点结果的 JSON
- 手工 QQ 导出文本

同时写一份手动验收清单：

- 页面能打开
- `?file=xxx.json` 能加载
- 左侧角色列表正确
- 改颜色后预览刷新
- 图片能显示/隐藏
- 场外发言能过滤
- OB 能识别
- 原始文本能下载
- Word / HTML 导出不崩

### 第 1 阶段：清理明显残留

- 处理 `router/index.ts`。
  - 如果不用 router，就删除或归档。
  - 如果要用 router，就补上缺失的页面并在 `main.ts` 挂载。

- 给 `template.vue` 标记 legacy。
  - 暂时不要继续维护双份逻辑。
  - 后续确认无引用后再删除。

- 清理生产路径里的 `console.log`。
  - 保留必要的 `console.warn` / `console.error`。
  - 不要让普通用户打开控制台看到大量调试输出。

- 修 active UI 文案乱码。
  - 优先修按钮、开关、标题、placeholder。
  - 注释可以后面顺手修。

### 第 2 阶段：补类型，不改行为

先扩展 `LogItem`，把现在实际用到的字段写进去：

- `date`
- `time`
- `images`
- `is_comment`
- `isObserver`
- `observer`
- `role`
- `who`
- `messageSanitized`

然后新增：

- `RoleType`
- `PreviewFilterOptions`
- `PreviewItem`

这一步目标不是把所有 `any` 一次性删光，而是让后面抽函数时有类型可依赖。

### 第 3 阶段：抽 JSON loader

把 `main.vue` 里的 `loadJsonFile()` 抽到：

```text
src/logManager/loaders/pluginJsonLoader.ts
```

这个模块负责：

- 校验文件名
- 请求 `/export/{file}`
- 判断返回结构
- 过滤空消息
- 标准化字段
- 保留 `images`、`isObserver`、`role`、`isDice`

短期可以继续输出当前文本格式，保证页面不坏。但要同时保留结构化数据，为后续预览和导出绕开“文本再解析”做准备。

### 第 4 阶段：抽预览和过滤

新增：

```text
src/logManager/filters/filterLogItems.ts
src/logManager/preview/buildPreviewItems.ts
```

目标：

- 预览和导出共用同一套过滤逻辑。
- 图片、场外、时间、账号、OB 都从同一个 filter 入口处理。
- `showPreview()` / `getPreviewText()` 不再各写一套。
- `preview-main.vue` 只负责渲染，不负责推断业务规则。

这一阶段可以顺手实现“隐藏 OB 发言”。

### 第 5 阶段：拆 UI 组件

拆 UI 要晚一点做，因为现在状态耦合太重。

建议顺序：

1. 先拆操作区。
   - 下载、清空、刷新这类按钮主要是事件转发，风险最低。

2. 再拆角色列表。
   - 角色名、颜色、身份、删除都可以通过 props + emits 做。

3. 最后拆编辑器和预览区。
   - 这里和 `cmContent`、preview mode、CodeMirror extension 关系最复杂。

拆完后 `main.vue` 应该变成组合页面，而不是业务大杂烩。

### 第 6 阶段：恢复 importer/exporter 架构

等数据流稳定后再处理 importer/exporter。

要做：

- 恢复 importer registry。
- 未实现 importer 不要静默返回空数组，应该明确报 unsupported。
- 实现 plugin JSON importer。
- 确认 EditLog importer 是正经入口。
- QQ / SealDice / FVTT 等 importer 后续逐个补。
- 把 Word / HTML 导出从 Vue 组件里移出去。
- 删除或实现空的 `exportFileQQ()` / `exportFileIRC()`。

### 第 7 阶段：追上海豹染色器的核心体验

这一阶段不是照抄 UI，而是补齐能力面。

优先顺序：

1. 多格式导入。
   - 插件 JSON。
   - QQ 文本。
   - 海豹/SealDice 文本。
   - 塔骰文本。

2. 多格式导出。
   - doc/docx。
   - HTML。
   - BBCode/论坛代码。
   - 回声工坊兼容格式。
   - 纯文本。

3. 多套着色方案。
   - 默认方案。
   - 高对比方案。
   - 柔和方案。
   - 自定义方案保存/载入。

4. 大日志性能。
   - 减少重复解析。
   - 预览虚拟列表。
   - 导出时显示进度或放入异步任务。

## TODO

### 高优先级

- [x] 准备插件 JSON、图片、OB、骰点、QQ 文本样例。
- [x] 跑一次 `npm run build`，记录当前基线。
- [x] 处理未使用且破损的 router。
- [x] 确认 `template.vue` 是否仍被使用。
- [x] 将 `template.vue` 标记为 legacy。
- [ ] 修复 `main.vue` 里用户可见的中文乱码。
- [x] 修复 `CodeMirror.vue` 的 placeholder 乱码。
- [x] 清理 `loadJsonFile()`、parsed callback、预览、导出里的调试日志。
- [x] 增加“隐藏 OB 发言”过滤选项。
- [x] 让 OB 过滤同时影响预览和导出。
- [x] 修正图片从插件 JSON 到预览/导出的保留链路。
- [ ] 补一组“特殊符号/多行/引用/空行/仅图片”验收样例。
- [ ] 明确当前要兼容的外部染色器能力基线：QQ、海豹、塔骰、doc、BBCode、回声工坊。

### 中优先级

- [x] 补齐 `LogItem` 字段。
- [x] 新增 `PreviewItem` 类型。
- [x] 新增 `PreviewFilterOptions` 类型。
- [x] 抽出 `pluginJsonLoader.ts`。
- [x] 抽出角色列表构建逻辑。
- [x] 抽出统一颜色 key helper。
- [x] 抽出 `buildPreviewItems.ts`。
- [x] 抽出 `filterLogItems.ts`。
- [ ] 让 BBS/TRG 预览变成真实格式，或明确标为实验功能。
- [x] 把 Word / HTML 导出构建逻辑移出 Vue 文件。
- [ ] 实现至少一个非插件 JSON importer，例如 QQ 或海豹文本。
- [ ] 新增 BBCode/论坛代码导出器。
- [ ] 新增回声工坊兼容导出器草案。
- [ ] 增加着色方案保存/载入。
- [ ] 增加一键切换预设色板。

### 低优先级

- [ ] 等边界稳定后再考虑 Pinia 或更正式的 store。
- [ ] 恢复 QQ、SealDice、FVTT、DiceKokona、RenderedLog、SinaNya importer。
- [ ] 实现或删除 `exportFileQQ()`。
- [ ] 实现或删除 `exportFileIRC()`。
- [ ] 给预览过滤和导出增加 smoke test。
- [ ] 一个稳定周期后删除或归档 `template.vue`。
- [ ] 加入大日志虚拟滚动。
- [ ] 导出任务进度提示或后台 worker。
- [ ] 做日志列表和历史分享管理。

## 不建议现在做的事

- 不要一次性重写 `main.vue`。
- 不要一次性删除 `template.vue`。
- 不要全项目批量格式化。
- 不要全项目批量“修乱码”。
- 不要在没有样例日志的情况下重写 parser。
- 不要现在就把 store 改成 Pinia。
- 不要一口气实现所有 importer。
- 不要为了追上海豹染色器的功能面而先做视觉重做。
- 不要先做回声工坊导出，除非已经有稳定的 preview/export 中间结构。

## 建议下一步

最稳的下一步是：

1. 补样例日志和验收清单。
2. 跑一次 build，确认当前失败点。
3. 处理 router 和 `template.vue` 的归属。
4. 做一个小功能闭环：新增 OB 过滤，并让预览和导出共用同一套过滤逻辑。
5. 增加 QQ/海豹/塔骰格式兼容性的 importer 设计草案。

这个顺序收益比较高，因为 OB 标记已经从插件侧传过来了，前端加过滤能马上验证整个日志链路是否真的通。

对照海豹染色器后，真正的中期目标应该是：我们不只是“能打开插件 JSON”，而是要成为一个能导入多骰系日志、能统一清洗筛选、能输出多目标格式的日志加工工具。

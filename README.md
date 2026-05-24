# TRPGdice-Complete

为 Astrbot 设计的 TRPG 骰子插件（参考 [Dice!](https://forum.kokona.tech/) 与 [海豹](https://dice.weizaima.com/) 的实现），提供掷骰、技能判定、人物卡管理与日志导出等常用功能，便于在群聊中进行跑团玩法支持。

为所有使用astrbot平台但想要有与其他骰娘相同体验的骰主设计。

本插件是 [Astrbot_plugin_TRPGdice](https://github.com/WhiteEurya/Astrbot_plugin_TRPGdice) 的升级版。

---


## 更新日志 V2.4

```
> 增加 .查询法术 指令：接入不全书，直接从5R不全书中获取最新的法术。
> 法术查询切换为 HTML 卡片截图输出，并修正 AstrBot 图片组件发送方式。
> 补充 Playwright 与 log-painter 后端依赖声明；CoC 规则库会在读取前自动建表，不再需要上传本地 cocrule.db。
> 更多新功能请在骰子内使用help查看。
```

## 更新日志 V2.3

```
> 重构了插件目录结构，将掷骰、CoC、角色卡、日志、先攻和通用工具拆分到 component/ 下的独立模块。
> 抽出了内联指令解析、角色卡展示、日志统计、CoC 检定辅助、群名片格式化等逻辑，降低 main.py 体量。
> 增加并完善了测试覆盖，包括掷骰解析、CoC 检定、角色卡存储和法术查询。
> 扩展 CoC 检定：支持 .rc/.rch/.rcv 入口、.rah 暗中检定、.rav/.rcv 对抗检定、困难/极难难度前缀和技能修正值。
> 增加 .st 模板/.st template，补充 .st show 的属性筛选、阈值查看、@他人查看和批量录入相关能力。
> 增加 .sn coc/.sn cocL/.sn none/.sn off 等群名片模式，并整理角色卡群名片生成逻辑。
> 增加 .cocN/.dndN 这类无空格角色生成写法，并限制一次生成数量为 1~10。
> 增加 .log stat、.log export，以及 .log ob add/del/list/clear 的 OB 管理功能。
> 增加 .ob 快捷指令，用户可以快速切换自己在当前日志中的 OB 状态。
> 日志导出增强：记录骰点、图片、OB 标记，JSON 导出可被 log-painter 识别，文本导出会标记 OB 发言。
> log-painter 前端完成构建修复，加入共享过滤逻辑、隐藏 OB 开关、插件 JSON 加载器、预览构建器、角色列表/侧栏/编辑区组件拆分。
> log-painter 增加 Word 导出整理、角色颜色 key 辅助、测试样例和手动验收清单，构建流程已恢复可通过。
```

## 更新日志 V2.2

```
> 修复了一大堆BUG。很可能包括您之前遇到的所有BUG。
> 增加了.dicehelp功能
> 增加了@人代骰功能
> 增加了跨群pc卡同步，像是github一样管理人物卡的功能
> 增加了新的BUG...(?)
```

## 安装

1. 克隆仓库到本地：
   ```bash
   git clone https://github.com/WhiteEurya/Astrbot_plugin_TRPGdice-Complete.git
   ````

2. 将插件文件/目录放入 Astrbot 的插件目录（plugin folder）。

3. 安装 Python 依赖：

   ```bash
   pip install -r requirements.txt
   python -m playwright install chromium
   ```

4. 如需自定义回复文案或染色器地址，可以复制默认配置后修改：

   ```bash
   cp component/config.default.yaml component/config.yaml
   ```

5. 启动或重启 Astrbot，确认控制台输出已加载本插件。

> 如果 Astrbot 有插件管理命令或配置文件，请根据 Astrbot 的文档把本插件添加到插件列表中。

---

## 功能

- **基础掷骰**
  - 支持常见的 DnD / CoC / 跑团检定
  - 支持算式，例如 `1d100+5`
  - 支持小众规则的掷骰 (目前已支持吸血鬼规则)

- **角色卡与检定**
  - 支持角色属性绑定
  - 一键进行 **技能检定**、**对抗检定**

- **自定义别名**
  - 角色名、技能名可自定义
  - 方便团队内的快速调用

- **日志与记录**
  - 自动保存跑团对话日志
  - 支持导出记录，便于存档和复盘

- **法术查询**
  - 支持 `.查询法术` 查询 SeaDice 内置资料中的 DND/COC 法术
  - 输出中会标注 SeaDice、DicePP 或 CoC 魔法大典整理者等资料来源

- **预览与染色**
  - 对日志进行高亮显示
  - 支持过滤表情、时间戳、账号等冗余信息

- **自定义风格回复**
  - 将所有回复集成到 `config.yaml` 中，方便自由修改

- **更多方便的功能**
  - 生成名字、抽取恐慌症状等...

---

## 快速使用示例

> 插件加载后，可在群聊或私聊中使用下列示例指令进行测试

* 基本掷骰（示例）：

  ```
  .r
  ```
* 技能判定（示例）：

  ```
  .ra侦查50
  ```
* 人物卡管理（示例）：
  本插件接收 **COC7版规则卡** 的 `.st` 输入

  ```
  .pc create <名字>
  .pc change <名字>
  .pc update 幸运+1
  .st 属性值
  ```

* 日志 / 会话（示例）：

  ```
  .log new <日志名>
  .log off
  .log on
  .log end
  ```

* 法术查询（示例）：

  ```
  .查询法术 火球术
  .查询法术 神话 驱逐实体
  ```

如需完整指令说明，请运行插件内置的帮助命令 `.dicehelp` 或查看源码中的命令实现部分。

---

## 仓库

项目地址：
[https://github.com/WhiteEurya/Astrbot\_plugin\_TRPGdice-Complete](https://github.com/WhiteEurya/Astrbot_plugin_TRPGdice-Complete)

---

## 上传前检查

发布给其他人使用时，请确认下列静态文件或模板一并提交：

- `component/config.default.yaml`：插件回复文案和染色器前端地址的默认配置。
- `log-painter/backend/config.default.yaml`：染色器后端导出目录的默认配置。
- `data/mania.json`、`data/phobias.json`：`.ti` / `.li` 疯狂症状数据。
- `data/sealdice-builtins/`：`.查询法术` 的 SeaDice DND/COC 资料来源。
- `spellsearcher/`：图片版 `.查询法术` 使用的本地 HTML 法术书。
- `data/velinithra.png`：`.bot` 信息图资源。
- `V20_char_sheet/setup.sql`：V20 角色卡建表模板。

不应上传本地运行数据：`chara_data/`、`chara_data_/`、`data/group_logs/`、`data/settings/`、`*.db`、`config.yaml`、`node_modules/`、`dist/`。

---

## 染色器搭建

本插件提供了类似 [海豹LOG染色器](https://log.weizaima.com/) 的染色功能，保存在 `/log-painter`下，感谢海豹LOG染色器提供的模板与思路。
如果要使用染色器，需要通过npm和fastapi在本地进行搭建。
若您不方便配置域名、没有合适的服务器，可以直接使用我的染色器网址: [https://painter.velinithra.space/](https://painter.velinithra.space/)

如果您愿意搭建自己的染色器，则可以参考下列教程

---

### 后端 (FastAPI)

1. 进入后端目录，创建虚拟环境并激活：

```bash
cd log-painter/backend

# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 启动 FastAPI 服务：

```bash
# Windows / macOS / Linux
uvicorn main:app --reload
```

> 默认运行在 `http://127.0.0.1:8000`

---

### 前端 (npm)

1. 进入前端目录：

```bash
cd log-painter/frontend
```

2. 安装依赖：

```bash
npm install
```

3. 启动开发服务器：

```bash
npm run dev
```

> 默认运行在 `http://localhost:5173`（端口可能根据框架不同而变化）

4. 构建生产环境：

```bash
npm run build
```

### 配置

进入 `log-painter/backend/` 复制默认配置，并修改目标文件夹到您存放 export log 的位置：

```bash
cp config.default.yaml config.yaml
```

进入 `log-painter/frontend/vite.config.ts` 中，在 `allowedHosts` 一项中修改您的服务器域名。

进入 `component/config.yaml` 中将 `setting.website` 一项修改为您自己的染色器前端域名。

---

### 注意事项

* 确保后端服务已经启动，否则前端无法正常请求 API。
* 如果遇到权限问题，请尝试使用管理员/sudo 权限。大部分npm操作可能都需要您提供管理员权限

## 别的想说的

在完成之前一版TRPG_Dice之后，本来已经准备摆了，但是朋友们以及其他的用户不断给我反馈以及提供idea、编码上的帮助，这给了我动力将曾经的插件进行大幅度优化，目前比起曾经那个简单的骰子和屎山代码已经有了很大优化。当然这个插件一定还有很多bug和优化的地方，因此如果大家对这个插件有任何问题、发现了任何BUG，都可以在issue中与我交流。

## Contributors

感谢以下为本项目做出贡献的朋友：

<a href="https://github.com/RealVitaminC">
  <img src="https://github.com/RealVitaminC.png" width="50" height="50"/>
</a>
<a href="https://github.com/YumoFS">
  <img src="https://github.com/YumoFS.png" width="50" height="50"/>
</a>

## 许可

本项目采用 MIT 协议，欢迎自由使用与修改

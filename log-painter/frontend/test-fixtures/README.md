# log-painter mock fixtures

这些文件用于手工测试前端，不依赖真实群日志。

## 文件

- `logs/basic-chat.json`：普通对话。
- `logs/with-images.json`：图片和纯图片消息。
- `logs/with-ob.json`：OB/旁观者消息。
- `logs/with-dice.json`：指令和骰点结果。
- `logs/special-cases.json`：特殊字符、多行、场外、引用文本。
- `logs/qq-basic.txt`：可直接粘贴进编辑器的 QQ 风格文本。

## 使用方式

最简单：

1. 打开前端页面。
2. 打开 `qq-basic.txt`。
3. 全选复制内容，粘贴进编辑器。
4. 检查角色列表、预览、下载原文、Word 导出。

测试 JSON 加载：

1. 需要后端 `/export/{file}` 可访问。
2. 将某个 JSON fixture 放到后端 export 目录。
3. 浏览器打开 `/?file=basic-chat.json` 这类地址。

注意：当前前端的 JSON 加载入口固定请求 `/export/{file}`，不会直接读取 `test-fixtures` 目录。

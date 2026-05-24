# log-painter frontend

## 配置端口和转发

先复制一份本地配置：

```bash
cp .env.example .env
```

然后在 `.env` 里改你 Cloudflare 指向的端口：

```bash
LOG_PAINTER_PORT=5173
```

常用配置：

```bash
LOG_PAINTER_HOST=0.0.0.0
LOG_PAINTER_ALLOWED_HOSTS=.velinithra.space
LOG_PAINTER_API_TARGET=https://worker.firehomework.top/dice/api
LOG_PAINTER_EXPORT_TARGET=http://localhost:8000
```

`LOG_PAINTER_PORT` 同时影响 `npm run dev` 和 `npm run preview`。配置里启用了 `strictPort`，端口被占用时会直接失败，避免 Cloudflare 还指向旧端口但 Vite 自动换到别的端口。

## 方便改动和测试

开发时使用：

```bash
npm run dev
```

它会监听 `.env` 中的端口，支持热更新，适合边改边测。

## 接近生产的本地预览

测试构建产物：

```bash
npm run serve
```

这个命令会先构建，再用 Vite preview 挂到同一个端口。

## 长期后台运行

如果已经确认功能稳定，可以用 PM2 后台运行构建预览：

```bash
npm run build
pm2 start npm --name log-painter -- run preview
pm2 save
```

更新代码后：

```bash
npm run build
pm2 restart log-painter
```

查看状态和日志：

```bash
pm2 status
pm2 logs log-painter
```

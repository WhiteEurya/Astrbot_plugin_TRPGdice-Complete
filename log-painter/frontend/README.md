# log-painter frontend

For normal deployment, use the project-level script from the parent directory:

```bash
cd ..
./start.sh
```

That starts both the FastAPI backend and the built frontend in the background.

## Development

For frontend-only development, copy the local env file:

```bash
cp .env.example .env
```

Then adjust the port or proxy targets if needed:

```bash
LOG_PAINTER_PORT=5173
LOG_PAINTER_HOST=0.0.0.0
LOG_PAINTER_ALLOWED_HOSTS=.velinithra.space
LOG_PAINTER_API_TARGET=https://worker.firehomework.top/dice/api
LOG_PAINTER_EXPORT_TARGET=http://localhost:8000
```

`LOG_PAINTER_PORT` affects both `npm run dev` and `npm run preview`. `strictPort` is enabled, so Vite exits if the port is already in use.

Start the Vite dev server:

```bash
npm run dev
```

Preview the built frontend:

```bash
npm run serve
```

# Log Painter

TRPG log painter includes a FastAPI backend and a Vite/Vue frontend.

## One-command start

Run from this directory:

```bash
./start.sh
```

The script will:

- create `backend/.venv` if needed
- install backend dependencies
- install frontend dependencies with `npm ci` if needed
- build the frontend
- start the backend and frontend in the background with `nohup`

The service keeps running after the terminal or SSH session is closed.

Open:

```text
http://localhost:5173
```

## Manage service

```bash
./start.sh status
./start.sh logs
./start.sh stop
./start.sh restart
```

Runtime logs and PID files are written to `.runtime/`.

## Ports and proxy

Defaults:

```text
Backend:  http://localhost:8000
Frontend: http://localhost:5173
```

Override ports when starting:

```bash
BACKEND_PORT=8001 LOG_PAINTER_PORT=5174 ./start.sh
```

The frontend proxies `/export` to the backend through `LOG_PAINTER_EXPORT_TARGET`.

## If dependency install fails

If an older or broken virtual environment was created, remove it and start again:

```bash
rm -rf backend/.venv
./start.sh
```

The backend intentionally uses `uvicorn` instead of `uvicorn[standard]` to avoid optional native build dependencies on older systems.

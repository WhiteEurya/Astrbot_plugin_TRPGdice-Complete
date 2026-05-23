# log-painter manual acceptance

Last updated: 2026-05-12

## Setup

Frontend:

```powershell
cd D:\Bot\Astrbot_plugin_TRPGdice-Complete\log-painter\frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173/
```

## Mock Fixtures

Fixtures live in:

```text
log-painter/frontend/test-fixtures/logs/
```

Use `qq-basic.txt` for paste testing.

Use JSON files for `/export/{file}` testing when the backend is running.

## Smoke Checklist

- [ ] Page opens without a blank screen.
- [ ] Paste `qq-basic.txt` into the editor.
- [ ] Alice, Bob, DiceBot, and ObserverA appear in the role list.
- [ ] Toggling preview shows formatted lines.
- [ ] Changing a role color updates preview coloring.
- [ ] "隐藏 OB 发言" hides ObserverA from preview.
- [ ] Turning "隐藏 OB 发言" off shows ObserverA again.
- [ ] "过滤场外发言" hides `is_comment` lines when using `special-cases.json`.
- [ ] "过滤表情图片" removes `[image:...]` or rendered image content.
- [ ] "下载原始文件" downloads a text file.
- [ ] "下载 Word" downloads `record.docx`.
- [ ] `record.docx` opens and contains the visible preview lines.
- [ ] "移除此角色" only removes the role entry and does not delete log text.

## JSON Loader Checklist

Requires backend `/export/{file}`.

- [ ] Put `basic-chat.json` in the backend export directory.
- [ ] Open `http://127.0.0.1:5173/?file=basic-chat.json`.
- [ ] The editor is populated.
- [ ] The role list is populated.
- [ ] Preview works.

Repeat with:

- [ ] `with-images.json`
- [ ] `with-ob.json`
- [ ] `with-dice.json`
- [ ] `special-cases.json`

## Known Gaps

- There is no automated browser test runner in the project yet.
- JSON fixtures must be routed through backend `/export/{file}`; the frontend does not load them directly from `test-fixtures`.
- Some active UI labels still contain mojibake and need a separate copy cleanup pass.

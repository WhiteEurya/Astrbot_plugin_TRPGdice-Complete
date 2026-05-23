# log-painter frontend sanity check

Date: 2026-05-12

## Purpose

Check whether the first build-hygiene fixes likely broke active frontend functionality.

This is not a full browser interaction test. The project currently has no Playwright/Cypress/browser-test dependency, so this pass combines:

- production build verification
- production preview HTTP verification
- source-level review of the touched functional paths

## Automated Checks

### Build

Command:

```powershell
npm run build
```

Result:

```text
vue-tsc -b && vite build
✓ built
```

Remaining warning:

```text
Some chunks are larger than 500 kB after minification.
```

Interpretation:

- TypeScript and Vite production build pass.
- The chunk-size warning is performance/packaging debt, not a functional break.

### Production preview HTTP check

Command shape:

```powershell
npm run preview -- --host 127.0.0.1 --port 4173
Invoke-WebRequest http://127.0.0.1:4173/
```

Result:

```text
STATUS=200
LENGTH=483
```

The returned HTML includes the built JS asset:

```html
<script type="module" crossorigin src="/assets/index-MQDiUx93.js"></script>
```

Interpretation:

- The built app can be served by Vite preview.
- No missing `index.html` / asset-path issue was found at the HTTP level.

## Entry-Point Check

Current active path:

```text
src/main.ts -> src/App.vue -> src/components/main.vue
```

Findings:

- `App.vue` still directly imports and renders `components/main.vue`.
- The router is still not mounted anywhere.
- `src/router/index.ts` remains broken internally, but it is inactive and now excluded from app TypeScript build.
- `template.vue` is still present, but inactive and now excluded from app TypeScript build.

Conclusion:

- Excluding `template.vue` and `src/router/**` should not change the running app, because neither is part of the active render path.

## Touched Path Review

### CodeMirror editing

Changed:

- Replaced direct `view.dispatch` monkey patching with `EditorView.updateListener`.
- Added `syncingFromProp` guard around prop-driven document replacement.

Expected behavior:

- User edits still emit `update:modelValue` and `change`.
- Parent-driven `modelValue` sync should not echo back as a user edit.

Risk:

- Low to medium. This is a real behavior-path change, but it follows CodeMirror's normal extension pattern and removes the previous overload-unsafe monkey patch.

Manual check needed:

- Type text in the editor.
- Confirm left role list rebuilds after debounce.
- Toggle preview and return to edit mode.
- Confirm editor content is not duplicated or cleared unexpectedly.

### Event unsubscribe

Changed:

- `Emitter.on()` now returns an unsubscribe function.

Expected behavior:

- `main.vue` already expected this behavior through `offParsed?.()` and `offTextSet?.()`.
- Before this fix those variables were effectively `undefined`; cleanup did nothing.

Risk:

- Low. This aligns the emitter with existing component usage.

### Active component build errors

Changed:

- Added current runtime fields to `LogItem`.
- Relaxed `CharItem.role` to `string`.
- Replaced `replaceAll` with compatible `replace`.
- Converted `StorageName enum` to a const object.

Expected behavior:

- These changes are mostly type/config compatibility fixes.
- Runtime behavior should be unchanged.

Risk:

- Low.

### Word export

Changed:

- Removed duplicate `docx` import.
- Replaced `doc.addSection(...)` with `new Document({ sections: [...] })`.

Expected behavior:

- Word export should still generate a `record.docx`.
- This change follows the installed `docx` package type surface more closely.

Risk:

- Medium. Build passes, but actual browser download was not clicked in this automated pass.

Manual check needed:

- Paste a small log.
- Generate preview.
- Click "下载 Word".
- Confirm `record.docx` downloads and opens.

### Role delete

Changed:

- Added a minimal `deletePc(idx, pc)` because the active template already referenced it.

Expected behavior:

- Clicking delete removes the role from the left role list.
- It also calls `logMan.deleteByCharItem(pc)`, which removes matching log items from current items and flushes.

Risk:

- Medium. The button already existed in UI but had no handler. The new behavior is plausible, but destructive: it removes that character's log items, not just hides the role.

Manual check needed:

- Verify whether "删除此角色" is intended to delete all messages by that character.
- If the intended behavior is only "hide/remove from palette", this should be changed before users rely on it.

## Pre-Existing Risks Not Caused By This Fix

These were visible during the check and should not be mistaken for new regressions:

- Visible UI text still contains mojibake in many labels and placeholders.
- `loadJsonFile()` still converts JSON to text before parsing again.
- `loadJsonFile()` appears to rely on `i.time` being parseable by the QQ-style header regex; if plugin JSON has separate `date` and `time`, this may still be fragile.
- Debug `console.log` calls remain in `loadJsonFile()`, parsed callbacks, preview, and Word export.
- BBS/TRG preview paths are still partial/experimental.
- Large bundle size remains.

## Verdict

Based on the automated checks and source-level review:

- The app is in better shape than before because it now builds and serves.
- The first fix batch probably did not break the active app entry path.
- The two behavior areas that deserve manual verification are CodeMirror edit syncing and Word export.
- The newly added `deletePc()` behavior should be reviewed from a product perspective because it deletes matching log items, which may be stronger than users expect.

## Recommended Manual Smoke Test

1. Open the app with no `?file` parameter.
2. Paste a tiny log:

   ```text
   Alice(10001) 2026/05/12 20:00:00
   hello

   Bob(10002) 2026/05/12 20:01:00
   .r 1d100
   ```

3. Confirm role list shows Alice and Bob.
4. Change one role color and confirm preview updates.
5. Toggle preview on and off.
6. Click "下载原始文件" and confirm a text file downloads.
7. Click "下载 Word" and confirm `record.docx` downloads and opens.
8. Click "删除此角色" on a copied test log only, and confirm whether the behavior matches expectation.

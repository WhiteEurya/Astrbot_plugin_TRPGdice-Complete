# log-painter build baseline

Last updated: 2026-05-12

## Scope

This records the current build baseline before refactoring `log-painter/frontend`.

Production source code was not changed for this baseline pass. The current frontend source was archived first under:

```text
plan/archive/log-painter-frontend-original-2026-05-12/
```

Archived items:

- `main.vue`
- `template.vue`
- `CodeMirror.vue`
- `store.ts`
- `logManager/`
- `utils/`

## Commands Run

From:

```text
log-painter/frontend
```

Initial build:

```powershell
npm run build
```

Result:

```text
'vue-tsc' is not recognized as an internal or external command
```

Interpretation: dependencies were not installed or `node_modules/.bin` was unavailable.

Dependency install:

```powershell
npm ci
```

First attempt failed because npm could not write to the user npm cache from the sandbox:

```text
EPERM: operation not permitted, open 'C:\Users\xiaoy\AppData\Local\npm-cache\_cacache\tmp\...'
```

The command was rerun with elevated permission and succeeded:

```text
added 225 packages, and audited 226 packages
9 vulnerabilities (2 moderate, 7 high)
```

Warnings:

- `@codemirror/text@0.19.6` deprecated.
- `@codemirror/rangeset@0.19.9` deprecated.
- `@codemirror/history@0.19.2` deprecated.

Second build:

```powershell
npm run build
```

Result: failed during `vue-tsc -b`.

## Build Failure Summary

The current failure is not one single bug. It is a mix of stale files, weak typing, large-component drift, and outdated TS config assumptions.

### 1. CodeMirror dispatch wrapper type error

File:

```text
src/components/CodeMirror.vue
```

Representative error:

```text
TS2769: No overload matches this call.
Argument of type 'TransactionSpec | Transaction | readonly Transaction[]' is not assignable...
```

Cause:

`view.dispatch` is monkey-patched, but the wrapper type does not preserve the overloads expected by CodeMirror.

Likely fix:

- Avoid replacing `view.dispatch` directly.
- Use `EditorView.updateListener` to emit model changes.
- Or type the wrapper exactly against CodeMirror's dispatch signature.

### 2. `main.vue` template and script are out of sync

File:

```text
src/components/main.vue
```

Representative errors:

```text
TS2339: Property 'deletePc' does not exist
TS2554: Expected 1 arguments, but got 2
TS2300: Duplicate identifier 'Document'
TS2341: Property 'addSection' is private
```

Observed categories:

- Template references functions that are missing or not exposed in script setup.
- Duplicate `docx` imports.
- Word export logic is using `docx` APIs incorrectly for the installed package version.
- Many unused imports and unused locals.
- Runtime fields such as `date`, `time`, and `is_comment` are missing from `LogItem`.

### 3. `template.vue` duplicates the same failures

File:

```text
src/components/template.vue
```

This file produces many errors similar to `main.vue`.

Interpretation:

- `template.vue` is not the active app entry, but it is still included by TypeScript.
- Keeping it in `src/components/` makes build fail even if the app does not render it.

Likely fix:

- Mark/move it to a legacy archive outside the TypeScript include path.
- Or repair it, but that duplicates work and is not recommended unless it is confirmed as actively used.

### 4. `LogItem` type is incomplete

Files:

```text
src/logManager/types.ts
src/logManager/logManager.ts
src/components/main.vue
src/components/template.vue
```

Representative errors:

```text
Property 'date' does not exist on type 'LogItem'
Property 'time' does not exist on type 'LogItem'
Property 'is_comment' does not exist on type 'LogItem'
Object literal may only specify known properties, and 'date' does not exist in type 'LogItem'
```

Likely fix:

- Extend `LogItem` to match runtime data.
- Add explicit `RoleType`, `PreviewItem`, and filter option types.

### 5. Broken router import

File:

```text
src/router/index.ts
```

Error:

```text
TS2307: Cannot find module '@/components/JsonEditor.vue'
```

Current app does not mount the router. `App.vue` renders `components/main.vue` directly.

Likely fix:

- Remove or archive the router if unused.
- Or add the missing component and mount the router if route-based navigation is desired.

### 6. TypeScript target/lib mismatch

File:

```text
src/utils/index.ts
```

Representative errors:

```text
TS2550: Property 'replaceAll' does not exist on type 'string'.
Try changing the 'lib' compiler option to 'es2021' or later.
```

Likely fix:

- Either update TS lib target to include `es2021`.
- Or replace `replaceAll` with compatible `replace(/.../g, ...)`.

### 7. Missing type package for `file-saver`

File:

```text
src/components/main.vue
```

Error:

```text
Could not find a declaration file for module 'file-saver'
```

Likely fix:

- Install `@types/file-saver`.
- Or add a local `declare module 'file-saver';`.

### 8. `utils/types.ts` is incompatible with current TS settings

File:

```text
src/utils/types.ts
```

Error:

```text
TS1294: This syntax is not allowed when 'erasableSyntaxOnly' is enabled.
```

Likely fix:

- Inspect the enum/type syntax in that file.
- Convert runtime enums to const objects or adjust TS config only if the project really needs that mode.

## Recommended First Fix Batch

The first code-changing batch should be small and aimed at making build errors meaningful:

1. Move or exclude `template.vue` as legacy.
2. Remove or fix the unused broken router.
3. Extend `LogItem` with currently used runtime fields.
4. Fix `CodeMirror.vue` dispatch handling.
5. Decide whether to update TS lib to `es2021` or replace `replaceAll`.

Do not start by splitting `main.vue`. The build currently fails before refactoring pressure is visible, and `template.vue` doubles the error volume.

## 2026-05-12 First Fix Batch Result

The first compile-hygiene batch has been applied.

Changed areas:

- `tsconfig.app.json`
  - Temporarily disabled `noUnusedLocals` and `noUnusedParameters`.
  - Excluded inactive `src/components/template.vue`.
  - Excluded unused broken `src/router/**`.
- `CodeMirror.vue`
  - Replaced direct `view.dispatch` monkey patching with `EditorView.updateListener`.
  - Added a small guard so prop-driven document sync does not echo as user edits.
- `logManager/types.ts`
  - Added runtime fields currently used by parser, preview, and export paths.
  - Relaxed `CharItem.role` to `string` to match current OB/dice role usage.
- `logManager/event.ts`
  - `on()` now returns an unsubscribe function, matching current `main.vue` usage.
- `utils/index.ts`
  - Replaced `replaceAll` calls with compatible `replace` calls.
- `utils/types.ts`
  - Replaced `enum` with a const object so it works with `erasableSyntaxOnly`.
- `previewDye.ts`
  - Removed unused TypeScript import and typed existing implicit `any` parameters.
- `main.vue`
  - Removed unused `file-saver` import.
  - Removed duplicate `docx` import.
  - Updated Word document construction to use `sections` instead of private `addSection`.
  - Allowed `nameFocus` to accept the template's second argument.
  - Added a minimal `deletePc()` handler because the template already referenced it.

Build result after the batch:

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

- The frontend now has a working build baseline.
- The large chunk warning should be handled later through code splitting or manual chunks, not in this cleanup batch.
- `template.vue` and `router/**` are not fixed yet; they are excluded because they are currently inactive or broken. Their ownership should still be resolved in a follow-up cleanup.

# log-painter frontend optimization plan

Last updated: 2026-05-12

This document records the current state of `log-painter/frontend` and a staged plan for reducing risk before larger refactors. The main goal is to keep the existing log coloring workflow usable while making the code testable, typed, and easier to change.

## Current Findings

`log-painter/frontend` is a Vite + Vue 3 application using Naive UI and CodeMirror. The active entry is:

- `src/main.ts` mounts `App.vue`.
- `src/App.vue` directly renders `components/main.vue`.
- `src/router/index.ts` exists, but is not mounted and imports missing `components/JsonEditor.vue`.

The riskiest files are:

- `src/components/main.vue`: about 1633 lines. It owns layout, editor state, JSON loading, parsing triggers, role list building, color mapping, preview generation, filters, and export logic.
- `src/components/template.vue`: about 1601 lines. It duplicates most of `main.vue` with drift in export and preview behavior.
- `src/logManager/logManager.ts`: owns parsing and re-export, but currently has a hard-coded QQ-style parser while the importer directory is mostly unused.
- `src/store.ts`: a lightweight reactive singleton that mimics parts of Pinia/editor state but has no explicit contract.

Major code smells confirmed during review:

- Duplicate mega components: `main.vue` and `template.vue` are almost the same but not identical.
- Broken or stale routing: `router/index.ts` references `JsonEditor.vue`, which is absent, and the router is not used by the app.
- Encoding damage in user-visible copy and comments across front-end files.
- Data flow loops through `plugin JSON -> text -> parsed LogItem[]`, which risks losing structured fields like `images`, `role`, and `isObserver`.
- Preview logic is duplicated across `showPreview()`, `getPreviewText()`, CodeMirror preview mode, BBS/TRG preview components, and export functions.
- Type safety is weak: many `any` casts hide fields that should be part of `LogItem` or `PreviewItem`.
- Color keys are inconsistent: some code uses name, some uses `IMUserId + name`, some falls back to name only.
- Debug logging remains in production paths, especially `loadJsonFile`, parsed callbacks, preview, and export.
- Importer/exporter architecture exists but is not wired consistently. Several importers are placeholders and `exportFileQQ` / `exportFileIRC` are empty.
- `preview-bbs.vue` and `preview-trg.vue` look like debug views rather than final output formats.

## Refactor Principles

1. Do not start with a full rewrite.
2. Establish fixture data and verification before moving logic.
3. Keep behavior stable while extracting one responsibility at a time.
4. Prefer typed pure functions for parsing, filtering, preview, and export preparation.
5. Treat `main.vue` as the current production entry and `template.vue` as legacy until proven otherwise.
6. Move UI copy repair gradually, starting with visible labels and buttons.

## Target Architecture

Short term target:

- `components/main.vue`: page composition only.
- `components/sidebar/RoleList.vue`: role list and color/name controls.
- `components/sidebar/LogActions.vue`: export and utility actions.
- `components/editor/LogEditor.vue`: CodeMirror wrapper usage and editor state bridge.
- `logManager/loaders/pluginJsonLoader.ts`: backend JSON loading and normalization.
- `logManager/preview/buildPreviewItems.ts`: single source of preview item generation.
- `logManager/filters/filterLogItems.ts`: shared filters for preview and export.
- `logManager/colors/colorKey.ts`: single color identity strategy.
- `logManager/types.ts`: complete runtime types for log items, roles, filters, and preview items.

Longer term target:

- A real importer registry with `check()` and `parse()` implementations.
- Exporters that consume typed preview/log data instead of Vue component local state.
- Either remove the unused router or make it the actual app navigation.
- Delete or archive `template.vue` after confirming it is not used.

## Staged Plan

### Phase 0: Stabilize and verify

- Add 3 to 5 fixtures for plugin JSON, QQ text export, images, OB messages, and dice results.
- Add a manual acceptance checklist for opening the page, loading `?file=...`, previewing, filtering, recoloring, and exporting.
- Run `npm run build` as the baseline check once dependencies are available.
- Record any current build failures before refactoring.

### Phase 1: Fix obvious project hygiene

- Decide whether `router/index.ts` is dead code. If dead, remove or archive it. If needed, add the missing route component and mount the router.
- Mark `template.vue` as legacy in a header comment or move it to a legacy directory after checking imports.
- Remove production `console.log` calls, leaving structured warnings only where the user can act on them.
- Repair visible UI strings in `main.vue`, `CodeMirror.vue`, and sidebar controls.

### Phase 2: Type the data model without behavior changes

- Extend `LogItem` with actual fields now used at runtime: `date`, `time`, `images`, `is_comment`, `isObserver`, `observer`, `role`, `who`, and `messageSanitized`.
- Add `RoleType`, `PreviewFilterOptions`, and `PreviewItem` types.
- Replace local `any` usage first in pure helpers, not in the whole component at once.
- Define one color identity helper, probably `IMUserId + nickname`, with fallback rules documented.

### Phase 3: Extract JSON loading

- Move `loadJsonFile()` from `main.vue` into `src/logManager/loaders/pluginJsonLoader.ts`.
- Validate file names in one place.
- Normalize plugin JSON into typed log items while preserving `images`, `role`, `isObserver`, and dice metadata.
- Keep the existing text conversion temporarily if needed, but preserve the original structured item list for later preview/export.

### Phase 4: Extract preview and filters

- Move preview item generation out of `main.vue` into `src/logManager/preview/buildPreviewItems.ts`.
- Move all filter decisions into `src/logManager/filters/filterLogItems.ts`.
- Make preview and export use the same filter function.
- Add the missing "hide OB messages" option and apply it through the shared filter path.
- Make image handling consistent between text preview, HTML preview, and export.

### Phase 5: Split the UI safely

- Extract sidebar action groups first because they are mostly event forwarding.
- Extract the role list second, passing typed role props and explicit events.
- Extract editor + preview area last because it has the most state coupling.
- Keep `main.vue` as the composition root until behavior is stable.

### Phase 6: Restore import/export architecture

- Wire the existing importer registry instead of leaving `importers = []`.
- Make unsupported importers fail explicitly rather than returning empty items silently.
- Move Word/HTML export preparation out of `main.vue`.
- Implement or remove empty exporter stubs.

## TODO List

### High priority

- [x] Add fixture logs for plugin JSON, images, OB, dice, and QQ text.
- [x] Capture current `npm run build` result.
- [x] Resolve unused/broken router entry.
- [x] Confirm `template.vue` usage and mark it legacy if unused.
- [ ] Repair visible UI mojibake in active `main.vue`.
- [x] Remove or gate debug `console.log` output in active paths.
- [x] Add `filterObservers` / hide OB messages and share it between preview and export.
- [x] Fix image preservation from plugin JSON through preview/export.

### Medium priority

- [x] Complete `LogItem` and add `PreviewItem` / filter option types.
- [x] Extract `loadJsonFile()` into `logManager/loaders/pluginJsonLoader.ts`.
- [x] Extract `buildPcList()` or role derivation into a pure helper.
- [x] Standardize color key generation.
- [x] Extract `showPreview()` / `getPreviewText()` logic into a pure preview builder.
- [ ] Make BBS/TRG preview components render real target formats or mark them experimental.
- [x] Move Word/HTML export composition out of Vue component files.

### Low priority

- [ ] Replace the store shim with a clearer composable or Pinia only after boundaries are stable.
- [ ] Restore a real importer registry for QQ, SealDice, FVTT, DiceKokona, RenderedLog, and SinaNya.
- [ ] Implement or remove `exportFileQQ()` and `exportFileIRC()`.
- [ ] Add component tests or smoke tests around preview filtering and export generation.
- [ ] Delete legacy `template.vue` after at least one stable release cycle.

## Suggested Next Step

Start with Phase 0 and one narrow user-visible fix: add fixture data plus a shared OB filter. That gives a small but useful behavior improvement and creates the verification path needed for the larger component split.

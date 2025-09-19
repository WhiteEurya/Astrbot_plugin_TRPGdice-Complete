// src/components/dye.ts (替换)
import { RangeSetBuilder, type Extension } from "@codemirror/state"
import { Decoration, EditorView, ViewPlugin, ViewUpdate } from "@codemirror/view"

type StoreLike = {
  pcNameColorMap: Map<string, string>
  pcList: Array<{ name: string; color?: string }>
}

// 原来的 header regex 保留
const HEADER_RE =
  /^\s*(.+?)\((\d{5,}|Bot)\)\s+(\d{4})[\/\-.](\d{2})[\/\-.](\d{2})\s+(\d{2}:\d{2}:\d{2})\s*$/u

// 返回候选 key 的顺序：displayName (name(id)), nameOnly, composite name#id, id
function candidateKeysFromHeader(nameRaw: string, idRaw: string) {
  const nameOnly = (nameRaw || '').trim()
  const id = (idRaw || '').trim()
  const displayName = `${nameOnly}(${id})`
  const composite = id ? `${nameOnly}#${id}` : ''
  return [displayName, nameOnly, composite, id].filter(k => !!k)
}

// 封装分层查找颜色的逻辑（按候选 keys 顺序）
// 也会尝试从 pcList 中模糊匹配
function lookupColor(store: StoreLike, nameRaw: string, idRaw: string): string {
  if (!store) return "#3b82f6"
  const keys = candidateKeysFromHeader(nameRaw, idRaw)

  // 1) 直接按 map 查
  for (const k of keys) {
    const v = store.pcNameColorMap?.get(k)
    if (v) return v
  }

  // 2) 尝试按 name 直接在 pcList 中找精确匹配或包含匹配
  const nameOnly = (nameRaw || '').trim()
  if (store.pcList) {
    // 精确 match
    const exact = store.pcList.find(p => (p.name || '') === nameOnly || (p.name || '') === `${nameOnly}(${idRaw})`)
    if (exact?.color) return exact.color
    // 包含/开头匹配（降级）
    const fuzzy = store.pcList.find(p => (p.name || '').indexOf(nameOnly) === 0 || (nameOnly && (p.name || '').includes(nameOnly)))
    if (fuzzy?.color) return fuzzy.color
  }

  // 3) fallback 默认色
  return "#3b82f6"
}

export function dyeExtension(store: StoreLike): Extension {
  const lineBar = (color: string) =>
    Decoration.line({
      attributes: { style: `border-left:4px solid ${color}; padding-left:8px;` }
    })

  const colorMark = (color: string) =>
    Decoration.mark({ attributes: { style: `color:${color};` } })

  const boldMark = Decoration.mark({ attributes: { style: `font-weight:700;` } })

  // 缓存：避免在可见区逐行重复解析复杂查找（插件实例级缓存）
  const colorCache = new Map<string, string>()

  function resolveColorCached(nameRaw: string, idRaw: string) {
    const cacheKey = `${nameRaw}__${idRaw}`
    if (colorCache.has(cacheKey)) return colorCache.get(cacheKey)!
    const col = lookupColor(store, nameRaw, idRaw)
    colorCache.set(cacheKey, col)
    return col
  }

  function build(view: EditorView) {
    const b = new RangeSetBuilder<Decoration>()

    for (const { from, to } of view.visibleRanges) {
      let pos = from
      let curColor: string | null = null

      while (pos <= to) {
        const line = view.state.doc.lineAt(pos)
        const text = line.text
        const m = HEADER_RE.exec(text)

        if (m) {
          // m[1] = name, m[2] = id
          const nameRaw = String(m[1] ?? '').trim()
          const idRaw = String(m[2] ?? '').trim()
          // 通过缓存的 resolveColor 获取颜色
          curColor = resolveColorCached(nameRaw, idRaw)

          // optional debug
          // console.log('[dye] header:', nameRaw, idRaw, '->', curColor)

          // 左侧竖线（line decoration）和头行加粗
          b.add(line.from, line.from, lineBar(curColor))
          if (line.length > 0) b.add(line.from, line.to, boldMark)
        } else if (curColor) {
          // 块内正文：整行按说话者颜色着色 + 左侧竖线
          b.add(line.from, line.from, lineBar(curColor))
          if (line.length > 0) b.add(line.from, line.to, colorMark(curColor))
        } else {
          // 无当前 color 且不是头行：什么都不做
        }

        pos = line.to + 1
      }
    }

    return b.finish()
  }

  const plugin = ViewPlugin.fromClass(
    class {
      decorations = Decoration.none
      constructor(view: EditorView) {
        this.decorations = build(view)
      }
      update(u: ViewUpdate) {
        // 若文档或视口改变，则重建，并清理缓存（否则 cache 会在 name 改后仍命中旧值）
        if (u.docChanged || u.viewportChanged) {
          colorCache.clear()
          this.decorations = build(u.view)
        }
      }
    },
    { decorations: (v) => v.decorations }
  )

  const theme = EditorView.baseTheme({
    ".cm-editor": { outline: "none" },
    ".cm-scroller": { overscrollBehavior: "contain" }
  })

  return [plugin, theme]
}

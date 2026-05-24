import { RangeSetBuilder, type Extension } from "@codemirror/state"
import { Decoration, EditorView, ViewPlugin, ViewUpdate } from "@codemirror/view"
import type { CharItem, PreviewFilters } from '../logManager/types'
import { rebuildColorMap, resolveColor } from '../logManager/roles/colorKey'

type StoreLike = {
  roles: CharItem[]
  filters?: PreviewFilters
}

const HEADER_RE =
  /^\s*(.+?)\((\d{5,}|Bot)\)\s+(\d{4})[\/\-.](\d{2})[\/\-.](\d{2})\s+(\d{2}:\d{2}:\d{2})\s*$/u

export function dyeExtension(store: StoreLike): Extension {
  const lineBar = (color: string) =>
    Decoration.line({
      attributes: { style: `border-left:4px solid ${color}; padding-left:8px;` }
    })

  const colorMark = (color: string) =>
    Decoration.mark({ attributes: { style: `color:${color};` } })

  const boldMark = Decoration.mark({ attributes: { style: `font-weight:700;` } })
  const hiddenMark = Decoration.replace({})
  const hiddenLine = Decoration.line({ attributes: { style: 'display:none' } })

  function addHeaderFilterMarks(
    b: RangeSetBuilder<Decoration>,
    lineFrom: number,
    text: string,
    match: RegExpExecArray,
    filters?: PreviewFilters
  ) {
    if (!filters) return
    const name = String(match[1] ?? '')
    const id = String(match[2] ?? '')
    const nameStart = text.indexOf(name)
    const accountStart = text.indexOf(`(${id})`, Math.max(0, nameStart + name.length))
    const accountEnd = accountStart >= 0 ? accountStart + id.length + 2 : -1

    if (filters.hideAccount && accountStart >= 0) {
      b.add(lineFrom + accountStart, lineFrom + accountEnd, hiddenMark)
    }

    if (accountEnd < 0) return
    const tail = text.slice(accountEnd)
    const dateTime = /(\s+)(\d{4}[\/\-.]\d{1,2}[\/\-.]\d{1,2})(\s+)(\d{1,2}:\d{2}:\d{2})/.exec(tail)
    if (!dateTime) return

    const dateStart = accountEnd + dateTime[1].length
    const dateEnd = dateStart + dateTime[2].length
    const timeStart = dateEnd + dateTime[3].length
    const timeEnd = timeStart + dateTime[4].length

    if (filters.hideDate) b.add(lineFrom + dateStart, lineFrom + dateEnd, hiddenMark)
    if (filters.hideTime) b.add(lineFrom + timeStart, lineFrom + timeEnd, hiddenMark)
  }

  function build(view: EditorView) {
    const b = new RangeSetBuilder<Decoration>()
    const colorMap = rebuildColorMap(store.roles || [])

    for (const { from, to } of view.visibleRanges) {
      let pos = from
      let curColor: string | null = null
      let curBlockHidden = false

      while (pos <= to) {
        const line = view.state.doc.lineAt(pos)
        const text = line.text
        const m = HEADER_RE.exec(text)

        if (m) {
          const nameRaw = String(m[1] ?? '').trim()
          const idRaw = String(m[2] ?? '').trim()
          curColor = resolveColor({ nickname: nameRaw, IMUserId: idRaw }, colorMap)
          curBlockHidden = Boolean(store.filters?.hideObservers && /\bOB\b|旁观|observer/i.test(nameRaw))

          b.add(line.from, line.from, lineBar(curColor))
          if (curBlockHidden) b.add(line.from, line.from, hiddenLine)
          if (line.length > 0) b.add(line.from, line.to, boldMark)
          addHeaderFilterMarks(b, line.from, text, m, store.filters)
        } else if (curColor) {
          b.add(line.from, line.from, lineBar(curColor))
          if (curBlockHidden || (store.filters?.hideOffTopic && /^[(（\[{【]/.test(text.trim()))) {
            b.add(line.from, line.from, hiddenLine)
          }
          if (line.length > 0) b.add(line.from, line.to, colorMark(curColor))
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
        if (u.docChanged || u.viewportChanged) {
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

import { Decoration, EditorView, ViewPlugin, ViewUpdate } from '@codemirror/view'
import { RangeSetBuilder } from '@codemirror/state'
import { isTemplateExpression } from 'typescript'

export function previewHighlightExtension(lines: any[], store) {
  return ViewPlugin.fromClass(class {
    decorations

    constructor(view: EditorView) {
      this.decorations = this.buildDeco(view)
    }

    update(update: ViewUpdate) {
      // 如果 lines 不变，可以不用重新计算
      this.decorations = this.buildDeco(update.view)
    }

    buildDeco(view: EditorView) {
      const builder = new RangeSetBuilder<Decoration>()
      let pos = 0

      for (let i = 0; i < lines.length; i++) {
        const lineObj = lines[i]
        const lineText = lineObj?.line ?? ""
        if (lineObj && !lineObj.is_comment) {
          const color = store.pcList.find(p => p.name === lineObj.nickname)?.color ?? null
          if (color) {
            builder.add(
              pos,
              pos + lineText.length,
              Decoration.mark({ attributes: { style: `color: ${color}` } })
            )
          }
        }
        pos += lineText.length + 1
      }

      return builder.finish()
    }
  }, { decorations: v => v.decorations })
}

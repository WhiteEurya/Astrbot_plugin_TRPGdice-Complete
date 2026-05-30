import type { PreviewFilters, PreviewItem } from '../types'
import { previewLine } from '../preview/buildPreviewItems'

function downloadBlob(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function escapeHtml(text: string) {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

export function exportPlainText(items: PreviewItem[], filters: PreviewFilters) {
  downloadBlob(
    'log-painter.txt',
    `${filters.exportTitle || 'TRPG Log Painter'}\n\n${items.map((item) => previewLine(item, filters)).join('\n\n')}`,
    'text/plain;charset=utf-8'
  )
}

export function exportHtml(items: PreviewItem[], filters: PreviewFilters) {
  const mode = filters.mode || 'record'
  const body = items
    .map((item) => {
      const meta = [
        filters.hideDate ? '' : item.date,
        filters.hideTime ? '' : item.time,
        filters.hideAccount ? '' : item.IMUserId
      ]
        .filter(Boolean)
        .join(' ')
      const images =
        filters.hideImages || !filters.exportImages || !item.images?.length
          ? ''
          : `<div class="imgs">${item.images
              .map((src) => `<img src="${escapeHtml(src)}" alt="" referrerpolicy="no-referrer" />`)
              .join('')}</div>`
      const colorStyle = filters.exportColors ? `style="--accent:${escapeHtml(item.color)}"` : ''
      const nameStyle = filters.exportColors ? `style="color:${escapeHtml(item.color)}"` : ''
      return `<article class="msg ${mode} ${escapeHtml(item.roleType || '')}" ${colorStyle}><header><strong ${nameStyle}>${escapeHtml(
        item.displayName
      )}</strong><span>${escapeHtml(meta)}</span></header><p>${escapeHtml(item.message).replaceAll('\n', '<br>')}</p>${images}</article>`
    })
    .join('\n')

  const title = filters.exportTitle || 'TRPG Log Painter'
  downloadBlob(
    'log-painter.html',
    `<!doctype html><meta charset="utf-8"><title>${escapeHtml(title)}</title><style>body{font-family:system-ui,sans-serif;line-height:1.6;padding:24px;background:#f7f9fe;color:#1f2937}.wrap{max-width:980px;margin:auto}h1{font-size:24px}.msg{--accent:#4f83ff;border-left:4px solid var(--accent);padding:10px 12px;margin:10px 0;background:#fff;border-radius:0 8px 8px 0;box-shadow:0 8px 24px rgba(31,41,55,.07)}.msg header{display:flex;gap:12px;align-items:baseline}.msg span{color:#777;font-size:12px}.msg p{white-space:normal;margin:6px 0 0}.script{border-left:0;border-bottom:1px solid #dfe7f3;box-shadow:none;border-radius:0}.script span{display:none}.骰子{background:#f1f5f9}.OB{opacity:.78;border-left-style:dashed}.imgs{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}.imgs img{max-width:320px;max-height:260px;object-fit:contain;border:1px solid #ddd;border-radius:8px;background:#fff}</style><main class="wrap"><h1>${escapeHtml(title)}</h1>${body}</main>`,
    'text/html;charset=utf-8'
  )
}

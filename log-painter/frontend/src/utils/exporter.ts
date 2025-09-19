import type { LogItem } from '../logManager/types'
function dl(name: string, mime: string, data: string){
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([data],{type:mime}))
  a.download = name; a.click(); URL.revokeObjectURL(a.href)
}
export function exportFileRaw(text: string){ dl('log.txt','text/plain;charset=utf-8', text) }
export function exportFileQQ(_items: LogItem[], _opt: any){}
export function exportFileIRC(_items: LogItem[], _opt: any){}
export function exportFileDoc(html: string){
  const payload = `<!doctype html><meta charset="utf-8"><body>${html}</body>`
  dl('log.html','text/html;charset=utf-8', payload)
}

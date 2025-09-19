// src/utils/msgFormatters.ts
export * from './types'

/** 计算文本宽度 */
export function getTextWidth(text: string, font: string): number {
  const canvas = (getTextWidth as any).canvas || ((getTextWidth as any).canvas = document.createElement('canvas'))
  const context = canvas.getContext('2d')!
  context.font = font
  return context.measureText(text).width
}

/** 获取元素字体 CSS 描述 */
function getCssStyle(el: any, prop: string) {
  return window.getComputedStyle(el, null).getPropertyValue(prop)
}

export function getCanvasFontSize(el = document.body) {
  const fontWeight = getCssStyle(el, 'font-weight') || 'normal'
  const fontSize = getCssStyle(el, 'font-size') || '16px'
  const fontFamily = getCssStyle(el, 'font-family') || 'Times New Roman'
  return `${fontWeight} ${fontSize} ${fontFamily}`
}

/** 图片处理 */
export function msgImageFormat(item: any, options: any, htmlText = false) {
  const images: string[] = item.images || []

  if (options.imageHide || !images.length) {
    return item.message || ''
  }

  let msg = item.message || ''

  if (htmlText) {
    // 把 images 拼接成 <img> 标签
    const imgs = images.map(src => `<img style="max-width:300px" src="${src}" />`).join(' ')
    msg = msg + (msg ? '\n' : '') + imgs
  }

  return msg
}

/** 场外发言处理 */
export function msgOffTopicFormat(msg: string, options: any, isDice = false) {
  if (options.offTopicHide && !isDice) {
    msg = msg.replaceAll(/^\s*(?:@\S+\s+)*[（\(].*/gm, '')
  }
  return msg
}

/** 指令处理 */
export function msgCommandFormat(msg: string, options: any) {
  if (options.commandHide) {
    msg = msg.replaceAll(/^[\.。\/](?![\.。\/])(.|\n)*$/g, '')
  }
  return msg
}

/** 用户ID/骰子处理 */
export function msgIMUseridFormat(msg: string, options: any, isDice = false) {
  if (isDice) {
    msg = msg.replaceAll('<', '')
    msg = msg.replaceAll('>', '')
  }
  return msg.trim()
}

/** @ 回复处理 */
export function msgAtFormat(msg: string, pcList: any[]) {
  for (const pc of pcList) {
    // QQ/Discord/Kook 都用统一的 @name 替换
    const patterns = [
      new RegExp(`\\[CQ:at,qq=${pc.IMUserId}\\]`, 'g'),
      new RegExp(`&lt;@${pc.IMUserId}&gt;`, 'g'),
      new RegExp(`\\(met\\)${pc.IMUserId}\\(met\\)`, 'g')
    ]
    for (const p of patterns) {
      msg = msg.replace(p, `@${pc.name}`)
    }
  }
  return msg
}

/** HTML 转义 */
export function escapeHTML(html: string) {
  const div = document.createElement('div')
  div.appendChild(document.createTextNode(html))
  return div.innerHTML
}

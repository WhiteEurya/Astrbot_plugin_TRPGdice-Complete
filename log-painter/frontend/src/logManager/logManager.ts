import { Emitter } from './event'
import type { LogItem, CharItem } from './types'
import { EditLogExporter } from './exporters/EditLogExporter'
import type { indexInfoListItem } from './exporters/logExporter'

type TextInfo = { items: LogItem[], startText?: string, exporter?: string }

/** 规范化：去 BOM、统一换行 */
function normalize(text: string) {
  return text.replace(/\uFEFF/g, '').replace(/\r\n/g, '\n')
}

/**
 * 消息头正则（QQ 导出的两行一条）：
 * 例：海豹一号机(2589922907) 2022/03/21 19:05:05
 * 说明：
 *  - 名字允许广义字符（尽量宽松，必要时可收紧）
 *  - QQ 号捕获为连续 5+ 位数字
 *  - 日期分隔符 / - . 均可
 */
const HEADER_RE =
  /^\s*(.+?)\((\d+|Bot)\)\s+(\d{4})[\/\-.](\d{2})[\/\-.](\d{2})\s+(\d{2}:\d{2}:\d{2})\s*$/u

export class LogManager {
  ev = new Emitter<{ 'textSet': (text: string) => void, 'parsed': (ti: any) => void }>(this)

  /** 不再使用外部 importers（保留空数组避免其他模块误用） */
  importers: Array<[string, any]> = []

  exporters = { editLog: new EditLogExporter() }

  lastText = ''
  curItems: LogItem[] = []
  lastIndexInfoList: indexInfoListItem[] = []
  working = false

  /** 改名：沿用你的逻辑（根据 nickname + IMUserId 匹配） */
  rename(item: CharItem, lastPCName: string, name: string) {
    // item.name / lastPCName / name 现在是纯用户名
    const nameTagRegex = new RegExp(`^<${lastPCName}>`)
    for (const i of this.curItems) {
      // 以 IMUserId 和 nickname 匹配（nickname 为纯用户名）
      if (item.IMUserId === (i as any).IMUserId && lastPCName === (i as any).nickname) {
        (i as any).nickname = name
      }
      // 只替换开头的 <旧名> -> <新名>
      i.message = i.message.replace(nameTagRegex, `<${name}>`)
    }
    this.flush()
  }


  deleteByCharItem(item: CharItem) {
    // 按 IMUserId + nickname (纯用户名) 删除
    this.curItems = this.curItems.filter(
      i => !((item.IMUserId === (i as any).IMUserId) && (item.name === (i as any).nickname))
    )
    this.flush()
  }

  /**
   * ✨ 直接内置“QQ 两行一条”解析逻辑
   * 结构：
   *   头部：  用户名(QQ) yyyy/MM/dd HH:mm:ss
   *   内容：  后续若干行，直至下一个头部（或文件末尾）
   * 生成：
   *   message: `<用户名(QQ)> 内容`   <-- 保持兼容（头行格式）
   *   (any) nickname = 用户名         <-- 纯用户名（不含括号）
   *   (any) IMUserId = QQ
   *   (any) time     = `YYYY-MM-DD HH:mm:ss`
   */
parse(text: string, genFakeHeadItem = false): TextInfo | undefined {
  const raw = normalize(text)
  const lines = raw.split('\n')

  type Pending = {
    name: string          // 纯用户名（不包含括号/ID）
    uin: string           // QQ 号
    datetime: string
    buf: string[]
  }

  const items: LogItem[] = []
  let startText: string | undefined
  let cur: Pending | null = null

  const flushCurrent = () => {
    if (!cur) return

    const content = cur.buf.join('\n').trimEnd() // ✅ 只保留消息内容

    // 原逻辑判断是否骰子
    const isBotDice = /\(Bot\)$/i.test(cur.name)
    const isDice = isBotDice

    // 新增 role 字段
    const role = isDice ? 'dice' : '角色'

    // 新增 is_comment 字段：整句被括号包围
    const is_comment = /^[(（\[{【][\s\S]+[)\]}\]】]$/.test(content.trim())

    // 拆分日期和时间
    const [date, time] = cur.datetime.split(' ') // cur.datetime 原始是 'YYYY-MM-DD HH:mm:ss'

    const item: LogItem = {
      isRaw: false,
      isDice,
      message: content,       // ✅ 只包含消息内容
      nickname: cur.name.trim(),
      IMUserId: cur.uin,
      date,                   // 新增字段
      time,                   // 保留原 time
      role,
      is_comment
    }

    items.push(item)
    cur = null
  }

  for (let i = 0; i < lines.length; i++) {
    const s = lines[i]
    const m = HEADER_RE.exec(s)
    if (m) {
      flushCurrent()
      const [, nameRaw, uin, y, mo, d, tim] = m
      const nameOnly = nameRaw.trim()
      cur = {
        name: nameOnly,
        uin: uin.trim(),
        datetime: `${y}-${mo}-${d} ${tim}`,
        buf: []
      }
      continue
    }

    if (cur) {
      cur.buf.push(s)
    } else if (s.trim()) {
      if (!startText) startText = s.trim()
    }
  }

  flushCurrent()

  if (genFakeHeadItem && startText) {
    items.unshift({ isRaw: true, message: startText } as LogItem)
  }

  const ret: TextInfo = { items, startText, exporter: 'editLog' }
  this.ev.emit('parsed', ret as any)
  return ret
}


  /** 导出为 EditLog 文本并通知编辑器（与原逻辑一致） */
  flush() {
    const ret = this.exporters.editLog.doExport(this.curItems)
    if (ret) {
      const { text, indexInfoList } = ret
      this.lastText = text
      this.lastIndexInfoList = indexInfoList
      this.ev.emit('textSet', text)
    }
  }

  /**
   * 编辑器文本变更 → 全量重解析（先保证正确，后续可做区间优化）
   * r1 / r2 只是为兼容原签名，这里不使用
   */
  syncChange(curText: string, r1: number[], r2: number[]) {
    void r1; void r2;
    if (curText === this.lastText) return
    if (this.working) return
    this.working = true

    if (!this.lastText) {
      const info = this.parse(curText, true)
      if (info) {
        this.curItems = info.items
        const ret = this.exporters.editLog.doExport(info.items)
        if (ret) {
          const { text, indexInfoList } = ret
          this.lastText = text
          this.lastIndexInfoList = indexInfoList
          this.ev.emit('textSet', text)
        }
      }
      this.working = false
      return
    }

    // 简化实现：直接全量重解析
    const info = this.parse(curText, true)
    if (info) {
      this.curItems = info.items
      const ret = this.exporters.editLog.doExport(info.items)
      if (ret) {
        const { text, indexInfoList } = ret
        this.lastText = text
        this.lastIndexInfoList = indexInfoList
        this.ev.emit('textSet', text)
      }
    }
    this.working = false
  }
}

export const logMan = new LogManager()
// 便于开发时在控制台访问
setTimeout(() => { (globalThis as any).logMan = logMan }, 1000)

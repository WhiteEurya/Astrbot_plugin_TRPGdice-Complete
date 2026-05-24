import type { LogItem } from './types'

const HEADER_RE =
  /^\s*(.+?)\((\d{5,}|Bot|OB|Observer)\)\s+(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})\s+(\d{1,2}:\d{2}:\d{2})\s*$/u

function pad2(value: string) {
  return value.padStart(2, '0')
}

function normalizeText(text: string) {
  return text.replace(/\uFEFF/g, '').replace(/\r\n?/g, '\n')
}

function isOffTopic(message: string) {
  const trimmed = message.trim()
  return /^[(（\[{【][\s\S]*[)）\]}】]$/.test(trimmed)
}

function isObserverName(name: string, message: string) {
  return /\bOB\b|旁观|observer/i.test(name) || /^[-=]*\s*OB\s*[:：]/i.test(message)
}

function extractImages(message: string) {
  const images: string[] = []
  const cqImageRe = /\[CQ:image,[^\]]*(?:url|file)=([^,\]]+)[^\]]*\]/giu
  let match: RegExpExecArray | null
  while ((match = cqImageRe.exec(message))) {
    const value = decodeURIComponent(match[1] || '').trim()
    if (value) images.push(value)
  }

  const markdownImageRe = /!\[[^\]]*\]\(([^)]+)\)/gu
  while ((match = markdownImageRe.exec(message))) {
    const value = (match[1] || '').trim()
    if (value) images.push(value)
  }

  const urlImageRe = /((?:https?:\/\/[^\s"'<>]+?\.(?:png|jpe?g|gif|webp|bmp)(?:\?[^\s"'<>]*)?)|(?:data:image\/[a-z0-9.+-]+[^\s"'<>]*))/giu
  while ((match = urlImageRe.exec(message))) {
    const value = (match[1] || '').trim()
    if (value) images.push(value)
  }

  return Array.from(new Set(images))
}

function stripImageLinks(message: string) {
  return message
    .replace(/\[CQ:image,[^\]]*(?:url|file)=[^,\]]+[^\]]*\]/giu, '')
    .replace(/!\[[^\]]*\]\([^)]+\)/gu, '')
    .replace(
      /((?:https?:\/\/[^\s"'<>]+?\.(?:png|jpe?g|gif|webp|bmp)(?:\?[^\s"'<>]*)?)|(?:data:image\/[a-z0-9.+-]+[^\s"'<>]*))/giu,
      ''
    )
    .split('\n')
    .map((line) => line.trimEnd())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export function parseLogText(text: string): LogItem[] {
  const lines = normalizeText(text).split('\n')
  const items: LogItem[] = []
  let current:
    | {
        name: string
        id: string
        date: string
        time: string
        rawHeader: string
        body: string[]
      }
    | null = null

  const flush = () => {
    if (!current) return
    const rawMessage = current.body.join('\n').trimEnd()
    if (!rawMessage.trim()) {
      current = null
      return
    }
    const isDice = current.id === 'Bot' || /骰|dice|bot/i.test(current.name)
    const images = extractImages(rawMessage)
    const message = images.length ? stripImageLinks(rawMessage) : rawMessage
    items.push({
      id: `${items.length}`,
      index: items.length,
      nickname: current.name,
      IMUserId: current.id,
      date: current.date,
      time: current.time,
      rawHeader: current.rawHeader,
      message,
      isDice,
      isObserver: isObserverName(current.name, message),
      isComment: isOffTopic(message),
      images
    })
    current = null
  }

  for (const line of lines) {
    const match = HEADER_RE.exec(line)
    if (match) {
      flush()
      const [, name, id, year, month, day, time] = match
      current = {
        name: name.trim(),
        id: id.trim(),
        date: `${year}-${pad2(month)}-${pad2(day)}`,
        time,
        rawHeader: line,
        body: []
      }
      continue
    }

    if (current) {
      current.body.push(line)
    } else if (line.trim()) {
      items.push({
        id: `${items.length}`,
        index: items.length,
        nickname: '未识别',
        message: line,
        isRaw: true
      })
    }
  }

  flush()
  return items
}

export function serializeLogItems(items: LogItem[]) {
  return items
    .map((item) => {
      if (item.isRaw) return item.message
      const id = item.IMUserId || 'unknown'
      const date = item.date?.replaceAll('-', '/') || '0000/00/00'
      const time = item.time || '00:00:00'
      return `${item.nickname}(${id}) ${date} ${time}\n${item.message}`
    })
    .join('\n\n')
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function renameLogSpeaker(text: string, oldName: string, id: string, newName: string) {
  const safeOldName = escapeRegExp(oldName.trim())
  const safeId = escapeRegExp(id.trim())
  if (!safeOldName || !safeId || !newName.trim()) return text

  const header = new RegExp(
    `(^|\\n)[ \\t]*${safeOldName}\\(${safeId}\\)([ \\t]+\\d{4}[\\/\\-.]\\d{1,2}[\\/\\-.]\\d{1,2}[ \\t]+\\d{1,2}:\\d{2}:\\d{2}[ \\t]*)`,
    'gu'
  )
  return text.replace(header, (_match, prefix: string, suffix: string) => `${prefix}${newName.trim()}(${id})${suffix}`)
}

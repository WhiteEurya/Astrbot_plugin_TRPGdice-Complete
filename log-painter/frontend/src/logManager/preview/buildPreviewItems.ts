import type { CharItem, LogItem, PreviewFilters, PreviewItem } from '../types'
import { findRole, resolveColor, rebuildColorMap, roleKeyOf } from '../roles/colorKey'

export function applyFilters(items: LogItem[], filters: PreviewFilters, roles: CharItem[] = []) {
  return items.filter((item) => {
    const role = findRole(item, roles)
    const roleType = role?.role
    if (roleType === '隐藏') return false
    if (filters.hideObservers && (item.isObserver || roleType === 'OB')) return false
    if (filters.hideOffTopic && item.isComment) return false
    if (filters.roleKey && roleKeyOf(item) !== filters.roleKey) return false
    const query = filters.query.trim().toLowerCase()
    if (query) {
      const haystack = `${role?.name || item.nickname} ${item.nickname} ${item.IMUserId || ''} ${item.message}`.toLowerCase()
      if (!haystack.includes(query)) return false
    }
    return true
  })
}

export function buildPreviewItems(
  items: LogItem[],
  roles: CharItem[],
  filters: PreviewFilters
): PreviewItem[] {
  const colorMap = rebuildColorMap(roles)
  return applyFilters(items, filters, roles).map((item) => {
    const role = findRole(item, roles)
    const roleType = role?.role
    const diceResult = /大成功|大失败|成功|失败|极难成功|困难成功/i.exec(item.message)?.[0]
    return {
      ...item,
      roleType,
      diceResult,
      displayName: role?.name || item.nickname,
      color: resolveColor(item, colorMap, item.isDice || roleType === '骰子' ? '#7a7f8a' : '#4f83ff')
    }
  })
}

export function previewLine(item: PreviewItem, filters: PreviewFilters) {
  const meta = [
    filters.hideDate ? '' : item.date,
    filters.hideTime ? '' : item.time,
    filters.hideAccount ? '' : item.IMUserId ? `(${item.IMUserId})` : ''
  ]
    .filter(Boolean)
    .join(' ')

  return `${item.displayName}${meta ? ` ${meta}` : ''}\n${item.message}`
}

export function previewMeta(item: PreviewItem, filters: PreviewFilters) {
  return [
    filters.hideDate ? '' : item.date,
    filters.hideTime ? '' : item.time,
    filters.hideAccount ? '' : item.IMUserId ? `(${item.IMUserId})` : ''
  ]
    .filter(Boolean)
    .join(' ')
}

import randomColor from 'randomcolor'
import type { CharItem, LogItem, RoleType } from '../types'
import { roleKeyOf } from './colorKey'

function roleOf(item: LogItem): RoleType {
  if (item.isObserver) return 'OB'
  if (item.isDice) return '骰子'
  return '角色'
}

export function deriveRoles(items: LogItem[], previous: CharItem[]) {
  const old = new Map(previous.map((role) => [role.key || roleKeyOf(role), role]))
  const roles = new Map<string, CharItem>()

  for (const item of items) {
    if (item.isRaw || !item.nickname) continue
    const key = roleKeyOf(item)
    const existing = old.get(key)
    roles.set(key, {
      key,
      name: existing?.name || item.nickname,
      originalName: item.nickname,
      IMUserId: item.IMUserId || '',
      role: existing?.role || roleOf(item),
      color:
        existing?.color ||
        randomColor({
          luminosity: 'dark',
          seed: key
        })
    })
  }

  return Array.from(roles.values())
}

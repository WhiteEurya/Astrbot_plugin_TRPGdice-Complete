import type { CharItem, LogItem } from '../types'

type ColorIdentity =
  | Pick<LogItem, 'nickname' | 'IMUserId'>
  | Pick<CharItem, 'name' | 'originalName' | 'IMUserId'>

export function colorKeyOf(input: ColorIdentity) {
  const name = 'nickname' in input ? input.nickname : input.originalName || input.name
  return `${(name || '').trim()}#${(input.IMUserId || '').trim()}`
}

export function colorCandidates(input: ColorIdentity) {
  const name = ('nickname' in input ? input.nickname : input.originalName || input.name || '').trim()
  const id = (input.IMUserId || '').trim()
  return [colorKeyOf(input as any), name, id, `${name}(${id})`].filter(Boolean)
}

export function roleKeyOf(input: ColorIdentity) {
  return colorKeyOf(input)
}

export function findRole(
  item: Pick<LogItem, 'nickname' | 'IMUserId'>,
  roles: CharItem[]
) {
  const key = roleKeyOf(item)
  const role = roles.find((itemRole) => (itemRole.key || roleKeyOf(itemRole)) === key)
  if (!role?.mergedIntoKey) return role
  return roles.find((itemRole) => (itemRole.key || roleKeyOf(itemRole)) === role.mergedIntoKey) || role
}

export function resolveColor(
  item: Pick<LogItem, 'nickname' | 'IMUserId'>,
  colorMap: Map<string, string>,
  fallback = '#4f83ff'
) {
  for (const key of colorCandidates(item)) {
    const color = colorMap.get(key)
    if (color) return color
  }
  return fallback
}

export function rebuildColorMap(roles: CharItem[]) {
  const map = new Map<string, string>()
  for (const role of roles) {
    for (const key of colorCandidates(role)) {
      if (role.color) map.set(key, role.color)
    }
  }
  return map
}

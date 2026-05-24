export type RoleType = '主持人' | '角色' | '骰子' | 'OB' | '其他' | '隐藏'
export type PreviewMode = 'record' | 'script'

export interface LogItem {
  id?: string
  nickname: string
  message: string
  rawHeader?: string
  isRaw?: boolean
  isDice?: boolean
  isObserver?: boolean
  isComment?: boolean
  is_comment?: boolean
  index?: number
  IMUserId?: string
  date?: string
  time?: string
  color?: string
  role?: RoleType | string
  images?: string[]
}

export interface CharItem {
  key?: string
  name: string
  originalName?: string
  IMUserId: string
  role: RoleType
  color?: string
  mergedIntoKey?: string
}

export interface PreviewItem extends LogItem {
  displayName: string
  color: string
  roleType?: RoleType
  diceResult?: string
}

export interface PreviewFilters {
  hideImages: boolean
  hideOffTopic: boolean
  hideDate: boolean
  hideTime: boolean
  hideAccount: boolean
  hideObservers: boolean
  query: string
  roleKey: string
  mode: PreviewMode
  exportTitle: string
  exportImages: boolean
  exportColors: boolean
}

export function packNameId(i: Pick<LogItem, 'nickname' | 'IMUserId'>) {
  return `${i.nickname}#${i.IMUserId ?? ''}`
}

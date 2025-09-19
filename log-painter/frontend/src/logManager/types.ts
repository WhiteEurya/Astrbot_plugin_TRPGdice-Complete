export interface LogItem {
  nickname: string
  message: string
  isRaw?: boolean
  isDice?: boolean
  index?: number
  IMUserId?: string
  color?: string
}
export interface CharItem {
  name: string
  IMUserId: string
  role: '主持人'|'角色'|'骰子'|'隐藏'
  color?: string
}
export function packNameId(i: LogItem){
  return `${i.nickname}#${i.IMUserId ?? ''}`
}

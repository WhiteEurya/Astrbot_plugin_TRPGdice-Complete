type Handler<T> = (payload: T) => void
export class Emitter<TMap extends Record<string, (...a:any)=>any>>{
  private map = new Map<keyof TMap, Set<Handler<any>>>()
  constructor(_this?: any){}
  on<K extends keyof TMap>(e: K, fn: TMap[K]){
    if(!this.map.has(e)) this.map.set(e, new Set()); this.map.get(e)!.add(fn as any)
  }
  emit<K extends keyof TMap>(e: K, ...args: Parameters<TMap[K]>){
    this.map.get(e)?.forEach(fn => (fn as any)(...args))
  }
}

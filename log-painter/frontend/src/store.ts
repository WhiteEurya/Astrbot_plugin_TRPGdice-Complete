import { reactive } from 'vue'
import type { CharItem } from './logManager/types'

const state = reactive({
  pcList: [] as CharItem[],
  pcMap: new Map<string, CharItem>(),
  pcNameColorMap: new Map<string, string>(),
  exportOptions: reactive({ offTopicHide: false, imageHide: false }),
  doEditorHighlight: false,
  editor: {
    state: {
      doc: {
        _text: '',
        get length(){ return this._text.length },
        toString(){ return this._text }
      }
    },
    dispatch({ changes }: any){
      const { from, to, insert } = changes
      const cur = (this.state.doc as any)._text
      ;(this.state.doc as any)._text = cur.slice(0, from) + insert + cur.slice(to)
    }
  }
})

export function useStore(){
  return {
    ...state,
    colorMapLoad(){},
    colorMapSave(){},
    updatePcList(m: Map<string, CharItem>){
      state.pcMap = m
      state.pcList = Array.from(m.values())
    },
    async tryFetchLog(_key: string, _password: string){
      throw new Error('remote disabled in local scaffold')
    },
    reloadEditor(){},
  }
}

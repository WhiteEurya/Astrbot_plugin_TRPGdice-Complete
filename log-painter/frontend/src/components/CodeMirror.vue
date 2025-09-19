<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import type { Extension } from '@codemirror/state'
import { EditorState, Compartment } from '@codemirror/state'
import {
  EditorView,
  lineNumbers,
  highlightActiveLineGutter,
  highlightActiveLine,
  keymap,
  placeholder as cmPlaceholder
} from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'

const props = withDefaults(defineProps<{
  modelValue: string
  showLineNumbers?: boolean
  lineWrapping?: boolean
  readOnly?: boolean
  placeholder?: string
  extraExtensions?: Extension[]
  autofocus?: boolean
  preview?: boolean
}>(), {
  modelValue: '',
  showLineNumbers: true,
  lineWrapping: true,
  readOnly: false,
  placeholder: '在这里粘贴聊天记录…',
  extraExtensions: () => [],
  autofocus: false,
  preview: false
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
  (e: 'change', v: string): void
  (e: 'ready', view: EditorView): void
}>()

const root = ref<HTMLDivElement | null>(null)
let view: EditorView | null = null

// —— 可动态重配的 compartments —— 
const guttersComp = new Compartment()
const wrapComp = new Compartment()
const editableComp = new Compartment()
const placeholderComp = new Compartment()
const extraComp = new Compartment() // ⬅️ 承载染色等扩展

// —— 透明背景，保持现有视觉 —— 
const transparentTheme = EditorView.theme({
  '&': { backgroundColor: 'transparent' },
  '.cm-scroller': { backgroundColor: 'transparent' }
})

// —— 预览模式主题 —— 
const previewTheme = EditorView.theme({
  '.cm-cursor': { display: 'none' },
  '&': { backgroundColor: '#f9f9f9' },
  '.cm-scroller': { backgroundColor: '#f9f9f9' }
})

const isPreview = ref(props.preview)

onMounted(async () => {
  if (!root.value) return

  const baseExt: Extension[] = [
    history(),
    highlightActiveLine(),
    guttersComp.of(props.showLineNumbers ? [lineNumbers(), highlightActiveLineGutter()] : []),
    wrapComp.of(props.lineWrapping ? EditorView.lineWrapping : []),
    editableComp.of(EditorView.editable.of(!props.readOnly && !isPreview.value)),
    placeholderComp.of(cmPlaceholder(props.placeholder)),
    transparentTheme,
    keymap.of([...defaultKeymap, ...historyKeymap]),
    // 用 compartment 包住，后续可热更新
    extraComp.of([...(props.extraExtensions ?? []), ...(isPreview.value ? [previewTheme] : [])])
  ]

  view = new EditorView({
    parent: root.value,
    state: EditorState.create({
      doc: props.modelValue ?? '',
      extensions: baseExt
    })
  })

  // 透传 v-model & change
  const orig = view.dispatch.bind(view)
  view.dispatch = (tr) => {
    const prev = view!.state.doc.toString()
    orig(tr)
    const cur = view!.state.doc.toString()
    if (cur !== prev) {
      emit('update:modelValue', cur)
      emit('change', cur)
    }
  }

  emit('ready', view)
  if (props.autofocus) { await nextTick(); view.focus() }
})

onBeforeUnmount(() => { view?.destroy(); view = null })

// —— v-model 同步 —— 
watch(() => props.modelValue, (val) => {
  if (!view) return
  const cur = view.state.doc.toString()
  if (val !== cur) {
    // 保存当前选区
    const selection = view.state.selection

    // 更新文档，同时保持光标和滚动位置
    view.dispatch({
      changes: { from: 0, to: cur.length, insert: val ?? '' },
      selection,          // 保持光标
      scrollIntoView: true // 保持滚动位置
    })
  }
})

// —— 动态配置 compartments —— 
watch(() => props.showLineNumbers, (v) => {
  if (!view) return
  view.dispatch({ effects: guttersComp.reconfigure(v ? [lineNumbers(), highlightActiveLineGutter()] : []) })
})
watch(() => props.lineWrapping, (v) => {
  if (!view) return
  view.dispatch({ effects: wrapComp.reconfigure(v ? EditorView.lineWrapping : []) })
})
watch([() => props.readOnly, isPreview], ([readOnly, preview]) => {
  if (!view) return
  view.dispatch({ effects: editableComp.reconfigure(EditorView.editable.of(!readOnly && !preview)) })
})
watch(() => props.placeholder, (v) => {
  if (!view) return
  view.dispatch({ effects: placeholderComp.reconfigure(cmPlaceholder(v)) })
})
watch(() => props.extraExtensions, (exts) => {
  if (!view) return
  const extsToApply = [...(exts ?? []), ...(isPreview.value ? [previewTheme] : [])]
  view.dispatch({ effects: extraComp.reconfigure(extsToApply) })
}, { deep: true })

watch(() => props.preview, (v) => {
  isPreview.value = v
})

// —— 动态切换预览模式 —— 
watch(isPreview, (v) => {
  if (!view) return
  view.dispatch({
    effects: editableComp.reconfigure(EditorView.editable.of(!v))
  })
})

// 暴露便捷方法
defineExpose({
  focus() { view?.focus() },
  getView() { return view },
  setPreview(preview: boolean) { isPreview.value = preview },
  reconfigureExtra(exts: Extension[] = []) {
    if (!view) return
    const extsToApply = [...exts, ...(isPreview.value ? [previewTheme] : [])]
    view.dispatch({ effects: extraComp.reconfigure(extsToApply) })
  }
})
</script>

<template>
  <div ref="root" class="cm-root"></div>
</template>

<style scoped>
.cm-root { height: 100%; }
:deep(.cm-gutters){
  background: transparent !important;
  border-right: 1px solid rgba(0,0,0,.08) !important;
}
:deep(.cm-lineNumbers){
  min-width: 2.5em;
  text-align: right;
  opacity: .65;
}
:global(.dark) :deep(.cm-gutters){
  border-right-color: rgba(255,255,255,.12) !important;
}
</style>

<script setup lang="ts">
import { ref } from 'vue'
import type { Extension } from '@codemirror/state'
import CodeMirror from './CodeMirror.vue'
import type { PreviewFilters, PreviewItem } from '../logManager/types'
import { previewMeta } from '../logManager/preview/buildPreviewItems'

defineProps<{
  modelValue: string
  extensions: Extension[]
  previewItems: PreviewItem[]
  filters: PreviewFilters
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const zoomImage = ref('')

function itemClass(item: PreviewItem) {
  return [
    'preview-item',
    `mode-${item.roleType || '角色'}`,
    {
      dice: item.roleType === '骰子' || item.isDice,
      observer: item.roleType === 'OB' || item.isObserver,
      comment: item.isComment,
      keeper: item.roleType === '主持人'
    }
  ]
}
</script>

<template>
  <main class="workspace">
    <section class="editor-shell">
      <header>
        <div>
          <h1>source.log</h1>
          <span>CodeMirror editor</span>
        </div>
      </header>
      <div class="editor-body">
        <CodeMirror
          :model-value="modelValue"
          :extra-extensions="extensions"
          :show-line-numbers="true"
          :line-wrapping="true"
          @update:model-value="emit('update:modelValue', $event)"
        />
      </div>
    </section>

    <section class="preview-shell">
      <header>
        <div>
          <h2>preview.html</h2>
          <span>{{ previewItems.length }} rendered blocks</span>
        </div>
      </header>
      <div class="preview-list" :class="`preview-${filters.mode}`">
        <article v-for="item in previewItems" :key="item.id" :class="itemClass(item)" :style="{ '--accent': item.color }">
          <div class="preview-head">
            <strong>{{ item.displayName }}</strong>
            <b v-if="item.diceResult" class="dice-badge">{{ item.diceResult }}</b>
            <span>{{ previewMeta(item, filters) }}</span>
          </div>
          <p v-if="item.message">{{ item.message }}</p>
          <div v-if="!filters.hideImages && item.images?.length" class="preview-images">
            <button v-for="src in item.images" :key="src" type="button" @click="zoomImage = src">
              <img :src="src" alt="" />
            </button>
          </div>
        </article>
      </div>
    </section>

    <div v-if="zoomImage" class="image-lightbox" @click.self="zoomImage = ''">
      <button type="button" class="close-lightbox" @click="zoomImage = ''">关闭</button>
      <img :src="zoomImage" alt="" />
    </div>
  </main>
</template>

<style scoped>
.workspace {
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(340px, .95fr);
  gap: 12px;
  padding: 12px;
  box-sizing: border-box;
}
.editor-shell, .preview-shell {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, .68);
  border-radius: 10px;
  background: rgba(255, 255, 255, .5);
  backdrop-filter: blur(22px) saturate(1.22);
  box-shadow: 0 18px 42px rgba(75, 98, 150, .11);
}
header {
  min-height: 44px;
  display: flex;
  align-items: center;
  padding: 8px 13px;
  border-bottom: 1px solid rgba(255, 255, 255, .66);
  background: rgba(255, 255, 255, .42);
}
h1, h2 {
  margin: 0;
  color: #25324a;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.1;
}
header span {
  color: #718096;
  font-size: 11px;
}
.editor-body { flex: 1 1 auto; min-height: 0; }
.preview-list {
  overflow: auto;
  padding: 12px 14px 20px;
  background:
    linear-gradient(90deg, rgba(79, 110, 247, .05) 1px, transparent 1px),
    linear-gradient(180deg, rgba(251,253,255,.6) 0%, rgba(255,255,255,.32) 100%);
  background-size: 28px 28px, auto;
}
.preview-item {
  border-left: 4px solid var(--accent);
  padding: 10px 12px;
  margin: 9px 0;
  background: rgba(255,255,255,.72);
  border-radius: 0 10px 10px 0;
  box-shadow: 0 10px 24px rgba(75, 98, 150, .09);
  backdrop-filter: blur(12px);
}
.preview-item.dice {
  --accent: #64748b;
  background: rgba(241, 245, 249, .82);
}
.preview-item.observer {
  opacity: .78;
  border-left-style: dashed;
}
.preview-item.comment {
  background: rgba(255, 251, 235, .78);
}
.preview-item.keeper {
  background: rgba(239, 246, 255, .78);
}
.preview-script .preview-item {
  border-left-width: 0;
  box-shadow: none;
  background: rgba(255,255,255,.5);
  border-bottom: 1px solid rgba(216, 225, 239, .72);
  border-radius: 0;
}
.preview-script .preview-head span {
  display: none;
}
.preview-script .preview-item p {
  margin-left: 1em;
}
.preview-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}
.preview-head strong { color: var(--accent); }
.preview-head span { color: #6b7280; font-size: 12px; }
.dice-badge {
  border-radius: 999px;
  background: rgba(79, 110, 247, .12);
  color: #405bd5;
  font-size: 11px;
  line-height: 20px;
  padding: 0 8px;
}
.preview-item p {
  margin: 6px 0 0;
  color: #273449;
  white-space: pre-wrap;
  line-height: 1.65;
}
.preview-images { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.preview-images button {
  border: 0;
  background: transparent;
  padding: 0;
}
.preview-images img {
  max-width: min(260px, 100%);
  max-height: 220px;
  object-fit: contain;
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,.72);
  background: rgba(255,255,255,.8);
  box-shadow: 0 10px 24px rgba(75, 98, 150, .12);
  cursor: zoom-in;
}
.image-lightbox {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  padding: 48px;
  background: rgba(15, 23, 42, .58);
  backdrop-filter: blur(14px);
}
.image-lightbox img {
  max-width: 92vw;
  max-height: 86vh;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 30px 80px rgba(0,0,0,.35);
}
.close-lightbox {
  position: fixed;
  top: 18px;
  right: 18px;
  height: 34px;
  border: 1px solid rgba(255,255,255,.5);
  border-radius: 8px;
  background: rgba(255,255,255,.2);
  color: #fff;
  padding: 0 14px;
}
@media (max-width: 980px) {
  .workspace { grid-template-columns: 1fr; height: auto; min-height: 100vh; }
  .editor-shell { min-height: 58vh; }
}
</style>

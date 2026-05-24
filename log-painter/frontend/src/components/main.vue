<script setup lang="ts">
import { computed } from 'vue'
import SidebarPanel from './SidebarPanel.vue'
import EditorWorkspace from './EditorWorkspace.vue'
import { dyeExtension } from './dye'
import { useLogPainter } from '../composables/useLogPainter'

const painter = useLogPainter()
const {
  text,
  roles,
  filters,
  items,
  previewItems,
  updateRoleColor,
  updateRoleType,
  mergeRole,
  updateRoleName,
  updateRoleNames,
  clearText,
  loadSample,
  downloadText,
  downloadHtml
} = painter

const editorExtensions = computed(() => [
  dyeExtension({
    roles: roles.value,
    filters: { ...filters }
  })
])

const imageCount = computed(() => items.value.reduce((count, item) => count + (item.images?.length || 0), 0))
const observerCount = computed(() => items.value.filter((item) => item.isObserver).length)
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="product">
        <span class="product-mark"></span>
        <div>
          <div class="product-name">TRPG Log Painter</div>
          <div class="product-sub">fresh IDE workspace</div>
        </div>
      </div>
      <div class="topbar-actions">
        <button type="button" @click="loadSample">示例</button>
        <button type="button" @click="downloadText">TXT</button>
        <button class="primary-action" type="button" @click="downloadHtml">导出 HTML</button>
      </div>
    </header>

    <div class="workbench">
      <SidebarPanel
        :roles="roles"
        :filters="filters"
        :item-count="items.length"
        @update-role-color="updateRoleColor"
        @update-role-type="updateRoleType"
        @merge-role="mergeRole"
        @update-role-name="updateRoleName"
        @update-role-names="updateRoleNames"
        @clear="clearText"
        @sample="loadSample"
        @export-text="downloadText"
        @export-html="downloadHtml"
      />
      <EditorWorkspace
        :model-value="text"
        :extensions="editorExtensions"
        :preview-items="previewItems"
        :filters="filters"
        @update:model-value="(value) => (text = value)"
      />
    </div>

    <footer class="statusbar">
      <span>消息 {{ items.length }}</span>
      <span>角色 {{ roles.length }}</span>
      <span>图片 {{ imageCount }}</span>
      <span>OB {{ observerCount }}</span>
      <span class="status-mode">Dev Preview</span>
    </footer>
  </div>
</template>

<style scoped>
.app-shell {
  width: 100%;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
  display: grid;
  grid-template-rows: 54px minmax(0, 1fr) 28px;
  background:
    radial-gradient(circle at 12% 8%, rgba(112, 203, 255, .34) 0, transparent 28%),
    radial-gradient(circle at 86% 12%, rgba(255, 153, 204, .26) 0, transparent 26%),
    radial-gradient(circle at 62% 92%, rgba(91, 124, 250, .18) 0, transparent 32%),
    linear-gradient(135deg, #f8fcff 0%, #eef7ff 45%, #f8f4ff 100%);
  color: #1f2937;
}
.topbar {
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 18px;
  border-bottom: 1px solid rgba(255, 255, 255, .62);
  background: rgba(255, 255, 255, .58);
  backdrop-filter: blur(22px) saturate(1.3);
  box-shadow: 0 10px 30px rgba(75, 98, 150, .08);
}
.product {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.product-mark {
  width: 18px;
  height: 18px;
  border-radius: 6px;
  background: linear-gradient(135deg, #5b7cfa 0%, #53d6c8 55%, #ff8fc3 100%);
  box-shadow: 0 8px 18px rgba(91, 124, 250, .28);
}
.product-name {
  font-size: 14px;
  font-weight: 800;
  line-height: 1.1;
}
.product-sub {
  color: #718096;
  font-size: 11px;
}
.topbar-actions {
  display: flex;
  gap: 8px;
}
.topbar-actions button {
  height: 32px;
  border: 1px solid #d8e1ef;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  padding: 0 12px;
  font-size: 13px;
}
.topbar-actions button:hover {
  border-color: #afc0e8;
  color: #315bdc;
}
.topbar-actions .primary-action {
  border-color: transparent;
  background: #4969f5;
  color: #fff;
  box-shadow: 0 8px 18px rgba(73, 105, 245, .22);
}
.workbench {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  background: rgba(255, 255, 255, .16);
  overflow: hidden;
}
.statusbar {
  min-height: 0;
  height: 28px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 14px;
  border-top: 1px solid rgba(255, 255, 255, .56);
  background: rgba(241, 247, 255, .68);
  backdrop-filter: blur(18px) saturate(1.2);
  color: #526070;
  font-size: 12px;
  overflow: hidden;
  white-space: nowrap;
}
.statusbar span {
  flex: 0 0 auto;
}
.status-mode {
  margin-left: auto;
  color: #4969f5;
  font-weight: 700;
}
@media (max-width: 760px) {
  .app-shell {
    height: 100%;
    min-height: 0;
    grid-template-rows: auto minmax(0, 1fr) 28px;
  }
  .topbar {
    flex-wrap: wrap;
    padding: 12px;
  }
  .workbench {
    grid-template-columns: 1fr;
  }
}
</style>

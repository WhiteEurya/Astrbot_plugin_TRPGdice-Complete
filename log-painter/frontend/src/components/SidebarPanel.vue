<script setup lang="ts">
import RoleListPanel from './RoleListPanel.vue'
import { computed } from 'vue'
import type { CharItem, PreviewFilters, PreviewMode, RoleType } from '../logManager/types'
import { roleKeyOf } from '../logManager/roles/colorKey'

const props = defineProps<{
  roles: CharItem[]
  filters: PreviewFilters
  itemCount: number
}>()

const emit = defineEmits<{
  (e: 'update-role-color', index: number, color: string): void
  (e: 'update-role-type', index: number, role: RoleType): void
  (e: 'merge-role', index: number, targetKey: string): void
  (e: 'update-role-name', index: number, name: string): void
  (e: 'update-role-names', changes: Array<{ index: number; name: string }>): void
  (e: 'clear'): void
  (e: 'sample'): void
  (e: 'export-text'): void
  (e: 'export-html'): void
}>()

const roleFilterOptions = computed(() =>
  props.roles.map((role) => ({
    key: role.key || roleKeyOf(role),
    name: role.name
  }))
)

const previewModes: Array<{ value: PreviewMode; label: string }> = [
  { value: 'record', label: '记录' },
  { value: 'script', label: '剧本' }
]
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-scroll">
      <div class="brand">
        <span class="brand-dot"></span>
        <div>
          <div class="brand-title">Explorer</div>
          <div class="brand-sub">{{ itemCount }} messages indexed</div>
        </div>
      </div>

      <section class="panel">
        <h2>Workspace</h2>
        <div class="actions">
          <button @click="emit('sample')">载入示例</button>
          <button @click="emit('clear')">清空</button>
          <button @click="emit('export-text')">导出 TXT</button>
          <button @click="emit('export-html')">导出 HTML</button>
        </div>
      </section>

      <section class="panel">
        <h2>Filters</h2>
        <input v-model="filters.query" class="field" placeholder="搜索角色、账号或正文" />
        <select v-model="filters.roleKey" class="field">
          <option value="">全部角色</option>
          <option v-for="role in roleFilterOptions" :key="role.key" :value="role.key">{{ role.name }}</option>
        </select>
        <label><input v-model="filters.hideImages" type="checkbox" /> <span>隐藏图片</span></label>
        <label><input v-model="filters.hideObservers" type="checkbox" /> <span>隐藏 OB</span></label>
        <label><input v-model="filters.hideOffTopic" type="checkbox" /> <span>隐藏场外</span></label>
        <label><input v-model="filters.hideDate" type="checkbox" /> <span>隐藏日期</span></label>
        <label><input v-model="filters.hideTime" type="checkbox" /> <span>隐藏时间</span></label>
        <label><input v-model="filters.hideAccount" type="checkbox" /> <span>隐藏账号</span></label>
      </section>

      <section class="panel">
        <h2>Preview</h2>
        <div class="segmented">
          <button
            v-for="mode in previewModes"
            :key="mode.value"
            type="button"
            :class="{ active: filters.mode === mode.value }"
            @click="filters.mode = mode.value"
          >
            {{ mode.label }}
          </button>
        </div>
      </section>

      <section class="panel">
        <h2>Export</h2>
        <input v-model="filters.exportTitle" class="field" placeholder="导出标题" />
        <label><input v-model="filters.exportImages" type="checkbox" /> <span>导出图片</span></label>
        <label><input v-model="filters.exportColors" type="checkbox" /> <span>导出颜色</span></label>
      </section>

      <section class="panel">
        <RoleListPanel
          :roles="roles"
          @update-color="(index, color) => emit('update-role-color', index, color)"
          @update-role="(index, role) => emit('update-role-type', index, role)"
          @merge-role="(index, targetKey) => emit('merge-role', index, targetKey)"
          @update-name="(index, name) => emit('update-role-name', index, name)"
          @update-names="(changes) => emit('update-role-names', changes)"
        />
      </section>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  height: 100%;
  width: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  padding: 0;
  border-right: 1px solid rgba(255, 255, 255, .62);
  background: rgba(255, 255, 255, .42);
  backdrop-filter: blur(22px) saturate(1.25);
  box-shadow: inset -1px 0 0 rgba(122, 150, 190, .08);
  box-sizing: border-box;
}
.sidebar-scroll {
  width: 100%;
  height: 100%;
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 14px 16px 14px 12px;
  scrollbar-gutter: stable;
}
.brand {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 8px 8px 14px;
}
.brand-dot {
  width: 10px;
  height: 10px;
  border-radius: 4px;
  background: #4f6ef7;
  box-shadow: 0 0 0 4px rgba(79, 110, 247, .12);
}
.brand-title {
  color: #25324a;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.1;
}
.brand-sub { color: #718096; font-size: 11px; }
.panel {
  width: auto;
  min-width: 0;
  margin: 10px 0 0;
  border: 1px solid rgba(255, 255, 255, .62);
  border-radius: 10px;
  padding: 12px 10px;
  background: rgba(255, 255, 255, .44);
  box-shadow: 0 10px 24px rgba(75, 98, 150, .07);
}
.panel h2 {
  margin: 0 0 10px;
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}
.actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.field {
  display: block;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  height: 32px;
  margin-bottom: 8px;
  border: 1px solid rgba(216, 225, 239, .9);
  border-radius: 8px;
  background: rgba(255, 255, 255, .68);
  color: #25324a;
  padding: 0 9px;
  font-size: 12px;
}
.field:focus {
  border-color: #8fa2f8;
  box-shadow: 0 0 0 3px rgba(73, 105, 245, .12);
  outline: 0;
}
.segmented {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}
button {
  min-width: 0;
  min-height: 32px;
  border: 1px solid rgba(216, 225, 239, .9);
  background: rgba(255, 255, 255, .68);
  border-radius: 8px;
  color: #334155;
  padding: 7px 8px;
  font-size: 12px;
  cursor: pointer;
}
.segmented button.active {
  border-color: transparent;
  background: #4969f5;
  color: #fff;
  box-shadow: 0 8px 18px rgba(73, 105, 245, .2);
}
button:hover {
  background: rgba(255, 255, 255, .9);
  border-color: #b9c8e8;
  color: #315bdc;
}
label {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 28px;
  color: #334155;
  font-size: 13px;
}
input[type='checkbox'] {
  flex: 0 0 auto;
  width: 14px;
  height: 14px;
  accent-color: #4969f5;
}
@media (max-width: 760px) {
  .sidebar {
    border-right: 0;
    border-bottom: 1px solid #dfe7f3;
  }
}
</style>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import ColorDot from './ColorDot.vue'
import type { CharItem, RoleType } from '../logManager/types'
import { roleKeyOf } from '../logManager/roles/colorKey'

const props = defineProps<{
  roles: CharItem[]
}>()

const emit = defineEmits<{
  (e: 'update-color', index: number, color: string): void
  (e: 'update-role', index: number, role: RoleType): void
  (e: 'merge-role', index: number, targetKey: string): void
  (e: 'update-name', index: number, name: string): void
  (e: 'update-names', changes: Array<{ index: number; name: string }>): void
}>()

const roleOptions: RoleType[] = ['角色', '主持人', '骰子', 'OB', '其他', '隐藏']

const drafts = reactive<Record<string, string>>({})
const dirty = reactive<Record<string, boolean>>({})

function roleKey(role: CharItem, index: number) {
  return role.key || `${role.originalName || role.name}-${role.IMUserId}-${index}`
}

function stableRoleKey(role: CharItem) {
  return role.key || roleKeyOf(role)
}

watch(
  () => props.roles,
  (roles) => {
    for (let index = 0; index < roles.length; index++) {
      const role = roles[index]
      const key = roleKey(role, index)
      if (!(key in drafts) || !dirty[key]) drafts[key] = role.name
    }
  },
  { immediate: true, deep: true }
)

function commitName(index: number) {
  const role = props.roles[index]
  if (!role) return
  const key = roleKey(role, index)
  const nextName = (drafts[key] || '').trim()
  if (nextName && nextName !== role.name) {
    emit('update-name', index, nextName)
    dirty[key] = false
  } else {
    drafts[key] = role.name
    dirty[key] = false
  }
}

function updateDraft(index: number, value: string) {
  const role = props.roles[index]
  if (!role) return
  const key = roleKey(role, index)
  drafts[key] = value
  dirty[key] = value !== role.name
}

function collectNameChanges() {
  const changes: Array<{ index: number; name: string }> = []
  for (let index = 0; index < props.roles.length; index++) {
    const role = props.roles[index]
    const key = roleKey(role, index)
    const nextName = (drafts[key] || '').trim()
    if (nextName && nextName !== role.name) changes.push({ index, name: nextName })
  }
  return changes
}

function hasNameChanges() {
  return collectNameChanges().length > 0
}

function commitAllNames() {
  const changes = collectNameChanges()
  if (!changes.length) return
  emit('update-names', changes)
  for (const change of changes) {
    const role = props.roles[change.index]
    if (!role) continue
    const key = roleKey(role, change.index)
    dirty[key] = false
  }
}
</script>

<template>
  <section class="role-panel">
    <header class="panel-head">
      <span>角色</span>
      <b>{{ roles.length }}</b>
    </header>

    <div v-if="!roles.length" class="empty">暂无可识别角色</div>

    <div v-for="(role, index) in roles" :key="roleKey(role, index)" class="role-row">
      <ColorDot :model-value="role.color" @update:model-value="(color) => emit('update-color', index, color)" />
      <input
        class="role-name"
        :value="drafts[roleKey(role, index)] ?? role.name"
        @input="updateDraft(index, ($event.target as HTMLInputElement).value)"
        @keydown.enter.prevent="commitAllNames"
      />
      <select class="role-type" :value="role.role" @change="emit('update-role', index, ($event.target as HTMLSelectElement).value as RoleType)">
        <option v-for="option in roleOptions" :key="option" :value="option">{{ option }}</option>
      </select>
      <select class="role-merge" :value="role.mergedIntoKey || ''" @change="emit('merge-role', index, ($event.target as HTMLSelectElement).value)">
        <option value="">独立</option>
        <option
          v-for="target in roles.filter((candidate) => stableRoleKey(candidate) !== stableRoleKey(role))"
          :key="stableRoleKey(target)"
          :value="stableRoleKey(target)"
        >
          合并到 {{ target.name }}
        </option>
      </select>
    </div>

    <button class="sync-name" :disabled="!hasNameChanges()" type="button" @click="commitAllNames">
      同步全部改名
    </button>
  </section>
</template>

<style scoped>
.role-panel { display: flex; flex-direction: column; gap: 8px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; color: #25324a; font-weight: 800; }
.panel-head b { color: #718096; font-size: 12px; }
.empty { color: #6b7280; font-size: 13px; padding: 8px 0; }
.role-row {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) 68px;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 3px 0;
}
.role-name {
  height: 28px;
  border: 1px solid rgba(216, 225, 239, .9);
  border-radius: 8px;
  min-width: 0;
  padding: 0 8px;
  background: rgba(255, 255, 255, .68);
  color: #1f2937;
  font-size: 12px;
}
.role-name:focus {
  border-color: #8fa2f8;
  box-shadow: 0 0 0 3px rgba(73, 105, 245, .12);
  outline: 0;
}
.role-type,
.role-merge {
  height: 28px;
  border: 1px solid rgba(223, 231, 243, .82);
  border-radius: 8px;
  background: rgba(245, 248, 254, .72);
  color: #64748b;
  font-size: 11px;
  padding: 0 6px;
  white-space: nowrap;
}
.role-merge {
  grid-column: 2 / 4;
  width: 100%;
}
.role-type:focus,
.role-merge:focus {
  border-color: #8fa2f8;
  outline: 0;
}
.sync-name {
  border: 1px solid rgba(216, 225, 239, .9);
  border-radius: 8px;
  background: rgba(255, 255, 255, .68);
  color: #334155;
  padding: 7px 9px;
  font-size: 13px;
  cursor: pointer;
  width: 100%;
  margin-top: 4px;
}
.sync-name:disabled {
  opacity: .42;
  cursor: default;
}
</style>

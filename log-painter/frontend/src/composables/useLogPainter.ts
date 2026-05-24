import { computed, reactive, ref, watch } from 'vue'
import type { CharItem, PreviewFilters, RoleType } from '../logManager/types'
import { parseLogText, renameLogSpeaker } from '../logManager/parse'
import { deriveRoles } from '../logManager/roles/deriveRoles'
import { rebuildColorMap, roleKeyOf } from '../logManager/roles/colorKey'
import { buildPreviewItems } from '../logManager/preview/buildPreviewItems'
import { exportHtml, exportPlainText } from '../logManager/export/exporters'
import demoAllText from '../../test-fixtures/logs/demo-all.txt?raw'

const SAMPLE_TEXT = demoAllText.trim()

export function useLogPainter() {
  const text = ref(SAMPLE_TEXT)
  const roles = ref<CharItem[]>([])
  const filters = reactive<PreviewFilters>({
    hideImages: false,
    hideOffTopic: false,
    hideDate: false,
    hideTime: false,
    hideAccount: false,
    hideObservers: false,
    query: '',
    roleKey: '',
    mode: 'record',
    exportTitle: 'TRPG Log Painter',
    exportImages: true,
    exportColors: true
  })

  const items = computed(() => parseLogText(text.value))
  const colorMap = computed(() => rebuildColorMap(roles.value))
  const previewItems = computed(() => buildPreviewItems(items.value, roles.value, filters))

  watch(
    items,
    (next) => {
      roles.value = deriveRoles(next, roles.value)
    },
    { immediate: true }
  )

  function updateRoleColor(index: number, color: string) {
    const next = roles.value.slice()
    if (!next[index]) return
    next[index] = { ...next[index], color }
    roles.value = next
  }

  function updateRoleType(index: number, role: RoleType) {
    const next = roles.value.slice()
    if (!next[index]) return
    next[index] = { ...next[index], role }
    roles.value = next
  }

  function mergeRole(index: number, targetKey: string) {
    const source = roles.value[index]
    if (!source) return
    const sourceKey = source.key || roleKeyOf(source)
    roles.value = roles.value.map((role, roleIndex) =>
      roleIndex === index
        ? {
            ...role,
            mergedIntoKey: targetKey && targetKey !== sourceKey ? targetKey : undefined
          }
        : role
    )
  }

  function updateRoleName(index: number, name: string) {
    const role = roles.value[index]
    if (!role) return
    const oldName = role.originalName || role.name
    const nextText = renameLogSpeaker(text.value, oldName, role.IMUserId, name)

    if (nextText !== text.value) {
      roles.value = roles.value.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              key: `${name.trim()}#${item.IMUserId}`,
              name,
              originalName: name
            }
          : item
      )
      text.value = nextText
      return
    }

    roles.value = roles.value.map((item, itemIndex) => (itemIndex === index ? { ...item, name } : item))
  }

  function updateRoleNames(changes: Array<{ index: number; name: string }>) {
    let nextText = text.value
    let nextRoles = roles.value.slice()

    for (const change of changes) {
      const role = nextRoles[change.index]
      if (!role) continue
      const nextName = change.name.trim()
      if (!nextName) continue
      const oldName = role.originalName || role.name
      nextText = renameLogSpeaker(nextText, oldName, role.IMUserId, nextName)
      nextRoles[change.index] = {
        ...role,
        key: `${nextName}#${role.IMUserId}`,
        name: nextName,
        originalName: nextName
      }
    }

    roles.value = nextRoles
    text.value = nextText
  }

  function clearText() {
    text.value = ''
  }

  function loadSample() {
    text.value = SAMPLE_TEXT
  }

  function downloadText() {
    exportPlainText(previewItems.value, filters)
  }

  function downloadHtml() {
    exportHtml(previewItems.value, filters)
  }

  return {
    text,
    roles,
    filters,
    items,
    colorMap,
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
  }
}

import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { CharItem, LogItem, PreviewFilters, RoleType } from '../logManager/types'
import { parseLogText, pluginExportToItems, pluginExportToLogText, renameLogSpeaker } from '../logManager/parse'
import { deriveRoles } from '../logManager/roles/deriveRoles'
import { rebuildColorMap, roleKeyOf } from '../logManager/roles/colorKey'
import { buildPreviewItems } from '../logManager/preview/buildPreviewItems'
import { exportHtml, exportPlainText } from '../logManager/export/exporters'
import demoAllText from '../../test-fixtures/logs/demo-all.txt?raw'

const SAMPLE_TEXT = demoAllText.trim()

export function useLogPainter() {
  const text = ref(SAMPLE_TEXT)
  const sourceFile = ref('')
  const loadStatus = ref('')
  const importedItems = ref<LogItem[] | null>(null)
  const importedText = ref('')
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

  const items = computed(() =>
    importedItems.value && text.value === importedText.value ? importedItems.value : parseLogText(text.value)
  )
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
    importedItems.value = null
    importedText.value = ''
    text.value = ''
  }

  function loadSample() {
    sourceFile.value = ''
    loadStatus.value = ''
    importedItems.value = null
    importedText.value = ''
    text.value = SAMPLE_TEXT
  }

  async function loadExportUuid(logUuid: string) {
    const safeUuid = logUuid.trim().toLowerCase()
    if (!/^[0-9a-f]{8}$/i.test(safeUuid)) {
      loadStatus.value = '日志链接无效'
      return
    }

    sourceFile.value = safeUuid
    loadStatus.value = '正在加载日志'

    try {
      const response = await fetch(`/export?uuid=${encodeURIComponent(safeUuid)}`, {
        headers: { Accept: 'application/json' },
        cache: 'no-store'
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      importedItems.value = pluginExportToItems(data)
      const renderedText = pluginExportToLogText(data)
      text.value = renderedText
      importedText.value = renderedText
      filters.exportTitle = String(data?.name || safeUuid)
      loadStatus.value = renderedText ? `已加载 ${filters.exportTitle}` : `已加载空日志 ${filters.exportTitle}`
    } catch (error) {
      loadStatus.value = `加载失败：${error instanceof Error ? error.message : '未知错误'}`
    }
  }

  async function loadExportFile(fileName: string) {
    const safeName = fileName.trim()
    if (!safeName || safeName.includes('..') || safeName.includes('/') || safeName.includes('\\') || !safeName.endsWith('.json')) {
      loadStatus.value = '日志链接无效'
      return
    }

    sourceFile.value = safeName
    loadStatus.value = '正在加载日志'

    try {
      const response = await fetch(`/export/${encodeURIComponent(safeName)}`, {
        headers: { Accept: 'application/json' },
        cache: 'no-store'
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      importedItems.value = pluginExportToItems(data)
      const renderedText = pluginExportToLogText(data)
      text.value = renderedText
      importedText.value = renderedText
      filters.exportTitle = safeName.replace(/\.json$/i, '')
      loadStatus.value = renderedText ? `已加载 ${safeName}` : `已加载空日志 ${safeName}`
    } catch (error) {
      loadStatus.value = `加载失败：${error instanceof Error ? error.message : '未知错误'}`
    }
  }

  onMounted(() => {
    const params = new URLSearchParams(window.location.search)
    const logUuid = params.get('uuid')
    if (logUuid) {
      void loadExportUuid(logUuid)
      return
    }

    const fileName = params.get('file')
    if (fileName) {
      void loadExportFile(fileName)
    }
  })

  function downloadText() {
    exportPlainText(previewItems.value, filters)
  }

  function downloadHtml() {
    exportHtml(previewItems.value, filters)
  }

  return {
    text,
    sourceFile,
    loadStatus,
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
    loadExportUuid,
    loadExportFile,
    downloadText,
    downloadHtml
  }
}

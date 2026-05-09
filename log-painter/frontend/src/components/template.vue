<template>
  <n-config-provider
    :theme="isDark ? darkTheme : null"
    :theme-overrides="{
      ...napTheme,
      Layout: {
        color: 'transparent',
        colorEmbedded: 'transparent',
        siderColor: 'transparent',
        headerColor: 'transparent',
        footerColor: 'transparent'
      }
    }"
  >
    <n-layout class="app-shell">
      <n-layout-content class="app-bg">
        <n-layout has-sider class="app-main">
          <!-- ========== 左侧：固定 320px；内容放在右侧 2/3 列；左侧 1/3 为空白缩进 ========== -->
          <n-layout-sider :native-scrollbar="false" class="sider-clear sider-fixed">
            <div class="sider-grid">
              <!-- 第 1 列（1/3）：空白缩进，不放任何内容 -->
              <div class="sider-gutter"></div>

              <!-- 第 2 列（2/3）：所有内容 -->
              <div class="sider-col">
                <!-- 标题（与选项完全对齐） -->
                <div class="nav-brand">
                  <div class="brand-left">
                    <span class="brand-dot" />
                    <div class="brand-text">
                      <div class="brand-title">TRPG跑团</div>
                      <div class="brand-sub">Log 着色器</div>
                    </div>
                  </div>
                </div>

                <!-- 选项区域 -->
                <div class="nav-track">
                  <n-collapse class="nav-collapse" accordion arrow-placement="right">
                    <!-- 大选项：操作 -->
                    <n-collapse-item name="ops">
                      <template #header>
                        <div class="nav-group">操作</div>
                      </template>
                      <ul class="nav-children">
                        <li><button class="nav-item" @click="exportRecordRaw">下载原始文件</button></li>
                        <li><button class="nav-item" @click="exportRecordDOC">下载 Word</button></li>
                        <li><button class="nav-item" @click="exportRecordTalkDOC">下载对话 Word</button></li>
                      </ul>
                    </n-collapse-item>

                    <!-- 大选项：预览与工具（设置行 + 右侧开关） -->
                    <n-collapse-item name="tools">
                      <template #header>
                        <div class="nav-group">预览与工具</div>
                      </template>
                      <div class="nav-children">
                        <div class="op-row">
                          <span class="op-label">预览</span>
                          <n-switch v-model:value="isShowPreview" />
                        </div>

                        <div class="op-row">
                          <span class="op-label">论坛代码</span>
                          <n-switch
                            v-model:value="isShowPreviewBBS"
                            @update:value="(val) => { isShowPreviewBBS = val; previewClick('bbs') }"
                          />
                        </div>

                        <div class="op-row">
                          <span class="op-label">回声工坊</span>
                          <n-switch
                            v-model:value="isShowPreviewTRG"
                            @update:value="(val) => { isShowPreviewTRG = val; previewClick('trg') }"
                          />
                        </div>

                        <div class="op-row">
                          <span class="op-label">刷新色板</span>
                          <button class="op-action" @click="doFlush">执行</button>
                        </div>
                      </div>
                    </n-collapse-item>

                    <!-- 大选项：选项 -->
                    <n-collapse-item name="opts">
                      <template #header>
                        <div class="nav-group">选项</div>
                      </template>
                      <div class="nav-children">
                        <div class="op-row">
                          <span class="op-label">清空内容</span>
                          <button class="op-action" @click="clearText">执行</button>
                        </div>
                        <div class="op-row">
                          <span class="op-label">强制刷新</span>
                          <button class="op-action" @click="doFlush">执行</button>
                        </div>

                        <!-- 新增过滤选项 -->
                        <div class="op-row">
                          <span class="op-label">过滤表情图片</span>
                          <n-switch v-model:value="filters.image" />
                        </div>
                        <div class="op-row">
                          <span class="op-label">过滤场外发言</span>
                          <n-switch v-model:value="filters.comment" />
                        </div>
                        <div class="op-row">
                          <span class="op-label">过滤具体时间</span>
                          <n-switch v-model:value="filters.time" />
                        </div>
                        <div class="op-row">
                          <span class="op-label">过滤年月日</span>
                          <n-switch v-model:value="filters.date" />
                        </div>
                        <div class="op-row">
                          <span class="op-label">过滤账号</span>
                          <n-switch v-model:value="filters.account" />
                        </div>
                      </div>
                    </n-collapse-item>

                    <!-- 大选项：角色列表（示例） -->
                    <!-- 大选项：角色列表（每个角色是一个子折叠项） -->
                    <n-collapse-item name="roles">
                      <template #header>
                        <div class="nav-group nav-group--roles">角色列表</div>
                      </template>

                      <n-collapse class="role-collapse" accordion>
                        <n-collapse-item
                          v-for="(pc, idx) in store.pcList"
                          :key="(pc.IMUserId || 'noid') + '|' + idx"
                          :name="idx"
                          class="role-item role-item--compact"
                          :style="{ '--role-accent': pc.color || 'rgba(99,102,241,.35)' }"
                        >
                          <!-- 头部：小圆点 + 名字（省略号），不显示折叠箭头 -->
                          <template #header>
                            <div class="role-header role-header--compact">
                              <ColorDot v-model="pc.color" />
                              <span class="role-name" :title="pc.name">{{ pc.name }}</span>
                            </div>
                          </template>

                          <!-- 子项：一行一个，紧凑排列；左侧竖线使用角色专属颜色 -->
                          <div class="role-fields role-fields--compact">
                            <div class="role-field">
                              <span class="label">角色名</span>
                              <div class="field-body">
                                <n-input
                                  v-model:value="nameDraft[(pc.IMUserId || 'noid') + '|' + idx]"
                                  size="small"
                                  placeholder="角色名"
                                  @focus="nameFocus(pc, idx)"
                                  @change="nameChanged(pc, idx)"
                                  :style="{ width: `calc(${Math.max(8, (nameDraft[(pc.IMUserId || 'noid') + '|' + idx] || '').length)}ch + 18px)` }"
                                />
                              </div>
                            </div>

                            <div class="role-field">
                              <span class="label">编号</span>
                              <div class="field-body">
                                <n-input v-model:value="pc.IMUserId" size="small" disabled 
                                :style="{ width: `calc(${Math.max(8, (pc.name || '').length)}ch + 18px)` }"/>
                              </div>
                            </div>

                            <div class="role-field">
                              <span class="label">身份</span>
                              <div class="field-body">
                                <n-select
                                  v-model:value="pc.role"
                                  size="small"
                                  style="width: 132px"
                                  :options="[
                                    { value: '主持人', label: '主持人' },
                                    { value: '角色',   label: '角色'   },
                                    { value: '骰子',   label: '骰子'   },
                                    { value: '隐藏',   label: '隐藏'   }
                                  ]"
                                />
                              </div>
                            </div>

                            <div class="role-field">
                              <span class="label">颜色</span>
                              <div class="field-body">
                                <ColorDot
                                  v-model="pc.color"
                                  @update:modelValue="(v) => onColorPicked(pc, v)"
                                />
                                <button class="link xs" @click="doFlush">换一组</button>
                              </div>
                            </div>

                            <div class="role-field">
                              <span class="label">操作</span>
                              <div class="field-body">
                                <button class="link danger xs" @click="deletePc(idx, pc)">删除此角色</button>
                              </div>
                            </div>
                          </div>
                        </n-collapse-item>
                      </n-collapse>
                    </n-collapse-item>
                  </n-collapse>
                </div>
              </div>
            </div>
          </n-layout-sider>

          <!-- ========== 右侧：编辑区；右侧缩进 mirror 左侧 1/3 空白 ========== -->
          <n-layout-content class="work-area only-right-scroll" :content-style="{ overflow: 'hidden' }">
            <section class="editor-shell glass">
              <header class="editor-head">
                <h2 class="editor-title"><span class="dot"></span>染色器</h2>
              </header>
              <div class="editor-body">
                <code-mirror
                  v-model="cmContent"
                  :show-line-numbers="true"
                  :line-wrapping="true"
                  :extra-extensions="cmExtensions"
                  :preview="isShowPreview"
                />
                <preview-main v-if="isShowPreview" :key="'pm:'+previewColorSig" :is-show="true" :preview-items="previewItems" />
                <preview-bbs v-if="isShowPreviewBBS" :key="'bbs:'+previewColorSig" :is-show="true" :preview-items="previewItems" />
                <preview-trg v-if="isShowPreviewTRG" :key="'trg:'+previewColorSig" :is-show="true" :preview-items="previewItems" />
              </div>
            </section>
          </n-layout-content>
        </n-layout>
      </n-layout-content>
    </n-layout>
  </n-config-provider>
</template>

<script setup lang="ts">

/* --- 重构版（不改函数名字）---------------------------------------------
   目标：
   1) 修正类型导入次序；
   2) 统一颜色映射 key 策略（IMUserId || name）；
   3) 去除重复解析 & 去重预览生成逻辑（showPreview → 代理到 recomputePreview）；
   4) 在卸载时取消防抖；
   5) UA 检测后再提示下载能力；
   6) 颜色选择即时更新色板 & 统一刷新通道；
   7) 修正“颜色不刷新要开 F12 才更新”的 reactivity 问题；
   8) 保留所有原函数名，便于直接替换。
--------------------------------------------------------------------- */

/* --- 重构版（不改函数名字）---------------------------------------------
   目标：
   1) 修正类型导入次序；
   2) 颜色键改为“复合键”(ID+Name)：区分“不同名但同 ID”；
   3) 颜色选择即时更新色板 & 强制触发视图更新（替换 store.pcList 中的对象/数组）；
   4) 去除重复解析 & 去重预览生成逻辑（showPreview → recomputePreview）；
   5) 在卸载时取消防抖；
   6) UA 检测后再提示下载能力；
   7) 保留所有原函数名与对外 API，便于直接替换。
--------------------------------------------------------------------- */

import {
  // Provider & 布局 & 抽屉
  NConfigProvider, NLayout, NLayoutHeader, NLayoutContent, NLayoutSider,
  NDrawer, NDrawerContent,
  // 常用UI
  NCard, NFlex, NIcon, NTag, NInput, NSelect, NColorPicker,
  NCheckbox, NDivider, NTooltip, NSpin, NSpace, NSwitch
  // 主题
} from 'naive-ui'

import { ref  } from 'vue'
import { Menu } from '@vicons/carbon' // 顶栏的汉堡按钮图标

// 小屏抽屉开关
const showLeftMenu = ref(false)

const napTheme: GlobalThemeOverrides = {
  common: {
    primaryColor: '#3B82F6',          // 蓝色
    primaryColorHover: '#60A5FA',
    primaryColorPressed: '#2563EB',
    primaryColorSuppl: '#3B82F6',
    warningColor: '#FB923C',          // 橙
    borderRadius: '12px',
    fontWeightStrong: '600'
  },
  Card: { borderRadius: '16px' },
  Button: { borderRadius: '10px' },
  Tag: { borderRadius: '10px' },
  Checkbox: { colorChecked: '#3B82F6' }
}

const filters = reactive({
  image: false,
  comment: false,
  time: false,
  date: false,
  account: false
})

import { darkTheme, type GlobalThemeOverrides } from 'naive-ui'
import { Sun, Moon, Download, Document } from '@vicons/carbon' // 图标

/* --- Vue / 基础 --- */
import { nextTick, onMounted, reactive, onBeforeUnmount, watch, h, render, computed } from 'vue'

import { useStore } from '../store'

import CodeMirror from './CodeMirror.vue'

import ColorDot from './ColorDot.vue'

import { debounce /* , delay */ } from 'lodash-es'
import { exportFileRaw, exportFileDoc } from '../utils/exporter'
// import { strFromU8, unzlibSync } from 'fflate'
import { UAParser } from 'ua-parser-js'

import { EditorView } from '@codemirror/view'
import { logMan } from '../logManager/logManager'
import type { ViewUpdate } from '@codemirror/view'
import type { TextInfo } from '../logManager/importers/_logImpoter'

/* 预览组件都在同级的 previews 子目录 */
import previewMain from './previews/preview-main.vue'
import previewBbs from './previews/preview-bbs.vue'
import previewTrg from './previews/preview-trg.vue'
import PreviewItem from './previews/preview-main-item.vue'
import PreviewTableTR from './previews/preview-table-tr.vue'

import { dyeExtension } from './dye'
import {previewHighlightExtension} from './previewDye'

import type { LogItem, CharItem } from '../logManager/types'
import { packNameId } from '../logManager/types'
import { setCharInfo } from '../logManager/importers/_logImpoter'
import {
  msgCommandFormat,
  msgImageFormat,
  msgIMUseridFormat,
  msgOffTopicFormat,
  msgAtFormat
} from '../utils'

import axios from 'axios'

import { NButton, NText, useMessage, useModal } from 'naive-ui'
import { User, LogoGithub, Delete as IconDelete } from '@vicons/carbon'
import { breakpointsTailwind, useBreakpoints, useDark } from '@vueuse/core'

/* OptionView 与 main.vue 在同一层级的 components 目录 */
import OptionView from './OptionView.vue'

/* --- 本地化说明 ---
   ① 去掉了与远程/大文件相关的 parquet/hyperparam/hyparquet-compressors 三个包的 import
   ② lodash-es 的 delay 暂时未用，先注释；后续需要再开
*/

/* --- 响应式与环境 --- */
const breakpoints = useBreakpoints(breakpointsTailwind)
const notMobile = breakpoints.greater('sm')

const isDark = useDark()

const message = useMessage()
const modal = useModal()
const store = useStore()   

const loading = ref<boolean>(false)

const isMobile = ref(false)
const downloadUsableRank = ref(0)

const isShowPreview = ref(false)
const isShowPreviewBBS = ref(false)
const isShowPreviewTRG = ref(false)

const nameDraft = reactive<Record<string, string>>({})

const cmContent = computed({
  get() {
    return isShowPreview.value ? getPreviewText().map(i => i.line).join('\n') : text.value
  },
  set(val: string) {
    if (!isShowPreview.value) text.value = val
  }
})

function draftKey(pc: CharItem, idx: number) {
  return `${pc.IMUserId || 'noid'}|${idx}`
}

function getNameDraft(pc: CharItem, idx: number) {
  const k = draftKey(pc, idx)
  // 若无草稿，回退到当前 pc.name
  return nameDraft[k] ?? (pc.name ?? '')
}

function setNameDraft(pc: CharItem, idx: number, val: string) {
  nameDraft[draftKey(pc, idx)] = val ?? ''
}

const roleOptions = [
  { value: '主持人', label: '主持人' },
  { value: '角色',   label: '角色' },
  { value: '骰子',   label: '骰子' },
  { value: '隐藏',   label: '隐藏' }
]

// 需要的导入

// ===== 1) 绑定编辑器文本，用它做“实时解析”的来源 =====
const text = ref('')               // 你的 <code-mirror v-model="text" /> 会写这里
const previewItems = ref<LogItem[]>([])

// 实时喂给解析器（做个轻微防抖，避免每个字符都重算）
const feedParser = debounce((val: string) => {
  logMan.syncChange(val ?? '', [], [])
}, 120)

// 左侧角色列表构建（从 items 推出唯一个体）——保持“按 name 聚合”，满足“同 ID 不同名分开”

let isFlushing = false

watch(isShowPreview, (val) => {
  previewClick('preview')
})

function safeDoFlush() {
  if (isFlushing) return
  try {
    doFlush()
    isFlushing = true
  } finally {
    isFlushing = false
  }
}

function buildPcList(items: LogItem[]) {
  const map = new Map<string, CharItem>()

  // 1) 先把旧 pcList 的角色放进去（保留已有属性，避免初次读取丢人）
  for (const pc of store.pcList || []) {
    const key = colorKeyOf(pc)
    if (key) map.set(key, { ...pc })
  }

  // 2) 再把新解析到的角色加进去：以 name 为主键（若已存在则仅更新 name/IMUserId，但保留 color/role）
  for (const it of items) {
    if ((it as any).isRaw) continue
    const parsed = parseNameIdFromLine((it as any).message ?? '')
    const name = (it as any).nickname ?? parsed.name ?? '未知'
    const IMUserId = (it as any).IMUserId ?? parsed.IMUserId ?? ''

    const key = name.trim()
    if (!map.has(key)) {
      // color 优先从 pcNameColorMap 以 name 取（你现在的约定）
      const color = store.pcNameColorMap.get(key) ?? randomColor()
      map.set(key, {
        name,
        IMUserId,
        role: '角色',
        color
      } as CharItem)
      store.pcNameColorMap.set(key, color)
    } else {
      // 已存在：确保 IMUserId 与名字是最新（保留 color/role）
      const existing = map.get(key)!
      if (!existing.IMUserId && IMUserId) existing.IMUserId = IMUserId
      // 如果 nickname 字段比 existing.name 更可靠，也可同步（此处以现存 name 为准）
    }
  }

  const result = Array.from(map.values())
  // console.log('[buildPcList] rebuilt pcList (len=%d) sample:', result.length, result.slice(0, 6))
  // console.log('[buildPcList] pcNameColorMap keys sample:', Array.from((store.pcNameColorMap || new Map()).keys()).slice(0, 8))

  return result
}

const previewLines = computed(() => getPreviewText())

const cmExtensions = computed(() => {
  if (isShowPreview.value) {
    const lines = getPreviewText()  // ✅ 先拿到最新数组
    return [
      previewHighlightExtension(lines, store), // 传数组，不是函数
      EditorView.editable.of(false)
    ]
  } else {
    return [
      dyeExtension(store),
      EditorView.editable.of(true)
    ]
  }
})

const editorDyeExt = computed(() => {
  return store.doEditorHighlight ? [dyeExtension(store)] : []
})

const previewColorSig = computed(() =>
  (store.pcList || [])
    .map(p => `${p.IMUserId || ''}:${p.name}:${p.color || ''}`)
    .join('|')
)

// 零宽空格，不改变可见文本
const ZWSP = '\u200B'

/** 触发一次“与剪切→粘贴等价”的解析链：
 *  1) 对 v-model 的 text 做一次 +ZWSP 再还原
 *  2) 同步 CodeMirror 文档做一次插入/删除（保持一致性）
 *  3) flush 防抖，确保 feedParser / logMan.syncChange 立刻执行
 */
async function simulateCutPasteParse() {
  const t = text.value

  // ① v-model：加一个不可见字符
  text.value = t + ZWSP
  // 让 watch(text) 捕获到变化
  await nextTick()
  // 立刻执行一次（防止 debounce 吞掉）
  feedParser.flush?.()
  // 再显式调用一次，双保险
  logMan.syncChange(text.value, [], [])

  // ② 还原 v-model
  text.value = t
  await nextTick()
  feedParser.flush?.()
  logMan.syncChange(text.value, [], [])

  // ③ 同步 CodeMirror（如果存在），做一次等价的插入/删除
  try {
    const ed = store.editor
    if (ed?.state) {
      const len = ed.state.doc.length
      // 插入一个不可见字符
      ed.dispatch({ changes: { from: len, to: len, insert: ZWSP } })
      // 立刻删掉它
      ed.dispatch({ changes: { from: len, to: len + 1, insert: '' } })
    }
  } catch { /* 忽略 */ }
}

// ========= 新增：工具函数（放在文件函数区任意位置即可） =========

function extractWho(i: any): string {
  return i?.nickname ?? /^<([^>]+)>/.exec(i.message)?.[1] ?? '未知'
}

// 把消息中的内联颜色剥离，防止旧 HTML 抢着上色
function stripInlineColor(html: string): string {
  if (typeof html !== 'string') return html as any
  // 去掉 style="...color: xxx;..." 里的 color 声明
  html = html.replace(/style\s*=\s*"([^"]*)"/gi, (_m, s) => {
    const cleaned = String(s)
      .replace(/(^|;)\s*color\s*:[^;"]*/gi, '$1')
      .replace(/^\s*;|;\s*$/g, '')
      .trim()
    return cleaned ? `style="${cleaned}"` : ''
  })
  // 去掉元素上的 color="xxx"
  html = html.replace(/\scolor\s*=\s*"[^"]*"/gi, '')
  return html
}


// 右侧预览生成（沿用你之前的逻辑入口）
// ========= 替换你的 showPreview（或同步修改 recomputePreview） =========
function showPreview() {
  const tmp: LogItem[] = []
  let index = 0
  for (const i of logMan.curItems) {
    if ((i as any).isRaw) continue

    // 你的原格式化链（先按老流程生成内容）
    let msg = msgImageFormat(i.message, store.exportOptions)
    msg = msgAtFormat(msg, store.pcList)
    msg = msgOffTopicFormat(msg, store.exportOptions, (i as any).isDice)
    msg = msgCommandFormat(msg, store.exportOptions)
    msg = msgIMUseridFormat(msg, store.exportOptions, (i as any).isDice)
    msg = msgOffTopicFormat(msg, store.exportOptions, (i as any).isDice)
    if (msg.trim() === '') continue

    // 🔑 关键：剥掉旧 HTML 里的颜色，让颜色控制权回到 pc.color
    const sanitized = stripInlineColor(msg)

    // 🔑 关键：附带“谁说的”和 IMUserId，供预览里实时查色
    const who = extractWho(i)
    const IMUserId = (i as any).IMUserId ?? ''

    tmp.push({
      ...(i as any),
      who,
      IMUserId,
      message: sanitized,               // 用去色后的 HTML
      messageSanitized: sanitized,      // 冗余一份以便子组件直接用
      index: index as any
    } as any)
    index++
  }
  previewItems.value = tmp
}


// ===== 2) 实时解析：监听 text 变化 =====
watch(text, async (val) => {
  if (isFlushing) return
  isFlushing = true
  feedParser(val ?? '')
  feedParser.flush() 
  await simulateCutPasteParse()
  isFlushing = false
})

// ===== 3) 订阅解析结果，更新左栏 & 预览 =====
let offParsed: (() => void) | undefined
let offTextSet: (() => void) | undefined

const browserAlert = () => {
  if (downloadUsableRank.value === 0) {
    message.warning('你目前所使用的浏览器无法下载文件，请更换 Chrome / Firefox / Edge')
    return
  }
  if (downloadUsableRank.value === 1 && isMobile.value) {
    message.warning('移动端部分浏览器下载可能乱码或失败，建议用 Chrome / Firefox / Edge')
  }
}


async function loadJsonFile(fileName: string) {
  if (!fileName.endsWith('.json')) {
    console.warn('[loadJsonFile] 无效文件名:', fileName)
    return
  }

  try {
    console.log('[TEST] 请求 JSON：', fileName)
    const res = await axios.get(`/export/${fileName}`)
    console.log('[TEST] 后端返回：', res.data)

    const arr = Array.isArray(res.data) ? res.data : res.data.items || []

    // 过滤逻辑：空白消息且 images 为空 → 删除
    const filtered = arr.filter((i: any) => {
      const msgEmpty = (i.message || '').trim() === ''
      const hasImages = Array.isArray(i.images) && i.images.length > 0
      return !msgEmpty || hasImages
    })

    // 转换为聊天文本格式，并把 images 拼接到消息后面
    const txt = filtered
      .map((i: any) => {
        const who = `${i.nickname || '未知'}(${i.IMUserId || ''}) ${i.time || ''}`
        let msg = i.message || ''
        if (Array.isArray(i.images) && i.images.length > 0) {
          const imgs = i.images.map((src: string) => `[image:${src}]`).join(' ')
          msg = msg ? `${msg} \n${imgs}` : imgs
        }
        return `${who}\n${msg}\n`
      })
      .join('\n')

    text.value = txt
    await nextTick()
    feedParser.flush?.()
    logMan.syncChange(text.value, [], [])
  } catch (err) {
    console.error('[loadJsonFile] 加载失败:', err)
  }
}


onMounted(() => {
  const params = new URLSearchParams(window.location.search)
  const fileName = params.get('file')  // 例如 http://localhost:5173/?file=976953944_9d3f855a.json
  if (fileName) loadJsonFile(fileName)

  // 保留原有初始化逻辑
  offParsed = logMan.ev.on('parsed', (ret: { items: LogItem[] }) => {
    logMan.curItems = ret.items ?? []
    store.pcList = buildPcList(logMan.curItems)
    showPreview()
    rebuildSwatches()
    console.log('[parsed] rebuild pcList -> first few pc:', store.pcList.slice(0,5))
  })

  offTextSet = logMan.ev.on('textSet', (_txt: string) => { /* 不回写 */ })

  text.value = store.editor.state.doc.toString()
  feedParser.flush?.()
  logMan.syncChange(text.value, [], [])
  browserAlert()
})

onBeforeUnmount(() => {
  offParsed?.(); offParsed = undefined
  offTextSet?.(); offTextSet = undefined
})

// ===== 4) 你的原有函数：做了小调整以适配 text 源 =====
const colors = ref<string[]>([])
function rebuildSwatches() {
  const seen = new Set<string>()
  for (const pc of store.pcList) {
    const c = (pc.color || '').trim()
    if (c) seen.add(c)
  }
  // 不够时补一些常用保底色（可删）
  const base = ['#2563eb','#f97316','#16a34a','#a855f7','#ef4444','#0ea5e9','#f59e0b','#10b981']
  for (const c of base) {
    if (seen.size >= 16) break
    if (!seen.has(c)) seen.add(c)
  }
  colors.value = Array.from(seen).slice(0, 16)
}

function parseNameIdFromLine(s: string) {
  if (!s || typeof s !== 'string') return { name: '未知', IMUserId: '' }

  // 1) <名字>
  const m1 = s.match(/^<([^>]+)>/)
  if (m1) return { name: m1[1].trim(), IMUserId: '' }

  // 2) 行首 名字(或（)id)
  const m2 = s.match(/^[ \t]*([^\(\)（）<>\r\n]+?)[ \t]*[（(]([^)）\r\n]+)[)）]/)
  if (m2) return { name: m2[1].trim(), IMUserId: (m2[2] || '').trim() }

  // 3) 名字: 开头（例如 "名字：..." 或 "名字: ..."）
  const m3 = s.match(/^([^\r\n:：]+)[:：]/)
  if (m3) return { name: m3[1].trim(), IMUserId: '' }

  // 4) 最后一手：如果文本包含像 "名字(ID)" 的形式但被其他字符包裹，尝试捕获 name/id
  const m4 = s.match(/([^\s<]{1,40})[ \t]*[（(]([0-9a-zA-Z_\-]+)[)）]/)
  if (m4) return { name: m4[1].trim(), IMUserId: (m4[2] || '').trim() }

  // 5) 再退回：取行首第一个“词”
  const m5 = s.match(/^[ \t]*([^\s<]{1,40})/)
  if (m5) return { name: m5[1].trim(), IMUserId: '' }

  return { name: '未知', IMUserId: '' }
}

function randomColor(): string {
  // 返回一个亮度适中的随机颜色
  const h = Math.floor(Math.random() * 360);
  const s = 60 + Math.random() * 20; // 60~80% 饱和度
  const l = 50 + Math.random() * 10; // 50~60% 亮度
  return `hsl(${h}, ${s}%, ${l}%)`;
}

/* === 新增 1：替换 Map 引用，让依赖 pcNameColorMap 的组件也能感知更新 === */
function bumpColorMapRef() {
  // Pinia-safe：优先用 $patch，确保替换的是“引用”
  if (typeof (store as any).$patch === 'function') {
    (store as any).$patch((s: any) => {
      s.pcNameColorMap = new Map(s.pcNameColorMap)
    })
  } else {
    // 直接替换引用（若 store 不是 Pinia 也 OK）
    ;(store as any).pcNameColorMap = new Map((store as any).pcNameColorMap)
  }
}

/* === 新增 2：把 Map 中的颜色“应用回” pcList，并在有变化时整体替换数组引用 === */
function applyColorMapToPcList() {
  // 把 map 的颜色“应用回” pcList，并在有变化时整体替换数组引用
  const next = (store.pcList || []).map((p: CharItem) => {
    const mapped = store.pcNameColorMap.get(p.name)
    const newColor = mapped ?? p.color
    // 若颜色或其他需要变更的字段不同，则返回新对象（便于 Vue 侦测）
    return newColor !== p.color ? ({ ...p, color: newColor } as CharItem) : p
  })

  // 如果有任何一项对象发生替换，则整体替换数组引用，确保触发渲染
  let changed = false
  for (let i = 0; i < next.length; i++) {
    if (next[i] !== store.pcList[i]) { changed = true; break }
  }
  if (changed) {
    // @ts-ignore 若是 Pinia state，这种直接赋值 OK
    store.pcList = next
  }

  rebuildSwatches()
}

/** 当你点了色点选择颜色后：同步到着色映射 + 刷新（Map 与 pcList 双路刷新） */
const onColorPicked = debounce(async (pc: CharItem, v: string) => {
  if (!pc || !v) return
  // 先照旧写色
  pc.color = v
  if (pc.name) {
    store.pcNameColorMap.set(pc.name, v)
    store.colorMapSave?.()
  }
  // 关键：触发“剪贴等价”解析
  await simulateCutPasteParse()
}, 120)

function handlePcColorChange(pc: CharItem, v: string) {
  if (!pc || !v) return
  pc.color = v
  if (pc.name) {
    store.pcNameColorMap.set(pc.name, v)
    store.colorMapSave?.()
  }
  // 关键：触发“剪贴等价”解析
  simulateCutPasteParse()
}



/** 只要任何一个角色的颜色发生变化，就重建色板（展示“已用颜色”） */
watch(
  () => store.pcList.map(p => `${p.name}:${p.color}`),
  rebuildSwatches,
  { deep: false }
)

function recomputePreview() {
  const out: LogItem[] = []
  let idx = 0

  console.log('curItems:', logMan.curItems)

  for (const it of logMan.curItems) {
    if ((it as any).isRaw) continue

    // 一次性套所有导出规则（与原逻辑一致）
    let msg = msgImageFormat(it.message, store.exportOptions)
    msg = msgAtFormat(msg, store.pcList)
    msg = msgOffTopicFormat(msg, store.exportOptions, (it as any).isDice)
    msg = msgCommandFormat(msg, store.exportOptions)
    msg = msgIMUseridFormat(msg, store.exportOptions, (it as any).isDice)
    msg = msgOffTopicFormat(msg, store.exportOptions, (it as any).isDice) // 再过滤一次
    if (msg.trim() === '') continue

    out.push({ ...it, message: msg, index: idx as any })
    idx++
  }

  previewItems.value = out
  console.log(out)
}

const refreshCanvas = debounce(() => {
  recomputePreview()
  // 预览模式改变时也让编辑器装饰重算（有些导出开关会影响高亮）
  store.reloadEditor()
}, 120)

const clearText = () => {
  // 只操作 text 即可，watch(text) 会驱动解析 & 刷新
  text.value = ''
  // 如果你仍依赖 store.editor 的其他 API，可同步一份（不建议每次都 dispatch）
  store.editor.dispatch({ changes: { from: 0, to: store.editor.state.doc.length, insert: '' } })
}

const doFlush = async () => {
  // console.log('[UI] flush, len=', text.value.length)

  if(isFlushing) return

  await simulateCutPasteParse()
  // 不手动 showPreview：让 parsed 回调接管（与剪贴时的行为一致）
}

function getPreviewText() {
  return logMan.curItems
    .filter(i => !(i as any).is_comment) // 可按需要过滤场外发言
    .map((i, index) => {
      const date = i.date ?? ''
      const time = i.time ?? ''
      const name = i.nickname ?? ''
      const uin = i.IMUserId ?? ''
      const content = i.message ?? ''
      const prefix = `<${name}${uin ? `(${uin})` : ''}>:`
      const line = `${date ? date.replace(/-/g, '/') : ''} ${time} ${prefix} ${content}`.trim()
      return { line, nickname: name, date, time, IMUserId: uin, is_comment: i.is_comment, index }
    })
}

// 预览切换：保持你的逻辑
function previewClick(mode: 'preview' | 'bbs' | 'trg') {
  if (mode === 'preview') {
    isShowPreviewBBS.value = false
    isShowPreviewTRG.value = false
    store.exportOptions.imageHide = false
  } else if (mode === 'bbs') {
    isShowPreview.value    = false
    isShowPreviewTRG.value = false
    store.exportOptions.imageHide = true
  } else {
    isShowPreview.value    = false
    isShowPreviewBBS.value = false
    store.exportOptions.imageHide = true
  }
  refreshCanvas()
}

watch([isShowPreview, isShowPreviewBBS, isShowPreviewTRG], refreshCanvas)
watch(() => store.exportOptions, refreshCanvas, { deep: true })


// 导出：用 text.value 作为当前源（防止 store.editor 与 UI 不一致）
function exportRecordRaw() {
  browserAlert()
  exportFileRaw(text.value)
}

function exportRecordDOC() {
  browserAlert()
  if (isMobile.value) {
    message.warning('你当前处于移动端环境，已知只有WPS能够查看生成的Word文件，且无法看图！使用PC打开可以查看图片。')
  }

  const solveImg = (el: Element) => {
    if (el.tagName === 'IMG') {
      let width = (el as HTMLElement).clientWidth
      let height = (el as HTMLElement).clientHeight
      if (width === 0) { width = 300; height = 300 }
      el.setAttribute('width', `${width}`)
      el.setAttribute('height', `${height}`)
    }
    for (let i = 0; i < el.children.length; i += 1) solveImg(el.children[i])
  }

  const map = store.pcMap
  const items: string[] = []

  showPreview()

  for (const i of previewItems.value) {
    if ((i as any).isRaw) continue
    const id = packNameId(i)
    if (map.get(id)?.role === '隐藏') continue

    const mount = document.createElement('span')
    render(h(PreviewItem, { source: i }), mount)
    solveImg(mount)
    items.push(mount.innerHTML)
    render(null, mount)
  }

  exportFileDoc(items.join('\n'))
}

function exportRecordTalkDOC() {
  browserAlert()
  if (isMobile.value) {
    message.warning('你当前处于移动端环境，已知只有WPS能够查看生成的Word文件，且无法看图！使用PC打开可以查看图片。')
  }

  const solveImg = (el: Element) => {
    if (el.tagName === 'IMG') {
      let width = (el as HTMLElement).clientWidth
      let height = (el as HTMLElement).clientHeight
      if (width === 0) { width = 300; height = 300 }
      el.setAttribute('width', `${width}`)
      el.setAttribute('height', `${height}`)
    }
    for (let i = 0; i < el.children.length; i += 1) solveImg(el.children[i])
  }

  const map = store.pcMap
  const rows: string[] = []

  showPreview()

  for (const i of previewItems.value) {
    if ((i as any).isRaw) continue
    const id = packNameId(i)
    if (map.get(id)?.role === '隐藏') continue

    const mount = document.createElement('span')
    render(h(PreviewTableTR, { source: i }), mount)
    solveImg(mount)
    rows.push(mount.innerHTML)
    render(null, mount)
  }

  exportFileDoc(`<table style="border-collapse: collapse;"><tbody>${rows.join('\n')}</tbody></table>`)
}


/* ====== 实用函数 ====== */
function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** 颜色/映射用的 key：以 (name, IMUserId) 作为复合键，避免“同 ID 不同名被合并” */
function colorKeyOf(pc: CharItem) {
  // 以 name 为主键（你要求 pcname 可视为唯一）
  return (pc?.name ?? '').trim()
}
/** 让预览与编辑器做一个“零宽脉冲”来强制刷新（替代 F12/剪贴板） */
const renderNonce = ref(0)


/* ====== 名字编辑：焦点 & 变更 ====== */
const LP = '[\\(（]';
const RP = '[\\)）]';

let lastPCName = ''
const nameFocus = (i: CharItem) => { lastPCName = i.name || '' }

let lastNameChange = 0

/** 名字变更（仅改“该角色的发言行”里的名字，不处理 @） */
const nameChanged = async (i: CharItem, idx?: number) => {
  const now = Date.now()
  if (now - lastNameChange < 100) return
  lastNameChange = now

  // oldName：优先用 lastPCName，否则用 i.name
  const oldName = (lastPCName ?? '').trim() || (i.name ?? '').trim()
  const newName = (typeof idx === 'number' ? getNameDraft(i, idx) : i.name || '').trim()

  if (!newName) {
    if (typeof idx === 'number') setNameDraft(i, idx, oldName)
    i.name = oldName
    message.warning('名字不能为空')
    return
  }
  if (oldName === newName) return

  const id = (i.IMUserId || '').trim()

  // 1) 替换文本中名字，但保留空行和 ID
  let src = text.value
  let replaced = 0

  if (id) {
    // 仅替换名字部分，不动 ID，也不吞掉空行
    const reWithId = new RegExp(`(?<=^|\\n)${escapeRegExp(oldName)}(?=\\(${escapeRegExp(id)}\\))`, 'g')
    src = src.replace(reWithId, () => { replaced++; return newName })
  }
  if (!id || replaced === 0) {
    // 替换纯名字（不含括号）
    const reNoId = new RegExp(`(?<=^|\\n)${escapeRegExp(oldName)}(?=\\s|$|\\()`, 'g')
    src = src.replace(reNoId, () => { replaced++; return newName })
  }
  text.value = src

  // 2) 更新 pcList 中对象名字，保留 color/role/ID
  const foundIndex = (store.pcList || []).findIndex(p => (p.name || '').trim() === oldName)
  if (foundIndex !== -1) {
    const found = store.pcList[foundIndex]
    const newObj = { ...found, name: newName } as CharItem

    const next = store.pcList.slice()
    next[foundIndex] = newObj
    store.pcList = next

    // 迁移颜色
    const keptColor = found.color ?? i.color ?? '#8884ff'
    store.pcNameColorMap.set(newName, keptColor)
    if (store.pcNameColorMap.has(oldName) && oldName !== newName) store.pcNameColorMap.delete(oldName)
  } else {
    // 找不到旧对象：直接新增
    const keptColor = i.color ?? '#8884ff'
    const pushObj: CharItem = { name: newName, IMUserId: id, role: '角色', color: keptColor } as CharItem
    store.pcList = (store.pcList || []).concat(pushObj)
    store.pcNameColorMap.set(newName, keptColor)
    console.warn('[nameChanged] oldName not found in pcList; pushed new object')
  }

  store.colorMapSave?.()
  bumpColorMapRef()
  applyColorMapToPcList()

  // 3) 强制解析与刷新
  feedParser(text.value); feedParser.flush?.()
  await nextTick()
  renderNonce.value++
  store.reloadEditor?.()
  recomputePreview()

  if (typeof idx === 'number') setNameDraft(i, idx, newName)
  if (replaced === 0) message.warning('未在文本中找到可替换的说话行')
  else message.success(`已将「${oldName}」改为「${newName}」（${replaced} 处）`)
}


// =================== 调试工具 ===================
function logPcList(title = '[DEBUG] pcList') {
  console.log(title, store.pcList.map(p => ({
    name: p.name,
    IMUserId: p.IMUserId,
    color: p.color,
    role: p.role
  })))
}

function logPcMap(title = '[DEBUG] pcNameColorMap') {
  console.log(title, Array.from(store.pcNameColorMap.entries()))
}




/** 编辑器染色开关（改为吃布尔值，避免 e.target 冒泡带来的报错） */
const doEditorHighlightClick = (val: boolean) => {
  // 与 n-switch 的 @update:value 搭配
  const apply = () => setTimeout(() => { store.reloadEditor() }, 300)

  // 移动端开启染色给出提示（保留你的原逻辑）
  if (val && isMobile.value) {
    const m = modal.create({
      title: '开启编辑器染色？',
      preset: 'card',
      style: { width: '30rem' },
      content: '部分移动设备上的特定浏览器可能会因为兼容性问题而卡死，继续吗？',
      footer: () => [
        h(
          NButton,
          {
            type: 'default',
            onClick: () => {
              store.doEditorHighlight = false
              m.destroy()
              setTimeout(() => { doFlush() }, 300)
            },
            style: { marginRight: '1rem' }
          },
          () => '取消'
        ),
        h(
          NButton,
          {
            type: 'primary',
            onClick: () => {
              try { store.doEditorHighlight = true; apply() }
              catch {
                setTimeout(() => {
                  store.doEditorHighlight = false
                  store.reloadEditor()
                }, 300)
              } finally { m.destroy() }
            }
          },
          () => '确定'
        )
      ]
    })
    return
  }

  store.doEditorHighlight = val
  apply()
}

// —— 主题/配置变化时重载编辑器（保持原逻辑） —— //
const reloadFunc = () => { store.reloadEditor() }
const pcList = computed(() => store.pcList)
watch(pcList, reloadFunc, { deep: true })

const exportOptions = computed(() => store.exportOptions)
watch(exportOptions, reloadFunc, { deep: true })
</script>

<!-- 全局：变量 & 透明底 & 防溢出 -->
<style>
:root{
  --sider-width: 320px;
  --nav-track-frac: 0.6667;                  /* 左侧内容占 2/3 */
  --left-gutter: calc(var(--sider-width) * (1 - var(--nav-track-frac))); /* 左侧 1/3 空白 */
  --content-pad: 20px;                       /* 基本内边距 */
}
.n-layout,
.n-layout-sider,
.n-layout-header,
.n-layout-footer,
.n-layout .n-layout-scroll-container {
  background: transparent !important;
}
html, body { overflow-x: hidden; }
</style>

<style scoped>
/* ……(你已有的样式照旧，比如背景、sider-grid、collapse 等) …… */

/* 右侧工作区：不要再用 padding-right 套“右缩进”了 */
.work-area{
  padding-left: var(--content-pad);
  padding-right: var(--content-pad);   /* 先保持常规内边距 */
  padding-top: 18px;
  padding-bottom: 22px;
  display:flex; flex-direction:column; min-height:100vh;
  overflow-x: hidden;
  box-sizing: border-box;
}

/* 核心：直接给编辑器卡片加右侧外边距，镜像左侧 1/3 空白 */
.work-area > .editor-shell{
  margin-right: var(--left-gutter);    /* 这就是右侧“缩进”，与左侧空白完全相等 */
  margin-left: 0;                      /* 左边仍然靠近内容区 */
  width: auto;
  max-width: calc(100% - var(--left-gutter)); /* 防止超宽贴边 */
}

/* 如果你还想左右都更松一点，可以这样（可选）：
.work-area > .editor-shell{
  margin-left: var(--content-pad);
  margin-right: calc(var(--left-gutter) + var(--content-pad));
}
*/

/* 其余（玻璃态与 CodeMirror 高度/焦点）保持不变 */

.app-bg {
  min-height: 100vh;
  background: linear-gradient(
    90deg,
    #4a90e2 0%,   /* 更深的淡蓝 */
    #ffffff 50%, /* 中间白色 */
    #ff6fae 100% /* 更鲜艳的粉色 */
  );
}

/* 深色模式下可选的温和渐变（也可以继续用浅色，看你喜好） */
:global(.dark) .app-bg{
  background: linear-gradient(
    90deg,
    #0f172a 0%,
    #0b1020 50%,
    #1a0f1b 100%
  );
}

.editor-shell{ display:flex; flex-direction:column; border-radius:16px; overflow:hidden; }
.glass{
  background: rgba(255,255,255,.35);
  backdrop-filter: blur(12px) saturate(160%);
  -webkit-backdrop-filter: blur(12px) saturate(160%);
  border: 1px solid rgba(255,255,255,.45);
  box-shadow: 0 10px 24px rgba(0,0,0,.06);
}
:global(.dark) .glass{
  background: rgba(20,20,28,.38); border-color: rgba(255,255,255,.12);
  box-shadow: 0 10px 30px rgba(0,0,0,.45);
}
.editor-head{
  display:flex; align-items:center; justify-content:space-between;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(0,0,0,.06);
}
:global(.dark) .editor-head{ border-bottom-color: rgba(255,255,255,.10); }
.editor-title{
  display:flex; align-items:center; gap:10px;
  font-weight:800; font-size:18px; letter-spacing:.02em;
  background: linear-gradient(90deg,#4f83ff,#ff7fc7);
  -webkit-background-clip:text; background-clip:text; color:transparent;
}
.editor-title .dot{
  width:10px; height:10px; border-radius:50%;
  background: radial-gradient(circle at 30% 30%, #7db0ff, #e69fff);
  box-shadow: 0 0 0 5px rgba(125,176,255,.18);
}
.editor-body{ flex:1; min-height:0; padding: 12px; }

/* CodeMirror 全高 & 去掉 focus 外框 */
.editor-body :deep(.cm-root),
.editor-body :deep(.cm-editor){ height: 100%; width: 100%; box-sizing: border-box; }
.editor-body :deep(.cm-editor.cm-focused){ outline: none !important; box-shadow: none !important; }
.editor-body :deep(.cm-scroller){ overflow: auto; }

/* 响应式：小屏时取消右侧缩进（可选） */
@media (max-width: 1024px){
  .work-area > .editor-shell{
    margin-right: 0;
    max-width: 100%;
  }
}
</style>

<style scoped>

/* ============ 左侧：固定宽 + 网格实现“左 1/3 空白 / 右 2/3 内容” ============ */
.sider-clear{
  background: transparent !important;
  border-right: 1px solid rgba(0,0,0,.06);
}
:global(.dark) .sider-clear{ border-right-color: rgba(255,255,255,.08); }

/* 两列栅格：1fr(空白) + 2fr(内容) 保证左缩进总是存在 */
.sider-grid{
  display: grid;
  grid-template-columns: 1fr 2fr;  /* 比例与 1/3、2/3 等比 */
  height: 100%;
}
.sider-gutter{ /* 空着，制造左 1/3 缩进 */ }
.sider-col{
  padding-right: 8px;             /* 内容与右边界留点呼吸位 */
  display: flex;
  flex-direction: column;
}

/* 标题块 */
.nav-brand{
  display:flex; align-items:center; justify-content:flex-start;
  padding: 10px 0 6px 0;
}
.brand-left{ display:flex; align-items:center; gap:10px; }
.brand-dot{ width:10px; height:10px; border-radius:50%;
  background: radial-gradient(circle at 30% 30%, #8ec5ff, #e59bff);
  box-shadow: 0 0 0 6px rgba(142,197,255,.18);
}
.brand-title{ font-size:14px; font-weight:800; letter-spacing:.02em; }
.brand-sub{ font-size:12px; opacity:.65; }

/* 折叠：大选项之间不放任何分割元素 */
:deep(.nav-collapse .n-collapse-item){ border: none; margin: 6px 0; }
:deep(.nav-collapse .n-collapse-item__header){
  background: transparent;
  height: 30px; line-height: 30px; padding: 0;
  border-radius: 6px; cursor: pointer;
}
:deep(.nav-collapse .n-collapse-item__header:hover){ background: rgba(0,0,0,.04); }
:global(.dark) :deep(.nav-collapse .n-collapse-item__header:hover){ background: rgba(255,255,255,.06); }
.nav-group{
  font-weight: 800; font-size: 13px; letter-spacing:.02em;
  color: #4c73d8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
:global(.dark) .nav-group{ color: #93b2ff; }

/* 子项容器：缩进 + 从标题左侧引下来的竖线 */
.nav-children{
  position: relative;
  margin-top: 4px;
  margin-left: 8px;
  padding-left: 12px;
}
.nav-children::before{
  content: "";
  position: absolute;
  left: 0; top: -6px; bottom: 2px;
  width: 2px;
  background: linear-gradient(180deg, rgba(92,142,255,.35), rgba(255,122,69,.25));
  border-radius: 2px;
}

/* 子项：按钮式操作 */
.nav-children li{ list-style: none; }
.nav-item{
  appearance: none; border: none; background: transparent; color: inherit;
  text-align: left; padding: 4px 8px; margin: 2px 0; width: 100%;
  font-size: 13px; line-height: 22px; border-radius: 6px; cursor: pointer;
  white-space: nowrap; text-overflow: ellipsis; overflow: hidden;
  transition: background .12s, transform .05s;
}
.nav-item::before{
  content: ""; display:inline-block; width:6px; height:6px; margin-right:8px; border-radius:50%;
  background: radial-gradient(circle at 30% 30%, #7db0ff, #e69fff);
  vertical-align: middle;
}
.nav-item:hover{ background: rgba(0,0,0,.04); }
.nav-item:active{ transform: translateY(1px); }
:global(.dark) .nav-item:hover{ background: rgba(255,255,255,.06); }
.nav-item.danger{ color:#e15656; }
:global(.dark) .nav-item.danger{ color:#ff7a7a; }

/* 子项：设置行（左文字右开关/按钮） */
.op-row{
  display:flex; align-items:center; justify-content:space-between;
  padding: 4px 8px; margin: 2px 0; border-radius: 6px;
  transition: background .12s;
}
.op-row:hover{ background: rgba(0,0,0,.04); }
:global(.dark) .op-row:hover{ background: rgba(255,255,255,.06); }
.op-label{ font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.op-action{
  appearance:none; border:1px solid rgba(0,0,0,.12); background: rgba(0,0,0,.02);
  font-size:12px; line-height: 22px; padding: 0 10px; border-radius: 999px; cursor:pointer;
}
:global(.dark) .op-action{ border-color: rgba(255,255,255,.16); background: rgba(255,255,255,.06); }
.op-action:hover{ filter: brightness(1.05); }
.op-action:active{ transform: translateY(1px); }

/* 角色行 */
.pc-row{ display:flex; align-items:center; gap:8px; padding:4px 0; }
.nav-input :deep(.n-input__input-el){ height: 28px; font-size: 13px; }

/* ============ 右侧工作区：右侧缩进 = 左侧 1/3 空白（mirror） ============ */
.work-area{
  padding-left: var(--content-pad);
  padding-right: calc(var(--content-pad) + var(--left-gutter)); /* 右侧镜像缩进 */
  padding-top: 18px;
  padding-bottom: 22px;
  display:flex; flex-direction:column; min-height:100vh;
  overflow-x: hidden;
  box-sizing: border-box;
}

/* 编辑器卡片（玻璃态） */
.editor-shell{ display:flex; flex-direction:column; border-radius:16px; overflow:hidden; }
.glass {
  background: rgba(255,255,255,.35);
  backdrop-filter: blur(12px) saturate(160%);
  -webkit-backdrop-filter: blur(12px) saturate(160%);
  border: 1px solid rgba(255,255,255,.45);
}
:global(.dark) .glass{
  background: rgba(20,20,28,.38); border-color: rgba(255,255,255,.12);
}
.editor-head{
  display:flex; align-items:center; justify-content:space-between;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(0,0,0,.06);
}
:global(.dark) .editor-head{ border-bottom-color: rgba(255,255,255,.10); }
.editor-title{
  display:flex; align-items:center; gap:10px;
  font-weight:800; font-size:18px; letter-spacing:.02em;
  background: linear-gradient(90deg,#4f83ff,#ff7fc7);
  -webkit-background-clip:text; background-clip:text; color:transparent;
}
.editor-title .dot{
  width:10px; height:10px; border-radius:50%;
  background: radial-gradient(circle at 30% 30%, #7db0ff, #e69fff);
  box-shadow: 0 0 0 5px rgba(125,176,255,.18);
}
.editor-body{ flex:1; min-height:0; padding: 12px; }

/* CodeMirror：全高、去外轮廓 */
.editor-body :deep(.cm-root),
.editor-body :deep(.cm-editor){ height: 100%; width: 100%; box-sizing: border-box; }
.editor-body :deep(.cm-editor.cm-focused){ outline: none !important; box-shadow: none !important; }
.editor-body :deep(.cm-scroller){ overflow: auto; }
</style>

<style>
/* 让页面能撑满视口，否则看起来像只有白底 */
html, body, #app { height: 100%; }

/* 把渐变画在 body 上：左→右 淡蓝→白→粉（颜色更浓一点）*/
body{
  background:
    /* 顶层：纵向“洗白”遮罩 */
    linear-gradient(
      to bottom,
      rgba(255,255,255,0) 0%,
      rgba(255,255,255,0.35) 10vh,
      rgba(255,255,255,0.7) 25vh,
      #ffffff 40vh,
      #ffffff 100%
    ),
    /* 底层：横向蓝→白(宽区间)→粉 */
    linear-gradient(
      to right,
rgb(202, 221, 241) 0%,
      #ffffff 70%,
rgb(250, 224, 237) 100%
    ) !important;
  background-attachment: fixed;
}

/* 深色模式下的渐变（按需调） */
html.dark body {
  background: 
  linear-gradient(
    90deg,
    #0b1224 0%,
    #0a0f1f 50%,
    #1b0f19 100%
  ) !important;
  background-attachment: fixed;
}

/* 把 Naive UI 的容器背景统统设为透明，别挡住 body 的渐变 */
.n-layout,
.n-layout-sider,
.n-layout-header,
.n-layout-footer,
.n-layout-content,
.n-layout .n-layout-scroll-container {
  background: transparent !important;
}

/* 你的内容层抬到渐变之上（以防万一）*/
.app-shell, .app-bg, .app-main {
  position: relative;
  z-index: 1;
}

.role-header{
  display:flex;
  align-items:center;
  gap:.5rem;
  line-height: 1.2;
  padding: 2px 0;
}
.role-dot{
  width:6px; height:6px; border-radius:50%;
  box-shadow: 0 0 0 2px rgba(0,0,0,.05) inset;
}
.role-name{
  font-size: 14px;
  color: var(--nap-text, rgba(0,0,0,.82));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 展开区：每行一个操作（左：标签，右：控件） */
.role-fields{
  display:flex;
  flex-direction:column;
  gap:.5rem;
  padding:.5rem 0 .25rem;
}
.role-field{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:1rem;
  min-height: 32px;
  border-bottom: 1px dashed rgba(0,0,0,.06);
}
.role-field:last-child{ border-bottom: 0; }

.role-field .label{
  font-size: 13px;
  color: rgba(0,0,0,.45);
}

/* 内层折叠去掉多余背景/间距，保持干净的“线”风格 */
.role-collapse .n-collapse-item{
  background: transparent;
}
.role-collapse .n-collapse-item__header{
  padding: 6px 0;
}
.role-collapse .n-collapse-item__content{
  padding: 0 0 6px 0;
}

/* 角色折叠内容总容器，不能再把父列撑宽 */
.role-fields{
  display:flex;
  flex-direction:column;
  gap:.5rem;
  padding:.5rem 0 .25rem;
  width:100%;
  box-sizing:border-box;
}

/* 一行 = 左侧固定标签 + 右侧自适应区域 */
.role-field{
  display:flex;
  align-items:center;
  justify-content:flex-start;   /* 不要 space-between，否则会把控件推到最右 */
  gap:.5rem;
  width:100%;
  min-width:0;                  /* 允许在窄列中收缩 */
}

.role-field .label{
  flex:0 0 52px;                /* 标签固定宽度，别太大，适配 2/3 列宽 */
  text-align:right;
  font-size:13px;
  color:rgba(0,0,0,.45);
}

.role-field .field-body{
  flex:1 1 auto;                /* 控件区域自适应 */
  min-width:0;                  /* 防止溢出撑宽 */
}

/* 放在 field-body 里的表单控件默认占满可用宽度 */
.role-field .field-body .n-input,
.role-field .field-body .n-select,
.role-field .field-body .n-button,
.role-field .field-body .n-tag{
  width:100%;
}

/* 颜色触发器做成小而不撑行的样子 */
.role-field .field-body .n-color-picker{
  display:inline-block;
}
.role-field .field-body .n-color-picker .n-color-picker-trigger{
  width:28px;                   /* 小尺寸色块，不会挤出列宽 */
  height:20px;
  padding:0;
}

/* 如果你的 sider 2/3 列本身需要硬限制，保护一下 */
.sider-col{
  max-width:100%;
  overflow:visible;             /* 不隐藏内容，但不允许撑宽网格列 */
  box-sizing:border-box;
}

/* 防止 n-collapse 内部内容意外把列撑开 */
.nav-children, .role-collapse{
  max-width:100%;
  box-sizing:border-box;
}

/* 根：别让外层决定宽度 */
:deep(.cp-round){
  display: inline-block !important;
}

/* 关键：把触发器缩成圆点，并清掉 min-width */
:deep(.cp-round .n-color-picker-trigger){
  width: 22px !important;
  height: 22px !important;
  min-width: 0 !important;
  padding: 0 !important;
  border-radius: 9999px !important;
  box-shadow: 0 1px 2px rgba(0,0,0,.06) !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
}

/* 隐藏十六进制文本（不同版本内部结构不一样，全部兜一遍） */
:deep(.cp-round .n-color-picker-trigger__value),
:deep(.cp-round .n-color-picker-preview__value),
:deep(.cp-round .n-color-picker-trigger .n-input),
:deep(.cp-round .n-color-picker-trigger .n-input__input){
  display: none !important;
}

/* 让内部颜色块/棋盘也跟圆 */
:deep(.cp-round .n-color-picker-checkboard),
:deep(.cp-round .n-color-picker-trigger__fill),
:deep(.cp-round .n-color-picker-preview__fill){
  border-radius: 9999px !important;
}

/* 面板宽度别太大 */
:deep(.cp-round .n-color-picker-panel){
  max-width: 260px;
}

/* 与上方分组标题的距离更紧凑 */
.nav-group--roles { margin-top: 4px; }

/* —— 紧凑头部：小圆点 + 名字 —— */
.role-header--compact {
  display: flex; align-items: center; gap: 6px;
  min-width: 0;
  font-size: 13px;
  line-height: 1.2;
}

/* 把 ColorDot 缩小为更小尺寸（不改组件本体也能生效） */
.role-header--compact .color-dot {
  width: 14px; height: 14px;
  border-width: 1px;
}

/* 长名省略，不挤歪侧栏 */
.role-name {
  flex: 1 1 auto; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: rgba(60, 60, 67, .85);
}

/* 隐藏“子级”折叠箭头，仅保留点击折叠行为 */
.role-collapse .n-collapse-item__arrow { display: none !important; }

/* 折叠项外边距与内边距小型化 */
.role-item--compact .n-collapse-item__header {
  padding: 4px 0;
}
.role-fields--compact { padding: 4px 0 0 10px; }

/* 子项：单行栅格，紧凑字号/行高 */
.role-field {
  display: grid; grid-template-columns: 52px 1fr;
  align-items: center; gap: 6px;
  padding: 4px 0;
  border: none !important;           /* 去掉虚线之类 */
}
.role-field .label {
  color: rgba(60, 60, 67, .6);
  font-size: 12px;
  user-select: none;
}
.role-field .field-body {
  display: flex; align-items: center; gap: 6px;
}

/* 小号链接按钮（换一组 / 删除） */
.link {
  background: transparent; border: 0; padding: 0;
  color: #5b7dde; cursor: pointer;
  font-size: 13px;
}
.link.xs { font-size: 12px; }
.link.danger { color: #e15b5b; }

/* 输入/选择控件更紧凑 */
:deep(.n-input--small .n-input__input-el),
:deep(.n-base-selection--small .n-base-selection-label) {
  font-size: 12px;
}

/* 防止任何容器把侧栏挤歪 */
.sider-col, .nav-track, .role-collapse, .role-item { min-width: 0; }

/* 宽度铺满工具类 */
.w-fill { width: 100%; }

/* 与上方分组标题距离更紧凑 */
.nav-group--roles { margin-top: 4px; }

/* 隐藏子级折叠箭头，只保留“圆点+名字”的头部 */
.role-collapse .n-collapse-item__arrow { display: none !important; }

/* —— 紧凑头部：小圆点 + 名字 —— */
.role-item .n-collapse-item__header { padding: 4px 0; }
.role-header--compact{
  display:flex; align-items:center; gap:6px;
  min-width:0; font-size:13px; line-height:1.2;
}
/* 缩小 ColorDot（跨子组件作用域） */
.role-header--compact :deep(.color-dot){
  width:14px; height:14px; border-width:1px;
}

/* 长名省略，不挤歪侧栏 */
.role-name{
  flex:1 1 auto; min-width:0;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  color:rgba(60,60,67,.85);
}

/* 角色子选项：竖线使用角色专属颜色变量 */
.role-fields{
  padding:6px 0 2px 10px; margin-left:8px;
  border-left:2px solid var(--role-accent, rgba(99,102,241,.18));
}
.role-fields--compact{ padding-top:4px; }

/* 子项：单行栅格，紧凑字号/行高；无任何分隔线 */
.role-field{
  display:grid; grid-template-columns:52px 1fr;
  align-items:center; gap:6px; padding:4px 0; border:none !important;
}
.role-field .label{ color:rgba(60,60,67,.6); font-size:12px; user-select:none; }
.role-field .field-body{ display:flex; align-items:center; gap:6px; }

/* link 风格按钮（换一组 / 删除） */
.link{ background:transparent; border:0; padding:0; color:#5b7dde; cursor:pointer; font-size:13px; }
.link.xs{ font-size:12px; }
.link.danger{ color:#e15b5b; }

/* 输入/选择控件更紧凑 */
:deep(.n-input--small .n-input__input-el),
:deep(.n-base-selection--small .n-base-selection-label){ font-size:12px; }

/* 防止任何容器把侧栏挤歪 */
.sider-col, .nav-track, .role-collapse, .role-item{ min-width:0; }

/* 宽度铺满工具类 */
.w-fill{ width:100%; }

/* （可选）展开时给“角色名行”也来一条细色条，和子项呼应 */
.role-header{ position:relative; }
.role-header::before{
  content:""; position:absolute; left:-10px; top:2px; bottom:2px;
  width:2px; background:transparent; border-radius:1px;
}
:deep(.n-collapse-item--active) .role-header::before{
  background: var(--role-accent, rgba(99,102,241,.35));
}

/* 让页面本身不滚动，交给右侧区域滚 */
html, body, #app { height: 100%; overflow: hidden; }

/* 顶层布局充满视口 */
.app-shell, .app-main { height: 100vh; overflow: hidden; }

/* 左侧固定（不随页面滚动），自身内容超出时左栏内部滚动 */
.sider-fixed {
  position: sticky;   /* 也可用 fixed，但 sticky 更省心 */
  top: 0;
  align-self: flex-start; /* 防止被拉伸 */
  height: 100vh;
  overflow-y: auto;   /* 左侧内容太长时，左栏自身滚 */
}

/* 右侧独立滚动：只让右侧内容滚动 */
.only-right-scroll {
  height: 100vh;
  overflow: hidden;   /* 外层不滚，把滚动交给内部主体 */
}

/* 右侧编辑器壳子铺满高度，头部 + 自适应内容 */
.editor-shell {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;      /* 关键：允许子元素收缩 */
}

/* 编辑器正文占满剩余空间，并在此层开启滚动（给 CodeMirror 用） */
.editor-body {
  flex: 1 1 auto;
  min-height: 0;      /* 关键：配合 flex 才能让子元素 100% 高度生效 */
  overflow: hidden;   /* 由 CodeMirror 自己内部滚动 */
}

/* CodeMirror 容器与编辑器本体全高，滚动在 CM 里发生 */
.ide-box,
:deep(.cm-editor) {
  height: 100%;
}

/* 可选：去掉编辑器聚焦时外圈的“选框/阴影” */
.ide-box:focus-within { outline: none; box-shadow: none; }

/* 如果你想让右侧也保留一点右内边距，防止紧贴屏幕：自行调整 */
.only-right-scroll { padding-right: 20px; box-sizing: border-box; }

/* 兼容：Naive Layout 在有 sider 时用 flex，确保不被其他容器 overflow 影响 sticky */
:deep(.n-layout.has-sider) { overflow: visible; }

.sider-fixed {
  position: sticky;
  top: 0;
  align-self: flex-start;
  height: 100vh;
  overflow-y: auto;

  /* 关键：用 flex-basis / max-width 控制宽度为 ~50% */
  flex: 0 0 50%;
  max-width: 50%;
  min-width: 420px;   /* 可按需调小/调大，避免太窄 */
}

/* 右侧占剩余空间，不滚动（滚动交给编辑器内部） */
.work-area {
  flex: 1 1 0%;
  min-width: 0;
}

/* 如果你的布局在较窄屏时需要收缩一些，可以加响应式（可选） */
@media (max-width: 1440px) {
  .sider-fixed { flex-basis: 46%; max-width: 46%; }
}
@media (max-width: 1200px) {
  .sider-fixed { flex-basis: 42%; max-width: 42%; }
}

</style>

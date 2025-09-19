// src/main.ts
import { createApp } from 'vue'
import App from './App.vue'
import {
  create,
  // Provider & 布局 & 抽屉
  NConfigProvider, NMessageProvider, NDialogProvider, NModalProvider,
  NLayout, NLayoutHeader, NLayoutContent, NLayoutSider,
  NDrawer, NDrawerContent,
  // 常用UI
  NCard, NFlex, NButton, NText, NIcon, NTag, NInput, NSelect,
  NColorPicker, NCheckbox, NDivider, NTooltip, NSpin,
  NCollapse, NCollapseItem
} from 'naive-ui'

const app = createApp(App)

const naive = create({
  components: [
    NConfigProvider, NMessageProvider, NDialogProvider, NModalProvider,
    NLayout, NLayoutHeader, NLayoutContent, NLayoutSider,
    NDrawer, NDrawerContent,
    NCard, NFlex, NButton, NText, NIcon, NTag, NInput, NSelect,
    NColorPicker, NCheckbox, NDivider, NTooltip, NSpin,
    NCollapse, NCollapseItem
  ]
})

app.use(naive)
app.mount('#app')

<!-- src/App.vue -->
<script setup lang="ts">
import Main from './components/main.vue'
import {
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  NModalProvider
} from 'naive-ui'
</script>

<template>
  <n-config-provider>
    <n-message-provider>
      <n-dialog-provider>
        <n-modal-provider>
          <Main />
        </n-modal-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

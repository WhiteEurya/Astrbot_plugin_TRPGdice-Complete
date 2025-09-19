<script setup lang="ts">
const props = defineProps<{
  isShow: boolean
  previewItems: {
    nickname: string
    message: string
  }[]
}>()
</script>

<template>
  <pre v-if="props.isShow" class="preview">
    [TRG PREVIEW]\n{{ JSON.stringify(props.previewItems, null, 2) }}
  </pre>
</template>

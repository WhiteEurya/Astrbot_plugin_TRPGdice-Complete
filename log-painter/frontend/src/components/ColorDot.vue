<script setup lang="ts">
import { ref, watch, defineProps, defineEmits } from 'vue'

const props = defineProps<{
  modelValue?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const local = ref(props.modelValue || '#8884ff')

watch(() => props.modelValue, (v) => {
  if (v && v !== local.value) local.value = v
})

const openPicker = () => inputRef.value?.click()
const onInput = (e: Event) => {
  const v = (e.target as HTMLInputElement).value // #RRGGBB
  local.value = v
  emit('update:modelValue', v)
}
</script>

<template>
  <!-- 圆形色点按钮：不会撑开侧栏 -->
  <button
    type="button"
    class="color-dot"
    :style="{ backgroundColor: local }"
    aria-label="选择颜色"
    @click="openPicker"
  />
  <!-- 原生取色器：隐藏，仅用于调色 -->
  <input
    ref="inputRef"
    class="color-native"
    type="color"
    :value="local"
    @input="onInput"
  />
</template>

<style scoped>
/* 隐藏但可用 */
.color-native {
  position: absolute;
  opacity: 0;
  pointer-events: none;
  width: 0;
  height: 0;
}

/* 小圆点触发器 */
.color-dot {
  width: 20px;
  height: 20px;
  border-radius: 9999px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  padding: 0;
  display: inline-block;
}
.color-dot:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, .25);
}
</style>
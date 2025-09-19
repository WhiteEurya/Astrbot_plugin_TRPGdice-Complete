import { createRouter, createWebHistory } from 'vue-router';
import JsonEditor from '@/components/JsonEditor.vue';

const routes = [
  {
    // “:fileName?” 表示 fileName 可选
    path: '/editor/:fileName?',
    name: 'JsonEditor',
    component: JsonEditor
  }
];

export default createRouter({
  history: createWebHistory(),
  routes
});
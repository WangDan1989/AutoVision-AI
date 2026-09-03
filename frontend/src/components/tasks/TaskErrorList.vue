<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  tasks: any[];
}>();

const failedTasks = computed(() => props.tasks.filter((item) => item.status === "FAILED"));
</script>

<template>
  <section v-if="failedTasks.length" class="task-error-list">
    <article v-for="task in failedTasks" :key="task.id" class="task-error-card">
      <strong>{{ task.task_type }}</strong>
      <p>{{ task.error_message || "任务失败" }}</p>
    </article>
  </section>
</template>

<script setup lang="ts">
import { useToastStore } from "../../stores/toast";

const toast = useToastStore();
</script>

<template>
  <div class="toast-container">
    <div
      v-for="item in toast.items"
      :key="item.id"
      class="toast-item"
      :class="`toast-${item.type}`"
    >
      {{ item.message }}
    </div>
  </div>
</template>

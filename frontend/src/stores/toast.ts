import { defineStore } from "pinia";
import { ref } from "vue";

type ToastType = "success" | "error" | "info";

export const useToastStore = defineStore("toast", () => {
  const items = ref<Array<{ id: string; type: ToastType; message: string }>>([]);

  function push(type: ToastType, message: string) {
    const id = `${Date.now()}_${Math.random()}`;
    items.value.push({ id, type, message });
    window.setTimeout(() => {
      items.value = items.value.filter((item) => item.id !== id);
    }, 3000);
  }

  return {
    items,
    success: (message: string) => push("success", message),
    error: (message: string) => push("error", message),
    info: (message: string) => push("info", message),
  };
});

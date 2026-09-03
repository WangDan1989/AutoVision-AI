import { onBeforeUnmount, ref } from "vue";

import { useProjectWorkbenchStore } from "../stores/projectWorkbench";

export function useTaskPolling(projectId: string) {
  const store = useProjectWorkbenchStore();
  const timer = ref<number | null>(null);

  async function tick() {
    await store.refresh(projectId);
    if (!store.tasks.some((item) => item.status === "RUNNING")) {
      stop();
    }
  }

  function start() {
    if (timer.value !== null) return;
    timer.value = window.setInterval(() => {
      void tick();
    }, 2000);
  }

  function stop() {
    if (timer.value !== null) {
      clearInterval(timer.value);
      timer.value = null;
    }
  }

  onBeforeUnmount(stop);

  return { start, stop, tick };
}

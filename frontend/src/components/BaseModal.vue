<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';

const props = withDefaults(
  defineProps<{
    id: string;
    title: string;
    busy?: boolean;
  }>(),
  {
    busy: false,
  },
);

const emit = defineEmits<{
  close: [];
}>();

const dialog = ref<HTMLDialogElement | null>(null);
const heading = ref<HTMLHeadingElement | null>(null);

function requestClose() {
  if (props.busy) return;
  emit('close');
}

onMounted(() => {
  dialog.value?.showModal();
  heading.value?.focus();
});

onBeforeUnmount(() => {
  dialog.value?.close();
});
</script>

<template>
  <dialog
    ref="dialog"
    class="modal"
    :aria-labelledby="`${id}-title`"
    :aria-busy="busy"
    @cancel.prevent="requestClose"
  >
    <div class="modal-content">
      <h2 :id="`${id}-title`" ref="heading" tabindex="-1" class="modal-title">
        {{ title }}
      </h2>

      <slot />

      <div class="modal-actions">
        <slot name="actions" :request-close="requestClose" />
      </div>
    </div>
  </dialog>
</template>

<style scoped>
.modal {
  width: calc(100% - 32px);
  max-width: 520px;
  max-height: calc(100dvh - 32px);
  margin: auto;
  padding: var(--space-6);
  overflow-y: auto;

  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  color: var(--color-text);
  background-color: var(--color-surface);
}

.modal::backdrop {
  background-color: rgb(0 0 0 / 60%);
}

.modal-content {
  display: grid;
  gap: var(--space-4);
}

.modal-title {
  margin: 0;
}

.modal-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>

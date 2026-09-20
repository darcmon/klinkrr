<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'danger';
    type?: 'button' | 'submit' | 'reset';
    disabled?: boolean;
  }>(),
  {
    variant: 'primary',
    type: 'button',
    disabled: false,
  },
);
</script>

<template>
  <button
    class="base-button"
    :class="`base-button--${variant}`"
    :type="type"
    :disabled="disabled"
  >
    <slot />
  </button>
</template>

<style scoped>
.base-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  min-height: 44px;
  padding: var(--space-2) var(--space-4);
  border: 1px solid transparent;
  border-radius: var(--radius-medium);
  font-weight: var(--weight-semibold);
  cursor: pointer;
}

.base-button--primary {
  color: var(--color-on-primary);
  background-color: var(--color-primary);
}

.base-button--primary:hover:not(:disabled) {
  background-color: var(--color-primary-hover);
}

.base-button--secondary {
  color: var(--color-text);
  background-color: var(--color-surface);
  border-color: var(--color-border);
}

.base-button--secondary:hover:not(:disabled) {
  background-color: var(--color-surface-muted);
}

.base-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.base-button--danger {
  color: var(--color-on-danger);
  background-color: var(--color-danger);
}

.base-button--danger:hover:not(:disabled) {
  background-color: var(--color-danger-hover);
}
</style>

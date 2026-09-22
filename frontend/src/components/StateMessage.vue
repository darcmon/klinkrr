<script setup lang="ts">
withDefaults(
  defineProps<{
    message: string;
    tone?: 'neutral' | 'error' | 'success';
  }>(),
  {
    tone: 'neutral',
  },
);
</script>

<template>
  <div class="state-message" :class="`state-message--${tone}`">
    <p :role="tone === 'error' ? 'alert' : 'status'">
      {{ message }}
    </p>

    <div v-if="$slots.actions" class="state-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.state-message {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
  overflow-wrap: anywhere;
}

.state-message p {
  margin: 0;
}

.state-message--error {
  color: var(--color-rejected-text);
  background-color: var(--color-rejected-bg);
}

.state-message--success {
  color: var(--color-approved-text);
  background-color: var(--color-approved-bg);
}

.state-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>

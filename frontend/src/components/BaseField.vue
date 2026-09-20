<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  id: string;
  label: string;
  hint?: string;
  error?: string;
}>();

const describedBy = computed(() => {
  const ids = [];

  if (props.hint) ids.push(`${props.id}-hint`);
  if (props.error) ids.push(`${props.id}-error`);

  return ids.length > 0 ? ids.join(' ') : undefined;
});
</script>

<template>
  <div class="field">
    <label :for="id" class="field-label">
      {{ label }}
    </label>

    <slot :id="id" :described-by="describedBy" :invalid="Boolean(error)" />

    <p v-if="hint" :id="`${id}-hint`" class="field-hint">
      {{ hint }}
    </p>

    <p v-if="error" :id="`${id}-error`" class="field-error" role="alert">
      {{ error }}
    </p>
  </div>
</template>

<style scoped>
.field {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.field-label {
  font-weight: var(--weight-medium);
}

.field-hint,
.field-error {
  margin: 0;
  font-size: var(--text-small);
  overflow-wrap: anywhere;
}

.field-hint {
  color: var(--color-muted);
}

.field-error {
  color: var(--color-rejected-text);
}
</style>

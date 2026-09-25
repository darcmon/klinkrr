<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    tone?: 'neutral' | 'ok' | 'new' | 'pending' | 'error';
  }>(),
  { tone: 'neutral' },
);
</script>

<template>
  <span class="state-pill" :class="`state-pill--${tone}`">{{ label }}</span>
</template>

<style scoped>
.state-pill {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-pill);
  font-size: var(--text-small);
  font-weight: var(--weight-semibold);
  line-height: var(--leading-body);
  white-space: nowrap;
}

.state-pill--neutral {
  color: var(--color-superseded-text);
  background-color: var(--color-superseded-bg);
}

.state-pill--ok {
  color: var(--color-approved-text);
  background-color: var(--color-approved-bg);
}

.state-pill--new {
  color: var(--color-primary);
  background-color: var(--color-surface-muted);
}

.state-pill--pending {
  color: var(--color-pending-text);
  background-color: var(--color-pending-bg);
}

.state-pill--error {
  color: var(--color-rejected-text);
  background-color: var(--color-rejected-bg);
}
</style>

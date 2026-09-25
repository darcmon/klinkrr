<script setup lang="ts">
import StatePill from '../StatePill.vue';

defineProps<{
  id: string;
  title: string;
  pill: { label: string; tone: 'neutral' | 'ok' | 'new' | 'pending' | 'error' };
}>();
</script>

<template>
  <section class="submit-card" :aria-labelledby="`${id}-title`">
    <header class="submit-card-header">
      <h2 :id="`${id}-title`">{{ title }}</h2>
      <StatePill :label="pill.label" :tone="pill.tone" />
    </header>

    <slot />
  </section>
</template>

<style scoped>
.submit-card {
  display: grid;
  align-content: start;
  gap: var(--space-4);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.submit-card-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.submit-card-header h2 {
  margin: 0;
}

@media (min-width: 768px) {
  .submit-card {
    padding: var(--space-6);
  }
}
</style>

<script setup lang="ts">
defineProps<{
  id: string;
  title: string;
  description?: string;
}>();
</script>

<template>
  <section class="settings-section" :aria-labelledby="`${id}-title`">
    <header>
      <h2 :id="`${id}-title`">{{ title }}</h2>
      <p v-if="description" class="text-muted">{{ description }}</p>
    </header>

    <slot />
  </section>
</template>

<style scoped>
.settings-section {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.settings-section header > * {
  margin-bottom: var(--space-1);
}

.settings-section header > :last-child {
  margin-bottom: 0;
}

@media (min-width: 768px) {
  .settings-section {
    padding: var(--space-6);
  }
}
</style>

<script setup lang="ts">
import BrandMark from './BrandMark.vue';

defineProps<{
  labelledBy: string;
}>();
</script>

<template>
  <main class="auth-page">
    <section class="auth-card" :aria-labelledby="labelledBy">
      <div class="auth-brand">
        <BrandMark />
        <span>klinkrr</span>
      </div>

      <slot />
    </section>
  </main>
</template>

<style scoped>
.auth-page {
  width: 100%;
  padding: var(--space-8) var(--space-4);
}

.auth-card {
  display: grid;
  gap: var(--space-6);
  width: 100%;
  max-width: 440px;
  margin-inline: auto;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
  overflow-wrap: anywhere;
}

.auth-brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-page);
  font-weight: var(--weight-bold);
}
</style>

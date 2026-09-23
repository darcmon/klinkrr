<script setup lang="ts">
import { useRoute } from 'vue-router';
import AppHeader from './components/AppHeader.vue';
import AppLayout from './components/AppLayout.vue';
import ThemeSelector from './components/ThemeSelector.vue';

const route = useRoute();
</script>

<template>
  <AppLayout v-if="!route.meta.public">
    <template #header>
      <AppHeader />
    </template>
    <router-view />
  </AppLayout>

  <template v-else>
    <header class="public-header">
      <ThemeSelector />
    </header>
    <router-view />
  </template>
</template>

<style scoped>
.public-header {
  display: flex;
  justify-content: flex-end;
  width: 100%;
  max-width: 1200px;
  margin-inline: auto;
  padding: var(--space-4);
}

@media (min-width: 768px) {
  .public-header {
    padding-inline: var(--space-8);
  }
}
</style>

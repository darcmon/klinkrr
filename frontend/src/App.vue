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
  </AppLayout>

  <template v-else>
    <ThemeSelector />
    <router-view />
  </template>
</template>

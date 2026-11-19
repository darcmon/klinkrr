<script setup lang="ts">
import { useRoute } from 'vue-router';
import { useAuth } from './composables/useAuth';
import { useCurrentUser } from './composables/useCurrentUser';
import AppHeader from './components/AppHeader.vue';
import AppLayout from './components/AppLayout.vue';
import StateMessage from './components/StateMessage.vue';
import ThemeSelector from './components/ThemeSelector.vue';

const route = useRoute();
const { selectedOrganizationId, organizationAccessLost } = useAuth();
const { organizationPrompt } = useCurrentUser();
</script>

<template>
  <AppLayout
    v-if="!route.meta.public"
    :key="`${selectedOrganizationId ?? 'unselected'}:${organizationAccessLost}`"
  >
    <template #header>
      <AppHeader />
    </template>
    <StateMessage
      v-if="organizationAccessLost"
      class="context-notice"
      tone="error"
      message="You no longer have access to that organization."
    />
    <!-- Settings stays reachable: it works without an organization. -->
    <StateMessage
      v-if="organizationPrompt && route.name !== 'settings'"
      :message="organizationPrompt"
    />
    <router-view v-else />
  </AppLayout>

  <template v-else>
    <header class="public-header">
      <ThemeSelector />
    </header>
    <router-view />
  </template>
</template>

<style scoped>
.context-notice {
  margin-bottom: var(--space-4);
}

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

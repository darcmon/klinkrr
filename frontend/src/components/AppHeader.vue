<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useAuth } from '../composables/useAuth';
import ThemeSelector from './ThemeSelector.vue';

const router = useRouter();
const { logout } = useAuth();

function handleLogout() {
  logout();
  router.replace('/login');
}
</script>

<template>
  <div class="header-content">
    <router-link class="brand" to="/dashboard"> klinkrr </router-link>

    <nav class="header-nav" aria-label="Main navigation">
      <router-link to="/dashboard">Dashboard</router-link>
      <router-link to="/locations">Locations</router-link>
      <router-link to="/upload">Upload</router-link>
    </nav>

    <div class="header-actions">
      <ThemeSelector />
      <button type="button" @click="handleLogout">Log out</button>
    </div>
  </div>
</template>

<style scoped>
.header-content {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-4);
}

.brand {
  color: var(--color-text);
  font-size: var(--text-page);
  font-weight: var(--weight-bold);
  text-decoration: none;
}

.header-nav,
.header-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.header-actions {
  margin-inline-start: auto;
}

.header-nav a,
button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-small);
  font-weight: var(--weight-medium);
}

.header-nav a {
  color: var(--color-muted);
  text-decoration: none;
}

.header-nav a:hover,
.header-nav a.router-link-active {
  color: var(--color-text);
  background-color: var(--color-surface-muted);
}

button {
  border: 1px solid var(--color-border);
  color: var(--color-text);
  background-color: var(--color-surface);
  cursor: pointer;
}

button:hover {
  background-color: var(--color-surface-muted);
}
</style>

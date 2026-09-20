<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router';
import { useAuth } from '../composables/useAuth';
import BrandMark from './BrandMark.vue';
import ThemeSelector from './ThemeSelector.vue';

const route = useRoute();
const router = useRouter();
const { logout } = useAuth();

function handleLogout() {
  logout();
  router.replace('/login');
}
</script>

<template>
  <div class="header-content">
    <router-link class="brand" to="/dashboard">
      <BrandMark />
      <span>klinkrr</span>
    </router-link>

    <nav class="header-nav" aria-label="Main navigation">
      <router-link to="/dashboard">Dashboard</router-link>
      <router-link
        to="/locations"
        :class="{ 'section-active': route.name === 'archive' }"
        :aria-current="
          route.name === 'archive'
            ? 'location'
            : route.name === 'locations'
              ? 'page'
              : undefined
        "
      >
        Locations
      </router-link>
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
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
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
.header-nav a.router-link-active,
.header-nav a.section-active {
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

@media (max-width: 767px) {
  .header-actions {
    width: 100%;
    justify-content: space-between;
    margin-inline-start: 0;
  }

  .header-nav {
    position: fixed;
    inset-inline: 0;
    bottom: 0;
    z-index: 10;

    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-1);

    height: calc(var(--mobile-nav-height) + env(safe-area-inset-bottom, 0px));
    padding: var(--space-2);
    padding-bottom: calc(var(--space-2) + env(safe-area-inset-bottom, 0px));

    background-color: var(--color-surface);
    border-top: 1px solid var(--color-border);
  }

  .header-nav a {
    min-width: 0;
    padding-inline: var(--space-1);
    font-size: var(--text-small);
    text-align: center;
    overflow-wrap: anywhere;
  }
}
</style>

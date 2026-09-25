<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useCurrentUser } from '../composables/useCurrentUser';
import { useAuth } from '../composables/useAuth';
import BrandMark from './BrandMark.vue';
import ThemeSelector from './ThemeSelector.vue';

const route = useRoute();
const router = useRouter();
const { logout } = useAuth();
const { user, load } = useCurrentUser();
const pictureFailed = ref(false);
watch(() => user.value?.avatar_url, () => { pictureFailed.value = false; });
onMounted(() => { load().catch(() => { /* Keep the fallback if the profile is unavailable. */ }); });

function handleLogout() {
  logout();
  router.replace('/login');
}
</script>

<template>
  <div class="header-content">
    <router-link class="brand" to="/upload">
      <BrandMark />
      <span>klinkrr</span>
    </router-link>

    <nav class="header-nav" aria-label="Main navigation">
      <router-link to="/upload">Upload</router-link>
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
    </nav>

    <div class="header-actions">
      <ThemeSelector />
      <button class="logout-button" type="button" aria-label="Log out" title="Log out" @click="handleLogout">
        <span>Log out</span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
          <path d="M9 4H4v16h5M9 12h12m-5-5 5 5-5 5" />
        </svg>
      </button>
      <router-link class="profile-link" to="/settings" aria-label="Profile and settings" title="Profile and settings">
        <img v-if="user?.avatar_url && !pictureFailed" :src="user.avatar_url" alt="" referrerpolicy="no-referrer" @error="pictureFailed = true" />
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21v-2a8 8 0 0 1 16 0v2" />
        </svg>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.header-content {
  display: flex;
  flex-wrap: nowrap;
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
  flex-wrap: nowrap;
  align-items: center;
  gap: var(--space-2);
}

.header-actions {
  flex-shrink: 0;
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

.profile-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  overflow: hidden;
  color: var(--color-muted);
  background: var(--color-surface-muted);
}
.profile-link:hover,
.profile-link.router-link-active {
  color: var(--color-text);
  border-color: currentColor;
}
.profile-link img { width: 100%; height: 100%; object-fit: cover; }
.profile-link svg { width: 28px; height: 28px; }

.logout-button svg { display: none; width: 22px; height: 22px; }

@media (max-width: 767px) {
  .header-content { gap: var(--space-2); }
  .header-actions { gap: var(--space-1); }
  .logout-button { width: 44px; padding: 0; border-color: transparent; border-radius: 50%; }
  .logout-button span { display: none; }
  .logout-button svg { display: block; }

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

<script setup lang="ts">
import { computed } from 'vue';
import { useTheme, type ThemePreference } from '../composables/useTheme';

const { preference, setTheme } = useTheme();
const nextMode: Record<ThemePreference, ThemePreference> = {
  light: 'dark', dark: 'system', system: 'light',
};
const labels = { light: 'Light', dark: 'Dark', system: 'Auto' };
const label = computed(() =>
  `Theme: ${labels[preference.value]}. Switch to ${labels[nextMode[preference.value]]}.`,
);
</script>

<template>
  <button class="theme-toggle" type="button" :aria-label="label" :title="label"
    @click="setTheme(nextMode[preference])">
    <svg viewBox="0 0 32 32" aria-hidden="true" fill="currentColor">
      <!-- Courage: a ringed sun with eight pointed rays. -->
      <g v-if="preference === 'light'">
        <path fill-rule="evenodd" d="M16 9a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm0 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z" />
        <path d="m16 0 2.5 7h-5ZM32 16l-7 2.5v-5ZM16 32l-2.5-7h5ZM0 16l7-2.5v5ZM5 5l6 2-4 4ZM27 5l-2 6-4-4ZM27 27l-6-2 4-4ZM5 27l2-6 4 4Z" />
      </g>
      <!-- An upward-facing crescent, inspired by Lunamon's forehead mark. -->
      <path v-else-if="preference === 'dark'"
        d="M4 5a13 13 0 1 0 24 0c0 8-5 12-12 12S4 13 4 5Z" />
      <!-- Kindness: a round center embraced by two sweeping curves. -->
      <g v-else>
        <circle cx="16" cy="11" r="8" />
        <path d="M6 5C-1 16 4 25 17 21 8 21 3 16 6 5ZM25 5c10 10 5 18-5 21-5 2-9 3-10 6-3-7 4-11 10-14 5-3 7-7 5-13Z" />
      </g>
    </svg>
  </button>
</template>

<style scoped>
.theme-toggle {
  display: inline-flex;
  flex: 0 0 44px;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  padding: 9px;
  border: 1px solid transparent;
  border-radius: 50%;
  color: var(--color-text);
  background: transparent;
  cursor: pointer;
}
.theme-toggle:hover {
  background: var(--color-surface-muted);
  border-color: var(--color-border);
}
.theme-toggle svg { width: 26px; height: 26px; }
</style>

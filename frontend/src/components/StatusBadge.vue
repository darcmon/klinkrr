<script setup lang="ts">
import type { ArchivedVersion } from '../types/version';

defineProps<{
  status: ArchivedVersion['status'];
}>();

const labels = {
  pending: 'Pending',
  approved: 'Approved',
  rejected: 'Rejected',
  superseded: 'Superseded',
};
</script>

<template>
  <span class="status-badge" :class="`status-badge--${status}`">
    {{ labels[status] }}
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-pill);
  font-size: var(--text-small);
  font-weight: var(--weight-semibold);
  line-height: var(--leading-body);
}

.status-badge--approved {
  color: var(--color-approved-text);
  background-color: var(--color-approved-bg);
}

.status-badge--pending {
  color: var(--color-pending-text);
  background-color: var(--color-pending-bg);
}

.status-badge--rejected {
  color: var(--color-rejected-text);
  background-color: var(--color-rejected-bg);
}

.status-badge--superseded {
  color: var(--color-superseded-text);
  background-color: var(--color-superseded-bg);
}
</style>

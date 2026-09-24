<script setup lang="ts">
import { computed } from 'vue';
import type { PendingVersion } from '../types/version';

import BaseButton from './BaseButton.vue';

const props = withDefaults(
  defineProps<{
    version: PendingVersion;
    // Distinguishes the list and table copies, which are both in the DOM.
    idPrefix: string;
    busy?: boolean;
    approving?: boolean;
    rejecting?: boolean;
    layout?: 'fill' | 'inline';
  }>(),
  {
    busy: false,
    approving: false,
    rejecting: false,
    layout: 'fill',
  },
);

const emit = defineEmits<{
  approve: [];
  reject: [];
}>();

const noteId = computed(() => `${props.idPrefix}-note-${props.version.id}`);

// Rejecting your own version withdraws it.
const rejectLabel = computed(() => {
  if (props.rejecting) {
    return props.version.is_own ? 'Withdrawing…' : 'Rejecting…';
  }
  return props.version.is_own ? 'Withdraw…' : 'Reject…';
});

const note = computed(() => {
  const { is_own, can_approve } = props.version;
  if (is_own && can_approve) {
    return 'Your submission. Approving it yourself is recorded in the audit log.';
  }
  if (is_own) return 'Your submission. Someone else needs to approve it.';
  if (!can_approve) return 'Waiting for an approver.';
  return '';
});
</script>

<template>
  <div class="pending-actions">
    <div
      v-if="version.can_approve || version.can_reject"
      class="buttons"
      :class="`buttons--${layout}`"
    >
      <BaseButton
        v-if="version.can_approve"
        :disabled="busy"
        :aria-describedby="note ? noteId : undefined"
        @click="emit('approve')"
      >
        {{ approving ? 'Approving…' : 'Approve' }}
      </BaseButton>

      <BaseButton
        v-if="version.can_reject"
        variant="secondary"
        :disabled="busy"
        @click="emit('reject')"
      >
        {{ rejectLabel }}
      </BaseButton>
    </div>

    <p v-if="note" :id="noteId" class="note">{{ note }}</p>
  </div>
</template>

<style scoped>
.pending-actions {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.buttons--fill {
  display: grid;
  grid-auto-columns: minmax(0, 1fr);
  grid-auto-flow: column;
  gap: var(--space-2);
}

.buttons--inline {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--space-2);
}

.note {
  margin: 0;
  color: var(--color-muted);
  font-size: var(--text-small);
  overflow-wrap: anywhere;
}
</style>

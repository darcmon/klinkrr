<script setup lang="ts">
import { computed, ref } from 'vue';
import api, { ApiError } from '../../api/client';
import { useCurrentUser } from '../../composables/useCurrentUser';
import { publicUrlLabel } from '../../utils/location';
import type { LocationSummary } from '../../types/location';
import type { SubmitResult } from '../../types/submit';

import BaseButton from '../BaseButton.vue';
import StatePill from '../StatePill.vue';
import StateMessage from '../StateMessage.vue';

const result = defineModel<SubmitResult>({ required: true });

const emit = defineEmits<{ submitAnother: [] }>();

const { user, can } = useCurrentUser();

const approving = ref(false);
const approveError = ref('');
const approveBlocked = ref(false);

const url = computed(() => publicUrlLabel(result.value.location.slug));
const live = computed(() => result.value.location.published_version);
const policyChanged = computed(
  () => result.value.status !== result.value.expectedStatus,
);

// Both the role and the organization's setting must allow it; the server
// checks again when the button is used.
const canApproveNow = computed(
  () =>
    result.value.status === 'pending' &&
    !approveBlocked.value &&
    can('approve_own') &&
    Boolean(user.value?.organization?.allow_self_approval),
);

async function approveNow() {
  if (approving.value) return;
  approving.value = true;
  approveError.value = '';

  try {
    const approved = await api.post(`/admin/versions/${result.value.id}/approve`);
    if (approved === undefined) return;

    let location = result.value.location;
    try {
      const fresh: LocationSummary | undefined = await api.get(
        `/admin/locations/${encodeURIComponent(location.slug)}`,
      );
      if (fresh) location = fresh;
    } catch {
      // The approval worked; only the live-version details are stale.
    }
    result.value = { ...result.value, status: 'approved', location };
  } catch (e) {
    // Most likely self-approval was turned off since the page loaded.
    if (e instanceof ApiError && e.status === 403) approveBlocked.value = true;
    approveError.value = e instanceof Error ? e.message : 'Approval failed';
  } finally {
    approving.value = false;
  }
}
</script>

<template>
  <section class="outcome" aria-labelledby="outcome-title">
    <header class="outcome-header">
      <h2 id="outcome-title" tabindex="-1">
        {{
          result.status === 'approved'
            ? `Published as v${result.versionNumber}`
            : `Submitted as v${result.versionNumber}`
        }}
      </h2>
      <StatePill
        :label="result.status === 'approved' ? 'Live' : 'Pending approval'"
        :tone="result.status === 'approved' ? 'ok' : 'pending'"
      />
    </header>

    <template v-if="result.status === 'approved'">
      <p>
        <span class="text-mono url">{{ url }}</span> now serves this version.
      </p>
    </template>

    <template v-else>
      <p v-if="live">
        <span class="text-mono url">{{ url }}</span> still serves
        v{{ live.version_number }} · {{ live.label }}. Nothing public changes until
        v{{ result.versionNumber }} is approved.
      </p>
      <p v-else>
        Nothing is published at <span class="text-mono url">{{ url }}</span> yet.
        Nothing public changes until v{{ result.versionNumber }} is approved.
      </p>

      <table class="comparison">
        <caption class="visually-hidden">Live and pending versions</caption>
        <tbody>
          <tr>
            <th scope="row">Live</th>
            <td>
              <template v-if="live">v{{ live.version_number }} · {{ live.label }}</template>
              <span v-else class="text-muted">Nothing published</span>
            </td>
          </tr>
          <tr>
            <th scope="row">Pending</th>
            <td>v{{ result.versionNumber }} · {{ result.label }}</td>
          </tr>
        </tbody>
      </table>
    </template>

    <StateMessage
      v-if="policyChanged"
      message="This location’s approval setting changed while you were submitting."
    />

    <div v-if="canApproveNow" class="approve-now">
      <BaseButton
        variant="secondary"
        :disabled="approving"
        aria-describedby="approve-now-note"
        @click="approveNow"
      >
        {{ approving ? 'Approving…' : 'Approve now' }}
      </BaseButton>
      <p id="approve-now-note" class="text-muted text-small">
        You’re approving your own submission. This is recorded in the audit log.
      </p>
    </div>
    <StateMessage v-if="approveError" tone="error" :message="approveError" />

    <div class="outcome-actions">
      <router-link
        class="view-link"
        :to="{ name: 'archive', params: { slug: result.location.slug } }"
      >
        View {{ result.location.display_name }}
      </router-link>
      <BaseButton @click="emit('submitAnother')">Submit another version</BaseButton>
    </div>
  </section>
</template>

<style scoped>
.outcome {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.outcome-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.outcome-header h2,
.outcome p {
  margin: 0;
}

.url {
  overflow-wrap: anywhere;
}

.comparison {
  width: 100%;
  border-collapse: collapse;
}

.comparison th,
.comparison td {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-border);
  text-align: start;
  overflow-wrap: anywhere;
}

.comparison th {
  width: 6rem;
  color: var(--color-muted);
  font-weight: var(--weight-semibold);
}

.approve-now {
  display: grid;
  justify-items: start;
  gap: var(--space-2);
}

.outcome-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3) var(--space-4);
}

.view-link {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
}

@media (min-width: 768px) {
  .outcome {
    padding: var(--space-6);
  }
}
</style>

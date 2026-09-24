<script setup lang="ts">
import api from '../api/client';
import { computed, nextTick, ref, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { formatDate } from '../utils/format';
import { useCurrentUser } from '../composables/useCurrentUser';
import type { PendingFilter, PendingVersion } from '../types/version';

import BaseField from '../components/BaseField.vue';
import BaseModal from '../components/BaseModal.vue';
import BaseButton from '../components/BaseButton.vue';
import StatusBadge from '../components/StatusBadge.vue';
import StateMessage from '../components/StateMessage.vue';
import VersionSummary from '../components/VersionSummary.vue';
import PendingVersionActions from '../components/PendingVersionActions.vue';

const route = useRoute();
const router = useRouter();
const { load: loadCurrentUser, can } = useCurrentUser();

const pending = ref<PendingVersion[]>([]);
const loading = ref(true);
const loadError = ref('');
const actionError = ref('');
const actioningId = ref<string | null>(null);
const actionKind = ref<'approve' | 'reject' | null>(null);
const successMessage = ref('');
const rejectionTarget = ref<PendingVersion | null>(null);
const rejectionNotes = ref('');
const rejectionError = ref('');
const dashboardHeading = ref<HTMLHeadingElement | null>(null);
const userReady = ref(false);
let latestRequest = 0;

const filterOptions = computed(() => {
  const options: { value: PendingFilter; label: string }[] = [];
  if (can('review_any')) {
    options.push({ value: 'waiting_on_me', label: 'Waiting on me' });
  }
  options.push(
    { value: 'mine', label: 'My submissions' },
    { value: 'all', label: 'All pending' },
  );
  return options;
});

// Kept in the URL so it survives reloads and back/forward.
const filter = computed<PendingFilter>(() => {
  const match = filterOptions.value.find(
    (option) => option.value === route.query.filter,
  );
  if (match) return match.value;
  return can('review_any') ? 'waiting_on_me' : 'mine';
});

const emptyMessage = computed(
  () =>
    ({
      waiting_on_me: 'Nothing is waiting on you.',
      mine: 'You have no pending submissions.',
      all: 'No pending versions.',
    })[filter.value],
);

function setFilter(value: PendingFilter) {
  if (value === filter.value) return;

  successMessage.value = '';
  actionError.value = '';
  router.replace({ query: { ...route.query, filter: value } });
}

// A quiet load refreshes the list without replacing it with a loading state.
async function loadPending({ quiet = false } = {}) {
  const request = ++latestRequest;

  if (!quiet) {
    loading.value = true;
    loadError.value = '';
  }

  try {
    const data = await api.get(
      `/admin/versions/pending?filter=${filter.value}`,
    );

    // Ignore responses for a filter the user has already moved away from.
    if (data === undefined || request !== latestRequest) return;

    pending.value = data;
  } catch (e) {
    if (request !== latestRequest || quiet) return;

    loadError.value =
      e instanceof Error ? e.message : 'Failed to load pending versions';
  } finally {
    if (request === latestRequest) loading.value = false;
  }
}

async function approve(version: PendingVersion) {
  if (actioningId.value !== null) return;

  actionError.value = '';
  successMessage.value = '';
  actioningId.value = version.id;
  actionKind.value = 'approve';

  try {
    const result = await api.post(`/admin/versions/${version.id}/approve`);

    if (result === undefined) return;

    successMessage.value = version.is_own
      ? `Version ${version.version_number} approved and published. Approving your own submission is recorded in the audit log.`
      : `Version ${version.version_number} approved and published.`;
    await loadPending();

    await nextTick();
    dashboardHeading.value?.focus();
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : 'Approve failed';
    // What this user may do can change, e.g. self-approval being turned off.
    await loadPending({ quiet: true });
  } finally {
    actioningId.value = null;
    actionKind.value = null;
  }
}

function openReject(version: PendingVersion) {
  if (actioningId.value !== null) return;

  rejectionNotes.value = '';
  rejectionError.value = '';
  actionError.value = '';
  successMessage.value = '';
  rejectionTarget.value = version;
}

function closeReject() {
  if (actioningId.value !== null) return;
  rejectionTarget.value = null;
}

async function submitRejection() {
  const version = rejectionTarget.value;
  if (!version || actioningId.value !== null) return;

  rejectionError.value = '';
  actioningId.value = version.id;
  actionKind.value = 'reject';

  try {
    const result = await api.post(`/admin/versions/${version.id}/reject`, {
      notes: rejectionNotes.value.trim() || null,
    });

    if (result === undefined) return;

    successMessage.value = version.is_own
      ? `Version ${version.version_number} withdrawn. Published content is unchanged.`
      : `Version ${version.version_number} rejected. Published content is unchanged.`;

    await loadPending();
    rejectionTarget.value = null;

    await nextTick();
    dashboardHeading.value?.focus();
  } catch (e) {
    rejectionError.value = e instanceof Error ? e.message : 'Reject failed';
    await loadPending({ quiet: true });
  } finally {
    actioningId.value = null;
    actionKind.value = null;
  }
}

onMounted(async () => {
  try {
    await loadCurrentUser();
  } catch {
    // Fall back to "My submissions". Each item's actions still come from the
    // server, so nothing is offered that the user can't do.
  }
  userReady.value = true;
});

watch([userReady, filter], ([ready]) => {
  if (ready) loadPending();
});
</script>

<template>
  <div class="dashboard">
    <header>
      <h1 ref="dashboardHeading" tabindex="-1">Dashboard</h1>
      <p class="text-muted">
        Review pending files and links before they go live.
      </p>
    </header>

    <fieldset v-if="userReady" class="pending-filter">
      <legend class="visually-hidden">Show pending versions</legend>

      <label
        v-for="option in filterOptions"
        :key="option.value"
        class="filter-option"
      >
        <input
          type="radio"
          name="pending-filter"
          class="filter-input"
          :value="option.value"
          :checked="filter === option.value"
          @change="setFilter(option.value)"
        />
        <span>{{ option.label }}</span>
      </label>
    </fieldset>

    <StateMessage
      v-if="successMessage"
      tone="success"
      :message="successMessage"
    />

    <StateMessage v-if="actionError" tone="error" :message="actionError" />

    <StateMessage v-if="loading" message="Loading pending versions…" />

    <StateMessage v-else-if="loadError" tone="error" :message="loadError">
      <template #actions>
        <BaseButton variant="secondary" @click="loadPending">
          Try again
        </BaseButton>
      </template>
    </StateMessage>

    <StateMessage v-else-if="pending.length === 0" :message="emptyMessage" />

    <template v-else>
      <ul class="pending-list" role="list">
        <li v-for="v in pending" :key="v.id" class="pending-item">
          <div class="info">
            <StatusBadge status="pending" />
            <VersionSummary :version="v" />

            <div class="meta">
              <span
                >v{{ v.version_number }} · {{ v.location_display_name }}</span
              >

              <router-link
                :to="{ name: 'archive', params: { slug: v.location_slug } }"
                class="archive-link text-mono"
              >
                /{{ v.location_slug }} — View history →
              </router-link>
            </div>

            <span class="meta"> Submitted by {{ v.uploaded_by }} </span>
            <time class="meta" :datetime="v.uploaded_at">
              {{ formatDate(v.uploaded_at) }}
            </time>
          </div>
          <PendingVersionActions
            :version="v"
            id-prefix="list"
            :busy="actioningId !== null"
            :approving="actioningId === v.id && actionKind === 'approve'"
            :rejecting="actioningId === v.id && actionKind === 'reject'"
            @approve="approve(v)"
            @reject="openReject(v)"
          />
        </li>
      </ul>
      <div class="pending-table data-table-frame">
        <table class="data-table">
          <caption class="visually-hidden">
            Pending approvals
          </caption>

          <colgroup>
            <col style="width: 30%" />
            <col style="width: 20%" />
            <col style="width: 10%" />
            <col style="width: 22%" />
            <col style="width: 18%" />
          </colgroup>

          <thead>
            <tr>
              <th scope="col">Content</th>
              <th scope="col">Location</th>
              <th scope="col">Version</th>
              <th scope="col">Submitted</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="v in pending" :key="v.id">
              <td>
                <div class="info">
                  <StatusBadge status="pending" />
                  <VersionSummary :version="v" />
                </div>
              </td>

              <td>
                <div class="info">
                  <span>{{ v.location_display_name }}</span>
                  <router-link
                    :to="{ name: 'archive', params: { slug: v.location_slug } }"
                    class="text-mono"
                  >
                    /{{ v.location_slug }}
                  </router-link>
                </div>
              </td>

              <td class="text-mono">v{{ v.version_number }}</td>

              <td>
                <div class="info">
                  <span>{{ v.uploaded_by }}</span>

                  <time class="meta" :datetime="v.uploaded_at">
                    {{ formatDate(v.uploaded_at) }}
                  </time>
                </div>
              </td>

              <td>
                <PendingVersionActions
                  :version="v"
                  id-prefix="table"
                  layout="inline"
                  :busy="actioningId !== null"
                  :approving="actioningId === v.id && actionKind === 'approve'"
                  :rejecting="actioningId === v.id && actionKind === 'reject'"
                  @approve="approve(v)"
                  @reject="openReject(v)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <BaseModal
      v-if="rejectionTarget"
      id="reject-version"
      :title="
        rejectionTarget.is_own
          ? 'Withdraw this version?'
          : 'Reject this version?'
      "
      :busy="actioningId !== null"
      @close="closeReject"
    >
      <p class="text-muted">
        <template v-if="rejectionTarget.is_own">
          It won't be published.
        </template>
        The public link keeps serving its currently published content.
      </p>

      <VersionSummary :version="rejectionTarget" />

      <p class="meta">
        v{{ rejectionTarget.version_number }} · /{{
          rejectionTarget.location_slug
        }}
      </p>

      <BaseField
        id="rejection-notes"
        label="Reason (optional)"
        hint="Saved with this version’s review."
        v-slot="{ id, describedBy, invalid }"
      >
        <textarea
          :id="id"
          v-model="rejectionNotes"
          :aria-describedby="describedBy"
          :aria-invalid="invalid"
          :disabled="actioningId !== null"
          class="notes-input"
          rows="4"
        />
      </BaseField>

      <StateMessage
        v-if="rejectionError"
        tone="error"
        :message="rejectionError"
      />

      <template #actions="{ requestClose }">
        <BaseButton
          variant="secondary"
          :disabled="actioningId !== null"
          @click="requestClose"
        >
          Cancel
        </BaseButton>

        <BaseButton
          variant="danger"
          :disabled="actioningId !== null"
          @click="submitRejection"
        >
          <template v-if="rejectionTarget.is_own">
            {{ actioningId !== null ? 'Withdrawing…' : 'Withdraw version' }}
          </template>
          <template v-else>
            {{ actioningId !== null ? 'Rejecting…' : 'Reject version' }}
          </template>
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.dashboard {
  display: grid;
  gap: var(--space-6);
}

.dashboard > header p {
  margin-bottom: 0;
}

.pending-list {
  display: grid;
  gap: var(--space-4);
  margin: 0;
  padding: 0;
  list-style: none;
}

.pending-item {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.info {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
  justify-items: start;
}

.archive-link {
  display: flex;
  align-items: center;
  min-height: 44px;
  width: fit-content;
  max-width: 100%;
  overflow-wrap: anywhere;
}

.meta {
  color: var(--color-muted);
  font-size: var(--text-small);
  overflow-wrap: anywhere;
}

.pending-filter {
  display: grid;
  grid-auto-columns: minmax(0, 1fr);
  grid-auto-flow: column;
  gap: var(--space-1);
  margin: 0;
  padding: var(--space-1);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface-muted);
}

.filter-option {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-small);
  color: var(--color-muted);
  font-weight: var(--weight-semibold);
  text-align: center;
  cursor: pointer;
}

.filter-option:has(.filter-input:checked) {
  color: var(--color-text);
  background-color: var(--color-surface);
  box-shadow: 0 0 0 1px var(--color-border);
}

/* The radio is invisible, so its focus ring is drawn on the label. */
.filter-option:has(.filter-input:focus-visible) {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}

.filter-input {
  position: absolute;
  inset: 0;
  margin: 0;
  opacity: 0;
  cursor: pointer;
}

.notes-input {
  width: 100%;
  min-height: 120px;
  padding: var(--space-3);
  resize: vertical;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  color: var(--color-text);
  background-color: var(--color-surface);
}

.pending-table {
  display: none;
}

@media (min-width: 768px) {
  .pending-filter {
    width: fit-content;
  }

  .pending-list {
    display: none;
  }

  .pending-table {
    display: block;
  }
}
</style>

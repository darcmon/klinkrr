<script setup lang="ts">
import api from '../api/client';
import { nextTick, ref, onMounted } from 'vue';
import { formatDate } from '../utils/format';
import type { PendingVersion } from '../types/version';

import BaseField from '../components/BaseField.vue';
import BaseModal from '../components/BaseModal.vue';
import BaseButton from '../components/BaseButton.vue';
import StatusBadge from '../components/StatusBadge.vue';
import StateMessage from '../components/StateMessage.vue';
import VersionSummary from '../components/VersionSummary.vue';

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

async function loadPending() {
  loading.value = true;
  loadError.value = '';

  try {
    const data = await api.get('/admin/versions/pending');

    if (data === undefined) return;

    pending.value = data;
  } catch (e) {
    loadError.value =
      e instanceof Error ? e.message : 'Failed to load pending versions';
  } finally {
    loading.value = false;
  }
}

async function approve(id: string) {
  if (actioningId.value !== null) return;

  actionError.value = '';
  successMessage.value = '';
  actioningId.value = id;
  actionKind.value = 'approve';

  try {
    const result = await api.post(`/admin/versions/${id}/approve`);

    if (result === undefined) return;

    successMessage.value = 'Version approved.';
    await loadPending();

    await nextTick();
    dashboardHeading.value?.focus();
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : 'Approve failed';
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

    successMessage.value = `Version ${version.version_number} rejected. Published content is unchanged.`;

    await loadPending();
    rejectionTarget.value = null;

    await nextTick();
    dashboardHeading.value?.focus();
  } catch (e) {
    rejectionError.value = e instanceof Error ? e.message : 'Reject failed';
  } finally {
    actioningId.value = null;
    actionKind.value = null;
  }
}

onMounted(loadPending);
</script>

<template>
  <div class="dashboard">
    <header>
      <h1 ref="dashboardHeading" tabindex="-1">Dashboard</h1>
      <p class="text-muted">
        Review pending files and links before they go live.
      </p>
    </header>

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

    <StateMessage
      v-else-if="pending.length === 0"
      message="No pending versions to review."
    />

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
          <div class="actions">
            <BaseButton :disabled="actioningId !== null" @click="approve(v.id)">
              {{
                actioningId === v.id && actionKind === 'approve'
                  ? 'Approving…'
                  : 'Approve'
              }}
            </BaseButton>

            <BaseButton
              variant="secondary"
              :disabled="actioningId !== null"
              @click="openReject(v)"
            >
              {{
                actioningId === v.id && actionKind === 'reject'
                  ? 'Rejecting…'
                  : 'Reject…'
              }}
            </BaseButton>
          </div>
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
                <div class="data-table-actions">
                  <BaseButton
                    :disabled="actioningId !== null"
                    @click="approve(v.id)"
                  >
                    {{
                      actioningId === v.id && actionKind === 'approve'
                        ? 'Approving…'
                        : 'Approve'
                    }}
                  </BaseButton>

                  <BaseButton
                    variant="secondary"
                    :disabled="actioningId !== null"
                    @click="openReject(v)"
                  >
                    {{
                      actioningId === v.id && actionKind === 'reject'
                        ? 'Rejecting…'
                        : 'Reject…'
                    }}
                  </BaseButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <BaseModal
      v-if="rejectionTarget"
      id="reject-version"
      title="Reject this version?"
      :busy="actioningId !== null"
      @close="closeReject"
    >
      <p class="text-muted">
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
          {{ actioningId !== null ? 'Rejecting…' : 'Reject version' }}
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

.actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
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
  .pending-list {
    display: none;
  }

  .pending-table {
    display: block;
  }
}
</style>

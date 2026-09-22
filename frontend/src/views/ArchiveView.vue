<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { formatDate } from '../utils/format';
import type { ArchivedVersion, ArchiveResponse } from '../types/version';
import api, { API_URL } from '../api/client';

import BaseField from '../components/BaseField.vue';
import BaseButton from '../components/BaseButton.vue';
import StatusBadge from '../components/StatusBadge.vue';
import StateMessage from '../components/StateMessage.vue';
import VersionSummary from '../components/VersionSummary.vue';

const props = defineProps<{
  slug: string;
}>();

const publicLocationUrl = computed(() => {
  const base = API_URL.replace(/\/$/, '');
  return `${base}/${encodeURIComponent(props.slug)}`;
});

const archive = ref<ArchiveResponse | null>(null);
const downloadingId = ref<string | null>(null);
const downloadError = ref('');
const loading = ref(false);
const error = ref('');
const statusFilter = ref('');
const page = ref(1);
const perPage = 20;
const retryCount = ref(0);

let archiveContext = 0;

watch(
  [() => props.slug, page, statusFilter, retryCount],
  () => {
    archiveContext++;
    downloadError.value = '';
  },
  { flush: 'sync' },
);

async function downloadVersion(version: ArchivedVersion) {
  if (version.kind !== 'file' || downloadingId.value !== null) return;

  const startedInContext = archiveContext;

  downloadingId.value = version.id;
  downloadError.value = '';

  try {
    const blob = await api.download(
      `/admin/versions/${encodeURIComponent(version.id)}/download`,
    );
    if (!blob) return;

    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');

    try {
      anchor.href = objectUrl;
      anchor.download = version.original_filename || 'download';
      document.body.appendChild(anchor);
      anchor.click();
    } finally {
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    }
  } catch (e) {
    if (startedInContext === archiveContext) {
      downloadError.value = e instanceof Error ? e.message : 'Download failed';
    }
  } finally {
    downloadingId.value = null;
  }
}

watch([() => props.slug, statusFilter], () => {
  page.value = 1;
});

watch(
  [() => props.slug, page, statusFilter, retryCount],
  async ([slug, currentPage, status], _previousValues, onCleanup) => {
    let active = true;
    onCleanup(() => {
      active = false;
    });

    loading.value = true;
    error.value = '';
    archive.value = null;

    try {
      const statusQuery = status ? `&status=${encodeURIComponent(status)}` : '';

      const data = await api.get(
        `/admin/locations/${encodeURIComponent(slug)}/versions?page=${currentPage}&per_page=${perPage}${statusQuery}`,
      );
      if (active && data) {
        archive.value = data;
      }
    } catch (e) {
      if (active) {
        error.value = e instanceof Error ? e.message : 'Failed to load history';
      }
    } finally {
      if (active) {
        loading.value = false;
      }
    }
  },
  { immediate: true },
);
</script>

<template>
  <div class="archive">
    <router-link to="/locations">← Locations</router-link>
    <header class="archive-header">
      <h1>Version history</h1>
      <p class="text-muted">Location: /{{ slug }}</p>

      <a :href="publicLocationUrl" target="_blank" rel="noopener noreferrer">
        Open public location ↗
      </a>

      <p class="text-muted text-small">
        Opens the currently published content, if any.
      </p>
    </header>

    <BaseField
      id="status-filter"
      label="Status"
      class="status-filter"
      v-slot="{ id }"
    >
      <select :id="id" v-model="statusFilter" class="form-control">
        <option value="">All statuses</option>
        <option value="pending">Pending</option>
        <option value="approved">Approved</option>
        <option value="rejected">Rejected</option>
        <option value="superseded">Superseded</option>
      </select>
    </BaseField>

    <p v-if="downloadError" class="error" role="alert">
      {{ downloadError }}
    </p>

    <StateMessage v-if="loading" message="Loading history…" />

    <StateMessage v-else-if="error" tone="error" :message="error">
      <template #actions>
        <BaseButton variant="secondary" @click="retryCount++">
          Try again
        </BaseButton>
      </template>
    </StateMessage>

    <template v-else-if="archive">
      <h2>{{ archive.location_display_name }}</h2>
      <StateMessage
        v-if="archive.total === 0"
        :message="
          statusFilter ? 'No versions match this status.' : 'No versions yet.'
        "
      />

      <template v-else>
        <p>
          Page {{ page }} · {{ archive.total }}
          {{ statusFilter ? 'matching versions' : 'versions total' }}
        </p>

        <ul class="version-list" role="list">
          <li
            v-for="version in archive.versions"
            :key="version.id"
            class="version-card"
          >
            <div class="version-heading">
              <strong>Version {{ version.version_number }}</strong>
              <StatusBadge :status="version.status" />
            </div>

            <VersionSummary :version="version" />

            <div class="version-metadata">
              <p>Submitted by {{ version.uploaded_by }}</p>
              <p>
                Submitted on
                <time :datetime="version.uploaded_at">
                  {{ formatDate(version.uploaded_at) }}
                </time>
              </p>
              <p v-if="version.reviewed_by">
                Reviewed by {{ version.reviewed_by }}
              </p>

              <p v-if="version.reviewed_at">
                Reviewed on
                <time :datetime="version.reviewed_at">
                  {{ formatDate(version.reviewed_at) }}
                </time>
              </p>
            </div>

            <div v-if="version.review_notes" class="review-notes">
              <strong>Review notes</strong>
              <p>{{ version.review_notes }}</p>
            </div>

            <div v-if="version.kind === 'file'" class="version-actions">
              <BaseButton
                variant="secondary"
                :disabled="downloadingId !== null"
                @click="downloadVersion(version)"
              >
                {{
                  downloadingId === version.id
                    ? 'Downloading…'
                    : 'Download file'
                }}
              </BaseButton>
            </div>
          </li>
        </ul>
      </template>
    </template>

    <nav class="pagination" aria-label="Version history pages">
      <BaseButton
        variant="secondary"
        :disabled="loading || page === 1"
        @click="page--"
      >
        Previous
      </BaseButton>

      <BaseButton
        variant="secondary"
        :disabled="loading || !archive || page * perPage >= archive.total"
        @click="page++"
      >
        Next
      </BaseButton>
    </nav>
  </div>
</template>

<style scoped>
.archive {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
}

.archive-header {
  display: grid;
  justify-items: start;
  gap: var(--space-2);
  min-width: 0;
  overflow-wrap: anywhere;
}

.archive-header h1,
.archive-header p {
  margin: 0;
}

.version-list {
  display: grid;
  gap: var(--space-4);
  margin: 0;
  padding: 0;
  list-style: none;
}

.version-card {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.version-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.version-metadata {
  display: grid;
  gap: var(--space-1);
  color: var(--color-muted);
  font-size: var(--text-small);
  overflow-wrap: anywhere;
}

.version-metadata p {
  margin: 0;
}

.version-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.error {
  color: var(--color-rejected-text);
  overflow-wrap: anywhere;
}

.review-notes {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-3);
  border-inline-start: 3px solid var(--color-border);
  border-radius: var(--radius-small);
  background-color: var(--color-surface-muted);
  overflow-wrap: anywhere;
}

.review-notes strong {
  font-size: var(--text-small);
}

.review-notes p {
  margin: 0;
  white-space: pre-wrap;
}

.status-filter {
  width: 100%;
  max-width: 320px;
}

.form-control {
  width: 100%;
  min-width: 0;
  min-height: 44px;
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-small);
  background-color: var(--color-surface);
  color: var(--color-text);
}

.state-panel {
  display: grid;
  justify-items: start;
  gap: var(--space-3);
  margin: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.state-panel p {
  margin: 0;
}

.pagination {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--space-3);
}
</style>

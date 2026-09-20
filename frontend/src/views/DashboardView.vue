<script setup lang="ts">
import api from '../api/client';
import { ref, onMounted } from 'vue';
import type { PendingVersion } from '../types/version';

import BaseButton from '../components/BaseButton.vue';
import StatusBadge from '../components/StatusBadge.vue';
import VersionSummary from '../components/VersionSummary.vue';

const pending = ref<PendingVersion[]>([]);
const loading = ref(true);
const error = ref('');
const actioningId = ref<string | null>(null);

async function loadPending() {
  loading.value = true;
  error.value = '';
  try {
    pending.value = await api.get('/admin/versions/pending');
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load';
  } finally {
    loading.value = false;
  }
}

async function approve(id: string) {
  if (actioningId.value !== null) return;
  actioningId.value = id;
  try {
    await api.post(`/admin/versions/${id}/approve`);
    await loadPending();
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Approve failed';
  } finally {
    actioningId.value = null;
  }
}

async function reject(id: string) {
  if (actioningId.value !== null) return;

  if (!confirm('Reject this version?')) return;
  actioningId.value = id;
  try {
    await api.post(`/admin/versions/${id}/reject`);
    await loadPending();
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Reject failed';
  } finally {
    actioningId.value = null;
  }
}

onMounted(loadPending);
</script>

<template>
  <div class="dashboard">
    <header>
      <h1>Pending Approvals</h1>
    </header>

    <p v-if="loading">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <p v-else-if="pending.length === 0">
      No pending versions. Everything's up to date.
    </p>

    <ul v-else class="pending-list">
      <li v-for="v in pending" :key="v.id" class="pending-item">
        <div class="info">
          <StatusBadge status="pending" />
          <VersionSummary :version="v" />

          <span class="meta">
            v{{ v.version_number }} · {{ v.location_display_name }} (/{{
              v.location_slug
            }})
          </span>

          <span class="meta"> Submitted by {{ v.uploaded_by }} </span>
        </div>
        <div class="actions">
          <BaseButton :disabled="actioningId !== null" @click="approve(v.id)">
            Approve
          </BaseButton>

          <BaseButton
            variant="secondary"
            :disabled="actioningId !== null"
            @click="reject(v.id)"
          >
            Reject…
          </BaseButton>
        </div>
      </li>
    </ul>
  </div>
</template>

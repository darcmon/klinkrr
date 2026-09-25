<script setup lang="ts">
import { ref, onMounted } from 'vue';
import api, { API_URL } from '../api/client';

import BaseField from '../components/BaseField.vue';
import BaseButton from '../components/BaseButton.vue';
import StateMessage from '../components/StateMessage.vue';

interface Location {
  id: string;
  slug: string;
  display_name: string;
  description: string | null;
  reminder_email: string | null;
  current_approved_version_id: string | null;
}

const locations = ref<Location[]>([]);
const loading = ref(true);
const error = ref('');

const showForm = ref(false);
const form = ref({
  slug: '',
  display_name: '',
  description: '',
  reminder_email: '',
});
const formError = ref('');
const submitting = ref(false);

async function loadLocations() {
  loading.value = true;
  error.value = '';
  try {
    const data = await api.get('/admin/locations');
    if (data === undefined) return;

    locations.value = data.locations;
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load';
  } finally {
    loading.value = false;
  }
}

async function createLocation() {
  if (submitting.value) return;

  formError.value = '';
  submitting.value = true;

  try {
    const created = await api.post('/admin/locations', {
      slug: form.value.slug,
      display_name: form.value.display_name,
      description: form.value.description || null,
      reminder_email: form.value.reminder_email || null,
    });

    if (created === undefined) return;

    form.value = {
      slug: '',
      display_name: '',
      description: '',
      reminder_email: '',
    };
    showForm.value = false;
    await loadLocations();
  } catch (e) {
    formError.value = e instanceof Error ? e.message : 'Failed to create';
  } finally {
    submitting.value = false;
  }
}

function publishedUrl(slug: string): string {
  const base = API_URL.endsWith('/') ? API_URL.slice(0, -1) : API_URL;
  return `${base}/${encodeURIComponent(slug)}`;
}
onMounted(loadLocations);
</script>

<template>
  <div class="locations">
    <header class="page-header">
      <div>
        <h1>Locations</h1>
        <p class="text-muted">
          Permanent public URLs for your approved files and links.
        </p>
      </div>

      <BaseButton
        :variant="showForm ? 'secondary' : 'primary'"
        :disabled="submitting"
        :aria-expanded="showForm"
        @click="showForm = !showForm"
      >
        {{ showForm ? 'Cancel' : '+ New location' }}
      </BaseButton>
    </header>

    <!-- Create form -->
    <form
      v-if="showForm"
      class="create-form"
      :aria-busy="submitting"
      @submit.prevent="createLocation"
    >
      <h2>New location</h2>

      <BaseField
        id="location-slug"
        label="Slug (URL path)"
        hint="Use lowercase letters, numbers, and hyphens. For example: team-docs."
        v-slot="{ id, describedBy }"
      >
        <input
          :id="id"
          v-model="form.slug"
          :aria-describedby="describedBy"
          class="form-control"
          placeholder="documents"
          required
          maxlength="100"
          pattern="[a-z0-9\-]+"
          autocapitalize="none"
          :spellcheck="false"
          :disabled="submitting"
        />
      </BaseField>

      <BaseField id="location-name" label="Display name" v-slot="{ id }">
        <input
          :id="id"
          v-model="form.display_name"
          class="form-control"
          placeholder="Documents"
          required
          maxlength="255"
          :disabled="submitting"
        />
      </BaseField>

      <BaseField
        id="location-description"
        label="Description (optional)"
        v-slot="{ id }"
      >
        <textarea
          :id="id"
          v-model="form.description"
          class="form-control"
          rows="3"
          :disabled="submitting"
        />
      </BaseField>

      <p v-if="formError" class="form-error" role="alert">
        {{ formError }}
      </p>

      <div class="form-actions">
        <BaseButton type="submit" :disabled="submitting">
          {{ submitting ? 'Creating…' : 'Create location' }}
        </BaseButton>
      </div>
    </form>

    <!-- List -->
    <StateMessage v-if="loading" message="Loading locations…" />

    <StateMessage v-else-if="error" tone="error" :message="error">
      <template #actions>
        <BaseButton variant="secondary" @click="loadLocations">
          Try again
        </BaseButton>
      </template>
    </StateMessage>

    <StateMessage
      v-else-if="locations.length === 0"
      message="No locations yet. Create a location to give your files and links a permanent public URL."
    />
    <template v-else>
      <ul class="location-list" role="list">
        <li v-for="loc in locations" :key="loc.id" class="location-item">
          <div class="location-info">
            <strong>{{ loc.display_name }}</strong>
            <span class="slug">/{{ loc.slug }}</span>
            <p v-if="loc.description" class="desc">{{ loc.description }}</p>
          </div>
          <div class="status">
            <span
              :class="loc.current_approved_version_id ? 'serving' : 'empty'"
            >
              {{
                loc.current_approved_version_id
                  ? 'Published'
                  : 'No published version yet'
              }}
            </span>
            <a
              v-if="loc.current_approved_version_id"
              :href="publishedUrl(loc.slug)"
              target="_blank"
              rel="noopener noreferrer"
            >
              Open published version ↗
            </a>
            <router-link
              :to="{ name: 'upload', query: { location: loc.slug } }"
            >
              Submit a klink →
            </router-link>
            <router-link :to="{ name: 'archive', params: { slug: loc.slug } }">
              Archive →
            </router-link>
          </div>
        </li>
      </ul>
      <div class="location-table data-table-frame">
        <table class="data-table">
          <caption class="visually-hidden">
            Locations and publishing status
          </caption>

          <colgroup>
            <col style="width: 45%" />
            <col style="width: 25%" />
            <col style="width: 30%" />
          </colgroup>

          <thead>
            <tr>
              <th scope="col">Location</th>
              <th scope="col">Status</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="loc in locations" :key="loc.id">
              <th scope="row">
                <div class="location-info">
                  <strong>{{ loc.display_name }}</strong>
                  <span class="slug">/{{ loc.slug }}</span>
                  <p v-if="loc.description" class="desc">
                    {{ loc.description }}
                  </p>
                </div>
              </th>

              <td>
                <span
                  :class="loc.current_approved_version_id ? 'serving' : 'empty'"
                >
                  {{
                    loc.current_approved_version_id
                      ? 'Published'
                      : 'No published version yet'
                  }}
                </span>
              </td>

              <td>
                <div class="data-table-actions">
                  <a
                    v-if="loc.current_approved_version_id"
                    :href="publishedUrl(loc.slug)"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open published version ↗
                  </a>

                  <router-link
                    :to="{ name: 'upload', query: { location: loc.slug } }"
                  >
                    Submit a klink →
                  </router-link>

                  <router-link
                    :to="{ name: 'archive', params: { slug: loc.slug } }"
                  >
                    Archive →
                  </router-link>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.locations {
  display: grid;
  gap: var(--space-6);
}

.page-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.page-header p {
  margin-bottom: 0;
}

.location-list {
  display: grid;
  gap: var(--space-4);
  margin: 0;
  padding: 0;
  list-style: none;
}

.location-item {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.location-info,
.status {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
  justify-items: start;
}

.location-info,
.status {
  overflow-wrap: anywhere;
}

.location-table {
  display: none;
}

.location-table .serving,
.location-table .empty {
  display: inline-block;
}

@media (min-width: 768px) {
  .location-list {
    display: none;
  }

  .location-table {
    display: block;
  }
}

.slug {
  font-family: var(--font-mono);
  color: var(--color-muted);
  font-size: var(--text-small);
}

.desc {
  margin: 0;
  color: var(--color-muted);
}

.serving,
.empty {
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-pill);
  font-size: var(--text-small);
  font-weight: var(--weight-semibold);
}

.serving {
  color: var(--color-approved-text);
  background-color: var(--color-approved-bg);
}

.empty {
  color: var(--color-superseded-text);
  background-color: var(--color-superseded-bg);
}

.create-form {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.create-form h2 {
  margin: 0;
}

.form-error {
  margin: 0;
  color: var(--color-rejected-text);
  overflow-wrap: anywhere;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}
</style>

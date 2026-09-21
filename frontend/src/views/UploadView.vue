<script setup lang="ts">
import { formatSize } from '../utils/format';
import { ref, onMounted, watch } from 'vue';
import api from '../api/client';

import BaseField from '../components/BaseField.vue';
import BaseButton from '../components/BaseButton.vue';

interface Location {
  slug: string;
  display_name: string;
}

const ALLOWED = ['application/pdf', 'image/png', 'image/jpeg'];
const MAX_MB = 50;

const locations = ref<Location[]>([]);
const loadingLocations = ref(true);
const locationsError = ref('');
const selectedSlug = ref('');
const selectedFile = ref<File | null>(null);
const uploading = ref(false);
const submissionKind = ref<'file' | 'link'>('file');
const linkUrl = ref('');
const dragging = ref(false);
const error = ref('');
const result = ref<{
  label: string;
  version_number: number;
} | null>(null);

function clearFeedback() {
  error.value = '';
  result.value = null;
  dragging.value = false;
}

watch([selectedSlug, submissionKind], clearFeedback);

async function loadLocations() {
  loadingLocations.value = true;
  locationsError.value = '';

  try {
    const data = await api.get('/admin/locations');
    if (data === undefined) return;

    locations.value = data.locations;
  } catch (e) {
    locationsError.value =
      e instanceof Error ? e.message : 'Failed to load locations';
  } finally {
    loadingLocations.value = false;
  }
}

function validate(file: File): boolean {
  if (!ALLOWED.includes(file.type)) {
    error.value = 'File type not allowed. Use PDF, PNG, or JPEG.';
    return false;
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    error.value = `File too large. Max ${MAX_MB}MB.`;
    return false;
  }
  if (file.size === 0) {
    error.value = 'File is empty.';
    return false;
  }
  error.value = '';
  return true;
}

function chooseFile(file: File) {
  if (uploading.value) return;

  result.value = null;
  selectedFile.value = null;

  if (validate(file)) {
    selectedFile.value = file;
  }
}

function removeFile() {
  if (uploading.value) return;

  selectedFile.value = null;
  clearFeedback();
}

function onDrop(e: DragEvent) {
  dragging.value = false;
  if (uploading.value) return;

  const files = e.dataTransfer?.files;
  if (!files || files.length === 0) return;

  if (files.length > 1) {
    selectedFile.value = null;
    result.value = null;
    error.value = 'Choose one file at a time.';
    return;
  }

  const file = files[0];
  if (file) chooseFile(file);
}

function onFileInput(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];

  if (file) chooseFile(file);

  input.value = '';
}

async function upload() {
  if (!selectedFile.value || !selectedSlug.value || uploading.value) return;
  uploading.value = true;
  error.value = '';
  result.value = null;
  try {
    const formData = new FormData();
    formData.append('file', selectedFile.value);
    const created = await api.postForm(
      `/admin/locations/${selectedSlug.value}/upload`,
      formData,
    );
    if (!created) return;

    result.value = {
      label: created.original_filename,
      version_number: created.version_number,
    };
    selectedFile.value = null;
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Upload failed';
  } finally {
    uploading.value = false;
  }
}

async function submitLink() {
  const url = linkUrl.value.trim();
  if (!url || !selectedSlug.value || uploading.value) return;

  uploading.value = true;
  error.value = '';
  result.value = null;

  try {
    const created = await api.post(
      `/admin/locations/${selectedSlug.value}/link`,
      {
        link_url: url,
        link_mode: 'redirect',
      },
    );
    if (!created) return;

    result.value = {
      label: created.link_url,
      version_number: created.version_number,
    };
    linkUrl.value = '';
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Link submission failed';
  } finally {
    uploading.value = false;
  }
}

onMounted(loadLocations);
</script>

<template>
  <div class="upload">
    <header>
      <h1>Submit a version</h1>
      <p class="text-muted">
        Submit a file or redirect link for approval. Published content stays
        unchanged until approval.
      </p>
    </header>

    <p v-if="loadingLocations" role="status">Loading locations…</p>

    <div v-else-if="locationsError" class="state-panel">
      <p class="error" role="alert">{{ locationsError }}</p>
      <BaseButton variant="secondary" @click="loadLocations">
        Try again
      </BaseButton>
    </div>

    <div v-else-if="locations.length === 0" class="state-panel">
      <p>Create a location before submitting a version.</p>
      <router-link to="/locations">Go to Locations →</router-link>
    </div>

    <BaseField
      v-else
      id="upload-location"
      label="Location"
      hint="Choose the permanent public URL this version belongs to."
      v-slot="{ id, describedBy }"
    >
      <select
        :id="id"
        v-model="selectedSlug"
        :aria-describedby="describedBy"
        :disabled="uploading"
        class="form-control"
      >
        <option value="" disabled>Select a location…</option>
        <option v-for="loc in locations" :key="loc.slug" :value="loc.slug">
          {{ loc.display_name }} (/{{ loc.slug }})
        </option>
      </select>
    </BaseField>

    <fieldset v-if="selectedSlug" class="version-kind" :disabled="uploading">
      <legend>Version type</legend>

      <div class="kind-options">
        <label
          class="kind-option"
          :class="{ 'is-selected': submissionKind === 'file' }"
        >
          <input
            v-model="submissionKind"
            type="radio"
            name="submission-kind"
            value="file"
          />
          <span>
            <strong>File</strong>
            <small>PDF, PNG, or JPEG</small>
          </span>
        </label>

        <label
          class="kind-option"
          :class="{ 'is-selected': submissionKind === 'link' }"
        >
          <input
            v-model="submissionKind"
            type="radio"
            name="submission-kind"
            value="link"
          />
          <span>
            <strong>Redirect link</strong>
            <small>Send visitors to an HTTPS destination</small>
          </span>
        </label>
      </div>
    </fieldset>

    <form
      v-if="selectedSlug && submissionKind === 'link'"
      class="link-form"
      :aria-busy="uploading"
      @submit.prevent="submitLink"
    >
      <BaseField
        id="link-url"
        label="Destination URL"
        hint="Use an HTTPS URL. We check the destination before submitting it for approval."
        v-slot="{ id, describedBy }"
      >
        <input
          :id="id"
          v-model="linkUrl"
          :aria-describedby="describedBy"
          class="form-control"
          type="url"
          placeholder="https://example.com/handbook"
          required
          autocapitalize="none"
          :spellcheck="false"
          :disabled="uploading"
          @input="clearFeedback"
        />
      </BaseField>

      <div class="file-actions">
        <BaseButton type="submit" :disabled="uploading || !linkUrl.trim()">
          {{ uploading ? 'Checking link…' : 'Submit link' }}
        </BaseButton>
      </div>
    </form>

    <div
      v-if="submissionKind === 'file' && selectedSlug"
      class="file-submission"
    >
      <div
        class="dropzone"
        :class="{ dragging }"
        @dragover.prevent="dragging = !uploading"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
      >
        <BaseField
          id="upload-file"
          label="Choose a file"
          :hint="`PDF, PNG, or JPEG. Maximum ${MAX_MB} MB. One file per version.`"
          v-slot="{ id, describedBy }"
        >
          <input
            :id="id"
            type="file"
            class="file-input"
            accept="application/pdf,image/png,image/jpeg"
            :aria-describedby="describedBy"
            :disabled="uploading"
            @change="onFileInput"
          />
        </BaseField>

        <p class="drop-hint">You can also drag a file here.</p>
      </div>

      <div v-if="selectedFile" class="preview">
        <div class="file-details" role="status">
          <strong>{{ selectedFile.name }}</strong>
          <span class="text-muted">
            {{ formatSize(selectedFile.size) }}
          </span>
        </div>

        <div class="file-actions">
          <BaseButton :disabled="uploading" @click="upload">
            {{ uploading ? 'Uploading…' : 'Submit file' }}
          </BaseButton>

          <BaseButton
            variant="secondary"
            :disabled="uploading"
            @click="removeFile"
          >
            Remove
          </BaseButton>
        </div>
      </div>
    </div>

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <div v-if="result" class="success" role="status">
      <strong>Submitted for approval</strong>
      <p>
        {{ result.label }} — version {{ result.version_number }} is pending.
        Published content has not changed.
      </p>
      <router-link to="/dashboard">Review on the Dashboard →</router-link>
    </div>
  </div>
</template>

<style scoped>
.upload {
  display: grid;
  gap: var(--space-6);
  min-width: 0;
}

.upload header p {
  margin: 0;
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
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.state-panel p {
  margin: 0;
}

.error {
  color: var(--color-rejected-text);
  overflow-wrap: anywhere;
}

.version-kind {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.version-kind legend {
  margin-bottom: var(--space-3);
  padding: 0;
  font-weight: var(--weight-medium);
}

.kind-options {
  display: grid;
  gap: var(--space-3);
}

.kind-option {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  min-width: 0;
  padding: var(--space-4);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
  cursor: pointer;
}

.kind-option.is-selected {
  border-color: var(--color-primary);
  background-color: var(--color-surface-muted);
}

.kind-option input {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  margin: 2px 0 0;
  accent-color: var(--color-primary);
}

.kind-option span {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
  overflow-wrap: anywhere;
}

.kind-option small {
  color: var(--color-muted);
}

.version-kind:disabled .kind-option {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (min-width: 768px) {
  .kind-options {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.file-submission {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
}

.dropzone {
  min-width: 0;
  padding: var(--space-6);
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.dropzone.dragging {
  border-color: var(--color-primary);
  background-color: var(--color-surface-muted);
}

.file-input {
  width: 100%;
  min-width: 0;
  color: var(--color-text);
}

.file-input::file-selector-button {
  min-height: 44px;
  margin-inline-end: var(--space-3);
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-small);
  background-color: var(--color-surface-muted);
  color: var(--color-text);
  font: inherit;
  cursor: pointer;
}

.file-input:disabled {
  opacity: 0.6;
}

.drop-hint {
  display: none;
  margin: var(--space-4) 0 0;
  color: var(--color-muted);
}

.preview,
.file-details {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
  overflow-wrap: anywhere;
}

.file-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

@media (min-width: 768px) and (pointer: fine) {
  .drop-hint {
    display: block;
  }
}

.link-form {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.success {
  display: grid;
  justify-items: start;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-approved-text);
  border-radius: var(--radius-medium);
  background-color: var(--color-approved-bg);
  color: var(--color-approved-text);
  overflow-wrap: anywhere;
}

.success p {
  margin: 0;
}
</style>

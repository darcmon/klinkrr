<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import { formatSize } from '../../utils/format';
import {
  ALLOWED_FILE_TYPES,
  MAX_FILE_MB,
  fileProblem,
  hasContent,
  linkHost,
} from '../../utils/content';
import type { ContentDraft, ContentTab } from '../../types/submit';

import BaseButton from '../BaseButton.vue';
import BaseField from '../BaseField.vue';
import SubmitCard from './SubmitCard.vue';

const content = defineModel<ContentDraft>({ required: true });

defineProps<{ disabled?: boolean }>();

const TABS: { value: ContentTab; label: string }[] = [
  { value: 'file', label: 'File' },
  { value: 'link', label: 'Redirect link' },
];

const fileInput = ref<HTMLInputElement | null>(null);
const tabButtons = ref<HTMLButtonElement[]>([]);
const fileError = ref('');
const dragging = ref(false);
const linkTouched = ref(false);

const pill = computed(() =>
  hasContent(content.value)
    ? { label: 'Added', tone: 'ok' as const }
    : { label: 'Not added', tone: 'neutral' as const },
);

const link = computed({
  get: () => content.value.link,
  set: (value: string) => {
    content.value = { ...content.value, link: value };
  },
});

const host = computed(() => linkHost(link.value));
const linkError = computed(() =>
  linkTouched.value && link.value.trim() && !host.value
    ? 'Enter a full address starting with https://'
    : '',
);

const fileBadge = computed(() =>
  content.value.file ? ALLOWED_FILE_TYPES[content.value.file.type] : '',
);

function setTab(tab: ContentTab) {
  content.value = { ...content.value, tab };
}

// Arrow keys move between tabs, as in the WAI-ARIA tabs pattern.
async function onTabKeydown(event: KeyboardEvent, index: number) {
  const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
  if (!step) return;
  event.preventDefault();
  const next = (index + step + TABS.length) % TABS.length;
  setTab(TABS[next]!.value);
  await nextTick();
  tabButtons.value[next]?.focus();
}

function chooseFile(file: File) {
  const problem = fileProblem(file);
  fileError.value = problem ?? '';
  if (!problem) content.value = { ...content.value, file };
}

function onFileInput(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) chooseFile(file);
  // Allows choosing the same file again after removing it.
  input.value = '';
}

function onDrop(event: DragEvent) {
  dragging.value = false;
  const files = event.dataTransfer?.files;
  if (!files?.length) return;
  if (files.length > 1) {
    fileError.value = 'Choose one file at a time.';
    return;
  }
  chooseFile(files[0]!);
}

function removeFile() {
  fileError.value = '';
  content.value = { ...content.value, file: null };
}

function browse() {
  fileInput.value?.click();
}
</script>

<template>
  <SubmitCard id="content" title="Content" :pill="pill">
    <div class="tabs" role="tablist" aria-label="Content type">
      <button
        v-for="(tab, index) in TABS"
        :id="`content-tab-${tab.value}`"
        :key="tab.value"
        ref="tabButtons"
        type="button"
        role="tab"
        class="tab"
        :aria-selected="content.tab === tab.value"
        :aria-controls="`content-panel-${tab.value}`"
        :tabindex="content.tab === tab.value ? 0 : -1"
        :disabled="disabled"
        @click="setTab(tab.value)"
        @keydown="onTabKeydown($event, index)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- v-show, not v-if: switching tabs must not lose the other tab's value. -->
    <div
      v-show="content.tab === 'file'"
      id="content-panel-file"
      role="tabpanel"
      aria-labelledby="content-tab-file"
      class="panel"
    >
      <input
        ref="fileInput"
        type="file"
        class="visually-hidden"
        tabindex="-1"
        aria-hidden="true"
        :accept="Object.keys(ALLOWED_FILE_TYPES).join(',')"
        :disabled="disabled"
        @change="onFileInput"
      />

      <div
        v-if="!content.file"
        class="dropzone"
        :class="{ dragging }"
        @dragover.prevent="dragging = !disabled"
        @dragleave.prevent="dragging = false"
        @drop.prevent="!disabled && onDrop($event)"
      >
        <p class="drop-copy">Drag a file here, or</p>
        <BaseButton
          variant="secondary"
          class="browse"
          :disabled="disabled"
          aria-describedby="content-file-hint"
          @click="browse"
        >
          Choose a file
        </BaseButton>
        <p id="content-file-hint" class="text-muted text-small hint">
          PDF, PNG or JPEG · up to {{ MAX_FILE_MB }} MB
        </p>
      </div>

      <div v-else class="file-card">
        <span class="file-badge">{{ fileBadge }}</span>
        <div class="file-details">
          <strong class="file-name">{{ content.file.name }}</strong>
          <span class="text-muted text-small">{{ formatSize(content.file.size) }}</span>
        </div>
        <div class="file-actions">
          <BaseButton variant="secondary" :disabled="disabled" @click="browse">
            Replace
          </BaseButton>
          <BaseButton variant="secondary" :disabled="disabled" @click="removeFile">
            Remove
          </BaseButton>
        </div>
      </div>

      <p v-if="fileError" class="field-error" role="alert">{{ fileError }}</p>
    </div>

    <div
      v-show="content.tab === 'link'"
      id="content-panel-link"
      role="tabpanel"
      aria-labelledby="content-tab-link"
      class="panel"
    >
      <BaseField
        id="content-link"
        label="Destination URL"
        hint="Must start with https://. It’s checked for safety when you submit."
        :error="linkError"
        v-slot="{ id, describedBy, invalid }"
      >
        <input
          :id="id"
          v-model="link"
          type="url"
          inputmode="url"
          class="form-control text-mono"
          placeholder="https://example.com/menu"
          autocapitalize="none"
          :spellcheck="false"
          :aria-describedby="describedBy"
          :aria-invalid="invalid"
          :disabled="disabled"
          @blur="linkTouched = true"
        />
      </BaseField>

      <!-- A text input scrolls sideways, so show the whole address here. -->
      <div v-if="host" class="link-preview">
        <span>Visitors will be forwarded to <strong>{{ host }}</strong>.</span>
        <span class="text-mono text-small link-full">{{ link.trim() }}</span>
      </div>
    </div>
  </SubmitCard>
</template>

<style scoped>
.tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-1);
  padding: var(--space-1);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface-muted);
}

.tab {
  min-height: 44px;
  padding: var(--space-2) var(--space-3);
  border: 0;
  border-radius: var(--radius-small);
  color: var(--color-muted);
  background: transparent;
  font: inherit;
  font-weight: var(--weight-semibold);
  cursor: pointer;
}

.tab[aria-selected='true'] {
  color: var(--color-text);
  background-color: var(--color-surface);
  box-shadow: 0 0 0 1px var(--color-border);
}

.tab:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.panel {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
}

.dropzone {
  display: grid;
  justify-items: center;
  gap: var(--space-2);
  padding: var(--space-6) var(--space-4);
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-medium);
  text-align: center;
}

.dropzone.dragging {
  border-color: var(--color-primary);
  background-color: var(--color-surface-muted);
}

.drop-copy,
.hint {
  margin: 0;
}

/* Touch screens can't drag files in: offer one large button instead. */
@media (pointer: coarse) {
  .drop-copy {
    display: none;
  }

  .dropzone {
    padding: var(--space-4);
    border-style: solid;
  }

  .browse {
    width: 100%;
    min-height: 48px;
  }
}

.file-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-3);
  align-items: start;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface-muted);
}

.file-badge {
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-small);
  color: var(--color-on-primary);
  background-color: var(--color-primary);
  font-size: var(--text-small);
  font-weight: var(--weight-bold);
}

.file-details {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
}

/* Never truncate: people check the filename before submitting. */
.file-name {
  overflow-wrap: anywhere;
}

.file-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  grid-column: 1 / -1;
}

.field-error {
  margin: 0;
  color: var(--color-rejected-text);
  font-size: var(--text-small);
}

.link-preview {
  display: grid;
  gap: var(--space-1);
  padding: var(--space-3);
  border-radius: var(--radius-small);
  background-color: var(--color-surface-muted);
  overflow-wrap: anywhere;
}

.link-full {
  color: var(--color-muted);
}
</style>

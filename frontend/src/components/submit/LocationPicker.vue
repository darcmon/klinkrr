<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import api from '../../api/client';
import { isValidSlug, publicUrl, publicUrlLabel, slugify } from '../../utils/location';
import type { LocationSummary, SlugAvailability } from '../../types/location';
import type { Availability, Destination, NewLocationDraft } from '../../types/submit';

import BaseButton from '../BaseButton.vue';
import BaseField from '../BaseField.vue';
import StateMessage from '../StateMessage.vue';
import SubmitCard from './SubmitCard.vue';

const destination = defineModel<Destination>({ required: true });

defineProps<{
  disabled?: boolean;
  // Shown above the search, e.g. when a prefilled location wasn't found.
  notice?: string | null;
}>();

// A write to the model reaches the parent's v-model on its next render, so
// reading `destination.value` straight after writing it returns the old value.
// Handlers write through `write()` and read `latest()`; the template reads the
// model directly.
let written: Destination | null = null;

function latest(): Destination {
  return written ?? destination.value;
}

function latestDraft(): NewLocationDraft | null {
  const d = latest();
  return d.kind === 'new' ? d.draft : null;
}

function write(next: Destination) {
  written = next;
  destination.value = next;
}

// Once the model catches up (or the parent sets it), read from it again.
watch(
  destination,
  () => {
    written = null;
  },
  { flush: 'sync' },
);

const SEARCH_DELAY_MS = 250;
const AVAILABILITY_DELAY_MS = 300;

// Search state
const changing = ref(false);
const query = ref('');
const results = ref<LocationSummary[]>([]);
const recent = ref<LocationSummary[]>([]);
const searching = ref(false);
const searchError = ref('');
const activeIndex = ref(-1);
const searchInput = ref<HTMLInputElement | null>(null);
let searchTimer: ReturnType<typeof setTimeout> | undefined;
let searchRequest = 0;

// Create state
const createNameInput = ref<HTMLInputElement | null>(null);
const switchError = ref('');
let previousDestination: Destination = { kind: 'none' };
let availabilityTimer: ReturnType<typeof setTimeout> | undefined;
let availabilityRequest = 0;

const view = computed<'search' | 'selected' | 'create'>(() => {
  const kind = destination.value.kind;
  if (kind === 'new') return 'create';
  if ((kind === 'existing' || kind === 'created') && !changing.value) return 'selected';
  return 'search';
});

const current = computed(() =>
  destination.value.kind === 'existing' || destination.value.kind === 'created'
    ? destination.value.location
    : null,
);

const draft = computed(() =>
  destination.value.kind === 'new' ? destination.value.draft : null,
);

const pathUnavailable = computed(
  () =>
    draft.value?.availability.state === 'unavailable' &&
    // Invalid paths are shown as a field error, not a blocking alert.
    draft.value.availability.reason !== 'invalid',
);

const pill = computed(() => {
  const d = destination.value;
  if (d.kind === 'new') {
    return d.draft.availability.state === 'unavailable'
      ? { label: 'URL path unavailable', tone: 'error' as const }
      : { label: 'New · not created yet', tone: 'new' as const };
  }
  if (changing.value) return { label: 'Changing', tone: 'pending' as const };
  if (d.kind === 'created') return { label: 'Created', tone: 'ok' as const };
  if (d.kind === 'existing') {
    return d.via === 'prefill'
      ? { label: 'Prefilled', tone: 'ok' as const }
      : { label: 'Selected', tone: 'ok' as const };
  }
  return { label: 'Not chosen', tone: 'neutral' as const };
});

// The list the listbox shows: search results, or recent submissions.
const options = computed(() => (query.value.trim() ? results.value : recent.value));
const noMatch = computed(
  () =>
    query.value.trim() !== '' &&
    !searching.value &&
    !searchError.value &&
    results.value.length === 0,
);

function publishedLabel(location: LocationSummary) {
  const published = location.published_version;
  return published ? `Live: v${published.version_number} · ${published.label}` : 'Nothing published yet';
}

function policyLabel(location: LocationSummary) {
  return location.approval_required
    ? 'Approval required'
    : 'Publishes immediately · no approval';
}

async function loadRecent() {
  try {
    const data = await api.get('/admin/locations?sort=recent_submission&limit=6');
    if (data !== undefined) recent.value = data.locations;
  } catch {
    // Not essential: search still works.
    recent.value = [];
  }
}

function onQueryInput() {
  activeIndex.value = -1;
  searchError.value = '';
  clearTimeout(searchTimer);

  const q = query.value.trim();
  if (!q) {
    searching.value = false;
    results.value = [];
    return;
  }

  searching.value = true;
  searchTimer = setTimeout(async () => {
    const request = ++searchRequest;
    try {
      const data = await api.get(
        `/admin/locations?q=${encodeURIComponent(q)}&sort=name&limit=8`,
      );
      // Ignore responses for a query the user has since changed.
      if (request !== searchRequest || data === undefined) return;
      results.value = data.locations;
    } catch (e) {
      if (request !== searchRequest) return;
      searchError.value = e instanceof Error ? e.message : 'Search failed';
    } finally {
      if (request === searchRequest) searching.value = false;
    }
  }, SEARCH_DELAY_MS);
}

function select(location: LocationSummary) {
  write({ kind: 'existing', location, via: 'picked' });
  changing.value = false;
  query.value = '';
  results.value = [];
  activeIndex.value = -1;
}

async function startChange() {
  changing.value = true;
  query.value = '';
  results.value = [];
  activeIndex.value = -1;
  await nextTick();
  searchInput.value?.focus();
}

function cancelChange() {
  changing.value = false;
  query.value = '';
  results.value = [];
}

function onSearchKeydown(event: KeyboardEvent) {
  const count = options.value.length;
  if (event.key === 'ArrowDown' && count) {
    event.preventDefault();
    activeIndex.value = (activeIndex.value + 1) % count;
  } else if (event.key === 'ArrowUp' && count) {
    event.preventDefault();
    activeIndex.value = (activeIndex.value - 1 + count) % count;
  } else if (event.key === 'Enter' && activeIndex.value >= 0) {
    event.preventDefault();
    const option = options.value[activeIndex.value];
    if (option) select(option);
  } else if (event.key === 'Escape') {
    if (current.value) {
      event.preventDefault();
      cancelChange();
    } else if (query.value) {
      event.preventDefault();
      query.value = '';
      onQueryInput();
    }
  }
}

// --- Creating a location -------------------------------------------------

function setDraft(update: Partial<NewLocationDraft>) {
  const draft = latestDraft();
  if (!draft) return;
  write({ kind: 'new', draft: { ...draft, ...update } });
}

function checkAvailability() {
  clearTimeout(availabilityTimer);
  const slug = latestDraft()?.slug ?? '';

  if (!slug) {
    setDraft({ availability: { state: 'empty' } });
    return;
  }
  if (!isValidSlug(slug)) {
    setDraft({
      availability: {
        state: 'unavailable',
        reason: 'invalid',
        takenBy: null,
        message: 'Use lowercase letters, numbers and hyphens, up to 100 characters.',
      },
    });
    return;
  }

  setDraft({ availability: { state: 'checking' } });
  availabilityTimer = setTimeout(async () => {
    const request = ++availabilityRequest;
    let availability: Availability;
    try {
      const data: SlugAvailability | undefined = await api.get(
        `/admin/locations/slug-availability?slug=${encodeURIComponent(slug)}`,
      );
      if (data === undefined) return;
      availability = data.available
        ? { state: 'available' }
        : {
            state: 'unavailable',
            reason: data.reason ?? 'taken',
            takenBy: data.taken_by,
            message: data.message ?? 'This path is already in use.',
          };
    } catch {
      availability = { state: 'unknown' };
    }
    // Discard answers for a path the user has since changed.
    if (request === availabilityRequest && latestDraft()?.slug === slug) {
      setDraft({ availability });
    }
  }, AVAILABILITY_DELAY_MS);
}

async function startCreate(name = '') {
  const before = latest();
  previousDestination =
    before.kind === 'existing' || before.kind === 'created' ? before : { kind: 'none' };
  changing.value = false;
  switchError.value = '';
  write({
    kind: 'new',
    draft: {
      id: crypto.randomUUID(),
      displayName: name,
      slug: slugify(name),
      slugEdited: false,
      description: '',
      availability: { state: 'empty' },
    },
  });
  checkAvailability();
  await nextTick();
  createNameInput.value?.focus();
}

function cancelCreate() {
  clearTimeout(availabilityTimer);
  write(previousDestination);
  // Coming back from a change keeps the picker open on the search.
  changing.value = previousDestination.kind !== 'none';
  query.value = '';
  nextTick(() => searchInput.value?.focus());
}

function onNameInput(event: Event) {
  const displayName = (event.target as HTMLInputElement).value;
  if (latestDraft()?.slugEdited) {
    setDraft({ displayName });
    return;
  }
  setDraft({ displayName, slug: slugify(displayName) });
  checkAvailability();
}

function onSlugInput(event: Event) {
  setDraft({ slug: (event.target as HTMLInputElement).value.toLowerCase(), slugEdited: true });
  checkAvailability();
}

function onDescriptionInput(event: Event) {
  setDraft({ description: (event.target as HTMLTextAreaElement).value });
}

// "Submit to <name> instead" when the path is taken in your organization.
async function switchToOwner() {
  const slug = latestDraft()?.slug;
  if (!slug) return;
  switchError.value = '';
  try {
    const location: LocationSummary | undefined = await api.get(
      `/admin/locations/${encodeURIComponent(slug)}`,
    );
    if (location) select(location);
  } catch (e) {
    switchError.value = e instanceof Error ? e.message : 'Couldn’t open that location';
  }
}

// Stop a pending availability check once the draft is gone.
watch(
  () => destination.value.kind,
  (kind) => {
    if (kind !== 'new') clearTimeout(availabilityTimer);
  },
);

onMounted(() => {
  loadRecent();
});

onBeforeUnmount(() => {
  clearTimeout(searchTimer);
  clearTimeout(availabilityTimer);
});

defineExpose({ startChange });
</script>

<template>
  <SubmitCard id="location" title="Location" :pill="pill">
    <!-- Selected (existing, prefilled or just created) -->
    <template v-if="view === 'selected' && current">
      <div class="destination-card" :class="{ created: destination.kind === 'created' }">
        <strong class="destination-name">{{ current.display_name }}</strong>
        <span class="text-mono text-small url">{{ publicUrlLabel(current.slug) }}</span>
        <span class="text-small">{{ publishedLabel(current) }}</span>
        <span class="text-muted text-small">{{ policyLabel(current) }}</span>
      </div>

      <p
        v-if="destination.kind === 'existing' && destination.via === 'prefill'"
        class="text-muted text-small helper"
      >
        Selected because you started from {{ current.display_name }}.
      </p>

      <div>
        <BaseButton variant="secondary" :disabled="disabled" @click="startChange">
          Change
        </BaseButton>
      </div>
    </template>

    <!-- Choosing (empty, changing, no match) -->
    <template v-else-if="view === 'search'">
      <StateMessage v-if="notice" :message="notice" />

      <p v-if="current" class="text-small helper">
        Currently <strong>{{ current.display_name }}</strong> · Esc keeps it.
        Your content stays attached while you choose.
      </p>

      <BaseField id="location-search" label="Find a location" v-slot="{ id }">
        <input
          :id="id"
          ref="searchInput"
          v-model="query"
          type="search"
          class="form-control"
          placeholder="Search by name or URL path"
          role="combobox"
          aria-autocomplete="list"
          aria-controls="location-options"
          :aria-expanded="options.length > 0"
          :aria-activedescendant="
            activeIndex >= 0 ? `location-option-${activeIndex}` : undefined
          "
          autocomplete="off"
          :spellcheck="false"
          :disabled="disabled"
          @input="onQueryInput"
          @keydown="onSearchKeydown"
        />
      </BaseField>

      <p v-if="!query.trim() && recent.length" class="list-heading">
        Recent submissions
      </p>

      <ul
        v-show="options.length"
        id="location-options"
        role="listbox"
        class="options"
        :aria-label="query.trim() ? 'Matching locations' : 'Recent submissions'"
      >
        <li
          v-for="(option, index) in options"
          :id="`location-option-${index}`"
          :key="option.id"
          role="option"
          class="option"
          :class="{ active: index === activeIndex }"
          :aria-selected="index === activeIndex"
          @mousedown.prevent
          @click="!disabled && select(option)"
        >
          <strong>{{ option.display_name }}</strong>
          <span class="text-mono text-small url">{{ publicUrlLabel(option.slug) }}</span>
          <span class="text-muted text-small">{{ publishedLabel(option) }}</span>
        </li>
      </ul>

      <p v-if="searching" class="text-muted text-small" role="status">Searching…</p>
      <StateMessage v-if="searchError" tone="error" :message="searchError" />

      <div v-if="noMatch" class="no-match" role="status">
        <p>
          No locations match “{{ query.trim() }}”. Searched names and URL paths.
          Searching never creates a location.
        </p>
        <BaseButton :disabled="disabled" @click="startCreate(query.trim())">
          Create new location “{{ query.trim() }}”
        </BaseButton>
      </div>

      <div v-else class="create-entry">
        <BaseButton variant="secondary" :disabled="disabled" @click="startCreate()">
          + Create new location
        </BaseButton>
        <p class="text-muted text-small">
          You’ll see the URL before anything is created.
        </p>
      </div>

      <div v-if="current">
        <BaseButton variant="secondary" :disabled="disabled" @click="cancelChange">
          Keep {{ current.display_name }}
        </BaseButton>
      </div>
    </template>

    <!-- Creating a new location -->
    <template v-else-if="view === 'create' && draft">
      <BaseField id="new-location-name" label="Display name" v-slot="{ id }">
        <input
          :id="id"
          ref="createNameInput"
          :value="draft.displayName"
          class="form-control"
          maxlength="255"
          autocomplete="off"
          :disabled="disabled"
          @input="onNameInput"
        />
      </BaseField>

      <BaseField
        id="new-location-slug"
        label="URL path"
        hint="Lowercase letters, numbers and hyphens. This is permanent."
        :error="
          draft.availability.state === 'unavailable' && draft.availability.reason === 'invalid'
            ? draft.availability.message
            : undefined
        "
        v-slot="{ id, describedBy, invalid }"
      >
        <div class="slug-input" :class="{ unavailable: draft.availability.state === 'unavailable' }">
          <span class="slug-prefix text-mono" aria-hidden="true">
            {{ publicUrlLabel('') }}
          </span>
          <input
            :id="id"
            :value="draft.slug"
            class="text-mono"
            maxlength="100"
            autocapitalize="none"
            autocomplete="off"
            :spellcheck="false"
            :aria-describedby="`${describedBy ?? ''} new-location-url`.trim()"
            :aria-invalid="invalid || draft.availability.state === 'unavailable'"
            :disabled="disabled"
            @input="onSlugInput"
          />
        </div>
      </BaseField>

      <div id="new-location-url" class="url-preview" aria-live="polite">
        <span class="text-small">Public URL</span>
        <span class="text-mono url">{{ draft.slug ? publicUrl(draft.slug) : '—' }}</span>
        <span
          class="availability text-small"
          :class="`availability--${draft.availability.state}`"
        >
          <template v-if="draft.availability.state === 'checking'">Checking…</template>
          <template v-else-if="draft.availability.state === 'available'">✓ Available now</template>
          <template v-else-if="pathUnavailable">✕ Not available</template>
          <template v-else-if="draft.availability.state === 'unknown'">
            Couldn’t check availability. You can still submit.
          </template>
        </span>
      </div>

      <div v-if="pathUnavailable && draft.availability.state === 'unavailable'" class="path-alert" role="alert">
        <p>
          {{ draft.availability.message }} Enter a different path. klinkrr won’t add a
          number for you.
        </p>
        <BaseButton
          v-if="draft.availability.reason === 'taken' && draft.availability.takenBy"
          variant="secondary"
          :disabled="disabled"
          @click="switchToOwner"
        >
          Submit to {{ draft.availability.takenBy }} instead
        </BaseButton>
        <StateMessage v-if="switchError" tone="error" :message="switchError" />
      </div>

      <BaseField id="new-location-description" label="Description (optional)" v-slot="{ id }">
        <textarea
          :id="id"
          :value="draft.description"
          class="form-control"
          rows="2"
          :disabled="disabled"
          @input="onDescriptionInput"
        />
      </BaseField>

      <p class="text-small policy">
        <strong>Approval required</strong> · you can change this later in location settings.
      </p>

      <p class="text-muted text-small helper">
        The location is created when you submit, together with your content.
      </p>

      <div>
        <button type="button" class="link-button" :disabled="disabled" @click="cancelCreate">
          Choose an existing location instead
        </button>
      </div>
    </template>
  </SubmitCard>
</template>

<style scoped>
.destination-card {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
  padding: var(--space-4);
  border: 2px solid var(--color-primary);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface-muted);
}

.destination-card.created {
  border-color: var(--color-approved-text);
}

.destination-name,
.url {
  overflow-wrap: anywhere;
}

.url {
  color: var(--color-muted);
}

.helper,
.policy {
  margin: 0;
}

.list-heading {
  margin: 0;
  color: var(--color-muted);
  font-size: var(--text-small);
  font-weight: var(--weight-semibold);
}

.options {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  overflow: hidden;
}

.option {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
  min-height: 44px;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
}

.option:last-child {
  border-bottom: 0;
}

.option:hover,
.option.active {
  background-color: var(--color-surface-muted);
}

.option.active {
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.no-match,
.create-entry {
  display: grid;
  justify-items: start;
  gap: var(--space-2);
}

.no-match p,
.create-entry p {
  margin: 0;
}

.slug-input {
  display: flex;
  align-items: stretch;
  min-width: 0;
  min-height: 44px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-small);
  background-color: var(--color-surface);
}

.slug-input:focus-within {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}

.slug-input.unavailable {
  border-color: var(--color-rejected-text);
}

.slug-prefix {
  display: flex;
  align-items: center;
  max-width: 55%;
  padding: 0 var(--space-2) 0 var(--space-3);
  overflow: hidden;
  color: var(--color-muted);
  background-color: var(--color-surface-muted);
  border-radius: var(--radius-small) 0 0 var(--radius-small);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.slug-input input {
  flex: 1;
  min-width: 0;
  padding: 0 var(--space-3);
  border: 0;
  color: var(--color-text);
  background: transparent;
  font: inherit;
}

.slug-input input:focus {
  outline: none;
}

.url-preview {
  display: grid;
  gap: var(--space-1);
  padding: var(--space-3);
  border-radius: var(--radius-small);
  background-color: var(--color-surface-muted);
}

.availability--available {
  color: var(--color-approved-text);
}

.availability--unavailable {
  color: var(--color-rejected-text);
}

.availability--checking,
.availability--unknown {
  color: var(--color-muted);
}

.path-alert {
  display: grid;
  justify-items: start;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--color-rejected-text);
  border-radius: var(--radius-small);
  color: var(--color-rejected-text);
  background-color: var(--color-rejected-bg);
}

.path-alert p {
  margin: 0;
}

.link-button {
  min-height: 44px;
  padding: 0;
  border: 0;
  color: var(--color-primary);
  background: none;
  font: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.link-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>

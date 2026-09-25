<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import api, { ApiError, NetworkError } from '../api/client';
import { useCurrentUser } from '../composables/useCurrentUser';
import { hasContent } from '../utils/content';
import { publicUrlLabel } from '../utils/location';
import type { LocationSummary, SlugUnavailableReason } from '../types/location';
import type {
  ContentDraft,
  ContentTab,
  Destination,
  NewLocationDraft,
  SubmitResult,
  Submission,
} from '../types/submit';

import BaseButton from '../components/BaseButton.vue';
import StatePill from '../components/StatePill.vue';
import StateMessage from '../components/StateMessage.vue';
import ContentCard from '../components/submit/ContentCard.vue';
import LocationPicker from '../components/submit/LocationPicker.vue';
import SubmitOutcome from '../components/submit/SubmitOutcome.vue';

const route = useRoute();
const { load: loadCurrentUser } = useCurrentUser();

// --- Draft ------------------------------------------------------------------

const content = ref<ContentDraft>({ tab: 'file', file: null, link: '' });
const destination = ref<Destination>({ kind: 'none' });
const submission = ref<Submission>({ phase: 'idle' });
// Sent with the version so a retry can't create a duplicate. New whenever the
// content or destination changes; kept while retrying the same submission.
const versionId = ref(crypto.randomUUID());

const prefilling = ref(false);
const prefillNotice = ref<string | null>(null);
// Set when submit is pressed before the draft is ready, to draw the eye.
const attempted = ref(false);

const busy = computed(() =>
  ['creating', 'uploading', 'processing'].includes(submission.value.phase),
);

const currentLocation = computed<LocationSummary | null>(() =>
  destination.value.kind === 'existing' || destination.value.kind === 'created'
    ? destination.value.location
    : null,
);

// Identifies "the same submission": the active content plus where it goes.
// A new location's draft id becomes its location id, so creating it doesn't
// count as a change.
const submissionKey = computed(() => {
  const { tab, file, link } = content.value;
  const value =
    tab === 'file'
      ? file
        ? `${file.name}:${file.size}:${file.lastModified}`
        : ''
      : link.trim();
  const d = destination.value;
  const target =
    d.kind === 'new' ? d.draft.id : d.kind === 'none' ? '' : d.location.id;
  return `${tab}|${value}|${target}`;
});

watch(submissionKey, () => {
  if (busy.value) return;
  versionId.value = crypto.randomUUID();
  attempted.value = false;
  // A different submission: an earlier failure no longer applies.
  if (
    submission.value.phase === 'failed' ||
    submission.value.phase === 'unknown'
  ) {
    submission.value = { phase: 'idle' };
  }
});

// --- What the action bar says ------------------------------------------------

// The one thing still missing, or null when ready to submit.
const missing = computed<string | null>(() => {
  if (!hasContent(content.value)) return 'Add a file or link to submit.';
  const d = destination.value;
  if (d.kind === 'none') return 'Choose or create a location.';
  if (d.kind === 'new') {
    if (!d.draft.displayName.trim())
      return 'Enter a name for the new location.';
    if (!d.draft.slug) return 'Enter a URL path for the new location.';
    if (d.draft.availability.state === 'unavailable') {
      return 'Change the URL path to continue.';
    }
  }
  return null;
});

const summary = computed(() => {
  const d = destination.value;
  if (d.kind === 'new') {
    return {
      name: d.draft.displayName.trim() || 'New location',
      url: d.draft.slug ? publicUrlLabel(d.draft.slug) : null,
      isNew: true,
    };
  }
  if (d.kind === 'none') return null;
  return {
    name: d.location.display_name,
    url: publicUrlLabel(d.location.slug),
    isNew: false,
  };
});

const outcomeNote = computed(() => {
  const d = destination.value;
  if (d.kind === 'none')
    return 'Choose an existing location or create a new one.';
  if (d.kind === 'new') {
    return d.draft.availability.state === 'unavailable'
      ? 'This URL path can’t be used.'
      : 'Creates this location, then a pending version. Nothing is public until approved.';
  }
  // No version numbers here: the server decides them.
  return d.location.approval_required
    ? 'Creates a new pending version. Published content stays unchanged until approved.'
    : `Publishes this version immediately, replacing what’s live at ${publicUrlLabel(d.location.slug)}.`;
});

const buttonLabel = computed(() => {
  const s = submission.value;
  if (s.phase === 'creating') return 'Creating location…';
  if (s.phase === 'uploading')
    return `Uploading ${Math.floor(s.fraction * 100)}%`;
  if (s.phase === 'processing') {
    return content.value.tab === 'file' ? 'Processing…' : 'Submitting…';
  }
  if (s.phase === 'unknown') return 'Retry';
  if (destination.value.kind === 'new') return 'Create location & submit';
  if (currentLocation.value && !currentLocation.value.approval_required) {
    return 'Submit & publish';
  }
  return 'Submit version';
});

const contentLabel = computed(() =>
  content.value.tab === 'file'
    ? (content.value.file?.name ?? '')
    : content.value.link.trim(),
);

// Created a location here, but the version didn't go through (or might not have).
const partialFailure = computed(
  () =>
    destination.value.kind === 'created' &&
    (submission.value.phase === 'failed' ||
      submission.value.phase === 'unknown'),
);

const result = computed({
  get: () =>
    submission.value.phase === 'done' ? submission.value.result : null,
  set: (value: SubmitResult | null) => {
    if (value) submission.value = { phase: 'done', result: value };
  },
});

// --- Submitting -------------------------------------------------------------

function errorMessage(e: unknown, fallback: string) {
  return e instanceof Error ? e.message : fallback;
}

/** True when no clear answer came back, so the request may have taken effect.
 * A 503 from the link safety check is a clear "no". */
function isUnknownOutcome(e: unknown, kind?: ContentTab): boolean {
  if (e instanceof NetworkError) return true;
  if (e instanceof ApiError) {
    if (e.status === 503 && kind === 'link') return false;
    return e.status >= 500;
  }
  return true;
}

async function createLocation(
  draft: NewLocationDraft,
): Promise<LocationSummary | null> {
  submission.value = { phase: 'creating' };

  try {
    const location: LocationSummary | undefined = await api.post(
      '/admin/locations',
      {
        id: draft.id,
        slug: draft.slug,
        display_name: draft.displayName.trim(),
        description: draft.description.trim() || null,
        // approval_required is left out: new locations here always require it.
      },
    );
    if (location === undefined) return null;

    destination.value = { kind: 'created', location };
    return location;
  } catch (e) {
    if (
      e instanceof ApiError &&
      e.status === 409 &&
      e.code?.startsWith('slug_')
    ) {
      // Someone took the path since the availability check. Keep everything typed.
      const takenBy = e.detail?.taken_by;
      destination.value = {
        kind: 'new',
        draft: {
          ...draft,
          availability: {
            state: 'unavailable',
            reason: e.code.slice('slug_'.length) as SlugUnavailableReason,
            takenBy: typeof takenBy === 'string' ? takenBy : null,
            message: e.message,
          },
        },
      };
      submission.value = { phase: 'idle' };
      return null;
    }

    submission.value = isUnknownOutcome(e)
      ? { phase: 'unknown', stage: 'create' }
      : {
          phase: 'failed',
          message: errorMessage(e, 'Couldn’t create the location'),
        };
    return null;
  }
}

function submissionFailureMessage(e: unknown, kind: ContentTab): string {
  if (e instanceof ApiError && kind === 'link') {
    if (e.status === 422 && /flagged/i.test(e.message)) {
      return 'This URL was flagged by the safety check and can’t be used.';
    }
    if (e.status === 503) {
      return 'The URL safety check is unavailable right now. Try again in a moment.';
    }
  }
  return errorMessage(e, 'Submission failed');
}

async function submitContent(location: LocationSummary) {
  const { tab: kind, file, link } = content.value;
  const path = `/admin/locations/${encodeURIComponent(location.slug)}`;
  const id = versionId.value;

  try {
    let created;
    if (kind === 'file' && file) {
      const form = new FormData();
      form.append('file', file);
      form.append('id', id);
      submission.value = { phase: 'uploading', fraction: 0 };
      created = await api.uploadWithProgress(
        `${path}/upload`,
        form,
        (fraction) => {
          // Once the bytes are sent, the server is still storing them.
          submission.value =
            fraction >= 1
              ? { phase: 'processing' }
              : { phase: 'uploading', fraction };
        },
      );
    } else {
      submission.value = { phase: 'processing' };
      created = await api.post(`${path}/link`, {
        id,
        link_url: link.trim(),
        link_mode: 'redirect',
      });
    }
    if (created === undefined) return;

    // Refetch so the live version shown is the server's, not a guess.
    let fresh = location;
    try {
      fresh = (await api.get(path)) ?? location;
    } catch {
      // The submission worked; only the live-version details may be stale.
    }

    submission.value = {
      phase: 'done',
      result: {
        id: created.id,
        versionNumber: created.version_number,
        status: created.status,
        kind,
        label: kind === 'file' ? (file?.name ?? '') : link.trim(),
        location: fresh,
        expectedStatus: location.approval_required ? 'pending' : 'approved',
      },
    };
    await nextTick();
    document.getElementById('outcome-title')?.focus();
  } catch (e) {
    if (e instanceof ApiError && e.code === 'version_id_conflict') {
      versionId.value = crypto.randomUUID();
      submission.value = {
        phase: 'failed',
        message:
          'This submission conflicts with an earlier attempt. Submit again to send it as a new version.',
      };
      return;
    }

    submission.value = isUnknownOutcome(e, kind)
      ? { phase: 'unknown', stage: 'submit' }
      : { phase: 'failed', message: submissionFailureMessage(e, kind) };
  }
}

async function submit() {
  if (busy.value) return;
  // The button is aria-disabled rather than disabled, so it can still be
  // clicked; refuse here and point at what's missing.
  if (missing.value) {
    attempted.value = true;
    return;
  }

  let location: LocationSummary | null;
  const d = destination.value;
  if (d.kind === 'new') {
    location = await createLocation(d.draft);
  } else if (d.kind === 'existing' || d.kind === 'created') {
    location = d.location;
  } else {
    return;
  }

  if (location) await submitContent(location);
}

function submitAnother() {
  const done = result.value;
  content.value = { tab: content.value.tab, file: null, link: '' };
  if (done)
    destination.value = {
      kind: 'existing',
      location: done.location,
      via: 'picked',
    };
  submission.value = { phase: 'idle' };
  versionId.value = crypto.randomUUID();
  attempted.value = false;
}

// --- Entry --------------------------------------------------------------------

async function prefill(slug: string) {
  prefilling.value = true;
  try {
    const location: LocationSummary | undefined = await api.get(
      `/admin/locations/${encodeURIComponent(slug)}`,
    );
    if (location)
      destination.value = { kind: 'existing', location, via: 'prefill' };
  } catch (e) {
    prefillNotice.value =
      e instanceof ApiError && e.status === 404
        ? `We couldn’t find ${publicUrlLabel(slug)}. Choose a location instead.`
        : `Couldn’t load ${publicUrlLabel(slug)}. Choose a location instead.`;
  } finally {
    prefilling.value = false;
  }
}

onMounted(() => {
  // Needed for "Approve now"; the page works without it.
  loadCurrentUser().catch(() => {});

  const slug = route.query.location;
  if (typeof slug === 'string' && slug) prefill(slug);
});
</script>

<template>
  <div class="submit-page">
    <nav
      v-if="destination.kind === 'existing' && destination.via === 'prefill'"
      class="breadcrumb text-small"
      aria-label="Breadcrumb"
    >
      <router-link to="/locations">‹ Locations</router-link>
      <span aria-hidden="true">/</span>
      <span aria-current="page">{{ destination.location.display_name }}</span>
    </nav>

    <header>
      <h1>Submit a klink</h1>
      <p class="text-muted">
        Add content and choose a location, in either order. What happens on
        submit depends on the location’s approval setting, shown before you
        submit.
      </p>
    </header>

    <SubmitOutcome
      v-if="result"
      v-model="result"
      @submit-another="submitAnother"
    />

    <template v-else>
      <div class="cards">
        <ContentCard v-model="content" :disabled="busy" />

        <div v-if="prefilling" class="loading-card">
          <StateMessage message="Loading location…" />
        </div>
        <LocationPicker
          v-else
          v-model="destination"
          :disabled="busy"
          :notice="prefillNotice"
        />
      </div>

      <section
        v-if="partialFailure"
        class="partial"
        aria-labelledby="partial-title"
      >
        <h2 id="partial-title" role="alert">
          Location created, but the version wasn’t
          {{ submission.phase === 'unknown' ? 'confirmed' : 'submitted' }}
        </h2>
        <p v-if="currentLocation">
          <span class="text-mono url">{{
            publicUrlLabel(currentLocation.slug)
          }}</span>
          exists. Nothing is published there yet.
        </p>
        <p v-if="submission.phase === 'failed'">{{ submission.message }}</p>
        <p v-else>
          We couldn’t confirm whether your submission went through. Retrying is
          safe and won’t create a duplicate.
        </p>
        <p>
          Still selected: <strong class="url">{{ contentLabel }}</strong>
        </p>

        <div class="partial-actions">
          <BaseButton :disabled="busy" @click="submit"
            >Retry submission</BaseButton
          >
          <router-link
            v-if="currentLocation"
            class="text-link"
            :to="{ name: 'archive', params: { slug: currentLocation.slug } }"
          >
            View location
          </router-link>
        </div>
      </section>

      <section v-else class="action-bar" aria-label="Submit">
        <div class="summary">
          <span class="eyebrow">Submitting to</span>
          <template v-if="summary">
            <span class="destination">
              <strong>{{ summary.name }}</strong>
              <StatePill v-if="summary.isNew" label="New" tone="new" />
            </span>
            <span v-if="summary.url" class="text-mono text-small url">{{
              summary.url
            }}</span>
          </template>
          <strong v-else>No location chosen</strong>
          <p class="text-muted text-small note">{{ outcomeNote }}</p>
        </div>

        <div class="submit">
          <StateMessage
            v-if="submission.phase === 'failed'"
            tone="error"
            :message="submission.message"
          />
          <StateMessage
            v-else-if="submission.phase === 'unknown'"
            :message="
              submission.stage === 'create'
                ? 'We couldn’t confirm whether the location was created. Retrying is safe and won’t create a duplicate.'
                : 'We couldn’t confirm whether your submission went through. Retrying is safe and won’t create a duplicate.'
            "
          />

          <progress
            v-if="submission.phase === 'uploading'"
            class="progress"
            max="1"
            :value="submission.fraction"
            aria-label="Upload progress"
          />

          <BaseButton
            class="submit-button"
            :disabled="busy"
            :aria-disabled="missing ? 'true' : undefined"
            aria-describedby="submit-hint"
            @click="submit"
          >
            {{ buttonLabel }}
          </BaseButton>
          <p
            v-if="missing"
            id="submit-hint"
            class="hint text-small"
            :class="{ emphasis: attempted }"
            :role="attempted ? 'alert' : undefined"
          >
            {{ missing }}
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.submit-page {
  display: grid;
  gap: var(--space-6);
  min-width: 0;
}

.submit-page > header p {
  margin: 0;
}

.breadcrumb {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: calc(var(--space-2) * -1);
  overflow-wrap: anywhere;
}

.breadcrumb a {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
}

.cards {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
}

.loading-card {
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

.url {
  overflow-wrap: anywhere;
}

.action-bar,
.partial {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  background-color: var(--color-surface);
}

/* Mobile: the bar stays in view and always names the destination. */
.action-bar {
  position: sticky;
  bottom: 0;
  z-index: 1;
  box-shadow: 0 -4px 12px rgb(0 0 0 / 8%);
}

.summary {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
}

.eyebrow {
  color: var(--color-muted);
  font-size: var(--text-small);
  font-weight: var(--weight-semibold);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.destination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  overflow-wrap: anywhere;
}

.note {
  margin: 0;
}

.submit {
  display: grid;
  gap: var(--space-2);
}

.submit-button {
  width: 100%;
  min-height: 48px;
}

.submit-button[aria-disabled='true'] {
  cursor: not-allowed;
  opacity: 0.6;
}

.progress {
  width: 100%;
  height: 6px;
  accent-color: var(--color-primary);
}

.hint {
  margin: 0;
  color: var(--color-muted);
}

.hint.emphasis {
  color: var(--color-rejected-text);
  font-weight: var(--weight-semibold);
}

.partial {
  border-color: var(--color-rejected-text);
}

.partial h2,
.partial p {
  margin: 0;
}

.partial-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3) var(--space-4);
}

.text-link {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
}

@media (min-width: 768px) {
  .cards {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    align-items: start;
  }

  .action-bar {
    position: static;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    box-shadow: none;
  }

  .submit {
    justify-items: end;
    min-width: 16rem;
  }

  .submit-button {
    width: auto;
    min-height: 44px;
  }

  .hint {
    text-align: end;
  }
}
</style>

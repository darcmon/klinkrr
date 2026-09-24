<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import api from '../../api/client';
import { useCurrentUser } from '../../composables/useCurrentUser';
import type { CurrentUser } from '../../types/user';

import BaseButton from '../BaseButton.vue';
import BaseField from '../BaseField.vue';
import StateMessage from '../StateMessage.vue';
import SettingsSection from './SettingsSection.vue';

const props = defineProps<{ user: CurrentUser }>();

const { refresh } = useCurrentUser();

const displayName = ref(props.user.display_name);
const saving = ref(false);
const error = ref('');
const saved = ref(false);

watch(
  () => props.user.display_name,
  (name) => {
    displayName.value = name;
  },
);

const canSave = computed(() => {
  const trimmed = displayName.value.trim();
  return trimmed !== '' && trimmed !== props.user.display_name && !saving.value;
});

async function save() {
  if (!canSave.value) return;

  saving.value = true;
  error.value = '';
  saved.value = false;

  try {
    const result = await api.patch('/admin/me', {
      display_name: displayName.value.trim(),
    });
    if (result === undefined) return;

    await refresh();
    saved.value = true;
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to save';
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <SettingsSection id="profile" title="Profile">
    <form class="settings-form" :aria-busy="saving" @submit.prevent="save">
      <BaseField
        id="profile-name"
        label="Display name"
        hint="Shown to others in your organization."
        v-slot="{ id, describedBy }"
      >
        <input
          :id="id"
          v-model="displayName"
          :aria-describedby="describedBy"
          class="form-control"
          maxlength="255"
          required
          autocomplete="name"
          :disabled="saving"
          @input="saved = false"
        />
      </BaseField>

      <div class="read-only">
        <span class="read-only-label">Email</span>
        <span class="text-mono">{{ user.email }}</span>
        <span class="text-muted text-small">
          Your sign-in email. It can't be changed yet.
        </span>
      </div>

      <StateMessage v-if="error" tone="error" :message="error" />
      <StateMessage v-if="saved" tone="success" message="Profile saved." />

      <div class="form-actions">
        <BaseButton type="submit" :disabled="!canSave">
          {{ saving ? 'Saving…' : 'Save' }}
        </BaseButton>
      </div>
    </form>
  </SettingsSection>
</template>

<style scoped>
.settings-form {
  display: grid;
  gap: var(--space-4);
  max-width: 32rem;
}

.read-only {
  display: grid;
  gap: var(--space-1);
  overflow-wrap: anywhere;
}

.read-only-label {
  font-weight: var(--weight-medium);
}
</style>

<script setup lang="ts">
import { computed, ref } from 'vue';
import api from '../../api/client';
import type { CurrentUser, SignInMethod } from '../../types/user';

import BaseButton from '../BaseButton.vue';
import BaseField from '../BaseField.vue';
import StateMessage from '../StateMessage.vue';
import SettingsSection from './SettingsSection.vue';

const props = defineProps<{ user: CurrentUser }>();

const MIN_LENGTH = 12;

const METHOD_LABELS: Record<SignInMethod, string> = {
  password: 'Email and password',
  microsoft: 'Microsoft',
  google: 'Google',
};

const methods = computed(() =>
  props.user.sign_in_methods.map((method) => METHOD_LABELS[method]),
);
const hasPassword = computed(() =>
  props.user.sign_in_methods.includes('password'),
);

const current = ref('');
const next = ref('');
const confirm = ref('');
const saving = ref(false);
const error = ref('');
const saved = ref(false);

// Only shown once the field has something in it, so an empty form isn't red.
const nextError = computed(() =>
  next.value && next.value.length < MIN_LENGTH
    ? `Use at least ${MIN_LENGTH} characters.`
    : '',
);
const confirmError = computed(() =>
  confirm.value && confirm.value !== next.value
    ? "The passwords don't match."
    : '',
);
const canSave = computed(
  () =>
    current.value !== '' &&
    next.value.length >= MIN_LENGTH &&
    confirm.value === next.value &&
    !saving.value,
);

async function changePassword() {
  if (!canSave.value) return;

  saving.value = true;
  error.value = '';
  saved.value = false;

  try {
    await api.post('/admin/me/password', {
      current_password: current.value,
      new_password: next.value,
    });

    current.value = '';
    next.value = '';
    confirm.value = '';
    saved.value = true;
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to change password';
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <SettingsSection id="sign-in" title="Sign-in">
    <div class="read-only">
      <span class="read-only-label">Signs in with</span>
      <span>{{ methods.length ? methods.join(', ') : 'Not set up yet' }}</span>
    </div>

    <form
      v-if="hasPassword"
      class="settings-form"
      :aria-busy="saving"
      @submit.prevent="changePassword"
    >
      <h3>Change password</h3>

      <BaseField id="password-current" label="Current password" v-slot="{ id }">
        <input
          :id="id"
          v-model="current"
          type="password"
          class="form-control"
          autocomplete="current-password"
          required
          :disabled="saving"
        />
      </BaseField>

      <BaseField
        id="password-new"
        label="New password"
        :hint="`At least ${MIN_LENGTH} characters.`"
        :error="nextError"
        v-slot="{ id, describedBy, invalid }"
      >
        <input
          :id="id"
          v-model="next"
          type="password"
          class="form-control"
          autocomplete="new-password"
          required
          :minlength="MIN_LENGTH"
          maxlength="128"
          :aria-describedby="describedBy"
          :aria-invalid="invalid"
          :disabled="saving"
        />
      </BaseField>

      <BaseField
        id="password-confirm"
        label="Confirm new password"
        :error="confirmError"
        v-slot="{ id, describedBy, invalid }"
      >
        <input
          :id="id"
          v-model="confirm"
          type="password"
          class="form-control"
          autocomplete="new-password"
          required
          :aria-describedby="describedBy"
          :aria-invalid="invalid"
          :disabled="saving"
        />
      </BaseField>

      <StateMessage v-if="error" tone="error" :message="error" />
      <StateMessage v-if="saved" tone="success" message="Password changed." />

      <div class="form-actions">
        <BaseButton type="submit" :disabled="!canSave">
          {{ saving ? 'Changing…' : 'Change password' }}
        </BaseButton>
      </div>
    </form>

    <p v-else class="text-muted">
      Your account has no password. Sign in with the provider above.
    </p>
  </SettingsSection>
</template>

<style scoped>
.settings-form {
  display: grid;
  gap: var(--space-4);
  max-width: 32rem;
}

.settings-form h3 {
  margin-bottom: 0;
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

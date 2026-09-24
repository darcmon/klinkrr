<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import api from '../../api/client';
import { useCurrentUser } from '../../composables/useCurrentUser';
import type { OrganizationSummary } from '../../types/user';

import BaseButton from '../BaseButton.vue';
import BaseField from '../BaseField.vue';
import StateMessage from '../StateMessage.vue';
import SettingsSection from './SettingsSection.vue';

const props = defineProps<{ organization: OrganizationSummary }>();

const { refresh } = useCurrentUser();

const name = ref(props.organization.name);
const allowSelfApproval = ref(props.organization.allow_self_approval);
const saving = ref(false);
const error = ref('');
const saved = ref(false);

watch(
  () => props.organization,
  (organization) => {
    name.value = organization.name;
    allowSelfApproval.value = organization.allow_self_approval;
  },
);

// Only the fields that differ from what's saved.
const changes = computed(() => {
  const update: Partial<Pick<OrganizationSummary, 'name' | 'allow_self_approval'>> = {};
  const trimmed = name.value.trim();
  if (trimmed && trimmed !== props.organization.name) update.name = trimmed;
  if (allowSelfApproval.value !== props.organization.allow_self_approval) {
    update.allow_self_approval = allowSelfApproval.value;
  }
  return update;
});

const canSave = computed(
  () =>
    name.value.trim() !== '' &&
    Object.keys(changes.value).length > 0 &&
    !saving.value,
);

async function save() {
  if (!canSave.value) return;

  saving.value = true;
  error.value = '';
  saved.value = false;

  try {
    const result = await api.patch('/admin/organization', changes.value);
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
  <SettingsSection
    id="organization"
    title="Organization"
    description="Only owners see this section."
  >
    <form
      class="settings-form"
      :aria-busy="saving"
      @submit.prevent="save"
      @input="saved = false"
    >
      <BaseField id="organization-name" label="Name" v-slot="{ id }">
        <input
          :id="id"
          v-model="name"
          class="form-control"
          maxlength="255"
          required
          :disabled="saving"
        />
      </BaseField>

      <div class="checkbox-field">
        <input
          id="organization-self-approval"
          v-model="allowSelfApproval"
          type="checkbox"
          aria-describedby="organization-self-approval-hint"
          :disabled="saving"
        />
        <div>
          <label for="organization-self-approval" class="checkbox-label">
            Allow people to approve their own submissions
          </label>
          <p id="organization-self-approval-hint" class="text-muted text-small">
            <template v-if="allowSelfApproval">
              Anyone can approve a version they uploaded. Each self-approval is
              recorded in the audit log.
            </template>
            <template v-else>
              Someone other than the uploader must approve every version. Your
              organization needs at least two people who can approve.
            </template>
          </p>
        </div>
      </div>

      <StateMessage v-if="error" tone="error" :message="error" />
      <StateMessage v-if="saved" tone="success" message="Organization saved." />

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

.checkbox-field {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-3);
  align-items: start;
}

/* A 44px target without enlarging the visible box. */
.checkbox-field input {
  width: 20px;
  height: 20px;
  margin: 12px 0;
  accent-color: var(--color-primary);
}

.checkbox-label {
  display: flex;
  align-items: center;
  min-height: 44px;
  font-weight: var(--weight-medium);
  cursor: pointer;
}

.checkbox-field p {
  margin: 0;
}
</style>

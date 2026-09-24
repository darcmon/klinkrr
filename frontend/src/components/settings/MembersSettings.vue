<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import api from '../../api/client';
import { formatDate } from '../../utils/format';
import { useCurrentUser } from '../../composables/useCurrentUser';
import { ROLE_OPTIONS, type Member, type Role } from '../../types/user';

import BaseButton from '../BaseButton.vue';
import BaseField from '../BaseField.vue';
import BaseModal from '../BaseModal.vue';
import StateMessage from '../StateMessage.vue';
import SettingsSection from './SettingsSection.vue';

const props = defineProps<{ organizationName: string }>();

const { refresh } = useCurrentUser();

const members = ref<Member[]>([]);
const loading = ref(true);
const loadError = ref('');

// Add form
const newEmail = ref('');
const newName = ref('');
const newRole = ref<Role>('uploader');
const adding = ref(false);
const addError = ref('');
const addedMessage = ref('');

// Per-row state
const savingId = ref<string | null>(null);
const rowErrors = ref<Record<string, string>>({});
const removeTarget = ref<Member | null>(null);
const removeError = ref('');

const ownerCount = computed(
  () => members.value.filter((member) => member.role === 'owner').length,
);
const newRoleDescription = computed(
  () => ROLE_OPTIONS.find((option) => option.value === newRole.value)?.description,
);

function isLastOwner(member: Member) {
  return member.role === 'owner' && ownerCount.value === 1;
}

async function loadMembers() {
  loading.value = true;
  loadError.value = '';

  try {
    const data = await api.get('/admin/members');
    if (data === undefined) return;
    members.value = data.members;
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'Failed to load members';
  } finally {
    loading.value = false;
  }
}

async function addMember() {
  if (adding.value) return;

  adding.value = true;
  addError.value = '';
  addedMessage.value = '';

  try {
    const added: Member | undefined = await api.post('/admin/members', {
      email: newEmail.value,
      role: newRole.value,
      display_name: newName.value.trim() || null,
    });
    if (added === undefined) return;

    addedMessage.value = `Added ${added.email}. Let them know they can sign in with Microsoft or Google using that email.`;
    newEmail.value = '';
    newName.value = '';
    newRole.value = 'uploader';
    await loadMembers();
  } catch (e) {
    addError.value = e instanceof Error ? e.message : 'Failed to add member';
  } finally {
    adding.value = false;
  }
}

async function changeRole(member: Member, event: Event) {
  const select = event.target as HTMLSelectElement;
  const role = select.value as Role;
  if (role === member.role || savingId.value !== null) return;

  savingId.value = member.user_id;
  rowErrors.value = { ...rowErrors.value, [member.user_id]: '' };

  try {
    const updated: Member | undefined = await api.patch(
      `/admin/members/${member.user_id}`,
      { role },
    );
    if (updated === undefined) return;

    member.role = updated.role;
    // Your own role decides what you can see, including this section.
    if (member.is_you) await refresh();
  } catch (e) {
    select.value = member.role;
    rowErrors.value = {
      ...rowErrors.value,
      [member.user_id]: e instanceof Error ? e.message : 'Failed to change role',
    };
  } finally {
    savingId.value = null;
  }
}

function openRemove(member: Member) {
  if (savingId.value !== null) return;
  removeError.value = '';
  removeTarget.value = member;
}

function closeRemove() {
  if (savingId.value !== null) return;
  removeTarget.value = null;
}

async function removeMember() {
  const member = removeTarget.value;
  if (!member || savingId.value !== null) return;

  savingId.value = member.user_id;
  removeError.value = '';

  try {
    await api.del(`/admin/members/${member.user_id}`);
    removeTarget.value = null;

    if (member.is_you) {
      await refresh();
    } else {
      await loadMembers();
    }
  } catch (e) {
    removeError.value = e instanceof Error ? e.message : 'Failed to remove member';
  } finally {
    savingId.value = null;
  }
}

onMounted(loadMembers);
</script>

<template>
  <SettingsSection
    id="members"
    title="Members"
    description="Who can use klinkrr in this organization, and what they can do."
  >
    <form class="add-form" :aria-busy="adding" @submit.prevent="addMember">
      <h3>Add a member</h3>

      <div class="add-fields">
        <BaseField
          id="member-email"
          label="Email"
          hint="They sign in with Microsoft or Google using this email."
          v-slot="{ id, describedBy }"
        >
          <input
            :id="id"
            v-model="newEmail"
            type="email"
            class="form-control"
            required
            maxlength="255"
            autocomplete="off"
            :spellcheck="false"
            :aria-describedby="describedBy"
            :disabled="adding"
          />
        </BaseField>

        <BaseField
          id="member-name"
          label="Name (optional)"
          hint="They can change it later."
          v-slot="{ id, describedBy }"
        >
          <input
            :id="id"
            v-model="newName"
            class="form-control"
            maxlength="255"
            autocomplete="off"
            :aria-describedby="describedBy"
            :disabled="adding"
          />
        </BaseField>

        <BaseField
          id="member-role"
          label="Role"
          :hint="newRoleDescription"
          v-slot="{ id, describedBy }"
        >
          <select
            :id="id"
            v-model="newRole"
            class="form-control"
            :aria-describedby="describedBy"
            :disabled="adding"
          >
            <option
              v-for="option in ROLE_OPTIONS"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </BaseField>
      </div>

      <StateMessage v-if="addError" tone="error" :message="addError" />
      <StateMessage v-if="addedMessage" tone="success" :message="addedMessage" />

      <div class="form-actions">
        <BaseButton type="submit" :disabled="adding">
          {{ adding ? 'Adding…' : 'Add member' }}
        </BaseButton>
      </div>
    </form>

    <StateMessage v-if="loading" message="Loading members…" />

    <StateMessage v-else-if="loadError" tone="error" :message="loadError">
      <template #actions>
        <BaseButton variant="secondary" @click="loadMembers">Try again</BaseButton>
      </template>
    </StateMessage>

    <ul v-else class="member-list" role="list">
      <li v-for="member in members" :key="member.user_id" class="member">
        <div class="member-info">
          <strong>
            {{ member.display_name }}
            <span v-if="member.is_you" class="you">You</span>
          </strong>
          <span class="text-mono text-small">{{ member.email }}</span>
          <span class="text-muted text-small">
            {{
              member.last_login_at
                ? `Last signed in ${formatDate(member.last_login_at)}`
                : "Hasn't signed in yet"
            }}
          </span>
        </div>

        <div class="member-controls">
          <label class="visually-hidden" :for="`role-${member.user_id}`">
            Role for {{ member.display_name }}
          </label>
          <select
            :id="`role-${member.user_id}`"
            class="form-control"
            :value="member.role"
            :disabled="savingId !== null || isLastOwner(member)"
            :aria-describedby="
              isLastOwner(member) ? `last-owner-${member.user_id}` : undefined
            "
            @change="changeRole(member, $event)"
          >
            <option
              v-for="option in ROLE_OPTIONS"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>

          <BaseButton
            variant="secondary"
            :disabled="savingId !== null || isLastOwner(member)"
            @click="openRemove(member)"
          >
            {{ savingId === member.user_id ? 'Saving…' : 'Remove…' }}
          </BaseButton>
        </div>

        <p
          v-if="isLastOwner(member)"
          :id="`last-owner-${member.user_id}`"
          class="text-muted text-small row-note"
        >
          The only owner. Make someone else an owner first to change this.
        </p>

        <StateMessage
          v-if="rowErrors[member.user_id]"
          tone="error"
          :message="rowErrors[member.user_id]!"
        />
      </li>
    </ul>

    <BaseModal
      v-if="removeTarget"
      id="remove-member"
      :title="removeTarget.is_you ? 'Leave this organization?' : `Remove ${removeTarget.display_name}?`"
      :busy="savingId !== null"
      @close="closeRemove"
    >
      <p v-if="removeTarget.is_you">
        You'll lose access to {{ props.organizationName }} straight away. Only
        another owner can add you back.
      </p>
      <p v-else>
        They'll lose access to {{ props.organizationName }}. Their account isn't
        deleted, and their past submissions and reviews stay in the history.
      </p>

      <StateMessage v-if="removeError" tone="error" :message="removeError" />

      <template #actions="{ requestClose }">
        <BaseButton
          variant="secondary"
          :disabled="savingId !== null"
          @click="requestClose"
        >
          Cancel
        </BaseButton>
        <BaseButton
          variant="danger"
          :disabled="savingId !== null"
          @click="removeMember"
        >
          <template v-if="savingId !== null">Removing…</template>
          <template v-else>{{ removeTarget.is_you ? 'Leave' : 'Remove' }}</template>
        </BaseButton>
      </template>
    </BaseModal>
  </SettingsSection>
</template>

<style scoped>
.add-form {
  display: grid;
  gap: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.add-form h3 {
  margin-bottom: 0;
}

.add-fields {
  display: grid;
  gap: var(--space-4);
}

.member-list {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
}

.member {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
  padding: var(--space-4) 0;
  border-bottom: 1px solid var(--color-border);
}

.member:last-child {
  border-bottom: 0;
}

.member-info {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
  overflow-wrap: anywhere;
}

.you {
  margin-inline-start: var(--space-2);
  padding: 0 var(--space-2);
  border-radius: var(--radius-pill);
  color: var(--color-muted);
  background-color: var(--color-surface-muted);
  font-size: var(--text-small);
  font-weight: var(--weight-semibold);
}

.member-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-2);
}

.row-note {
  margin: 0;
}

@media (min-width: 768px) {
  .add-fields {
    grid-template-columns: minmax(0, 2fr) minmax(0, 2fr) minmax(0, 1.5fr);
    align-items: start;
  }

  .member {
    grid-template-columns: minmax(0, 1fr) minmax(16rem, auto);
    align-items: center;
    column-gap: var(--space-6);
  }

  .row-note,
  .member :deep(.state-message) {
    grid-column: 1 / -1;
  }
}
</style>

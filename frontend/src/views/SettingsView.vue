<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useCurrentUser } from '../composables/useCurrentUser';

import BaseButton from '../components/BaseButton.vue';
import StateMessage from '../components/StateMessage.vue';
import ProfileSettings from '../components/settings/ProfileSettings.vue';
import SignInSettings from '../components/settings/SignInSettings.vue';
import OrganizationSettings from '../components/settings/OrganizationSettings.vue';
import MembersSettings from '../components/settings/MembersSettings.vue';

const { user, load, can } = useCurrentUser();

const loading = ref(!user.value);
const loadError = ref('');

async function loadUser() {
  loading.value = !user.value;
  loadError.value = '';

  try {
    await load();
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'Failed to load settings';
  } finally {
    loading.value = false;
  }
}

onMounted(loadUser);
</script>

<template>
  <div class="settings">
    <header>
      <h1>Settings</h1>
      <p class="text-muted">Your profile, how you sign in, and your organization.</p>
    </header>

    <StateMessage v-if="loading" message="Loading settings…" />

    <StateMessage v-else-if="loadError" tone="error" :message="loadError">
      <template #actions>
        <BaseButton variant="secondary" @click="loadUser">Try again</BaseButton>
      </template>
    </StateMessage>

    <template v-else-if="user">
      <ProfileSettings :user="user" />
      <SignInSettings :user="user" />

      <StateMessage
        v-if="!user.organization"
        message="You're not a member of any organization yet. Ask an owner to add you."
      />

      <template v-else-if="can('manage_members')">
        <OrganizationSettings :organization="user.organization" />
        <MembersSettings :organization-name="user.organization.name" />
      </template>
    </template>
  </div>
</template>

<style scoped>
.settings {
  display: grid;
  gap: var(--space-6);
}

.settings > header p {
  margin-bottom: 0;
}
</style>

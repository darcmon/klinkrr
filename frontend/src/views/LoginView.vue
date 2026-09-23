<script setup lang="ts">
import { API_URL } from '../api/client';
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { loginWithPassword } from '../api/auth';
import { useAuth } from '../composables/useAuth';

import AuthLayout from '../components/AuthLayout.vue';
import BaseButton from '../components/BaseButton.vue';
import BaseField from '../components/BaseField.vue';

const router = useRouter();
const { setToken } = useAuth();

const showPasswordForm = ref(false);
const email = ref('');
const password = ref('');
const submitting = ref(false);
const loginError = ref('');
const error = new URLSearchParams(window.location.search).get('error');

async function submitPasswordLogin() {
  if (submitting.value) return;

  submitting.value = true;
  loginError.value = '';

  try {
    const data = await loginWithPassword(email.value, password.value);
    setToken(data.access_token);
    password.value = '';
    await router.replace('/dashboard');
  } catch (e) {
    loginError.value =
      e instanceof Error ? e.message : 'Sign-in failed. Please try again.';
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <AuthLayout labelled-by="login-title">
    <header>
      <h1 id="login-title">Sign in to Admin</h1>
      <p class="text-muted">
        Manage your locations, submissions, and published content.
      </p>
    </header>

    <p v-if="error === 'unauthorized'" class="login-error" role="alert">
      Your account isn't authorized. Contact your administrator.
    </p>
    <p v-else-if="error === 'provider'" class="login-error" role="alert">
      Sign-in failed. Please try again.
    </p>

    <div class="sso-options">
      <a :href="`${API_URL}/admin/auth/microsoft`" class="sso-link">
        Sign in with Microsoft
      </a>
      <a :href="`${API_URL}/admin/auth/google`" class="sso-link">
        Sign in with Google
      </a>
    </div>
    <BaseButton
      variant="secondary"
      :aria-expanded="showPasswordForm"
      aria-controls="password-login"
      :disabled="submitting"
      @click="showPasswordForm = !showPasswordForm"
    >
      {{ showPasswordForm ? 'Hide email sign-in' : 'Use email and password' }}
    </BaseButton>

    <form
      v-show="showPasswordForm"
      id="password-login"
      class="password-form"
      :aria-busy="submitting"
      @submit.prevent="submitPasswordLogin"
    >
      <BaseField id="login-email" label="Email" v-slot="{ id }">
        <input
          :id="id"
          v-model="email"
          name="email"
          type="email"
          autocomplete="username"
          autocapitalize="none"
          :spellcheck="false"
          class="form-control"
          required
          :disabled="submitting"
        />
      </BaseField>

      <BaseField id="login-password" label="Password" v-slot="{ id }">
        <input
          :id="id"
          v-model="password"
          name="password"
          type="password"
          autocomplete="current-password"
          class="form-control"
          required
          :disabled="submitting"
        />
      </BaseField>

      <p v-if="loginError" class="login-error" role="alert">
        {{ loginError }}
      </p>

      <BaseButton type="submit" :disabled="submitting">
        {{ submitting ? 'Signing in…' : 'Sign in' }}
      </BaseButton>
    </form>
  </AuthLayout>
</template>

<style scoped>
header p {
  margin: 0;
}

.sso-options {
  display: grid;
  gap: var(--space-3);
}

.sso-link {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  color: var(--color-text);
  background-color: var(--color-surface);
  text-align: center;
  text-decoration: none;
  font-weight: var(--weight-semibold);
}

.sso-link:hover {
  background-color: var(--color-surface-muted);
}

.password-form {
  display: grid;
  gap: var(--space-4);
  min-width: 0;
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.login-error {
  margin: 0;
  padding: var(--space-3);
  border-radius: var(--radius-small);
  background-color: var(--color-rejected-bg);
  color: var(--color-rejected-text);
  overflow-wrap: anywhere;
}
</style>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuth } from '../composables/useAuth';

import AuthLayout from '../components/AuthLayout.vue';

const router = useRouter();
const { setToken } = useAuth();
const callbackError = ref('');

onMounted(async () => {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');

  try {
    // Remove the token from the URL while preserving router history state.
    await router.replace({ name: 'auth-callback' });

    if (params.has('error')) {
      callbackError.value = 'Sign-in failed. Please try again.';
      return;
    }

    if (!token?.trim()) {
      callbackError.value =
        'Sign-in could not be completed. Return to sign in and try again.';
      return;
    }

    setToken(token);
    await router.replace('/dashboard');
  } catch {
    callbackError.value =
      'We could not complete sign-in in this browser. Please try again.';
  }
});
</script>

<template>
  <AuthLayout labelled-by="callback-title">
    <h1 id="callback-title">
      {{ callbackError ? 'Sign-in incomplete' : 'Completing sign-in' }}
    </h1>

    <template v-if="callbackError">
      <p class="callback-error" role="alert">
        {{ callbackError }}
      </p>
      <router-link to="/login" replace> Return to sign in → </router-link>
    </template>

    <p v-else class="text-muted" role="status">Signing you in…</p>
  </AuthLayout>
</template>

<style scoped>
h1,
p {
  margin: 0;
}

.callback-error {
  color: var(--color-rejected-text);
}
</style>

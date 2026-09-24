import { ref, watch } from 'vue';
import api from '../api/client';
import { useAuth } from './useAuth';
import type { CurrentUser, Permission } from '../types/user';

// Module-level = shared across every component that imports this
const user = ref<CurrentUser | null>(null);
let inFlight: Promise<CurrentUser | null> | null = null;

const { token } = useAuth();

// A new sign-in or a sign-out means a different user, role and organization.
watch(token, () => {
  user.value = null;
  inFlight = null;
});

export function useCurrentUser() {
  async function load(): Promise<CurrentUser | null> {
    if (user.value) return user.value;

    if (!inFlight) {
      const requestedWith = token.value;
      const request = (async () => {
        const data: CurrentUser | undefined = await api.get('/admin/me');
        // Ignore a response for a token that has since changed.
        if (token.value === requestedWith) user.value = data ?? null;
        return user.value;
      })();

      inFlight = request;
      request
        .finally(() => {
          if (inFlight === request) inFlight = null;
        })
        .catch(() => {});
    }

    return inFlight;
  }

  // Server permissions only; never infer them from the role name.
  function can(permission: Permission): boolean {
    return user.value?.permissions.includes(permission) ?? false;
  }

  return { user, load, can };
}

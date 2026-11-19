import { computed, ref, watch } from 'vue';
import api from '../api/client';
import { useAuth } from './useAuth';
import type { CurrentUser, Permission } from '../types/user';

// Module-level = shared across every component that imports this
const user = ref<CurrentUser | null>(null);
let inFlight: Promise<CurrentUser | null> | null = null;

const { token, selectedOrganizationId, organizationAccessLost } = useAuth();
let requestVersion = 0;

// A new sign-in or a sign-out means a different user, role and organization.
// Losing access counts too: a revoked sole membership changes no selection.
watch(
  [token, selectedOrganizationId, organizationAccessLost],
  () => {
    requestVersion += 1;
    user.value = null;
    inFlight = null;
  },
  { flush: 'sync' },
);

function fetchUser(): Promise<CurrentUser | null> {
  if (!token.value) return Promise.resolve(null);
  requestVersion += 1;
  const thisRequestVersion = requestVersion;
  const request = (async () => {
    const data: CurrentUser | undefined = await api.get('/admin/me');
    // Ignore responses superseded by a context change or newer request.
    if (thisRequestVersion !== requestVersion) return null;
    user.value = data ?? null;
    return user.value;
  })();

  inFlight = request;
  request
    .finally(() => {
      if (inFlight === request) inFlight = null;
    })
    .catch(() => {});

  return request;
}

export function useCurrentUser() {
  async function load(): Promise<CurrentUser | null> {
    if (user.value) return user.value;
    return inFlight ?? fetchUser();
  }

  // Reload after anything that changes the user, their role or organization.
  // Keeps the current value until the new one arrives, so the UI doesn't flicker.
  function refresh(): Promise<CurrentUser | null> {
    return fetchUser();
  }

  // Server permissions only; never infer them from the role name.
  function can(permission: Permission): boolean {
    return user.value?.permissions.includes(permission) ?? false;
  }

  // Why no organization is active, or '' when one is (or the user isn't loaded).
  const organizationPrompt = computed(() => {
    if (!user.value || user.value.organization) return '';
    return user.value.memberships.length > 0
      ? 'Choose an organization above to continue.'
      : "You're not a member of any organization yet. Ask an owner to invite you.";
  });

  return { user, load, refresh, can, organizationPrompt };
}

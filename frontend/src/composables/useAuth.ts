import { ref, computed } from 'vue';

// Module-level = shared across every component that imports this
const token = ref<string | null>(localStorage.getItem('token'));
const selectedOrganizationId = ref<string | null>(null);
// True after the selected organization revoked our access, until the next choice.
const organizationAccessLost = ref(false);

export function useAuth() {
  const isAuthenticated = computed(() => !!token.value);

  function selectOrganization(organizationId: string | null) {
    organizationAccessLost.value = false;
    selectedOrganizationId.value = organizationId;
  }

  // Dropping the selection clears the cached user and remounts the layout,
  // so the next /admin/me (sent without the header) lists what's left.
  function loseOrganizationAccess() {
    selectedOrganizationId.value = null;
    organizationAccessLost.value = true;
  }

  function setToken(newToken: string) {
    organizationAccessLost.value = false;
    selectedOrganizationId.value = null;
    token.value = newToken;
    localStorage.setItem('token', newToken);
  }

  function logout() {
    organizationAccessLost.value = false;
    selectedOrganizationId.value = null;
    token.value = null;
    localStorage.removeItem('token');
  }

  return {
    token,
    isAuthenticated,
    selectedOrganizationId,
    organizationAccessLost,
    selectOrganization,
    loseOrganizationAccess,
    setToken,
    logout,
  };
}

import { ref, computed } from 'vue';

// Module-level = shared across every component that imports this
const token = ref<string | null>(localStorage.getItem('token'));
const selectedOrganizationId = ref<string | null>(null);

export function useAuth() {
  const isAuthenticated = computed(() => !!token.value);

  function selectOrganization(organizationId: string | null) {
    selectedOrganizationId.value = organizationId;
  }

  function setToken(newToken: string) {
    selectedOrganizationId.value = null;
    token.value = newToken;
    localStorage.setItem('token', newToken);
  }

  function logout() {
    selectedOrganizationId.value = null;
    token.value = null;
    localStorage.removeItem('token');
  }

  return {
    token,
    isAuthenticated,
    selectedOrganizationId,
    selectOrganization,
    setToken,
    logout,
  };
}

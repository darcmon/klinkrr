import { beforeEach, expect, it, vi } from 'vitest';
import { flushPromises, shallowMount } from '@vue/test-utils';
import AppHeader from './AppHeader.vue';

const selectOrganization = vi.hoisted(() => vi.fn());
const canLeave = vi.hoisted(() => vi.fn());
vi.mock('../composables/useLeaveGuard', () => ({ canLeave }));
beforeEach(() => vi.clearAllMocks());
const logout = vi.hoisted(() => vi.fn());
const replace = vi.hoisted(() => vi.fn());
vi.mock('vue-router', () => ({
  useRoute: () => ({}),
  useRouter: () => ({ replace }),
}));
vi.mock('./ThemeSelector.vue', () => ({ default: { template: '<div />' } }));
vi.mock('../composables/useAuth', async () => {
  const { ref } = await import('vue');
  return { useAuth: () => ({
    logout,
    selectedOrganizationId: ref(null),
    selectOrganization,
  }) };
});
vi.mock('../composables/useCurrentUser', async () => {
  const { ref } = await import('vue');
  return { useCurrentUser: () => ({
    load: async () => null,
    user: ref({
      organization: { id: 'org-a' },
      memberships: [
        { organization: { id: 'org-a', name: 'Acme' } },
        { organization: { id: 'org-b', name: 'Beta' } },
      ],
    }),
  }) };
});

it('offers memberships and restores the selection when switching is blocked', async () => {
  const wrapper = shallowMount(AppHeader);
  try {
    const select = wrapper.get('select');
    expect(select.findAll('option').map((option) => option.text())).toEqual([
      'Choose organization', 'Acme', 'Beta',
    ]);
    expect((select.element as HTMLSelectElement).value).toBe('org-a');
    await select.setValue('org-a');
    expect(canLeave).not.toHaveBeenCalled();
    expect(selectOrganization).not.toHaveBeenCalled();

    canLeave.mockReturnValue(false);
    await select.setValue('org-b');
    expect(canLeave).toHaveBeenCalledOnce();
    expect(selectOrganization).not.toHaveBeenCalled();
    expect((select.element as HTMLSelectElement).value).toBe('org-a');

    canLeave.mockReturnValue(true);
    await select.setValue('org-b');
    expect(selectOrganization).toHaveBeenCalledExactlyOnceWith('org-b');
    expect((select.element as HTMLSelectElement).value).toBe('org-b');
  } finally {
    wrapper.unmount();
  }
});

it('stays signed in when a leave guard cancels logout', async () => {
  const wrapper = shallowMount(AppHeader);
  try {
    replace.mockResolvedValueOnce(new Error('navigation aborted'));
    await wrapper.get('.logout-button').trigger('click');
    await flushPromises();
    expect(logout).not.toHaveBeenCalled();

    replace.mockResolvedValueOnce(undefined);
    await wrapper.get('.logout-button').trigger('click');
    await flushPromises();
    expect(logout).toHaveBeenCalledOnce();
  } finally {
    wrapper.unmount();
  }
});

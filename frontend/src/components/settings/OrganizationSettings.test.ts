import { afterEach, expect, it, vi } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import OrganizationSettings from './OrganizationSettings.vue';

const registerGuard = vi.hoisted(() => vi.fn());
vi.mock('../../composables/useLeaveGuard', () => ({ useLeaveGuard: registerGuard }));
vi.mock('../../composables/useCurrentUser', () => ({
  useCurrentUser: () => ({ refresh: vi.fn() }),
}));
afterEach(() => vi.restoreAllMocks());

it('detects name and policy edits and accepts refreshed settings', async () => {
  const organization = {
    id: 'org-1', name: 'Acme', slug: 'acme', allow_self_approval: true,
  };
  const wrapper = shallowMount(OrganizationSettings, { props: { organization } });
  const guard = registerGuard.mock.lastCall![0] as Parameters<
    typeof import('../../composables/useLeaveGuard').useLeaveGuard
  >[0];
  const state = wrapper.vm as unknown as {
    name: string; allowSelfApproval: boolean;
  };
  try {
    expect(guard.isDirty()).toBe(false);
    state.name = '';
    expect(guard.isDirty()).toBe(true);
    state.name = organization.name;
    state.allowSelfApproval = false;
    expect(guard.isDirty()).toBe(true);
    await wrapper.setProps({ organization: { ...organization, allow_self_approval: false } });
    expect(guard.isDirty()).toBe(false);
  } finally {
    wrapper.unmount();
  }
});

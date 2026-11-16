import { afterEach, expect, it, vi } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import ProfileSettings from './ProfileSettings.vue';
import type { CurrentUser } from '../../types/user';

const registerGuard = vi.hoisted(() => vi.fn());
vi.mock('../../composables/useLeaveGuard', () => ({ useLeaveGuard: registerGuard }));
vi.mock('../../composables/useCurrentUser', () => ({
  useCurrentUser: () => ({ refresh: vi.fn() }),
}));
afterEach(() => vi.restoreAllMocks());

it('detects invalid profile edits and accepts the refreshed saved name', async () => {
  const user: CurrentUser = {
    id: 'user-1', email: 'a@example.com', display_name: 'Alex', avatar_url: null,
    organization: null, role: null, permissions: [], memberships: [], sign_in_methods: [],
  };
  const wrapper = shallowMount(ProfileSettings, { props: { user } });
  const guard = registerGuard.mock.lastCall![0] as Parameters<
    typeof import('../../composables/useLeaveGuard').useLeaveGuard
  >[0];
  const state = wrapper.vm as unknown as { displayName: string };
  try {
    expect(guard.isDirty()).toBe(false);
    state.displayName = '';
    expect(guard.isDirty()).toBe(true);
    await wrapper.setProps({ user: { ...user, display_name: 'Updated' } });
    expect(guard.isDirty()).toBe(false);
  } finally {
    wrapper.unmount();
  }
});

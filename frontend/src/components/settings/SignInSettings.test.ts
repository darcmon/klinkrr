import { afterEach, expect, it, vi } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import SignInSettings from './SignInSettings.vue';
import type { CurrentUser } from '../../types/user';

const registerGuard = vi.hoisted(() => vi.fn());
vi.mock('../../composables/useLeaveGuard', () => ({ useLeaveGuard: registerGuard }));
afterEach(() => vi.restoreAllMocks());

it('detects drafts in every password field, including spaces', () => {
  const user: CurrentUser = {
    id: 'user-1', email: 'a@example.com', display_name: 'Alex', avatar_url: null,
    organization: null, role: null, permissions: [], memberships: [],
    sign_in_methods: ['password'],
  };
  const wrapper = shallowMount(SignInSettings, { props: { user } });
  const guard = registerGuard.mock.lastCall![0] as Parameters<
    typeof import('../../composables/useLeaveGuard').useLeaveGuard
  >[0];
  const state = wrapper.vm as unknown as {
    current: string; next: string; confirm: string;
  };
  try {
    expect(guard.isDirty()).toBe(false);
    for (const field of ['current', 'next', 'confirm'] as const) {
      state[field] = ' ';
      expect(guard.isDirty()).toBe(true);
      state[field] = '';
    }
    state.next = 'unfinished';
    expect(guard.isDirty()).toBe(true);
    state.next = '';
    expect(guard.isDirty()).toBe(false);
  } finally {
    wrapper.unmount();
  }
});

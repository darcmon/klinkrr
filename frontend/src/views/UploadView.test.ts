import { afterEach, expect, it, vi } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import UploadView from './UploadView.vue';
import type { ContentDraft, Destination, Submission } from '../types/submit';

const registerGuard = vi.hoisted(() => vi.fn());
vi.mock('../composables/useLeaveGuard', () => ({ useLeaveGuard: registerGuard }));
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
}));
vi.mock('../composables/useCurrentUser', () => ({
  useCurrentUser: () => ({ user: { value: null }, load: async () => null }),
}));

afterEach(() => vi.restoreAllMocks());

it('detects unfinished submission drafts and ignores completed submissions', () => {
  const wrapper = shallowMount(UploadView);
  const guard = registerGuard.mock.lastCall![0] as Parameters<
    typeof import('../composables/useLeaveGuard').useLeaveGuard
  >[0];
  const state = wrapper.vm as unknown as {
    content: ContentDraft;
    destination: Destination;
    submission: Submission;
  };
  try {
    expect(guard.isDirty()).toBe(false);
    state.content.link = '   ';
    expect(guard.isDirty()).toBe(false);
    state.content.file = new File(['draft'], 'draft.txt');
    expect(guard.isDirty()).toBe(true);
    state.content.file = null;
    state.destination = { kind: 'new', draft: {} } as Destination;
    expect(guard.isDirty()).toBe(true);
    state.destination = { kind: 'none' };
    expect(guard.isDirty()).toBe(false);
    state.content.link = 'https://example.com';
    expect(guard.isDirty()).toBe(true);
    state.submission = { phase: 'done', result: {} } as Submission;
    expect(guard.isDirty()).toBe(false);
  } finally {
    wrapper.unmount();
  }
});

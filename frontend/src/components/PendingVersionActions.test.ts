import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import PendingVersionActions from './PendingVersionActions.vue';
import type { PendingVersion } from '../types/version';

function version(rights: {
  is_own: boolean;
  can_approve: boolean;
  can_reject: boolean;
}): PendingVersion {
  return {
    id: 'v1',
    version_number: 3,
    uploaded_by: 'someone@example.com',
    uploaded_by_id: 'u1',
    uploaded_at: '2026-09-24T00:00:00Z',
    location_slug: 'dock-a',
    location_display_name: 'Dock A',
    kind: 'link',
    link_url: 'https://example.com',
    link_mode: 'redirect',
    original_filename: null,
    content_type: null,
    file_size_bytes: null,
    ...rights,
  };
}

function mountFor(rights: Parameters<typeof version>[0]) {
  return mount(PendingVersionActions, {
    props: { version: version(rights), idPrefix: 'list' },
  });
}

const buttonLabels = (wrapper: ReturnType<typeof mountFor>) =>
  wrapper.findAll('button').map((button) => button.text());

describe('PendingVersionActions', () => {
  it("offers approve and reject on someone else's version", () => {
    const wrapper = mountFor({ is_own: false, can_approve: true, can_reject: true });

    expect(buttonLabels(wrapper)).toEqual(['Approve', 'Reject…']);
    expect(wrapper.find('.note').exists()).toBe(false);
  });

  it('discloses self-approval before the click', () => {
    const wrapper = mountFor({ is_own: true, can_approve: true, can_reject: true });

    expect(buttonLabels(wrapper)).toEqual(['Approve', 'Withdraw…']);
    const note = wrapper.find('.note');
    expect(note.text()).toContain('recorded in the audit log');
    expect(wrapper.find('button').attributes('aria-describedby')).toBe(
      note.attributes('id'),
    );
  });

  it('only offers withdraw when self-approval is not allowed', () => {
    const wrapper = mountFor({ is_own: true, can_approve: false, can_reject: true });

    expect(buttonLabels(wrapper)).toEqual(['Withdraw…']);
    expect(wrapper.find('.note').text()).toContain('Someone else needs to approve');
  });

  it("shows no actions on others' versions without review rights", () => {
    const wrapper = mountFor({ is_own: false, can_approve: false, can_reject: false });

    expect(wrapper.findAll('button')).toHaveLength(0);
    expect(wrapper.find('.note').text()).toBe('Waiting for an approver.');
  });

  it('emits approve and reject', async () => {
    const wrapper = mountFor({ is_own: false, can_approve: true, can_reject: true });
    const [approve, reject] = wrapper.findAll('button');

    await approve!.trigger('click');
    await reject!.trigger('click');

    expect(wrapper.emitted('approve')).toHaveLength(1);
    expect(wrapper.emitted('reject')).toHaveLength(1);
  });
});

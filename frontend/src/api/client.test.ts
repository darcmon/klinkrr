import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import api from './client';
import { useAuth } from '../composables/useAuth';

const auth = useAuth();

function reply(status: number, code: string) {
  return new Response(JSON.stringify({ detail: { code, message: code } }), { status });
}

beforeEach(() => {
  auth.setToken('test-token');
  auth.selectOrganization('org-a');
});
afterEach(() => vi.unstubAllGlobals());

it('drops a revoked selection but keeps it for an ordinary permission error', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply(403, 'permission_denied')));
  await expect(api.get('/admin/members')).rejects.toMatchObject({ code: 'permission_denied' });
  expect(auth.selectedOrganizationId.value).toBe('org-a');
  expect(auth.organizationAccessLost.value).toBe(false);

  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply(403, 'organization_access_denied')));
  await expect(api.get('/admin/me')).rejects.toMatchObject({ code: 'organization_access_denied' });
  expect(auth.selectedOrganizationId.value).toBeNull();
  expect(auth.organizationAccessLost.value).toBe(true);
});

it('recovers when a sole, automatically selected membership is revoked', async () => {
  const { useCurrentUser } = await import('../composables/useCurrentUser');
  const { user } = useCurrentUser();
  auth.selectOrganization(null);
  // A fresh Response per call: a body can only be read once.
  vi.stubGlobal('fetch', vi.fn(async () => reply(403, 'organization_membership_required')));

  // Before the user loads (a genuinely org-less account), it's not a revocation.
  await expect(api.get('/admin/locations')).rejects.toBeTruthy();
  expect(auth.organizationAccessLost.value).toBe(false);

  user.value = { organization: { id: 'org-a' } } as never;
  await expect(api.get('/admin/locations')).rejects.toBeTruthy();
  expect(auth.organizationAccessLost.value).toBe(true);
  expect(user.value).toBeNull();
});

it('ignores a revoked reply for an organization the user already left', async () => {
  let respond!: (response: Response) => void;
  vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve) => { respond = resolve; })));
  const request = api.get('/admin/me');
  auth.selectOrganization('org-b');
  respond(reply(403, 'organization_access_denied'));

  await expect(request).rejects.toMatchObject({ code: 'organization_access_denied' });
  expect(auth.selectedOrganizationId.value).toBe('org-b');
  expect(auth.organizationAccessLost.value).toBe(false);
});

export type Permission =
  | 'submit'
  | 'create_location'
  | 'approve_own'
  | 'review_any'
  | 'manage_locations'
  | 'manage_members';

export interface OrganizationSummary {
  id: string;
  name: string;
  allow_self_approval: boolean;
}

export type Role = 'uploader' | 'approver' | 'manager' | 'owner';

export type SignInMethod = 'password' | 'microsoft' | 'google';

// GET /admin/me. `organization` and `role` are null without a membership.
export interface CurrentUser {
  id: string;
  email: string;
  display_name: string;
  organization: OrganizationSummary | null;
  role: Role | null;
  permissions: Permission[];
  sign_in_methods: SignInMethod[];
}

export interface Member {
  user_id: string;
  email: string;
  display_name: string;
  role: Role;
  // Null until the person signs in for the first time.
  last_login_at: string | null;
  is_you: boolean;
}

// Lowest to highest; each role includes everything above it in this list.
export const ROLE_OPTIONS: { value: Role; label: string; description: string }[] = [
  {
    value: 'uploader',
    label: 'Uploader',
    description: 'Submits versions and creates locations.',
  },
  {
    value: 'approver',
    label: 'Approver',
    description: "Also approves and rejects other people's versions.",
  },
  {
    value: 'manager',
    label: 'Manager',
    description: 'Also edits any location and its approval setting.',
  },
  {
    value: 'owner',
    label: 'Owner',
    description: 'Also manages members and organization settings.',
  },
];

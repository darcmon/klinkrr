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

// GET /admin/me. `organization` and `role` are null without a membership.
export interface CurrentUser {
  id: string;
  email: string;
  display_name: string;
  organization: OrganizationSummary | null;
  role: string | null;
  permissions: Permission[];
}

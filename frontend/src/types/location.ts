export interface PublishedVersionSummary {
  id: string;
  version_number: number;
  kind: 'file' | 'link';
  // The filename, or the link's host.
  label: string;
}

// A location as the admin API returns it.
export interface LocationSummary {
  id: string;
  slug: string;
  display_name: string;
  description: string | null;
  reminder_email: string | null;
  approval_required: boolean;
  current_approved_version_id: string | null;
  created_at: string;
  updated_at: string;
  published_version: PublishedVersionSummary | null;
  last_submitted_at: string | null;
}

export type SlugUnavailableReason = 'invalid' | 'reserved' | 'retired' | 'taken';

// GET /admin/locations/slug-availability. Advisory only.
export interface SlugAvailability {
  available: boolean;
  reason: SlugUnavailableReason | null;
  // Only when the path is taken by a location in your organization.
  taken_by: string | null;
  message: string | null;
}

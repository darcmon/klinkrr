import type { LocationSummary, SlugUnavailableReason } from './location';

export type ContentTab = 'file' | 'link';

// Both values are kept when switching tabs; only `tab` is submitted.
export interface ContentDraft {
  tab: ContentTab;
  file: File | null;
  link: string;
}

export type Availability =
  | { state: 'empty' }
  | { state: 'checking' }
  | { state: 'available' }
  | {
      state: 'unavailable';
      reason: SlugUnavailableReason;
      takenBy: string | null;
      message: string;
    }
  // The check failed; submitting is still allowed and the server decides.
  | { state: 'unknown' };

export interface NewLocationDraft {
  // Sent as the location id, so retrying creation is safe.
  id: string;
  displayName: string;
  slug: string;
  // Until the user edits the path, it follows the display name.
  slugEdited: boolean;
  description: string;
  availability: Availability;
}

export type Destination =
  | { kind: 'none' }
  | { kind: 'existing'; location: LocationSummary; via: 'prefill' | 'picked' }
  | { kind: 'new'; draft: NewLocationDraft }
  // Created on the server by this page; the version isn't confirmed yet.
  | { kind: 'created'; location: LocationSummary };

export interface SubmitResult {
  id: string;
  versionNumber: number;
  status: 'pending' | 'approved';
  kind: ContentTab;
  // The filename or link.
  label: string;
  // Refetched after submitting, so the live version is current.
  location: LocationSummary;
  // What the action bar said would happen, to flag a policy change mid-submit.
  expectedStatus: 'pending' | 'approved';
}

export type Submission =
  | { phase: 'idle' }
  | { phase: 'creating' }
  | { phase: 'uploading'; fraction: number }
  | { phase: 'processing' }
  // The server said no; the draft is kept and retrying is fine.
  | { phase: 'failed'; message: string }
  // No response: it may or may not have happened. Retrying reuses the same ids.
  | { phase: 'unknown'; stage: 'create' | 'submit' }
  | { phase: 'done'; result: SubmitResult };

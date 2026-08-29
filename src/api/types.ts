/**
 * Response/request shapes mirroring `api/app/api/schemas.py` field for
 * field. Hand-written, not generated — see design.md's "API client"
 * decision for why. Keep in sync with schemas.py by hand; a field
 * added there needs the matching field added here.
 */

export type Citation = {
  source_document_id: string;
  source_url: string;
  verified_at: string | null;
};

export type Resource = {
  label: string;
  url: string;
  type: string;
};

export type RequirementKind = "document" | "step" | "prerequisite";

export type Requirement = {
  id: string;
  label: string;
  kind: RequirementKind;
  sequence: number;
  citation: Citation;
  resources: Resource[];
};

export type FeeBasis = "normal" | "urgent";

export type Fee = {
  basis: FeeBasis;
  base_amount: number;
  citation: Citation;
};

export type OfficeType = "head" | "regional" | "mission";

export type Office = {
  id: string;
  name: string;
  type: OfficeType;
};

export type ConflictNote = {
  note_text: string;
  primary_citation: Citation;
  secondary_citation: Citation | null;
};

export type OfficeResolution = {
  offices: Office[];
  conflict_note: ConflictNote | null;
  district_mapping_caveat: string | null;
};

export type AmendmentAlternative = {
  fee: Fee;
  requirements: Requirement[];
};

export type ScopeGate = {
  reason: string;
};

/**
 * `fee`/`offices`/`requirements` are only meaningful when `scope_gate`
 * is null — see specs/mobile-app-integration's "A scope-gated case
 * renders its refusal, never a partial plan" requirement. Always check
 * `scope_gate` first.
 */
export type CaseResolution = {
  requirements: Requirement[];
  fee: Fee | null;
  offices: OfficeResolution | null;
  amendment_alternative: AmendmentAlternative | null;
  scope_gate: ScopeGate | null;
};

export type QuestionAnswerType = "single" | "boolean" | "district";

export type Question = {
  id: string;
  prompt: string;
  answer_type: QuestionAnswerType;
  /** The rephrased text to render — never render `prompt` instead. */
  display_text: string;
  hint: string | null;
};

export type RagAnswer = {
  text: string;
  citations: Citation[];
  grounded: boolean;
};

export type ChatMessageRequest = {
  message: string;
  case_id?: string;
  device_ref?: string;
};

export type ChatMessageResponse = {
  case_id: string;
  answer: RagAnswer | null;
  next_question: Question | null;
  acknowledgement: string | null;
};

export type Service = {
  id: string;
  code: string;
  name: string;
  category: string;
};

export type ChatMessageRole = "user" | "assistant";

export type ChatMessageRecord = {
  id: string;
  role: ChatMessageRole;
  content: string;
  created_at: string;
  intent: string | null;
  cited_chunk_ids: string[] | null;
  tool_trace: Record<string, unknown>[] | null;
};

export type Transcript = {
  case_id: string | null;
  messages: ChatMessageRecord[];
};

export type Studio = {
  id: string;
  name: string;
  address: string;
  phone: string | null;
  citation: Citation;
};

export type StudioResolution = {
  district: string;
  studios: Studio[];
  receipt_note: string;
};

// --- Item 7: user accounts and saved plans ---

export type AuthToken = {
  access_token: string;
  token_type: string;
};

export type SavedPlan = {
  id: string;
  case_id: string;
  label: string;
  created_at: string;
};

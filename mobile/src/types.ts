// Types mirroring docs/protocol.md (single source of truth is the server).

export type Phase =
  | "lobby"
  | "preferences"
  | "matching"
  | "negotiation"
  | "voting"
  | "result";

export interface HardConstraints {
  max_runtime_min?: number | null;
  excluded_genres?: string[];
  excluded_keywords?: string[];
  max_content_rating?: string | null;
}

export interface SoftPreferences {
  preferred_genres?: string[];
  mood?: string | null;
  era?: string | null;
}

export interface Movie {
  id: string;
  title: string;
  year: number;
  runtime_min: number;
  genres: string[];
  tags: string[];
  content_rating: string;
  providers: string[];
  logline: string;
}

export interface CandidateReason {
  for_member: string | null;
  text: string;
}

export interface Candidate {
  movie: Movie;
  score: number;
  reasons: CandidateReason[];
}

export interface MemberView {
  id: string;
  name: string;
  submitted: boolean;
}

export interface ConcessionRequest {
  id: string;
  member_id: string;
  ask_text: string;
  relax_summary: string;
  deadline_ms?: number | null;
}

export interface TallyEntry {
  candidate_id: string;
  title: string;
  votes: number;
}

export interface RoomResult {
  no_pick: boolean;
  winner: Candidate | null;
  tally: TallyEntry[];
  explanation: string;
}

export interface RoomState {
  code: string;
  phase: Phase;
  members: MemberView[];
  candidates: Candidate[];
  voteProgress: { cast: number; total: number };
  voteDeadlineMs: number | null;
  negotiation: { targetName: string } | null;
  result: RoomResult | null;
}

export interface YouState {
  memberId?: string;
  role?: string;
  submitted?: boolean;
  voted?: boolean;
  pendingConcession?: ConcessionRequest | null;
}

export type ServerMessage =
  | { type: "joined"; role: string; memberId?: string; memberToken?: string; room: RoomState }
  | { type: "snapshot"; room: RoomState; you: YouState }
  | { type: "phase_changed"; phase: Phase }
  | { type: "candidates_ready"; candidates: Candidate[] }
  | { type: "concession_request"; concessionId: string; askText: string; relaxSummary: string; deadlineMs?: number }
  | { type: "concession_resolved"; concessionId: string; accepted: boolean }
  | { type: "concession_outcome"; memberName: string; accepted: boolean; relaxSummary?: string | null }
  | { type: "preferences_progress"; submitted: string; name: string }
  | { type: "preferences_ack"; forRequestId?: string }
  | { type: "vote_progress"; cast: number; total: number; deadlineMs?: number | null }
  | { type: "vote_ack"; forRequestId?: string }
  | { type: "result"; result: RoomResult }
  | { type: "error"; code: string; message: string; forRequestId?: string | null }
  | { type: "pong"; t: number };

export interface ClientSend {
  type: string;
  [key: string]: unknown;
}

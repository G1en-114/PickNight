import { useState } from "react";
import type { RoomState, YouState } from "../types";

const RUNTIME_OPTIONS: { label: string; value: number | null }[] = [
  { label: "≤ 90 min", value: 90 },
  { label: "≤ 2 h", value: 120 },
  { label: "≤ 2.5 h", value: 150 },
  { label: "Any length", value: null },
];

const RATING_OPTIONS: { label: string; value: string | null }[] = [
  { label: "G only", value: "G" },
  { label: "up to PG", value: "PG" },
  { label: "up to PG-13", value: "PG-13" },
  { label: "Anything", value: null },
];

const EXCLUDABLE = ["Horror", "Thriller", "Romance", "Documentary", "Drama"];
const PREFERABLE = ["Comedy", "Animation", "Action", "Sci-Fi", "Family", "Adventure", "Mystery", "Fantasy"];

export function Preferences({
  room,
  you,
  onSubmit,
}: {
  room: RoomState;
  you: YouState;
  onSubmit: (hard: Record<string, unknown>, soft: Record<string, unknown>, freeText: string) => void;
}) {
  const [maxRuntime, setMaxRuntime] = useState<number | null>(120);
  const [maxRating, setMaxRating] = useState<string | null>("PG-13");
  const [excluded, setExcluded] = useState<string[]>([]);
  const [preferred, setPreferred] = useState<string[]>([]);
  const [freeText, setFreeText] = useState("");
  const [sent, setSent] = useState(you.submitted ?? false);

  const toggle = (list: string[], setList: (v: string[]) => void, item: string) => {
    setList(list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);
  };

  const submit = () => {
    setSent(true);
    onSubmit(
      {
        max_runtime_min: maxRuntime,
        max_content_rating: maxRating,
        excluded_genres: excluded,
      },
      { preferred_genres: preferred },
      freeText.trim()
    );
  };

  if (sent) {
    return (
      <div>
        <div className="big-emoji">✅</div>
        <h1>Got your taste</h1>
        <div className="card">
          <h2>Who's in ({room.members.length})</h2>
          <div className="member-list">
            {room.members.map((m) => (
              <div key={m.id} className="member-row">
                <span>{m.name}</span>
                {m.submitted && <span className="done">ready ✓</span>}
              </div>
            ))}
          </div>
        </div>
        <div className="center-note">Waiting for the others…</div>
      </div>
    );
  }

  return (
    <div>
      <h1>Tonight, for you</h1>
      <p className="sub">
        Bottom lines are respected no matter what. Favorites just help us rank.
      </p>

      <div className="card">
        <label className="field-label">How much time do you have? (hard)</label>
        <div className="chips">
          {RUNTIME_OPTIONS.map((o) => (
            <button
              key={o.label}
              className={`chip ${maxRuntime === o.value ? "on" : ""}`}
              onClick={() => setMaxRuntime(o.value)}
            >
              {o.label}
            </button>
          ))}
        </div>

        <label className="field-label">Content rating up to (hard)</label>
        <div className="chips">
          {RATING_OPTIONS.map((o) => (
            <button
              key={o.label}
              className={`chip ${maxRating === o.value ? "on" : ""}`}
              onClick={() => setMaxRating(o.value)}
            >
              {o.label}
            </button>
          ))}
        </div>

        <label className="field-label">Hard no for you (veto)</label>
        <div className="chips">
          {EXCLUDABLE.map((g) => (
            <button
              key={g}
              className={`chip danger ${excluded.includes(g) ? "on" : ""}`}
              onClick={() => toggle(excluded, setExcluded, g)}
            >
              no {g}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <label className="field-label">What are you in the mood for? (soft)</label>
        <div className="chips">
          {PREFERABLE.map((g) => (
            <button
              key={g}
              className={`chip ${preferred.includes(g) ? "on" : ""}`}
              onClick={() => toggle(preferred, setPreferred, g)}
            >
              {g}
            </button>
          ))}
        </div>

        <label className="field-label">Anything else? (say it your way)</label>
        <textarea
          placeholder="e.g. nothing scary, ideally something funny and short"
          value={freeText}
          maxLength={500}
          onChange={(e) => setFreeText(e.target.value)}
        />
      </div>

      <button className="btn" onClick={submit}>
        Submit my taste
      </button>
    </div>
  );
}

export const BIN = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 6h18" />
    <path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
    <path d="M18.5 6l-.8 13.1A2 2 0 0 1 15.7 21H8.3a2 2 0 0 1-2-1.9L5.5 6" />
    <path d="M10 10.5v6M14 10.5v6" />
  </svg>
);

export const CHECK = (
  <svg className="check" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

export const FOLDER = (
  <svg className="opt-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 6a2 2 0 0 1 2-2h3.6l2 2.5H19a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  </svg>
);

export const SLIDERS = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
    <path d="M4 7h9M19 7h1M4 17h1M11 17h9" />
    <circle cx="15" cy="7" r="2" />
    <circle cx="9" cy="17" r="2" />
  </svg>
);

export function capitalize(s) {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

// Tier ids print capitalized ("medium" -> "Medium"); local-file ids print
// as-is without the "file:" prefix.
export function modelLabel(id) {
  if (!id) return id;
  return id.startsWith('file:') ? id.slice(5) : capitalize(id);
}

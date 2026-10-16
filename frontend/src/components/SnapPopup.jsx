// Windows 11-style snap flyout for our frameless window. The native flyout
// only exists on real caption buttons, so hovering the custom maximize button
// shows this popup instead; picking a zone moves the window via main.cjs.

const ZONES = [
  { id: 'left', label: 'Snap left', cells: [0, 2] },
  { id: 'right', label: 'Snap right', cells: [1, 3] },
  { id: 'top-left', label: 'Snap top left', cells: [0] },
  { id: 'top-right', label: 'Snap top right', cells: [1] },
  { id: 'bottom-left', label: 'Snap bottom left', cells: [2] },
  { id: 'bottom-right', label: 'Snap bottom right', cells: [3] },
];

export default function SnapPopup({ open, onSelect }) {
  if (!open) return null;
  return (
    <div className="snap-popup" role="menu" aria-label="Snap window">
      {ZONES.map(({ id, label, cells }) => (
        <button key={id} type="button" className="snap-option" title={label} aria-label={label} onClick={() => onSelect(id)}>
          <span className="snap-grid" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <span key={i} className={cells.includes(i) ? 'on' : ''} />
            ))}
          </span>
        </button>
      ))}
    </div>
  );
}

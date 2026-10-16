import { CHECK, capitalize } from './icons.jsx';

export default function ModelMenu({ open, tiers, current, onSelect }) {
  if (!open) return null;
  return (
    <div className="model-menu menu" role="menu" aria-label="Model tier">
      {tiers.map(({ name, description }) => (
        <button
          key={name}
          type="button"
          className="menu-option"
          role="menuitemradio"
          aria-checked={String(name === current)}
          onClick={() => onSelect(name)}
        >
          <span className="opt-text">
            <span className="opt-name">{capitalize(name)}</span>
            <span className="opt-desc">{description}</span>
          </span>
          {CHECK}
        </button>
      ))}
    </div>
  );
}

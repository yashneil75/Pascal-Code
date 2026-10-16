import { useEffect, useRef } from 'react';

export default function ConfirmDialog({ ask, onResolve }) {
  const ref = useRef(null);
  const never = useRef(null);

  useEffect(() => {
    if (ask) {
      if (never.current) never.current.checked = false;
      ref.current?.showModal();
    } else {
      ref.current?.close();
    }
  }, [ask]);

  return (
    <dialog
      ref={ref}
      className="ask"
      onClose={() => onResolve(ref.current?.returnValue === 'delete', never.current?.checked)}
    >
      <form method="dialog">
        <h2>{ask?.title}</h2>
        <p>{ask?.body}</p>
        <label className="ask-opt">
          <input ref={never} type="checkbox" />
          Never show me this again
        </label>
        <div className="ask-actions">
          <button type="submit" value="cancel" autoFocus>
            Cancel
          </button>
          <button type="submit" className="ask-delete" value="delete">
            Delete
          </button>
        </div>
      </form>
    </dialog>
  );
}

import { useEffect, useRef } from 'react';

// Auto-grow a textarea up to its max-height.
export function useAutosize(ref, value) {
  useEffect(() => {
    const el = typeof ref === 'object' ? ref.current : null;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [ref, value]);
}

export function useScrollToBottom(ref, deps) {
  const prev = useRef(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    prev.current = deps?.length ?? 0;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

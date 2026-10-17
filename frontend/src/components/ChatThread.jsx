import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function Message({ role, content, streaming }) {
  const copyBtn = useRef(null);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      const btn = copyBtn.current;
      if (!btn) return;
      btn.dataset.copied = '';
      setTimeout(() => delete btn.dataset.copied, 1500);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  return (
    <div className={`msg ${role}${streaming ? ' streaming' : ''}`}>
      {role === 'assistant' ? (
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      ) : (
        <p>{content}</p>
      )}
      {role === 'assistant' && !streaming && content && (
        <div className="actions">
          <button ref={copyBtn} type="button" data-copy aria-label="Copy" onClick={copy}>
            <svg className="icon-copy" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="9" width="11" height="11" rx="2" />
              <path d="M5 15V6a2 2 0 0 1 2-2h9" />
            </svg>
            <svg className="icon-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 6 9 17l-5-5" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}

export default function ChatThread({ messages, streamingText }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streamingText]);

  const visible = messages.filter(
    ({ role, content }) => (role === 'user' || role === 'assistant') && content,
  );

  return (
    <main ref={ref} className="thread" aria-live="polite">
      {visible.map((m, i) => (
        <Message key={i} role={m.role} content={m.content} />
      ))}
      {streamingText !== null && <Message role="assistant" content={streamingText} streaming />}
    </main>
  );
}

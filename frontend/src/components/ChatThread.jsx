import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function splitThinking(content) {
  const closeIdx = content.indexOf('</think>');
  if (closeIdx !== -1) {
    // Models may emit only the closing tag; treat everything before it as
    // reasoning (dropping a leading <think> if present).
    const thinking = content.slice(0, closeIdx).replace(/<think>/g, '').trim();
    const answer = content.slice(closeIdx + '</think>'.length).trim();
    return { thinking, answer, done: true };
  }
  const openIdx = content.indexOf('<think>');
  if (openIdx !== -1) {
    const thinking = content.slice(openIdx + '<think>'.length).trim();
    const answer = content.slice(0, openIdx).trim();
    return { thinking, answer, done: false };
  }
  return { thinking: '', answer: content.trim(), done: false };
}

function Spinner() {
  return <span className="spinner" aria-label="Thinking" />;
}

function Message({ role, content, streaming, tokPerSec }) {
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

  if (role === 'user') {
    return (
      <div className={`msg ${role}`}>
        <p>{content}</p>
      </div>
    );
  }

  const { thinking, answer, done } = splitThinking(content);
  const showSpinner = streaming;

  return (
    <div className={`msg ${role}${streaming ? ' streaming' : ''}`}>
      {thinking && (
        <details className="thinking" open>
          <summary>
            Thinking
            {showSpinner && !done && <Spinner />}
          </summary>
          <div className="thinking-box">{thinking}</div>
        </details>
      )}
      {answer && <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>}
      {showSpinner && (
        <div className="stream-spinner">
          <Spinner />
          <span className="tokps">{(tokPerSec || 0).toFixed(1)} tok/s</span>
        </div>
      )}
      {!streaming && content && (
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

export default function ChatThread({ messages, streamingText, tokPerSec }) {
  const ref = useRef(null);
  const stickToBottom = useRef(true);

  const isNearBottom = () => {
    const el = ref.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  useEffect(() => {
    const el = ref.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages, streamingText]);

  const onScroll = () => {
    stickToBottom.current = isNearBottom();
  };

  // A new message (sent or loaded) should re-engage auto-follow.
  useEffect(() => {
    stickToBottom.current = true;
  }, [messages.length]);

  const visible = messages.filter(
    ({ role, content }) => (role === 'user' || role === 'assistant') && content,
  );

  return (
    <main ref={ref} className="thread" aria-live="polite" onScroll={onScroll}>
      {visible.map((m, i) => (
        <Message key={i} role={m.role} content={m.content} tokPerSec={tokPerSec} />
      ))}
      {streamingText !== null && <Message role="assistant" content={streamingText} streaming tokPerSec={tokPerSec} />}
    </main>
  );
}
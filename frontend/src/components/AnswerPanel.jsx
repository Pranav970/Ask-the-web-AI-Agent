/**
 * AnswerPanel.jsx — Renders the streamed markdown answer with
 * a blinking cursor while streaming, and a copy button when done.
 */
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import clsx from 'clsx';

export default function AnswerPanel({ text, isStreaming, query }) {
  const [copied, setCopied] = useState(false);

  if (!text && !isStreaming) return null;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-dark-border bg-dark-surface overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3
                      border-b border-dark-border">
        <div className="flex items-center gap-2 text-sm font-medium text-dark-muted">
          <AnswerIcon />
          <span>Answer</span>
          {isStreaming && (
            <span className="text-xs text-brand-500 font-normal ml-1">
              • generating…
            </span>
          )}
        </div>
        {!isStreaming && text && (
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 text-xs text-dark-muted
                       hover:text-dark-text transition-colors px-2 py-1
                       rounded-lg hover:bg-white/5"
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        )}
      </div>

      {/* Content */}
      <div className="px-5 py-5">
        <div className="prose-dark">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Open links in new tab
              a: ({ node, ...props }) => (
                <a {...props} target="_blank" rel="noopener noreferrer" />
              ),
              // Style inline code
              code: ({ node, inline, ...props }) =>
                inline ? (
                  <code {...props} />
                ) : (
                  <pre>
                    <code {...props} />
                  </pre>
                ),
            }}
          >
            {text}
          </ReactMarkdown>
          {/* Blinking cursor during streaming */}
          {isStreaming && (
            <span className="inline-block w-0.5 h-4 bg-brand-500
                             animate-pulse ml-0.5 align-middle" />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────────────────

function AnswerIcon() {
  return (
    <svg width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2}
         viewBox="0 0 24 24" className="text-brand-500">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg width={12} height={12} fill="none" stroke="currentColor" strokeWidth={2}
         viewBox="0 0 24 24">
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"
            strokeLinecap="round" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width={12} height={12} fill="none" stroke="currentColor" strokeWidth={2}
         viewBox="0 0 24 24" className="text-green-400">
      <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

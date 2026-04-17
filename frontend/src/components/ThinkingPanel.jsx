/**
 * ThinkingPanel.jsx — Shows the agent's live thinking steps & tool calls.
 * Appears during streaming, collapses when done.
 */
import { useState } from 'react';
import clsx from 'clsx';

export default function ThinkingPanel({ steps, isActive }) {
  const [expanded, setExpanded] = useState(true);

  if (!steps.length) return null;

  return (
    <div
      className={clsx(
        'rounded-xl border transition-all duration-300',
        isActive
          ? 'border-brand-500/40 bg-brand-500/5'
          : 'border-dark-border bg-dark-surface'
      )}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3
                   text-sm font-medium text-dark-muted hover:text-dark-text
                   transition-colors"
      >
        <span className="flex items-center gap-2">
          {isActive ? (
            <>
              <ThinkingDots />
              <span className="text-brand-500">Agent is thinking…</span>
            </>
          ) : (
            <>
              <CheckIcon />
              <span>Research complete — {steps.length} step{steps.length !== 1 ? 's' : ''}</span>
            </>
          )}
        </span>
        <ChevronIcon expanded={expanded} />
      </button>

      {/* Steps list */}
      {expanded && (
        <div className="px-4 pb-3 space-y-1.5 animate-fade-in">
          {steps.map((step, i) => (
            <div
              key={i}
              className="flex items-start gap-2.5 text-sm text-dark-muted
                         animate-slide-up"
            >
              <span className="mt-0.5 shrink-0 text-brand-500">
                {getStepIcon(step)}
              </span>
              <span
                className="leading-relaxed"
                dangerouslySetInnerHTML={{ __html: formatStep(step) }}
              />
            </div>
          ))}
          {isActive && (
            <div className="flex items-center gap-2 pt-1 text-xs text-dark-muted">
              <ThinkingDots small />
              <span>Processing…</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────

function formatStep(text) {
  // Bold text between **
  return text.replace(/\*\*(.+?)\*\*/g, '<strong class="text-dark-text">$1</strong>');
}

function getStepIcon(step) {
  if (step.includes('Search') || step.includes('🔍')) return <SearchIcon />;
  if (step.includes('Read') || step.includes('📄'))   return <DocIcon />;
  if (step.includes('Strategy') || step.includes('📋')) return <PlanIcon />;
  return <DotIcon />;
}

// ── Sub-components ────────────────────────────────────────────────────────

function ThinkingDots({ small }) {
  const size = small ? 'w-1 h-1' : 'w-1.5 h-1.5';
  return (
    <span className="thinking-dots">
      <span className={size} />
      <span className={size} />
      <span className={size} />
    </span>
  );
}

function ChevronIcon({ expanded }) {
  return (
    <svg
      width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2}
      viewBox="0 0 24 24"
      className={clsx('transition-transform duration-200', expanded ? 'rotate-180' : '')}
    >
      <path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2}
         viewBox="0 0 24 24" className="text-green-400">
      <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width={13} height={13} fill="none" stroke="currentColor" strokeWidth={2}
         viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" strokeLinecap="round" />
    </svg>
  );
}

function DocIcon() {
  return (
    <svg width={13} height={13} fill="none" stroke="currentColor" strokeWidth={2}
         viewBox="0 0 24 24">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"
            strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" strokeLinecap="round" />
    </svg>
  );
}

function PlanIcon() {
  return (
    <svg width={13} height={13} fill="none" stroke="currentColor" strokeWidth={2}
         viewBox="0 0 24 24">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M9 21V9" strokeLinecap="round" />
    </svg>
  );
}

function DotIcon() {
  return <span className="inline-block w-1.5 h-1.5 rounded-full bg-brand-500 mt-1" />;
}

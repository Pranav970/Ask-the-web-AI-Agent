/**
 * SearchBar.jsx — Animated search input.
 * FIX: Suggestions are shown on focus (not just empty input).
 * FIX: Keyboard shortcut (/) focuses the input.
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import clsx from 'clsx';

const SUGGESTIONS = [
  'What is the current state of quantum computing?',
  'Latest AI breakthroughs in 2025',
  'How does Claude differ from GPT-4o?',
  'Best programming languages to learn in 2025',
  'What is happening with AI regulation globally?',
  'Explain the transformer architecture simply',
];

export default function SearchBar({ onSubmit, isLoading, onStop }) {
  const [value,           setValue]           = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef(null);

  // Auto-focus on mount
  useEffect(() => { inputRef.current?.focus(); }, []);

  // Press "/" anywhere to focus (Perplexity-style)
  useEffect(() => {
    const handler = (e) => {
      if (e.key === '/' && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const handleSubmit = (e) => {
    e?.preventDefault();
    const q = value.trim();
    if (!q || isLoading) return;
    setShowSuggestions(false);
    onSubmit(q);
  };

  const handleSuggestion = useCallback((s) => {
    setValue(s);
    setShowSuggestions(false);
    onSubmit(s);
  }, [onSubmit]);

  return (
    <div className="relative w-full">
      <form onSubmit={handleSubmit} autoComplete="off">

        {/* Search icon */}
        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-dark-muted pointer-events-none z-10">
          <MagIcon />
        </span>

        <input
          ref={inputRef}
          id="search-input"
          type="text"
          value={value}
          onChange={e => setValue(e.target.value)}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 160)}
          placeholder='Ask anything… (press "/" to focus)'
          className={clsx(
            'w-full pl-11 pr-32 py-4 rounded-2xl text-base',
            'bg-dark-surface border border-dark-border',
            'text-dark-text placeholder-dark-muted',
            'focus:outline-none focus:ring-2 focus:ring-brand-500/60 focus:border-brand-500/50',
            'transition-all duration-200',
          )}
        />

        {/* Right button */}
        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {/* Clear button */}
          {value && !isLoading && (
            <button
              type="button"
              onClick={() => { setValue(''); inputRef.current?.focus(); }}
              className="p-1.5 rounded-lg text-dark-muted hover:text-dark-text
                         hover:bg-white/5 transition-colors"
              title="Clear"
            >
              <XIcon />
            </button>
          )}

          {/* Stop / Submit */}
          {isLoading ? (
            <button
              type="button"
              onClick={onStop}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium
                         bg-red-500/20 text-red-400 border border-red-500/30
                         hover:bg-red-500/30 transition-colors"
            >
              <StopIcon />
              <span>Stop</span>
            </button>
          ) : (
            <button
              type="submit"
              disabled={!value.trim()}
              className={clsx(
                'flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium',
                'transition-all duration-150',
                value.trim()
                  ? 'bg-brand-600 text-white hover:bg-brand-700 shadow-lg shadow-brand-600/20 cursor-pointer'
                  : 'bg-dark-border text-dark-muted cursor-not-allowed opacity-50'
              )}
            >
              <MagIcon size={13} />
              <span>Search</span>
            </button>
          )}
        </div>
      </form>

      {/* Suggestions */}
      {showSuggestions && !value && (
        <div className="absolute top-full left-0 right-0 mt-2 rounded-2xl
                        bg-dark-surface border border-dark-border
                        shadow-2xl shadow-black/60 z-50 overflow-hidden
                        animate-fade-in">
          <p className="px-4 pt-3 pb-2 text-xs text-dark-muted font-semibold uppercase tracking-wider">
            Try asking
          </p>
          {SUGGESTIONS.map(s => (
            <button
              key={s}
              onMouseDown={() => handleSuggestion(s)}
              className="w-full text-left px-4 py-2.5 text-sm text-dark-text
                         hover:bg-white/5 transition-colors flex items-center gap-3
                         border-t border-dark-border/30 first:border-0"
            >
              <span className="text-brand-500 shrink-0 mt-0.5">✦</span>
              <span className="leading-snug">{s}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Icons ──────────────────────────────────────────────────────────────────────

function MagIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" strokeLinecap="round" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width={13} height={13} fill="currentColor" viewBox="0 0 24 24">
      <rect x="4" y="4" width="16" height="16" rx="2" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
      <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" />
    </svg>
  );
}

/**
 * App.jsx — Root component.
 *
 * FIX: Uses derived values from useSearch (isLoading, hasResults).
 * FIX: Error state shows retry button.
 * FIX: Sticky search bar uses correct Tailwind classes.
 */
import { useState } from 'react';
import { useSearch } from './hooks/useSearch';
import SearchBar       from './components/SearchBar';
import ThinkingPanel   from './components/ThinkingPanel';
import AnswerPanel     from './components/AnswerPanel';
import SourcesPanel    from './components/SourcesPanel';
import EvaluationBadge from './components/EvaluationBadge';
import HistoryDrawer   from './components/HistoryDrawer';

const FEATURE_CHIPS = [
  '🔍 Real-time search',
  '📚 Source citations',
  '🤔 Multi-step reasoning',
  '✅ Fact checking',
  '💾 Session memory',
  '⚡ Streaming answers',
];

export default function App() {
  const [drawerOpen, setDrawerOpen] = useState(false);

  const {
    status, query, streamedText, thinkingSteps,
    sources, evaluation, errorMsg, history,
    isLoading, hasResults,
    submit, stop, clearHistory,
  } = useSearch();

  const showHero = status === 'idle' && !hasResults;

  return (
    <div className="min-h-screen bg-dark-bg flex flex-col">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 bg-dark-bg/90 backdrop-blur-md border-b border-dark-border">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">

          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <span className="text-2xl select-none">🔍</span>
            <div>
              <h1 className="text-sm font-bold gradient-text leading-none">Ask the Web</h1>
              <p className="text-xs text-dark-muted hidden sm:block mt-0.5">
                AI Research Agent · Claude
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setDrawerOpen(true)}
              className="relative flex items-center gap-1.5 px-3 py-1.5 rounded-xl
                         text-sm text-dark-muted border border-dark-border
                         hover:text-dark-text hover:border-brand-500/50
                         transition-all duration-150"
            >
              <ClockIcon />
              <span className="hidden sm:inline">History</span>
              {history.length > 0 && (
                <span className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full
                                 bg-brand-600 text-white text-[10px] font-bold
                                 flex items-center justify-center leading-none">
                  {history.length > 9 ? '9+' : history.length}
                </span>
              )}
            </button>

            <a
              href="https://github.com/yourusername/ask-the-web-agent"
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded-xl text-dark-muted border border-dark-border
                         hover:text-dark-text hover:border-dark-muted
                         transition-all duration-150"
              title="GitHub"
            >
              <GithubIcon />
            </a>
          </div>
        </div>
      </header>

      {/* ── Main ───────────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col max-w-3xl mx-auto w-full px-4 pb-4">

        {/* Hero (idle) */}
        {showHero && (
          <div className="flex-1 flex flex-col items-center justify-center
                          text-center py-16 animate-fade-in">
            <div className="text-6xl mb-6 select-none">🌐</div>
            <h2 className="text-3xl sm:text-4xl font-bold gradient-text mb-3">
              Ask Anything
            </h2>
            <p className="text-dark-muted text-lg max-w-md leading-relaxed mb-8">
              Real-time web research powered by Claude AI.<br />
              Get cited, accurate answers in seconds.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {FEATURE_CHIPS.map(chip => (
                <span key={chip}
                      className="px-3 py-1.5 rounded-full text-sm
                                 bg-dark-surface border border-dark-border text-dark-muted">
                  {chip}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Results */}
        {!showHero && (
          <div className="flex-1 py-6 space-y-4 animate-slide-up">

            {/* Query heading */}
            {query && (
              <h2 className="text-xl font-semibold text-dark-text leading-snug">
                {query}
              </h2>
            )}

            {/* Agent thinking steps */}
            {thinkingSteps.length > 0 && (
              <ThinkingPanel steps={thinkingSteps} isActive={isLoading} />
            )}

            {/* Loading skeleton */}
            {isLoading && !streamedText && (
              <div className="rounded-xl border border-dark-border bg-dark-surface p-5 space-y-3">
                {[80, 95, 60].map((w, i) => (
                  <div key={i}
                       className="h-3 rounded-full bg-dark-border animate-pulse"
                       style={{ width: `${w}%` }} />
                ))}
              </div>
            )}

            {/* Answer */}
            {streamedText && (
              <AnswerPanel text={streamedText} isStreaming={isLoading} />
            )}

            {/* Sources */}
            {sources.length > 0 && (
              <SourcesPanel sources={sources} />
            )}

            {/* Evaluation scores */}
            {evaluation && !isLoading && (
              <EvaluationBadge evaluation={evaluation} />
            )}

            {/* Error */}
            {status === 'error' && errorMsg && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4">
                <p className="text-sm font-medium text-red-400 mb-1">Something went wrong</p>
                <p className="text-sm text-red-300/80">{errorMsg}</p>
                <button
                  onClick={() => submit(query)}
                  className="mt-3 text-xs text-red-400 underline underline-offset-2
                             hover:text-red-300 transition-colors"
                >
                  Try again →
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Search bar (sticky at bottom when results visible) ─────── */}
        <div className={`py-4 ${!showHero
          ? 'sticky bottom-0 bg-dark-bg/95 backdrop-blur-md border-t border-dark-border/50 -mx-4 px-4'
          : ''}`}>
          <SearchBar
            onSubmit={submit}
            isLoading={isLoading}
            onStop={stop}
          />
          <p className="text-center text-xs text-dark-muted mt-2 opacity-70">
            AI can make mistakes · Always verify important information from sources
          </p>
        </div>
      </main>

      {/* ── History drawer ─────────────────────────────────────────────── */}
      <HistoryDrawer
        history={history}
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onSelect={(q) => { submit(q); setDrawerOpen(false); }}
        onClear={clearHistory}
      />
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function ClockIcon() {
  return (
    <svg width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GithubIcon() {
  return (
    <svg width={16} height={16} fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482
               0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462
               -.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832
               .092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683
               -.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836a9.59 9.59
               0 012.504.337c1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699
               1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852
               0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12
               c0-5.523-4.477-10-10-10z" />
    </svg>
  );
}

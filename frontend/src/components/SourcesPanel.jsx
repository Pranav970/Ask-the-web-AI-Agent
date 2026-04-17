/**
 * SourcesPanel.jsx — Displays cited sources as clickable cards.
 * Each card shows domain favicon, title, and URL.
 */
import clsx from 'clsx';

export default function SourcesPanel({ sources }) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <SourcesIcon />
        <h3 className="text-sm font-semibold text-dark-muted uppercase tracking-wide">
          Sources
          <span className="ml-2 px-1.5 py-0.5 text-xs bg-dark-border
                           text-dark-muted rounded-full">
            {sources.length}
          </span>
        </h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {sources.map((source, i) => (
          <SourceCard key={source.url + i} source={source} index={i + 1} />
        ))}
      </div>
    </div>
  );
}

function SourceCard({ source, index }) {
  const domain = getDomain(source.url);
  const faviconUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=16`;

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className={clsx(
        'source-chip flex items-start gap-3 p-3 rounded-xl',
        'border border-dark-border bg-dark-surface',
        'hover:shadow-md transition-all duration-200',
        'group'
      )}
    >
      {/* Index badge */}
      <span
        className="shrink-0 w-5 h-5 rounded-full bg-brand-500/20
                   text-brand-500 text-xs font-bold flex items-center
                   justify-center mt-0.5"
      >
        {index}
      </span>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <p className="text-sm text-dark-text font-medium leading-snug
                      group-hover:text-brand-500 transition-colors truncate">
          {source.title || domain}
        </p>
        <div className="flex items-center gap-1.5 mt-1">
          <img
            src={faviconUrl}
            alt=""
            width={12}
            height={12}
            className="opacity-60"
            onError={(e) => { e.target.style.display = 'none'; }}
          />
          <span className="text-xs text-dark-muted truncate">{domain}</span>
          <ExternalIcon />
        </div>
      </div>
    </a>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────

function getDomain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

// ── Icons ─────────────────────────────────────────────────────────────────

function SourcesIcon() {
  return (
    <svg width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2}
         viewBox="0 0 24 24" className="text-dark-muted">
      <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"
            strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ExternalIcon() {
  return (
    <svg width={10} height={10} fill="none" stroke="currentColor" strokeWidth={2}
         viewBox="0 0 24 24" className="text-dark-muted shrink-0">
      <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"
            strokeLinecap="round" />
      <path d="M15 3h6v6M10 14L21 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

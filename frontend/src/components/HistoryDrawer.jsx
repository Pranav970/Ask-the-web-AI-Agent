/**
 * HistoryDrawer.jsx — Slide-in sidebar listing past queries in this session.
 */
import clsx from 'clsx';

export default function HistoryDrawer({ history, isOpen, onClose, onSelect, onClear }) {
  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 animate-fade-in"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <aside
        className={clsx(
          'fixed top-0 left-0 h-full w-80 z-50',
          'bg-dark-surface border-r border-dark-border',
          'flex flex-col transition-transform duration-300 ease-in-out',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4
                        border-b border-dark-border">
          <h2 className="font-semibold text-dark-text text-sm">Search History</h2>
          <div className="flex items-center gap-2">
            {history.length > 0 && (
              <button
                onClick={onClear}
                className="text-xs text-dark-muted hover:text-red-400
                           transition-colors px-2 py-1 rounded hover:bg-red-400/10"
              >
                Clear all
              </button>
            )}
            <button
              onClick={onClose}
              className="text-dark-muted hover:text-dark-text transition-colors p-1"
            >
              <CloseIcon />
            </button>
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto py-2">
          {history.length === 0 ? (
            <div className="flex flex-col items-center justify-center
                            h-full text-center px-6 text-dark-muted">
              <HistoryIcon />
              <p className="mt-3 text-sm">No searches yet</p>
              <p className="text-xs mt-1">Your queries will appear here</p>
            </div>
          ) : (
            [...history].reverse().map((item) => (
              <button
                key={item.id}
                onClick={() => { onSelect(item.query); onClose(); }}
                className="w-full text-left px-5 py-3 text-sm text-dark-text
                           hover:bg-white/5 transition-colors
                           border-b border-dark-border/50 last:border-0"
              >
                <p className="truncate font-medium">{item.query}</p>
                <p className="text-xs text-dark-muted mt-0.5 truncate">
                  {item.sources?.length
                    ? `${item.sources.length} source${item.sources.length !== 1 ? 's' : ''}`
                    : 'No sources'}
                </p>
              </button>
            ))
          )}
        </div>
      </aside>
    </>
  );
}

function CloseIcon() {
  return (
    <svg width={16} height={16} fill="none" stroke="currentColor" strokeWidth={2}
         viewBox="0 0 24 24">
      <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" />
    </svg>
  );
}

function HistoryIcon() {
  return (
    <svg width={32} height={32} fill="none" stroke="currentColor" strokeWidth={1.5}
         viewBox="0 0 24 24" className="opacity-30">
      <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * hooks/useSearch.js — Central state machine for the search experience.
 *
 * States: idle → loading → streaming → done | error
 *
 * FIX: Properly tracks full answer text for evaluation scoring.
 * FIX: abortRef cleanup on unmount via returned cleanup.
 * FIX: Session ID persisted via sessionStorage (survives hot-reload).
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { streamSearch, clearSession } from '../utils/api';

const SESSION_KEY = 'ask_web_session_id';

function getOrCreateSessionId() {
  let id = sessionStorage.getItem(SESSION_KEY);
  if (!id) {
    id = uuidv4();
    sessionStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export function useSearch() {
  const [status,        setStatus]        = useState('idle');
  const [query,         setQuery]         = useState('');
  const [streamedText,  setStreamedText]  = useState('');
  const [thinkingSteps, setThinkingSteps] = useState([]);
  const [sources,       setSources]       = useState([]);
  const [evaluation,    setEvaluation]    = useState(null);
  const [errorMsg,      setErrorMsg]      = useState('');
  const [history,       setHistory]       = useState([]);

  const abortRef    = useRef(null);
  const sessionIdRef = useRef(getOrCreateSessionId());
  // Track full answer for evaluation (streamedText ref avoids stale closure)
  const fullTextRef = useRef('');
  const sourcesRef  = useRef([]);

  // Cleanup on unmount
  useEffect(() => () => { abortRef.current?.(); }, []);

  // ── Submit ──────────────────────────────────────────────────────────────

  const submit = useCallback((userQuery) => {
    const q = userQuery?.trim();
    if (!q) return;

    // Abort any in-flight request
    abortRef.current?.();
    abortRef.current = null;

    // Reset state
    setQuery(q);
    setStatus('loading');
    setStreamedText('');
    setThinkingSteps([]);
    setSources([]);
    setEvaluation(null);
    setErrorMsg('');
    fullTextRef.current  = '';
    sourcesRef.current   = [];

    abortRef.current = streamSearch(
      q,
      sessionIdRef.current,
      (chunk) => {
        switch (chunk.type) {

          case 'thinking':
            setThinkingSteps(prev => [...prev, chunk.content]);
            setStatus('streaming');
            break;

          case 'text':
            fullTextRef.current += chunk.content;
            setStreamedText(fullTextRef.current);
            setStatus('streaming');
            break;

          case 'source': {
            const src = chunk.content;
            if (!sourcesRef.current.some(s => s.url === src.url)) {
              sourcesRef.current = [...sourcesRef.current, src];
              setSources([...sourcesRef.current]);
            }
            break;
          }

          case 'evaluation':
            setEvaluation(chunk.content);
            break;

          case 'done': {
            // Merge any sources from the done payload
            const doneSources = chunk.content?.sources ?? [];
            const merged = _dedupe([...sourcesRef.current, ...doneSources]);
            sourcesRef.current = merged;
            setSources(merged);
            setStatus('done');
            // Push to history
            setHistory(prev => [
              ...prev,
              {
                id:      uuidv4(),
                query:   q,
                answer:  fullTextRef.current,
                sources: merged,
              },
            ]);
            break;
          }

          case 'stream_end':
            setStatus(prev => prev === 'streaming' ? 'done' : prev);
            break;

          case 'error':
            setErrorMsg(chunk.content ?? 'Unknown error');
            setStatus('error');
            break;

          default:
            break;
        }
      }
    );
  }, []);

  // ── Stop ────────────────────────────────────────────────────────────────

  const stop = useCallback(() => {
    abortRef.current?.();
    abortRef.current = null;
    setStatus(prev => prev === 'idle' ? 'idle' : 'done');
  }, []);

  // ── Clear history ────────────────────────────────────────────────────────

  const clearHistory = useCallback(async () => {
    abortRef.current?.();
    abortRef.current = null;
    try {
      await clearSession(sessionIdRef.current);
    } catch {}
    // Generate a new session ID
    const newId = uuidv4();
    sessionIdRef.current = newId;
    sessionStorage.setItem(SESSION_KEY, newId);
    // Reset all UI state
    setHistory([]);
    setStatus('idle');
    setQuery('');
    setStreamedText('');
    setThinkingSteps([]);
    setSources([]);
    setEvaluation(null);
    setErrorMsg('');
  }, []);

  return {
    // State
    status,
    query,
    streamedText,
    thinkingSteps,
    sources,
    evaluation,
    errorMsg,
    history,
    // Derived
    isLoading:    status === 'loading' || status === 'streaming',
    isDone:       status === 'done',
    hasResults:   streamedText.length > 0,
    sessionId:    sessionIdRef.current,
    // Actions
    submit,
    stop,
    clearHistory,
  };
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function _dedupe(sources) {
  const seen = new Set();
  return sources.filter(s => {
    if (!s?.url || seen.has(s.url)) return false;
    seen.add(s.url);
    return true;
  });
}

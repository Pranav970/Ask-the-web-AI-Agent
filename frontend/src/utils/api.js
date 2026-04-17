/**
 * utils/api.js — API client for the Ask-the-Web backend.
 *
 * FIX: VITE_API_URL falls back to empty string (same-origin) so the
 *      Vite proxy handles requests in development without extra config.
 * FIX: Cleaner SSE parser that handles multi-line buffering correctly.
 */

const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

// ── Full search (wait for complete response) ──────────────────────────────

/**
 * @param {string} query
 * @param {string} sessionId
 * @param {string|null} route — 'simple' | 'deep' | 'factual' | null
 * @returns {Promise<object>}
 */
export async function search(query, sessionId, route = null) {
  const resp = await fetch(`${BASE_URL}/api/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId, route }),
  });

  if (!resp.ok) {
    let detail = resp.statusText;
    try { detail = (await resp.json()).detail; } catch {}
    throw new Error(detail || `Search failed (${resp.status})`);
  }

  return resp.json();
}

// ── Streaming search ──────────────────────────────────────────────────────

/**
 * Stream search results via SSE.
 *
 * Calls onChunk(chunk) for every parsed event:
 *   { type: 'thinking'|'text'|'source'|'evaluation'|'done'|'error', content: any }
 *
 * Returns an abort function: () => void
 *
 * @param {string} query
 * @param {string} sessionId
 * @param {function} onChunk
 * @returns {function} abort
 */
export function streamSearch(query, sessionId, onChunk) {
  const controller = new AbortController();
  let aborted = false;

  (async () => {
    try {
      const resp = await fetch(`${BASE_URL}/api/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, session_id: sessionId }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        onChunk({ type: 'error', content: `HTTP ${resp.status}: ${resp.statusText}` });
        return;
      }

      if (!resp.body) {
        onChunk({ type: 'error', content: 'No response body (streaming not supported?)' });
        return;
      }

      const reader  = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer    = '';

      while (!aborted) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are delimited by double newlines
        const parts = buffer.split('\n\n');
        // Keep the last (potentially incomplete) part in the buffer
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          // Each part may have multiple "data: " lines (multi-line events)
          const dataLines = part
            .split('\n')
            .filter(l => l.startsWith('data: '))
            .map(l => l.slice(6).trim());

          for (const data of dataLines) {
            if (data === '[DONE]') {
              onChunk({ type: 'stream_end' });
              return;
            }
            try {
              onChunk(JSON.parse(data));
            } catch {
              // malformed JSON line — skip silently
            }
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError' && !aborted) {
        onChunk({ type: 'error', content: err.message });
      }
    }
  })();

  return () => {
    aborted = true;
    controller.abort();
  };
}

// ── Health check ──────────────────────────────────────────────────────────

export async function healthCheck() {
  const resp = await fetch(`${BASE_URL}/api/health`);
  if (!resp.ok) throw new Error(`Health check failed: ${resp.status}`);
  return resp.json();
}

// ── Session management ────────────────────────────────────────────────────

export async function clearSession(sessionId) {
  const resp = await fetch(`${BASE_URL}/api/session/${sessionId}`, {
    method: 'DELETE',
  });
  return resp.json();
}

export async function getSessionHistory(sessionId) {
  const resp = await fetch(`${BASE_URL}/api/session/${sessionId}/history`);
  if (!resp.ok) return { history: [] };
  return resp.json();
}

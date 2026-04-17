/**
 * EvaluationBadge.jsx — Compact quality score widget shown below each answer.
 */
import clsx from 'clsx';

export default function EvaluationBadge({ evaluation }) {
  if (!evaluation) return null;

  const overall   = evaluation.overall ?? 0;
  const relevance = evaluation.relevance ?? 0;
  const sources   = evaluation.source_count ?? 0;
  const risk      = evaluation.hallucination_risk ?? 'unknown';
  const latency   = evaluation.latency_ms ?? 0;

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs animate-fade-in">
      {/* Overall score */}
      <ScorePill
        label="Quality"
        value={`${Math.round(overall * 100)}%`}
        color={scoreColor(overall)}
      />

      {/* Relevance */}
      <ScorePill
        label="Relevance"
        value={`${Math.round(relevance * 100)}%`}
        color={scoreColor(relevance)}
      />

      {/* Sources */}
      <ScorePill
        label="Sources"
        value={sources}
        color="text-blue-400 bg-blue-400/10 border-blue-400/20"
      />

      {/* Hallucination risk */}
      <ScorePill
        label="Hallucination risk"
        value={risk}
        color={riskColor(risk)}
      />

      {/* Latency */}
      <ScorePill
        label="Latency"
        value={`${(latency / 1000).toFixed(1)}s`}
        color="text-dark-muted bg-dark-border/30 border-dark-border"
      />
    </div>
  );
}

function ScorePill({ label, value, color }) {
  return (
    <span
      className={clsx(
        'flex items-center gap-1.5 px-2.5 py-1 rounded-full border',
        color
      )}
    >
      <span className="opacity-60">{label}:</span>
      <span className="font-semibold">{value}</span>
    </span>
  );
}

function scoreColor(score) {
  if (score >= 0.75) return 'text-green-400 bg-green-400/10 border-green-400/20';
  if (score >= 0.5)  return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20';
  return 'text-red-400 bg-red-400/10 border-red-400/20';
}

function riskColor(risk) {
  if (risk === 'low')    return 'text-green-400 bg-green-400/10 border-green-400/20';
  if (risk === 'medium') return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20';
  if (risk === 'high')   return 'text-red-400 bg-red-400/10 border-red-400/20';
  return 'text-dark-muted bg-dark-border/30 border-dark-border';
}

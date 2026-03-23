import React from "react";

export default function StatsBar({ summary }) {
  if (!summary || summary.total_nodes === 0) return null;

  const nodeTypes = Object.entries(summary.node_types || {});
  const relTypes = Object.entries(summary.relationship_types || {});

  return (
    <div className="stats-bar">
      <div className="stat-item main">
        <span className="stat-val">{summary.total_nodes?.toLocaleString()}</span>
        <span className="stat-label">nodes</span>
      </div>
      <div className="stat-divider" />
      <div className="stat-item main">
        <span className="stat-val">{summary.total_edges?.toLocaleString()}</span>
        <span className="stat-label">edges</span>
      </div>
      <div className="stat-divider" />
      {nodeTypes.slice(0, 5).map(([type, count]) => (
        <div className="stat-item" key={type}>
          <span className="stat-val">{count}</span>
          <span className="stat-label">{type}</span>
        </div>
      ))}
    </div>
  );
}

import React, { useState, useEffect, useCallback } from "react";
import GraphViewer from "./components/GraphViewer";
import ChatPanel from "./components/ChatPanel";
import UploadPanel from "./components/UploadPanel";
import StatsBar from "./components/StatsBar";
import "./App.css";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

export default function App() {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [summary, setSummary] = useState(null);
  const [highlightedNodes, setHighlightedNodes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [activeTab, setActiveTab] = useState("graph"); // "graph" | "chat"
  const [selectedNode, setSelectedNode] = useState(null);
  const [error, setError] = useState(null);

  const fetchGraph = useCallback(async () => {
    try {
      setLoading(true);
      const [graphRes, summaryRes] = await Promise.all([
        fetch(`${API}/graph?limit=300`),
        fetch(`${API}/graph/summary`),
      ]);
      if (graphRes.ok) {
        const data = await graphRes.json();
        setGraphData(data);
        setDataLoaded(data.nodes.length > 0);
      }
      if (summaryRes.ok) {
        setSummary(await summaryRes.json());
      }
    } catch (e) {
      setError("Cannot connect to backend. Make sure the server is running.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const handleUploadSuccess = () => {
    fetchGraph();
  };

  const handleNodeExpand = async (nodeId) => {
    try {
      const res = await fetch(`${API}/graph/node/${encodeURIComponent(nodeId)}`);
      if (res.ok) {
        const newData = await res.json();
        // Merge new nodes/edges into existing graph
        setGraphData((prev) => {
          const existingNodeIds = new Set(prev.nodes.map((n) => n.data.id));
          const existingEdgeIds = new Set(prev.edges.map((e) => e.data.id));
          const newNodes = newData.nodes.filter((n) => !existingNodeIds.has(n.data.id));
          const newEdges = newData.edges.filter((e) => !existingEdgeIds.has(e.data.id));
          return {
            nodes: [...prev.nodes, ...newNodes],
            edges: [...prev.edges, ...newEdges],
          };
        });
      }
    } catch (e) {
      console.error("Node expand error:", e);
    }
  };

  const handleHighlight = (nodeIds) => {
    setHighlightedNodes(nodeIds);
    if (nodeIds.length > 0) setActiveTab("graph");
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <div className="logo">
            <span className="logo-icon">⬡</span>
            <span className="logo-text">GraphIQ</span>
          </div>
          <span className="logo-tagline">Business Data Intelligence</span>
        </div>

        <nav className="header-nav">
          <button
            className={`nav-btn ${activeTab === "graph" ? "active" : ""}`}
            onClick={() => setActiveTab("graph")}
          >
            <span className="nav-icon">◈</span> Graph
          </button>
          <button
            className={`nav-btn ${activeTab === "chat" ? "active" : ""}`}
            onClick={() => setActiveTab("chat")}
          >
            <span className="nav-icon">◎</span> Query
          </button>
        </nav>

        <div className="header-right">
          <UploadPanel apiUrl={API} onSuccess={handleUploadSuccess} />
        </div>
      </header>

      {error && (
        <div className="error-banner">
          ⚠ {error}
        </div>
      )}

      {summary && <StatsBar summary={summary} />}

      <main className="app-main">
        {!dataLoaded && !loading && (
          <div className="empty-state">
            <div className="empty-icon">⬡</div>
            <h2>No Dataset Loaded</h2>
            <p>Upload your Excel dataset using the button in the top-right to begin exploring.</p>
          </div>
        )}

        {loading && (
          <div className="loading-overlay">
            <div className="spinner" />
            <p>Building graph...</p>
          </div>
        )}

        <div className={`panel-container ${activeTab === "graph" ? "show-graph" : "show-chat"}`}>
          <div className="graph-panel">
            <GraphViewer
              graphData={graphData}
              highlightedNodes={highlightedNodes}
              onNodeClick={setSelectedNode}
              onNodeExpand={handleNodeExpand}
            />
            {selectedNode && (
              <NodeDetail node={selectedNode} onClose={() => setSelectedNode(null)} onExpand={handleNodeExpand} />
            )}
          </div>

          <div className="chat-panel-wrap">
            <ChatPanel apiUrl={API} onHighlight={handleHighlight} />
          </div>
        </div>
      </main>
    </div>
  );
}

function NodeDetail({ node, onClose, onExpand }) {
  const data = node.data || {};
  const skip = ["id", "label", "type", "degree"];
  const meta = Object.entries(data).filter(([k]) => !skip.includes(k));

  return (
    <div className="node-detail">
      <div className="node-detail-header">
        <span className={`node-badge type-${data.type?.toLowerCase()}`}>{data.type}</span>
        <h3>{data.label}</h3>
        <button className="close-btn" onClick={onClose}>✕</button>
      </div>
      <div className="node-detail-body">
        {meta.map(([k, v]) => (
          <div className="meta-row" key={k}>
            <span className="meta-key">{k.replace(/_/g, " ")}</span>
            <span className="meta-val">{String(v || "—")}</span>
          </div>
        ))}
        <div className="meta-row">
          <span className="meta-key">connections</span>
          <span className="meta-val">{data.degree}</span>
        </div>
      </div>
      <button className="expand-btn" onClick={() => onExpand(data.id)}>
        Expand Neighbors →
      </button>
    </div>
  );
}

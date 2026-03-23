import React, { useEffect, useRef, useCallback } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import cytoscape from "cytoscape";
import cola from "cytoscape-cola";

cytoscape.use(cola);

// Color palette per node type
const TYPE_COLORS = {
  Customer: "#4f9cf9",
  SalesOrder: "#f97316",
  OrderItem: "#fb923c",
  Product: "#22c55e",
  Delivery: "#a78bfa",
  Billing: "#f43f5e",
  Payment: "#34d399",
  Journal: "#fbbf24",
  Address: "#94a3b8",
  Unknown: "#64748b",
};

const TYPE_SHAPES = {
  Customer: "ellipse",
  SalesOrder: "rectangle",
  OrderItem: "diamond",
  Product: "hexagon",
  Delivery: "round-rectangle",
  Billing: "pentagon",
  Payment: "star",
  Journal: "triangle",
};

const stylesheet = [
  {
    selector: "node",
    style: {
      "background-color": (ele) => TYPE_COLORS[ele.data("type")] || TYPE_COLORS.Unknown,
      "border-color": (ele) => TYPE_COLORS[ele.data("type")] || TYPE_COLORS.Unknown,
      "border-width": 2,
      "border-opacity": 0.7,
      shape: (ele) => TYPE_SHAPES[ele.data("type")] || "ellipse",
      label: "data(label)",
      "font-size": "10px",
      "font-family": "'JetBrains Mono', monospace",
      color: "#e2e8f0",
      "text-halign": "center",
      "text-valign": "bottom",
      "text-margin-y": 6,
      "text-max-width": "80px",
      "text-wrap": "ellipsis",
      width: (ele) => Math.max(24, Math.min(60, 20 + ele.data("degree") * 2)),
      height: (ele) => Math.max(24, Math.min(60, 20 + ele.data("degree") * 2)),
      "background-opacity": 0.9,
      "overlay-padding": 4,
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 4,
      "border-color": "#ffffff",
      "border-opacity": 1,
      "background-opacity": 1,
    },
  },
  {
    selector: "node.highlighted",
    style: {
      "border-color": "#facc15",
      "border-width": 5,
      "border-opacity": 1,
      "background-opacity": 1,
      "z-index": 999,
    },
  },
  {
    selector: "node.dimmed",
    style: {
      opacity: 0.2,
    },
  },
  {
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": "#334155",
      "target-arrow-color": "#475569",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      label: "data(relationship)",
      "font-size": "8px",
      color: "#64748b",
      "font-family": "'JetBrains Mono', monospace",
      "text-rotation": "autorotate",
      "edge-text-rotation": "autorotate",
      opacity: 0.7,
    },
  },
  {
    selector: "edge.highlighted",
    style: {
      "line-color": "#facc15",
      "target-arrow-color": "#facc15",
      opacity: 1,
      width: 3,
      "z-index": 999,
    },
  },
];

const layout = {
  name: "cola",
  animate: true,
  maxSimulationTime: 3000,
  nodeSpacing: 40,
  edgeLength: 120,
  randomize: false,
  fit: true,
  padding: 40,
};

export default function GraphViewer({ graphData, highlightedNodes, onNodeClick, onNodeExpand }) {
  const cyRef = useRef(null);

  // Apply highlighting when highlightedNodes changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().removeClass("highlighted dimmed");

    if (highlightedNodes && highlightedNodes.length > 0) {
      const ids = new Set(highlightedNodes);
      cy.nodes().forEach((node) => {
        if (ids.has(node.id())) {
          node.addClass("highlighted");
        } else {
          node.addClass("dimmed");
        }
      });
      cy.edges().forEach((edge) => {
        const src = edge.source().id();
        const tgt = edge.target().id();
        if (ids.has(src) || ids.has(tgt)) {
          edge.addClass("highlighted");
          edge.source().removeClass("dimmed");
          edge.target().removeClass("dimmed");
        }
      });

      // Pan to highlighted nodes
      const highlighted = cy.nodes(".highlighted");
      if (highlighted.length > 0) {
        cy.animate({ fit: { eles: highlighted, padding: 80 }, duration: 600, easing: "ease-in-out" });
      }
    }
  }, [highlightedNodes]);

  const handleCyInit = useCallback((cy) => {
    cyRef.current = cy;

    cy.on("tap", "node", (evt) => {
      onNodeClick && onNodeClick(evt.target);
    });

    cy.on("dblclick taphold", "node", (evt) => {
      onNodeExpand && onNodeExpand(evt.target.id());
    });

    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass("highlighted dimmed");
        onNodeClick && onNodeClick(null);
      }
    });
  }, [onNodeClick, onNodeExpand]);

  // Re-run layout when data changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || graphData.nodes.length === 0) return;
    const l = cy.layout({ ...layout, name: graphData.nodes.length > 150 ? "cose" : "cola" });
    l.run();
  }, [graphData]);

  const elements = [
    ...graphData.nodes,
    ...graphData.edges,
  ];

  return (
    <div className="graph-container">
      <div className="graph-legend">
        {Object.entries(TYPE_COLORS).filter(([k]) => k !== "Unknown").map(([type, color]) => (
          <div className="legend-item" key={type}>
            <span className="legend-dot" style={{ background: color }} />
            <span>{type}</span>
          </div>
        ))}
      </div>

      <div className="graph-controls">
        <button onClick={() => cyRef.current?.fit()} title="Fit view">⊡</button>
        <button onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.2)} title="Zoom in">+</button>
        <button onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.8)} title="Zoom out">−</button>
        <button onClick={() => {
          const cy = cyRef.current;
          if (cy) {
            const l = cy.layout({ ...layout });
            l.run();
          }
        }} title="Re-layout">↺</button>
      </div>

      {elements.length > 0 ? (
        <CytoscapeComponent
          elements={elements}
          stylesheet={stylesheet}
          layout={layout}
          style={{ width: "100%", height: "100%" }}
          cy={handleCyInit}
          wheelSensitivity={0.3}
        />
      ) : (
        <div className="graph-empty">
          <p>Upload a dataset to visualize the graph</p>
        </div>
      )}
    </div>
  );
}

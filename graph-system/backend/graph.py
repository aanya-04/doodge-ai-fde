"""
graph.py - Graph construction using NetworkX
Builds a knowledge graph from the relational SQLite data.
"""

import networkx as nx
import json
from database import get_connection, get_tables, execute_query

# Singleton graph instance
_graph: nx.DiGraph = None


def build_graph() -> nx.DiGraph:
    """
    Build a directed graph from the database.
    Nodes = entity records, Edges = relationships.
    """
    global _graph
    G = nx.DiGraph()
    tables = get_tables()
    print(f"Building graph from tables: {tables}")

    # ── NODE BUILDERS ──────────────────────────────────────────────────

    def add_nodes_from_table(table, id_col, label, props_cols, limit=500):
        rows, err = execute_query(f"SELECT * FROM {table} LIMIT {limit}")
        if err or not rows:
            return
        for row in rows:
            node_id = f"{label}:{row.get(id_col, '')}"
            props = {k: row.get(k) for k in props_cols if k in row}
            props["label"] = label
            props["table"] = table
            props["display"] = str(row.get(id_col, ""))
            G.add_node(node_id, **props)

    # Known schema tables
    known_tables = {
        "customers": ("customer_id", "Customer", ["customer_name", "city", "country"]),
        "products": ("material_id", "Product", ["material_desc", "material_group"]),
        "sales_orders": ("sales_order_id", "SalesOrder", ["order_date", "net_value", "currency", "status"]),
        "sales_order_items": ("item_id", "OrderItem", ["quantity", "net_price"]),
        "deliveries": ("delivery_id", "Delivery", ["delivery_date", "plant", "status"]),
        "billing_documents": ("billing_id", "Billing", ["billing_date", "net_value", "billing_type"]),
        "payments": ("payment_id", "Payment", ["payment_date", "amount", "currency"]),
        "journal_entries": ("journal_id", "Journal", ["posting_date", "amount", "account"]),
        "addresses": ("address_id", "Address", ["city", "country", "postal_code"]),
    }

    for table in tables:
        if table in known_tables:
            id_col, label, props = known_tables[table]
            add_nodes_from_table(table, id_col, label, props)
        else:
            # Dynamic table: detect a likely ID column
            rows, err = execute_query(f"SELECT * FROM {table} LIMIT 200")
            if err or not rows:
                continue
            cols = list(rows[0].keys())
            id_col = next((c for c in cols if "id" in c.lower()), cols[0])
            label = table.replace("_", " ").title().replace(" ", "")
            for row in rows:
                node_id = f"{label}:{row.get(id_col, '')}"
                G.add_node(node_id, label=label, table=table,
                           display=str(row.get(id_col, "")), **{k: row[k] for k in cols[:6]})

    # ── EDGE BUILDERS ──────────────────────────────────────────────────

    def add_edges(from_table, from_id, from_label, to_table, to_id, to_label, rel):
        rows, err = execute_query(f"SELECT {from_id}, {to_id} FROM {from_table} WHERE {to_id} IS NOT NULL LIMIT 2000")
        if err or not rows:
            return
        for row in rows:
            src = f"{from_label}:{row[from_id]}"
            tgt = f"{to_label}:{row[to_id]}"
            if G.has_node(src) and G.has_node(tgt):
                G.add_edge(src, tgt, relationship=rel)

    edge_defs = [
        ("sales_orders", "sales_order_id", "SalesOrder", "customers", "customer_id", "Customer", "PLACED_BY"),
        ("sales_order_items", "sales_order_id", "SalesOrder", "sales_orders", "sales_order_id", "SalesOrder", "BELONGS_TO"),
        ("sales_order_items", "item_id", "OrderItem", "products", "material_id", "Product", "IS_MATERIAL"),
        ("deliveries", "delivery_id", "Delivery", "sales_orders", "sales_order_id", "SalesOrder", "FULFILLS"),
        ("deliveries", "delivery_id", "Delivery", "customers", "customer_id", "Customer", "DELIVERED_TO"),
        ("billing_documents", "billing_id", "Billing", "sales_orders", "sales_order_id", "SalesOrder", "BILLED_FOR"),
        ("billing_documents", "billing_id", "Billing", "deliveries", "delivery_id", "Delivery", "BASED_ON_DELIVERY"),
        ("payments", "payment_id", "Payment", "billing_documents", "billing_id", "Billing", "PAYS"),
        ("journal_entries", "journal_id", "Journal", "billing_documents", "billing_id", "Billing", "RECORDS"),
    ]

    for ed in edge_defs:
        try:
            add_edges(*ed)
        except Exception as e:
            print(f"  ⚠️ Edge {ed[6]}: {e}")

    _graph = G
    print(f"✅ Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def get_graph() -> nx.DiGraph:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def get_graph_summary():
    G = get_graph()
    labels = {}
    for n, d in G.nodes(data=True):
        lbl = d.get("label", "Unknown")
        labels[lbl] = labels.get(lbl, 0) + 1

    rels = {}
    for u, v, d in G.edges(data=True):
        rel = d.get("relationship", "RELATED")
        rels[rel] = rels.get(rel, 0) + 1

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "node_types": labels,
        "relationship_types": rels,
    }


def get_graph_for_vis(limit_nodes=300):
    """
    Return graph data formatted for Cytoscape.js (frontend visualization).
    Limits nodes to avoid overwhelming the UI.
    """
    G = get_graph()

    # Priority: well-connected nodes first
    nodes_sorted = sorted(G.nodes(data=True), key=lambda x: G.degree(x[0]), reverse=True)
    nodes_subset = [n for n, d in nodes_sorted[:limit_nodes]]
    subgraph = G.subgraph(nodes_subset)

    cy_nodes = []
    for node, data in subgraph.nodes(data=True):
        cy_nodes.append({
            "data": {
                "id": node,
                "label": data.get("display", node),
                "type": data.get("label", "Unknown"),
                "degree": G.degree(node),
                **{k: str(v)[:100] for k, v in data.items() if k not in ("label", "display", "table") and v is not None}
            }
        })

    cy_edges = []
    for u, v, data in subgraph.edges(data=True):
        cy_edges.append({
            "data": {
                "id": f"{u}→{v}",
                "source": u,
                "target": v,
                "relationship": data.get("relationship", "RELATED"),
            }
        })

    return {"nodes": cy_nodes, "edges": cy_edges}


def get_node_neighbors(node_id: str):
    """Expand a node — return its neighbors and connecting edges."""
    G = get_graph()
    if node_id not in G:
        return {"nodes": [], "edges": []}

    neighbors = list(G.predecessors(node_id)) + list(G.successors(node_id))
    all_nodes = set([node_id] + neighbors)

    cy_nodes = []
    for n in all_nodes:
        d = G.nodes[n]
        cy_nodes.append({
            "data": {
                "id": n,
                "label": d.get("display", n),
                "type": d.get("label", "Unknown"),
                "degree": G.degree(n),
                **{k: str(v)[:100] for k, v in d.items() if k not in ("label", "display", "table") and v is not None}
            }
        })

    cy_edges = []
    for n in neighbors:
        if G.has_edge(node_id, n):
            d = G.edges[node_id, n]
            cy_edges.append({"data": {"id": f"{node_id}→{n}", "source": node_id, "target": n, "relationship": d.get("relationship", "")}})
        if G.has_edge(n, node_id):
            d = G.edges[n, node_id]
            cy_edges.append({"data": {"id": f"{n}→{node_id}", "source": n, "target": node_id, "relationship": d.get("relationship", "")}})

    return {"nodes": cy_nodes, "edges": cy_edges}

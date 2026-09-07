"""
Sugiyama DAG layout for Zuora Workflow CSS position computation.

Algorithm:
1. Layer assignment — longest-path from source nodes (topological ordering).
2. Crossing minimization — barycenter heuristic, LAYERED_SWEEPS passes.
3. Coordinate assignment — left = BASE_LEFT + layer * H_SPACING,
                           top  = BASE_TOP  + order_in_layer * V_SPACING

Returns: {task_id_int: {"left": "Npx", "top": "Mpx"}}
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Optional

# -----------------------------------------------------------------------
# Layout constants (pixel units)
# -----------------------------------------------------------------------
BASE_LEFT = 300  # offset from canvas left edge
BASE_TOP = 30  # offset from canvas top edge
H_SPACING = 450  # horizontal distance between task layers
V_SPACING = 200  # vertical distance between tasks in the same layer
LAYERED_SWEEPS = 4  # crossing minimisation passes (left-right, right-left alternating)


def compute_layout_from_steps(
    steps: list[dict],
    edges: Optional[list[dict]] = None,
) -> dict[int, dict[str, str]]:
    """
    Compute CSS positions for all tasks using Sugiyama layered DAG layout.

    Args:
        steps: list of {"step_id": str, "task_type": str}
        edges: list of {"from_step": str, "to_step": str, "edge_type": str}
               Pass [] or None for a disconnected (linear fallback) layout.

    Returns:
        {task_sequence_number_int: {"left": "Npx", "top": "Mpx"}}
    """
    if not steps:
        return {}

    if edges is None:
        edges = []

    node_ids = [s["step_id"] for s in steps]

    # -----------------------------------------------------------------
    # Step 1 — Build adjacency structures
    # -----------------------------------------------------------------
    successors: dict[str, list[str]] = defaultdict(list)
    predecessors: dict[str, list[str]] = defaultdict(list)

    valid_ids = set(node_ids)
    for edge in edges:
        src = str(edge.get("from_step", ""))
        tgt = str(edge.get("to_step", ""))
        if src in valid_ids and tgt in valid_ids and src != tgt:
            successors[src].append(tgt)
            predecessors[tgt].append(src)

    # -----------------------------------------------------------------
    # Step 2 — Layer assignment: longest-path from source
    # -----------------------------------------------------------------
    layers: dict[str, int] = {}

    # Topological sort (Kahn's algorithm)
    in_degree = {nid: len(predecessors[nid]) for nid in node_ids}
    queue: deque[str] = deque(nid for nid in node_ids if in_degree[nid] == 0)

    topo_order: list[str] = []
    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for succ in successors[node]:
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    # Handle cycles: any node not yet in topo_order gets appended at end
    remaining = [nid for nid in node_ids if nid not in set(topo_order)]
    topo_order.extend(remaining)

    # Assign layers via longest-path
    for nid in topo_order:
        if not predecessors[nid]:
            layers[nid] = 0
        else:
            layers[nid] = max(
                (layers.get(pred, 0) + 1 for pred in predecessors[nid]),
                default=0,
            )

    # -----------------------------------------------------------------
    # Step 3 — Build layer → nodes mapping
    # -----------------------------------------------------------------
    layer_nodes: dict[int, list[str]] = defaultdict(list)
    for nid in node_ids:
        layer_nodes[layers.get(nid, 0)].append(nid)

    # Preserve original insertion order within each layer as initial ordering
    for layer_idx in layer_nodes:
        layer_nodes[layer_idx] = list(
            dict.fromkeys(layer_nodes[layer_idx])  # deduplicate, preserve order
        )

    # -----------------------------------------------------------------
    # Step 4 — Crossing minimisation: barycenter heuristic
    # -----------------------------------------------------------------
    max_layer = max(layer_nodes.keys()) if layer_nodes else 0

    for _sweep in range(LAYERED_SWEEPS):
        if _sweep % 2 == 0:
            # Left-to-right sweep: reorder based on predecessors' positions
            for layer_idx in range(1, max_layer + 1):
                nodes = layer_nodes[layer_idx]
                bary = _compute_barycenters(nodes, predecessors, layers, layer_nodes)
                layer_nodes[layer_idx] = sorted(nodes, key=lambda n: bary.get(n, 0))
        else:
            # Right-to-left sweep: reorder based on successors' positions
            for layer_idx in range(max_layer - 1, -1, -1):
                nodes = layer_nodes[layer_idx]
                bary = _compute_barycenters(nodes, successors, layers, layer_nodes)
                layer_nodes[layer_idx] = sorted(nodes, key=lambda n: bary.get(n, 0))

    # -----------------------------------------------------------------
    # Step 5 — Coordinate assignment
    # -----------------------------------------------------------------
    positions: dict[int, dict[str, str]] = {}
    for layer_idx, nodes in layer_nodes.items():
        left_px = BASE_LEFT + layer_idx * H_SPACING
        for order, nid in enumerate(nodes):
            top_px = BASE_TOP + order * V_SPACING
            try:
                int_id = int(nid)
            except (ValueError, TypeError):
                int_id = hash(nid)
            positions[int_id] = {"left": f"{left_px}px", "top": f"{top_px}px"}

    return positions


# -----------------------------------------------------------------------
# Private helpers
# -----------------------------------------------------------------------


def _compute_barycenters(
    nodes: list[str],
    neighbor_map: dict[str, list[str]],
    layers: dict[str, int],
    layer_nodes: dict[int, list[str]],
) -> dict[str, float]:
    """
    Compute barycenter (average position) of each node's neighbours
    in the adjacent layer, for use in crossing minimisation.
    """
    bary: dict[str, float] = {}
    for node in nodes:
        neighbors = neighbor_map.get(node, [])
        if not neighbors:
            # No neighbours — use existing order to avoid disruption
            node_layer = layers.get(node, 0)
            current_order = layer_nodes.get(node_layer, [])
            try:
                bary[node] = float(current_order.index(node))
            except ValueError:
                bary[node] = 0.0
            continue

        positions_in_neighbor_layer: list[float] = []
        for nb in neighbors:
            nb_layer = layers.get(nb, 0)
            nb_order_list = layer_nodes.get(nb_layer, [])
            try:
                positions_in_neighbor_layer.append(float(nb_order_list.index(nb)))
            except ValueError:
                pass

        if positions_in_neighbor_layer:
            bary[node] = sum(positions_in_neighbor_layer) / len(positions_in_neighbor_layer)
        else:
            bary[node] = 0.0

    return bary

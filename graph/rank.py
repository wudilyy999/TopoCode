"""PageRank over the file reference graph (Aider RepoMap ranking idea).

Nodes are repo-relative file paths; edges come from resolved imports.
Coverage protection and bounded change-history weighting live in the caller.
"""

DAMPING = 0.85
ITERATIONS = 20


def pagerank(nodes, edges, iterations=ITERATIONS, damping=DAMPING):
    """nodes: iterable of ids. edges: iterable of (src, dst). Returns {id: score}."""
    nodes = list(nodes)
    N = len(nodes)
    if N == 0:
        return {}

    out_degree = {n: 0 for n in nodes}
    in_neighbors = {n: [] for n in nodes}
    for src, dst in edges:
        if src in out_degree and dst in in_neighbors and src != dst:
            out_degree[src] += 1
            in_neighbors[dst].append(src)

    base = (1.0 - damping) / N
    scores = {n: 1.0 / N for n in nodes}

    for _ in range(iterations):
        dangling_sum = sum(scores[n] for n in nodes if out_degree[n] == 0)
        dangling_contrib = damping * dangling_sum / N
        nxt = {}
        for n in nodes:
            rank = base + dangling_contrib
            for src in in_neighbors[n]:
                rank += damping * (scores[src] / out_degree[src])
            nxt[n] = rank
        scores = nxt

    return scores

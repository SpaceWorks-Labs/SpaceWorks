"""Deterministic minimum-cost maximum-flow assignment; no ORM or private identities.

Unit project→judge capacity prevents duplicate reviews. Increasing judge-slot costs
minimize squared workload, while augmenting paths avoid greedy false shortages.
"""

from collections import deque
from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class AssignmentPlan:
    pairs: tuple[tuple[int, int], ...]  # snapshot, role assignment
    deficits: dict[int, int]
    loads: dict[int, int]


def plan_assignments(snapshot_ids, judge_ids, *, target_views=3, blocked=frozenset(),
                     existing=frozenset(), max_load=100, seed="0", minimum_views=3):
    # Judging rounds keep their floor of three (#128 C-33); application review stages
    # (lane L21a) pass minimum_views=1 for their 1-20 reviews per application.
    projects, judges = sorted(set(snapshot_ids)), sorted(set(judge_ids))
    if (minimum_views not in (1, 3) or type(target_views) is not int or not minimum_views <= target_views <= 20
            or type(max_load) is not int or not 1 <= max_load <= 2000
            or len(projects) > 2000 or len(judges) > 500):
        raise ValueError("Assignment limits exceeded.")
    if any(type(value) is not int or value <= 0 for value in projects + judges):
        raise ValueError("Use positive IDs.")
    if any(p not in projects or j not in judges for p, j in existing):
        raise ValueError("Existing assignments must belong to this partition.")
    size = 2 + len(projects) + len(judges)
    source, sink = size - 2, size - 1
    graph = [[] for _ in range(size)]

    def edge(start, end, capacity, cost=0):
        forward = [end, len(graph[end]), capacity, cost]
        backward = [start, len(graph[start]), 0, -cost]
        graph[start].append(forward)
        graph[end].append(backward)
        return forward

    loads = {judge: sum(j == judge for _, j in existing) for judge in judges}
    project_edges, pair_edges = {}, {}
    judge_nodes = {judge: index + len(projects) for index, judge in enumerate(judges)}
    for index, project in enumerate(projects):
        needed = max(0, target_views - sum(p == project for p, _ in existing))
        project_edges[project] = edge(source, index, needed)
        ordered = sorted(judges, key=lambda judge: sha256(f"{seed}:{project}:{judge}".encode()).digest())
        for judge in ordered:
            if (project, judge) not in blocked and (project, judge) not in existing:
                pair_edges[project, judge] = edge(index, judge_nodes[judge], 1)
    for judge in judges:
        for load in range(loads[judge], min(max_load, len(projects))):
            edge(judge_nodes[judge], sink, 1, 2 * load + 1)
    while True:
        distance, previous = [float("inf")] * size, [None] * size
        distance[source] = 0
        queue, in_queue = deque([source]), {source}
        while queue:
            start = queue.popleft()
            in_queue.remove(start)
            for index, item in enumerate(graph[start]):
                end, _, capacity, cost = item
                if capacity and distance[end] > distance[start] + cost:
                    distance[end] = distance[start] + cost
                    previous[end] = (start, index)
                    if end not in in_queue:
                        queue.append(end)
                        in_queue.add(end)
        if previous[sink] is None:
            break
        node = sink
        while node != source:
            start, index = previous[node]
            item = graph[start][index]
            item[2] -= 1
            graph[node][item[1]][2] += 1
            node = start
    pairs = tuple(sorted(pair for pair, item in pair_edges.items() if item[2] == 0))
    for _, judge in pairs:
        loads[judge] += 1
    return AssignmentPlan(pairs, {p: item[2] for p, item in project_edges.items() if item[2]}, loads)

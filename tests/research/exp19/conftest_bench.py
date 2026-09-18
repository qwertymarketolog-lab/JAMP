from __future__ import annotations

import random

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

RELATION_TYPES = ("DEP", "REF", "DATA", "CTRL")
PROFILES = ("single", "mixed", "rare", "dominant", "empty", "near-complete")


def _relation_types(profile: str, count: int, rng: random.Random) -> list[str]:
    if profile == "single":
        return ["CTRL"] * count
    if profile == "mixed":
        return [RELATION_TYPES[index % len(RELATION_TYPES)] for index in range(count)]
    if profile == "rare":
        rare_count = max(1, count // 200)
        return ["CTRL"] * rare_count + ["DEP"] * (count - rare_count)
    if profile == "dominant":
        dominant_count = int(count * 0.96)
        return ["CTRL"] * dominant_count + [
            RELATION_TYPES[index % 3] for index in range(count - dominant_count)
        ]
    if profile == "empty":
        return ["DEP"] * count
    if profile == "near-complete":
        return [RELATION_TYPES[index % 2] for index in range(count)]
    raise ValueError(f"Unknown benchmark profile: {profile}")


def _edge_pairs(
    profile: str, vertices: int, edges: int, rng: random.Random
) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    if profile == "near-complete":
        dense_vertices = max(200, min(vertices, 300))
        candidates = [
            (source, target)
            for source in range(dense_vertices)
            for target in range(source + 1, dense_vertices)
        ]
        rng.shuffle(candidates)
        pairs.extend(candidates[: min(edges, len(candidates))])

    while len(pairs) < edges:
        source = rng.randrange(vertices - 1)
        target = rng.randrange(source + 1, vertices)
        pair = (source, target)
        if pair not in seen:
            seen.add(pair)
            pairs.append(pair)

    return pairs


def build_graph(
    profile: str,
    seed: int = 42,
    v: int = 10_000,
    e: int = 20_000,
) -> ObservationAdjacencyGraph:
    if profile not in PROFILES:
        raise ValueError(f"Unknown benchmark profile: {profile}")
    if v < 2 or e < 1:
        raise ValueError("Benchmark graph requires v >= 2 and e >= 1")

    rng = random.Random(seed)
    pairs = _edge_pairs(profile, v, e, rng)
    types = _relation_types(profile, e, rng)

    relations = tuple(
        ObservationRelation(
            source_id=f"n{source:05d}",
            target_id=f"n{target:05d}",
            relation_type=relation_type,
            params={"seed": seed, "ordinal": index},
        )
        for index, ((source, target), relation_type) in enumerate(
            zip(pairs, types, strict=True)
        )
    )
    return ObservationAdjacencyGraph(relations)

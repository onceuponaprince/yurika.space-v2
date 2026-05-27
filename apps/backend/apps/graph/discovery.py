"""Discovery queries against the Neo4j knowledge graph.

Two modes:
    - trending: most "held" domains overall (public, no auth required)
    - personalized: domains adjacent to the calling user's holdings
      (auth required; the curator's own peer-graph)

Both return the same payload shape so the frontend can render either
without knowing which it asked for: a list of dicts with `uid`, `fqdn`,
`status`, and a numeric `score`.
"""
from __future__ import annotations

from neomodel import db


def trending_domains(limit: int = 10) -> list[dict]:
    """Domains ranked by how many distinct users hold shards in them.

    Pure graph query — equivalent SQL would be a JOIN-and-COUNT across
    domains, campaigns, and holdings, but expressing it in Cypher is
    materially cleaner and the graph is what we want to exercise for
    the S5 verify gate.
    """
    query = """
    MATCH (d:DomainNode)<-[:HOLDS]-(u:UserNode)
    WITH d, count(DISTINCT u) AS holder_count
    RETURN d.uid AS uid, d.fqdn AS fqdn, d.status AS status, holder_count AS score
    ORDER BY score DESC, d.fqdn ASC
    LIMIT $limit
    """
    results, _ = db.cypher_query(query, {"limit": limit})
    return [
        {"uid": row[0], "fqdn": row[1], "status": row[2], "score": row[3]}
        for row in results
    ]


def personalized_discovery(user_uid: str, limit: int = 10) -> list[dict]:
    """Domains adjacent to the calling user's holdings (peer-curator graph).

    Implements three product decisions made during S5 design:

      • Decision 1 (peer definition): Jaccard-style weighted. Every user
        who shares >=1 holding with the caller counts as a peer; their
        weight = number of shared holdings. No threshold filter — broad
        signal collection that scales naturally as the graph densifies.

      • Decision 2 (ranking): Sum of peer weights per candidate. Classic
        collaborative-filter score: both "many peers like it" and "one
        very-aligned peer likes it" contribute to ranking, with the
        Jaccard weights gating noise from low-overlap peers.

      • Decision 3 (exclusions): Drop domains the caller already holds,
        domains they own as a founder, and any in `withdrawn` or
        `completed` status. Withdrawn = dead listing; completed =
        campaign closed, not actionable for "what should I fund next".

    Bound via $user_uid and $limit. Returns same shape as
    trending_domains(): list of {uid, fqdn, status, score} dicts.
    """
    query = """
    // Decision 1: find peers, weighted by # of shared holdings
    MATCH (me:UserNode {uid: $user_uid})-[:HOLDS]->(d)<-[:HOLDS]-(peer:UserNode)
    WHERE peer.uid <> $user_uid
    WITH me, peer, count(d) AS overlap_weight

    // Pivot: from peers, walk to candidate domains
    MATCH (peer)-[:HOLDS]->(candidate:DomainNode)

    // Decision 3: exclusions (already-held, owned, withdrawn, completed)
    WHERE NOT (me)-[:HOLDS]->(candidate)
      AND NOT (me)-[:OWNS]->(candidate)
      AND candidate.status <> 'withdrawn'
      AND candidate.status <> 'completed'

    // Decision 2: sum peer weights as the final ranking score
    WITH candidate, sum(overlap_weight) AS score
    RETURN candidate.uid    AS uid,
           candidate.fqdn   AS fqdn,
           candidate.status AS status,
           score
    ORDER BY score DESC, candidate.fqdn ASC
    LIMIT $limit
    """
    results, _ = db.cypher_query(query, {"user_uid": user_uid, "limit": limit})
    return [
        {"uid": row[0], "fqdn": row[1], "status": row[2], "score": row[3]}
        for row in results
    ]


def graph_stats() -> dict:
    """Coarse counts of nodes/edges, used by the discovery endpoint's
    fallback path and the dev panel."""
    counts_q = """
    OPTIONAL MATCH (u:UserNode)
    WITH count(DISTINCT u) AS users
    OPTIONAL MATCH (d:DomainNode)
    WITH users, count(DISTINCT d) AS domains
    OPTIONAL MATCH (p:ProjectNode)
    WITH users, domains, count(DISTINCT p) AS projects
    OPTIONAL MATCH ()-[h:HOLDS]->()
    WITH users, domains, projects, count(h) AS holds
    OPTIONAL MATCH ()-[o:OWNS]->()
    RETURN users, domains, projects, holds, count(o) AS owns
    """
    results, _ = db.cypher_query(counts_q)
    if not results:
        return {"users": 0, "domains": 0, "projects": 0, "holds": 0, "owns": 0}
    row = results[0]
    return {
        "users": row[0],
        "domains": row[1],
        "projects": row[2],
        "holds": row[3],
        "owns": row[4],
    }

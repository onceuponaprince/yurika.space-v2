"""Neo4j node definitions mirroring Postgres entities.

The Postgres UUID is the join key in both directions: every node has a
`uid` StringProperty matching the SQL primary key. We do NOT use
neomodel's `UniqueIdProperty` because that auto-generates a Neo4j-local
UUID and would diverge from the SQL source-of-truth.

Relationship semantics:
    (User)-[:OWNS]->(Domain)              — founder relationship
    (User)-[:HOLDS]->(Domain)             — curator (holds shards)
    (Domain)-[:HAS_PROJECT]->(Project)    — founder-side project artifact
"""
from __future__ import annotations

from neomodel import (
    RelationshipTo,
    StringProperty,
    StructuredNode,
)


class UserNode(StructuredNode):
    uid = StringProperty(unique_index=True, required=True)
    wallet_address = StringProperty(unique_index=True, required=True)

    owns = RelationshipTo("DomainNode", "OWNS")
    holds = RelationshipTo("DomainNode", "HOLDS")


class DomainNode(StructuredNode):
    uid = StringProperty(unique_index=True, required=True)
    name = StringProperty(required=True)
    tld = StringProperty(required=True)
    fqdn = StringProperty(unique_index=True, required=True)
    status = StringProperty(required=True)

    has_project = RelationshipTo("ProjectNode", "HAS_PROJECT")


class ProjectNode(StructuredNode):
    uid = StringProperty(unique_index=True, required=True)
    name = StringProperty(required=True)

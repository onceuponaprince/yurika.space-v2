"""Fixtures for graph tests.

We run against a real Neo4j (the docker-compose service is healthy
throughout the dev loop), not a mock. The autouse `clean_neo4j`
fixture wipes the graph before each test so test order is irrelevant
and prior leftover from other apps' tests doesn't bleed in.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clean_neo4j():
    from neomodel import db

    db.cypher_query("MATCH (n) DETACH DELETE n")
    yield
    db.cypher_query("MATCH (n) DETACH DELETE n")

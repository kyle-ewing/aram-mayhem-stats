"""Business logic for the champion-centric Mayhem stats product.

Modules here must not import Flask. They take plain inputs (and may use the
isolated ``app.db`` module) and return plain, JSON-serializable data so they are
unit-testable:

* ``ingest``    validate a Mayhem match payload and store it idempotently.
* ``stats``     aggregate per-champion / per-augment / synergy winrates.
* ``synergies`` serve the curated editorial synergy notes.
"""

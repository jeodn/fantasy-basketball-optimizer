"""
app/models.py
~~~~~~~~~~~~~
Backward-compatibility re-exports.

The stat-schema constants have moved to app.domain.stats.
The NBA-API column mapping has moved to app.ingestion.player_ingestion (private).
This module re-exports from their canonical locations so any external scripts
or notebooks that imported from here continue to work.
"""

from app.domain.stats import (  # noqa: F401
    STAT_MAP,
    SCALABLE_STAT_COLS,
    RAW_STAT_COLS,
)

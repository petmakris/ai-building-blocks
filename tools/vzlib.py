"""The shared diagram library (claude-annotate, skills/_shared/visuals), as this site uses it.

A block's map is diagrams/<id>.map.json and its walkthrough diagram diagrams/<id>.seq.json; both are drawn
by the library and embedded with its player, so the reader can see the whole, build it up, or follow the
request. The library lives in ~/projects/claude-annotate, or wherever VZ_HOME points.
"""
from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

from store import ROOT

HOME = Path(os.environ.get("VZ_HOME", Path.home() / "projects" / "claude-annotate"))
SHARED = HOME / "skills" / "_shared"
STATIC = SHARED / "static"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from visuals import map_svg, player, sequence_svg  # noqa: E402


def spec(block_id: str, kind: str) -> dict | None:
    p = ROOT / "diagrams" / f"{block_id}.{kind}.json"
    return json.loads(p.read_text()) if p.exists() else None


@lru_cache(maxsize=None)
def map_svg_of(block_id: str) -> str | None:
    s = spec(block_id, "map")
    return map_svg.render(s, f"{block_id}-map") if s else None


@lru_cache(maxsize=None)
def seq_svg_of(block_id: str) -> str | None:
    s = spec(block_id, "seq")
    return sequence_svg.render(s, f"{block_id}-seq") if s else None


def map_figure(block_id: str) -> str:
    s = spec(block_id, "map")
    if not s:
        return ""
    caps = s.get("captions") or {}
    return player.figure(map_svg_of(block_id), {"build": caps.get("build"), "route": caps.get("route")})


def sequence_figure(block_id: str) -> str:
    s = spec(block_id, "seq")
    if not s:
        return ""
    return player.figure(seq_svg_of(block_id), {"route": s.get("captions")})


def home_figure() -> str:
    """The home page's request path, diagrams/home.map.json, with its route (R0 to R13) to step through."""
    s = spec("home", "map")
    if not s:
        return ""
    return player.figure(map_svg_of("home"), {"route": (s.get("captions") or {}).get("route")})

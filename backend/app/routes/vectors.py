"""GET /api/v1/vectors — list the detectors pdfaudit has available."""
from __future__ import annotations

import sys

from fastapi import APIRouter

from pdfaudit import Engine, default_detectors

from ..schemas import VectorInfo, VectorsResponse

router = APIRouter()


# Pull each detector's MODULE docstring's first line as a description (the rich
# docstrings live at module level, not on the class). Computed once at import.
def _detector_descriptions() -> dict[str, str]:
    descs: dict[str, str] = {}
    for d in default_detectors():
        module = sys.modules.get(type(d).__module__)
        doc = (getattr(module, "__doc__", None) or "").strip()
        first_line = doc.split("\n", 1)[0].strip() if doc else ""
        descs[d.name] = first_line or f"{d.name} detector"
    return descs


_DESCRIPTIONS = _detector_descriptions()


@router.get("/vectors", response_model=VectorsResponse, tags=["meta"])
async def vectors() -> VectorsResponse:
    """Return the names + one-line descriptions of all detectors.

    The detector list mirrors `Engine.available_vectors()` exactly; if a
    consumer passes one of these names back as the `only` filter on /scan,
    the engine will respect it.
    """
    engine = Engine()
    names = engine.available_vectors()
    return VectorsResponse(
        vectors=[
            VectorInfo(name=name, description=_DESCRIPTIONS.get(name, ""))
            for name in names
        ]
    )
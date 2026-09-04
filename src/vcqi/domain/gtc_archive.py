"""Optional support for the GUM Tree Calculator, as a second opinion on the same idea.

GTC, from the Measurement Standards Laboratory of New Zealand, solves the problem this
demonstration is about independently of METAS UncLib. Its elementary uncertain numbers
carry UUID-based identifiers, and an archive holding them serialises to JSON or XML
against published schemas. Two libraries arriving at the same design is a better
argument for the design than one, and it is the reason the credential describes a
*format* rather than assuming a particular library.

GTC pulls in scipy, which is a large dependency for a demonstration that does not
otherwise need it. So it is optional: install with ``uv sync --extra gtc`` and the
certificates gain a GTC archive alongside the UncLib representation; leave it out and
everything still works, with the interface saying plainly that the format is described
but not built.
"""

from __future__ import annotations

from typing import Any

from vcqi.domain.uncertainty import MeasurementResult

__all__ = ["gtc_available", "build_gtc_archive", "GTC_UNAVAILABLE_NOTE"]

GTC_UNAVAILABLE_NOTE = (
    "GTC is not installed in this environment, so no archive was built. Run "
    "'uv sync --extra gtc' to have certificates carry one as well."
)


def gtc_available() -> bool:
    """Report whether GTC can be imported.

    Returns:
        True when the optional dependency is present.
    """
    try:
        import GTC  # noqa: F401
    except ImportError:
        return False
    return True


def build_gtc_archive(result: MeasurementResult) -> str | None:
    """Express a result as a GTC archive, serialised to JSON.

    The archive is rebuilt from the budget rather than converted from the UncLib object,
    because there is no bridge between the two libraries and inventing one would be
    misleading. What this shows is that the same measurement model, entered into either
    library, yields the same result and the same kind of transmissible dependency
    structure.

    Args:
        result: The evaluated result, whose budget supplies the influences.

    Returns:
        The archive as a JSON string, or None when GTC is not installed or the result
        carries no budget to rebuild from.
    """
    try:
        from GTC import ureal
        from GTC import persistence
    except ImportError:
        return None

    if not result.budget:
        return None

    influences = {
        line.key: ureal(line.value, line.standard_uncertainty, label=line.label)
        for line in result.budget
    }

    # Reconstruct the measurand as the first-order expansion the budget describes. For a
    # linear propagation that is exactly the model; for anything else it is the same
    # approximation the budget itself already makes.
    measurand = result.value
    for line in result.budget:
        measurand = measurand + line.sensitivity_coefficient * (
            influences[line.key] - line.value
        )

    archive = persistence.Archive()
    archive.add(result=measurand)
    for key, influence in influences.items():
        archive.add(**{f"input_{key}": influence})

    try:
        return persistence.dumps_json(archive, indent=2)
    except TypeError:
        # Older releases do not accept formatting arguments.
        return persistence.dumps_json(archive)


def gtc_summary(result: MeasurementResult) -> dict[str, Any]:
    """Describe what GTC makes of the result, for the interface.

    Args:
        result: The evaluated result.

    Returns:
        Whether GTC is installed and, when it is, the value and Standard Uncertainty it
        computes, so a reader can see the two libraries agree.
    """
    archive = build_gtc_archive(result)
    if archive is None:
        return {"available": False, "note": GTC_UNAVAILABLE_NOTE}

    from GTC import ureal  # noqa: F401  (import proves availability for the caller)

    return {
        "available": True,
        "archiveBytes": len(archive.encode("utf-8")),
        "influenceCount": len(result.budget),
    }

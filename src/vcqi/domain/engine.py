"""Which uncertainty engine this process uses, and why there is a choice.

The demonstrator computes uncertainty with METAS UncLib where it is available and with
:mod:`vcqi.domain.linprop` otherwise. That is not a preference about numerical quality —
the two agree, and ``tests/test_linprop_equivalence.py`` says so in detail. It is a
licensing fact. The METAS UncLib licence is a designated-computer licence that
prohibits distributing the software to third parties in any form, including
"incorporated into a software package" or "incorporated into any kind of device or
machine". A container image on a hosting provider is exactly that, so the deployed
demonstrator cannot carry UncLib and computes with the pure-Python engine instead.

Both engines present the same surface, which is UncLib's, so the rest of the code
imports ``mu`` from here and never learns which one it got:

    from vcqi.domain.engine import mu

Set ``VCQI_ENGINE=linprop`` to force the pure-Python engine on a machine that has
UncLib installed. That is what the equivalence test and the document-comparison
tooling use, and it is the only way to reproduce a deployed build locally.
"""

from __future__ import annotations

import os
from typing import Any, Final

__all__ = ["mu", "ENGINE", "UNCLIB", "LINPROP", "unclib_available", "engine_note"]

#: Name of the engine backed by METAS UncLib itself.
UNCLIB: Final[str] = "unclib"

#: Name of the pure-Python engine in :mod:`vcqi.domain.linprop`.
LINPROP: Final[str] = "linprop"

_REQUESTED: Final[str] = os.environ.get("VCQI_ENGINE", "").strip().lower()

mu: Any
ENGINE: str

if _REQUESTED == LINPROP:
    from vcqi.domain import linprop as mu  # type: ignore[no-redef]

    ENGINE = LINPROP
else:
    try:
        import metas_unclib as mu  # type: ignore[no-redef]

        mu.use_linprop()
        ENGINE = UNCLIB
    except Exception:
        # Anything at all: the wheel is absent, or present without a .NET runtime to
        # host its assemblies. Either way the pure-Python engine is the answer, and a
        # failure to import a proprietary optional dependency should not be fatal.
        from vcqi.domain import linprop as mu  # type: ignore[no-redef]

        ENGINE = LINPROP


def unclib_available() -> bool:
    """Report whether this process is computing with METAS UncLib itself.

    Returns:
        True when the real library is in use, False for the pure-Python engine.
    """
    return ENGINE == UNCLIB


#: Shown wherever the demonstrator reports how a number was produced, so a reader of
#: the deployed site is told which engine computed the budget in front of them.
_LINPROP_NOTE: Final[str] = (
    "Computed with the demonstrator's own linear-propagation engine rather than METAS "
    "UncLib, which is licensed for a designated computer and may not be redistributed "
    "in a container image. The two agree exactly on the models used here, and the "
    "dependency representations they write are byte-identical; the test suite checks "
    "both on a machine where UncLib is installed."
)

_UNCLIB_NOTE: Final[str] = (
    "Computed with METAS UncLib, the reference implementation of this propagation."
)


def engine_note() -> str:
    """Return a sentence naming the engine that computed this process's numbers.

    Returns:
        The note for whichever engine is in use.
    """
    return _UNCLIB_NOTE if unclib_available() else _LINPROP_NOTE

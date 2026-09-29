"""Check that every type and property in a JSON-LD document expands, without a network.

The UNTP Playground's JSON-LD step expands a credential against the contexts it names, in
safe mode, and fails on a type that expands to a relative IRI or a property that expands
to nothing. The 0.6.0 projection failed exactly there, on type names UNTP's schema filled
in and UNTP's context never defined, and nothing in this repository could have said so,
because nothing here expands JSON-LD: the credentials are signed with ``ecdsa-jcs-2019``,
which never needs to.

This module is the offline stand-in, over the vendored contexts. It follows the parts of
the JSON-LD 1.1 expansion algorithm that decide whether a term resolves:

* an embedded ``@context`` applies to the node and everything below it;
* a property-scoped context applies to the property's value and propagates;
* a type-scoped context applies to the node's own properties only, and nested nodes
  revert to the context from before it -- the reason a value object's properties can be
  undefined even though its parent's are not;
* type-scoped contexts are looked up in the context from before any of them were
  applied, and applied in lexicographic order of the type;
* ``@vocab`` resolves anything not defined as a term.

It is stricter than the Playground in one respect. A property that resolves only through
a scoped ``@vocab`` expands to *something*, so safe mode lets it through -- including a
misspelt one. Reported here as ``vocab-only``, because in a document written against a
context that defines its terms, a term the context does not define is a typo.

What it is not: a JSON-LD processor. It does not expand values, check IRIs, honour
``@propagate`` or protected-term rules, or compact anything, and it was written by the
same hand as the projection it checks. A clean result is a necessary condition for the
Playground's step to pass, not a substitute for running it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["TermProblem", "term_problems"]

#: Keys treated as keywords wherever they appear. The W3C credentials context aliases
#: ``id`` and ``type`` as protected terms, so every document here can rely on them.
_ID_KEYS = frozenset({"@id", "id"})
_TYPE_KEYS = frozenset({"@type", "type"})

#: Containers whose value is a map keyed by something other than terms.
_MAP_CONTAINERS = frozenset({"@language", "@index", "@id", "@type"})


@dataclass(frozen=True)
class TermProblem:
    """One term in a document that does not expand as a context-defined term.

    Attributes:
        kind: ``type``, ``property`` or ``context``.
        problem: ``undefined`` -- expansion fails on a type or drops a property;
            ``vocab-only`` -- it expands only through ``@vocab``; ``unknown`` -- a named
            context that was not supplied.
        term: The type name, property name or context URL.
        path: Where in the document, ``/``-separated from the root.
    """

    kind: str
    problem: str
    term: str
    path: str

    def to_json(self) -> dict[str, str]:
        """Render the problem for a report.

        Returns:
            A JSON-compatible object.
        """
        return {
            "kind": self.kind,
            "problem": self.problem,
            "term": self.term,
            "path": self.path,
        }


@dataclass(frozen=True)
class _Context:
    """An active context, reduced to what decides whether a term resolves.

    Attributes:
        terms: Term definitions by term. A definition is a string, a map, or None for a
            term the context explicitly undefines.
        vocab: The ``@vocab`` mapping, or None.
    """

    terms: dict[str, Any]
    vocab: str | None


_EMPTY = _Context(terms={}, vocab=None)


def term_problems(
    document: dict[str, Any], contexts: dict[str, dict[str, Any]]
) -> list[TermProblem]:
    """List every type and property in a document that does not expand as a defined term.

    Args:
        document: The JSON-LD document, for example a credential.
        contexts: The context documents it may name, by URL, each with a top-level
            ``@context`` member.

    Returns:
        The problems, in document order. Empty when every term resolves.
    """
    problems: list[TermProblem] = []
    _walk(document, _EMPTY, "", contexts, problems)
    return problems


def _process(
    active: _Context,
    local: Any,
    contexts: dict[str, dict[str, Any]],
    path: str,
    problems: list[TermProblem],
) -> _Context:
    """Apply a local context to an active one.

    Args:
        active: The active context.
        local: A context value: a URL, a map, None, or a list of those.
        contexts: The context documents that may be named, by URL.
        path: Where the context appears, for problems.
        problems: The problems so far, appended to.

    Returns:
        The resulting active context.
    """
    terms, vocab = dict(active.terms), active.vocab
    for item in local if isinstance(local, list) else [local]:
        if item is None:
            terms, vocab = {}, None
            continue
        if isinstance(item, str):
            named = contexts.get(item)
            if named is None:
                problems.append(TermProblem("context", "unknown", item, path or "/"))
                continue
            resolved = _process(
                _Context(terms, vocab), named.get("@context"), contexts, path, problems
            )
            terms, vocab = dict(resolved.terms), resolved.vocab
            continue
        if not isinstance(item, dict):
            continue
        if "@vocab" in item:
            vocab = item["@vocab"]
        for term, definition in item.items():
            if not term.startswith("@"):
                terms[term] = definition
    return _Context(terms, vocab)


def _scoped(definition: Any) -> Any:
    """Return the local context a term definition carries, if any.

    Args:
        definition: A term definition.

    Returns:
        The scoped context, or None.
    """
    return definition.get("@context") if isinstance(definition, dict) else None


def _resolves(term: str, context: _Context) -> str | None:
    """Say how a term resolves in a context.

    Args:
        term: A type name or property name.
        context: The context it is resolved in.

    Returns:
        ``defined`` for a term the context defines, ``iri`` for an absolute or compact
        IRI, ``vocab`` for a term only ``@vocab`` resolves, None when it does not resolve.
    """
    if term in context.terms:
        return "defined" if context.terms[term] is not None else None
    if ":" in term:
        return "iri"
    if context.vocab is not None:
        return "vocab"
    return None


def _walk(
    node: dict[str, Any],
    active: _Context,
    path: str,
    contexts: dict[str, dict[str, Any]],
    problems: list[TermProblem],
) -> None:
    """Check one node object and everything below it.

    Args:
        node: The node object.
        active: The context in force for it, with any type-scoped context of its parent
            already reverted and any property-scoped context already applied.
        path: Where it is, for problems.
        contexts: The context documents that may be named, by URL.
        problems: The problems so far, appended to.
    """
    if "@value" in node:
        return
    if "@context" in node:
        active = _process(active, node["@context"], contexts, path, problems)

    types: list[str] = []
    for key in _TYPE_KEYS & node.keys():
        value = node[key]
        values = value if isinstance(value, list) else [value]
        types.extend(item for item in values if isinstance(item, str))
    for name in types:
        how = _resolves(name, active)
        if how is None:
            problems.append(TermProblem("type", "undefined", name, path or "/"))
        elif how == "vocab":
            problems.append(TermProblem("type", "vocab-only", name, path or "/"))

    local = active
    for name in sorted(types):
        scoped = _scoped(active.terms.get(name))
        if scoped is not None:
            local = _process(local, scoped, contexts, path, problems)

    for key, value in node.items():
        if key == "@context" or key in _ID_KEYS or key in _TYPE_KEYS or key.startswith("@"):
            continue
        here = f"{path}/{key}"
        how = _resolves(key, local)
        if how is None:
            problems.append(TermProblem("property", "undefined", key, here))
            continue
        if how == "vocab":
            problems.append(TermProblem("property", "vocab-only", key, here))
        definition = local.terms.get(key)
        container = definition.get("@container") if isinstance(definition, dict) else None
        containers = set(container if isinstance(container, list) else [container])
        if containers & _MAP_CONTAINERS:
            continue
        child = active
        scoped = _scoped(definition)
        if scoped is not None:
            child = _process(active, scoped, contexts, here, problems)
        items = value if isinstance(value, list) else [value]
        for index, item in enumerate(items):
            if isinstance(item, dict):
                where = f"{here}/{index}" if isinstance(value, list) else here
                _walk(item, child, where, contexts, problems)

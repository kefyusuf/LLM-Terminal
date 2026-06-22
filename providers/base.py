"""Provider result type and the unified BaseProvider contract.

This module closes the gap between the function-based providers
(``search_hf_models``, ``search_ollama_models``) and the class-based
providers (``LMStudioProvider``, ``DockerProvider``, ``MLXProvider``).
Every provider now returns a single ``SearchResult`` value object
with the same shape, so the orchestrator can call them polymorphically
without inspecting tuple arity.

Before this module, ``tui_app.py:1426-1430`` had to special-case Ollama:

    if label == "ollama":
        if len(result) == 3:
            ollama_results, ollama_errors, _ = result
        else:
            ollama_results, ollama_errors = result

After, all 5 providers return ``SearchResult`` and the orchestrator
unpacks the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """Result of a provider ``search()`` call.

    Attributes:
        results: List of model result dicts (each conforming to the
            ``ModelResult`` TypedDict schema in ``core/models.py``).
        errors: List of human-readable error messages encountered while
            searching. The provider did not raise — it returned
            partial results + diagnostics.
        has_more_pages: True if the provider has more results beyond
            the current page. For providers without real pagination
            (Ollama), this is computed by comparing result count
            against ``page_size``.
    """

    results: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    has_more_pages: bool = False

    def extend(self, other: SearchResult) -> SearchResult:
        """Merge *other* into a new SearchResult. Non-mutating."""
        return SearchResult(
            results=self.results + other.results,
            errors=self.errors + other.errors,
            has_more_pages=self.has_more_pages or other.has_more_pages,
        )

    @classmethod
    def empty(cls) -> SearchResult:
        return cls()

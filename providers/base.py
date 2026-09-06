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

from core.errors import ProviderError


@dataclass
class SearchResult:
    """Result of a provider ``search()`` call.

    Attributes:
        results: List of model result dicts (each conforming to the
            ``ModelResult`` TypedDict schema in ``core/models.py``).
        errors: Backward-compatible list of human-readable error messages.
            Existing CLI, TUI, REST, and provider callers continue to use
            this surface unchanged during structured-error migration.
        structured_errors: Machine-readable provider diagnostics. This is
            additive and may remain empty while a provider has not yet been
            migrated to populate structured errors.
        has_more_pages: True if the provider has more results beyond
            the current page. For providers without real pagination
            (Ollama), this is computed by comparing result count
            against ``page_size``.
    """

    results: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    structured_errors: list[ProviderError] = field(default_factory=list)
    has_more_pages: bool = False

    def extend(self, other: SearchResult) -> SearchResult:
        """Merge *other* into a new SearchResult without mutating either input."""
        return SearchResult(
            results=self.results + other.results,
            errors=self.errors + other.errors,
            structured_errors=self.structured_errors + other.structured_errors,
            has_more_pages=self.has_more_pages or other.has_more_pages,
        )

    @classmethod
    def empty(cls) -> SearchResult:
        """Return an empty result with both diagnostic surfaces initialized."""
        return cls()

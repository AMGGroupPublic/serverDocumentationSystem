"""Per-host INDEX.md — lists discovered entities and any disappeared ones."""

from __future__ import annotations

from jinja2 import Environment

from ..model import Entity

_TEMPLATE = """\
---
host: {{ host }}
auto_generated: true
---

# DNS Name : {{ host }}

{% if scan_failed %}
> ⚠ Scan failed for this host on the last run. Existing pages preserved.
{% endif %}
{% if entities %}
## Active

| Type | Name | State | Notes | CPU | Memory (MB) |
|---|---|---|---|---|---|
{% for e in entities -%}
| {{ e.type }} | [[servers/{{ host }}/{{ e.type }}/{{ e.name }}/NOTES|{{ e.name }}]] | {{ e.state }} | {{ "✅" if (e.type, e.name) in customized else "❌" }} | {{ e.cpu if e.cpu is not none else "?" }} | {{ e.memory_mb if e.memory_mb is not none else "?" }} |
{% endfor %}
{% else %}
_No entities discovered on this host._
{% endif %}
{% if disappeared %}
## Disappeared

These entities were present in previous runs but were not seen on the latest scan.

{% for d in disappeared -%}
- [[servers/{{ host }}/{{ d.type }}/{{ d.name }}/NOTES|{{ d.type }}/{{ d.name }}]]
{% endfor %}
{% endif %}
---

[[README#Server Documentation|← Back to overview]]
"""


def render_host_index(
    host: str,
    entities: list[Entity],
    *,
    disappeared: list[Entity] | None = None,
    scan_failed: bool = False,
    customized_notes: set[tuple[str, str]] | None = None,
) -> str:
    env = Environment(autoescape=False, keep_trailing_newline=True)
    return env.from_string(_TEMPLATE).render(
        host=host,
        entities=_sorted_for_display(entities),
        disappeared=disappeared or [],
        scan_failed=scan_failed,
        customized=customized_notes or set(),
    )


def _sorted_for_display(entities: list[Entity]) -> list[Entity]:
    """Running first (alpha by name), then everything else (alpha by name)."""
    return sorted(entities, key=lambda e: (0 if e.state == "running" else 1, e.name.lower()))

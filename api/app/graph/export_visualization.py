"""Task 1.10 — exports the compiled graph's structure to a checked-in
Mermaid file, so the flow can be reviewed without reading the routing
code (graph-orchestration spec's "The graph's structure can be exported
for inspection" requirement).

Run with:  python -m app.graph.export_visualization
"""

from __future__ import annotations

from pathlib import Path

from app.graph.build import build_graph

OUTPUT_PATH = Path(__file__).parent / "graph_visualization.mmd"


def export() -> Path:
    compiled = build_graph().compile()
    mermaid = compiled.get_graph().draw_mermaid()
    OUTPUT_PATH.write_text(mermaid, encoding="utf-8")
    return OUTPUT_PATH


def main() -> None:
    path = export()
    print(f"Wrote graph visualization to {path}")


if __name__ == "__main__":
    main()

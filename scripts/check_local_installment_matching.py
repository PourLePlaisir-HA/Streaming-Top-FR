from __future__ import annotations

import ast
from difflib import SequenceMatcher
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/streaming_top_fr/sources.py"

tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
wanted_functions = {
    "_slug",
    "_matching_slug",
    "_explicit_installment_number",
    "_localized_title_alias",
}
nodes = [
    node for node in tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    and node.name in wanted_functions
]
namespace = {
    "re": re,
    "unicodedata": unicodedata,
}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)

matching_slug = namespace["_matching_slug"]
part_number = namespace["_explicit_installment_number"]
localized_alias = namespace["_localized_title_alias"]

wanted = matching_slug("La Bataille de Gaulle L Age de Fer", "movie")
correct = matching_slug(
    "La Bataille de Gaulle - Partie 1 : L'Age de Fer", "movie"
)
wrong = matching_slug(
    "La Bataille de Gaulle - Partie 2 : J'ecris ton nom", "movie"
)

assert part_number(wanted) is None
assert part_number(correct) == 1
assert part_number(wrong) == 2

# Regression: same franchise + same release year must never be sufficient to
# jump from an unnumbered local subtitle to an explicitly different part.
assert localized_alias(wanted, wrong) is False

# The real Part 1 remains discoverable through ordinary title similarity,
# independently of the permissive localized-title fallback.
assert SequenceMatcher(None, wanted, correct).ratio() >= 0.88

# If both localized forms explicitly refer to the same part, the fallback can
# still be used when needed.
same_part_a = matching_slug(
    "Saga Partie 2 Le Nom Francais Tres Long", "movie"
)
same_part_b = matching_slug(
    "Saga Partie 2 Completely Different Localized Subtitle", "movie"
)
assert localized_alias(same_part_a, same_part_b) is True

# Different explicit parts must always be rejected.
different_part = matching_slug(
    "Saga Partie 1 Completely Different Localized Subtitle", "movie"
)
assert localized_alias(same_part_a, different_part) is False

print("Local explicit-installment matching checks passed.")

# Copilot Suggestion: List Comprehension Filter

Copilot suggested: `results = [x for x in items if x > 0]`

CodeScope shows:
  x=3: added to results
  x=-5: filtered out
  x=0: filtered out (implicit falsy)

Key insight: x=0 gets silently dropped. Copilot often writes this
without explaining the implicit truthiness behavior.

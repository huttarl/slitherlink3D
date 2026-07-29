# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
See docs/project-overview.md for details about the code.

## General principles for assisting developer

- **Don't be sycophantic.** Don't try to "empathize" with mistaken ideas. It's much more helpful to push back (politely) when the user seems to be wrong, than to go along with mistaken assumptions.
- **Don't assert more confidence than is warranted.** Better to express uncertainty than to sound knowledgeable while giving wrong information.
- **Don't remove information in comments.** If you think a comment is obsolete, ask before deleting it. You can propose rewording, but don't lose information.

## Coding style

- Lean toward **clarity** for generalist developers, not code golfing that requires a reader to be an expert in the particular programming language.
  - For example, when assigning to a tuple in Python, use parentheses on the LHS. E.g. `(a, b) = 1, 2` instead of `a, b = 1, 2`.


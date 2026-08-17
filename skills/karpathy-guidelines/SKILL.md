---
name: karpathy-guidelines
description: Reduce common agent coding mistakes through explicit assumptions, minimal solutions, surgical changes, and verifiable success criteria. Use when writing, reviewing, debugging, designing, or refactoring code and project configuration where scope or quality judgment is required.
---

# Karpathy Guidelines

Apply these guidelines with judgment. Favor caution for meaningful changes; keep trivial edits lightweight.

## Think Before Coding

- State assumptions explicitly.
- Surface ambiguity and tradeoffs instead of hiding them.
- Prefer the simplest valid interpretation.
- Stop and ask when an unresolved choice would materially change the result.

## Keep It Simple

- Implement only what the request requires.
- Avoid abstractions, flexibility, and error handling without a concrete need.
- Prefer the smallest solution that satisfies the acceptance criteria.
- Reconsider the design when the implementation is much larger than the problem suggests.

## Make Surgical Changes

- Touch only files and lines required by the task.
- Preserve the repository's existing style and user changes.
- Do not refactor adjacent code merely because it could be improved.
- Remove only unused artifacts introduced by the current change.
- Ensure every changed line traces back to the request.

## Work Toward Verifiable Outcomes

Translate the request into concrete outcomes and checks before implementation.

```text
1. [Change] -> verify: [observable result]
2. [Change] -> verify: [test or inspection]
3. [Change] -> verify: [acceptance criterion]
```

- Reproduce bugs before fixing them when practical.
- Run proportionate tests before and after risky refactors.
- Inspect actual output instead of relying only on command success.
- Report checks that could not be performed and why.

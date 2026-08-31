# Development Instructions

## Purpose

Develop production-quality software that is maintainable, testable, understandable, and consistent with the existing codebase. Apply SOLID principles pragmatically; do not introduce abstractions without a demonstrated need.

## Working Method

Before changing code:

1. Read the relevant implementation, tests, interfaces, and nearby documentation.
2. Identify the requested behavior, affected boundaries, and likely regression risks.
3. For non-trivial work, state a short implementation plan before editing.
4. Reuse existing patterns unless they conflict with these instructions or clearly cause the problem.
5. Ask for clarification when an unresolved requirement would materially affect the public API or architecture.

While changing code:

- Make the smallest coherent change that fully solves the problem.
- Do not modify unrelated files or reformat unrelated code.
- Preserve backward compatibility unless the task explicitly authorizes a breaking change.
- Keep business logic separate from delivery mechanisms, frameworks, persistence, and external services.
- Do not hide failures with silent fallbacks or broad exception handling.

After changing code:

1. Add or update relevant tests.
2. Run the narrowest relevant checks first, followed by the broader suite when practical.
3. Review the final diff for accidental or unrelated changes.
4. Report what changed, why it changed, and what verification was performed.
5. Explicitly disclose checks that could not be run and the reason.

## SOLID Principles

### Single Responsibility Principle

- Give each module, class, and function one clear reason to change.
- Separate orchestration from domain logic and input/output concerns.
- Extract responsibilities when code mixes validation, persistence, formatting, networking, or business decisions.
- Do not split cohesive logic into tiny units merely to reduce file or function size.
- If a component needs a description containing several unrelated uses of “and,” reconsider its responsibilities.

### Open/Closed Principle

- Prefer adding behavior through stable extension points instead of repeatedly modifying central conditional logic.
- Use polymorphism, composition, strategies, handlers, or registration only when multiple variants exist or are reasonably expected.
- Keep extension contracts small, explicit, and documented.
- Avoid speculative abstractions intended only for hypothetical future requirements.
- Adding a new implementation should require minimal or no changes to existing implementations.

### Liskov Substitution Principle

- Every implementation must honor the behavioral contract of its abstraction.
- Do not strengthen preconditions, weaken postconditions, or introduce surprising side effects in a subtype.
- Preserve expected exception behavior, mutability rules, invariants, and return semantics.
- Do not use inheritance solely for code reuse when the child is not behaviorally substitutable for the parent.
- Prefer composition when implementations require incompatible behavior.

### Interface Segregation Principle

- Keep interfaces focused on the needs of their consumers.
- Do not force implementations to provide irrelevant methods or raise “not supported” errors for required interface members.
- Split broad interfaces by capability or role when consumers use only small subsets.
- Accept the narrowest useful dependency at each boundary.
- Avoid interfaces containing unrelated read, write, lifecycle, and administrative operations unless all consumers require them together.

### Dependency Inversion Principle

- High-level policy must not depend directly on low-level infrastructure details.
- Define abstractions at the boundary where they are consumed, when the language and project conventions support it.
- Inject external dependencies such as clocks, storage, network clients, message brokers, and third-party services.
- Keep dependency construction in an application entry point, factory, or composition root.
- Avoid service locators, hidden global state, and constructors that perform I/O.
- Depend on stable behavior contracts, not concrete framework classes, where substitution or testing is valuable.

## Architecture and Design

- Prefer composition over inheritance.
- Keep dependency direction pointing toward stable domain or application policy.
- Isolate external systems behind clear boundaries.
- Keep framework-specific code near the application edges.
- Separate commands that change state from queries that retrieve data when it improves clarity.
- Make side effects explicit.
- Avoid cyclic dependencies and bidirectional module relationships.
- Do not expose internal persistence or transport models as public domain APIs.
- Use design patterns only when they simplify an existing problem.
- Record significant architectural decisions when they introduce lasting constraints or trade-offs.

## Code Quality

- Follow the repository's existing naming, formatting, typing, and documentation conventions.
- Prefer clear, explicit code over clever or compressed code.
- Use descriptive names that express intent rather than implementation detail.
- Keep functions cohesive and at a consistent level of abstraction.
- Eliminate duplication when duplicated knowledge could diverge; tolerate small incidental similarity.
- Replace unexplained literals with named constants when the value has domain or behavioral meaning.
- Avoid mutable global state.
- Validate inputs at system boundaries.
- Represent invalid states so they are difficult to construct when practical.
- Add comments for reasoning, constraints, and non-obvious trade-offs—not to restate the code.

## Error Handling

- Fail clearly and as close as practical to the source of invalid state.
- Catch only exceptions that can be handled meaningfully.
- Preserve the original cause when translating errors across abstraction boundaries.
- Use specific error types or structured error results consistent with the codebase.
- Never swallow errors silently.
- Do not expose sensitive internal details through user-facing errors or logs.

## Testing

- Test externally observable behavior and contracts rather than private implementation details.
- Add regression tests for bug fixes.
- Cover normal behavior, boundary cases, invalid input, and meaningful failure paths.
- Keep tests deterministic, isolated, and independent of execution order.
- Replace external systems with fakes or test doubles at architectural boundaries, not throughout internal logic.
- Do not mock the unit under test.
- Use integration tests to verify important component boundaries.
- Name tests so the scenario and expected outcome are clear.
- Do not weaken, delete, or skip tests merely to make a change pass.

## Dependencies and Configuration

- Do not add or upgrade a production dependency without explaining the need and impact.
- Prefer existing dependencies or the standard library when they adequately solve the problem.
- Keep environment-specific values outside source code.
- Do not commit secrets, credentials, tokens, private keys, or real production data.
- Validate required configuration at startup and provide actionable error messages.
- Pin or constrain dependencies according to the repository's established policy.

## Security and Safety

- Treat all external input as untrusted.
- Apply least privilege to filesystem, network, database, and service access.
- Use parameterized APIs rather than constructing executable queries or commands from strings.
- Avoid logging secrets, credentials, or unnecessary personal data.
- Do not perform destructive operations unless explicitly required and correctly scoped.
- Preserve user changes and avoid destructive version-control commands.
- Flag security-sensitive behavior and assumptions in the final report.

## Performance

- Correctness and clarity come before optimization unless performance is a stated requirement.
- Do not optimize based only on intuition; measure or establish a credible bottleneck first.
- Avoid obviously wasteful repeated I/O, unnecessary full-data scans, and unbounded resource use.
- Document performance trade-offs when they affect readability, memory usage, latency, or complexity.
- Add benchmarks or performance tests when performance is part of the acceptance criteria.

## Refactoring Rules

- Refactor only as much as required to implement the requested change safely.
- Separate large structural refactors from behavioral changes when practical.
- Preserve behavior with tests before altering complex or poorly understood code.
- Do not introduce a new abstraction unless it removes real duplication, isolates volatility, or establishes a necessary boundary.
- Prefer incremental, reversible changes over broad rewrites.

## Definition of Done

A task is complete only when:

- The requested behavior is implemented.
- The design follows SOLID principles without unnecessary abstraction.
- Public contracts and backward compatibility are preserved unless explicitly changed.
- Relevant tests are added or updated and pass.
- Applicable formatting, linting, type-checking, build, and test commands pass.
- Error cases and boundary conditions are handled.
- Documentation is updated when behavior, configuration, or public APIs change.
- The final diff contains no unrelated changes.
- The final response summarizes changed files, design decisions, verification, and remaining risks.

## Prohibited Shortcuts

- Do not hardcode behavior merely to satisfy a test.
- Do not bypass established abstractions without explaining and justifying the exception.
- Do not add empty interfaces, one-implementation factories, or wrapper classes without a concrete architectural benefit.
- Do not leave dead code, commented-out implementations, placeholder logic, or unresolved TODOs unless explicitly requested.
- Do not claim that tests or checks passed unless they were actually run successfully.

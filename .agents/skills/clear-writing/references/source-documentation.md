# Source documentation

Use the language's documentation mechanism to explain behavior to a person who
needs to call, maintain or troubleshoot the code. This guide complements the
repository's policy; it does not override stronger project requirements.

## Content

Start with purpose and observable behavior. Add the information that matters:

- Input meaning, valid ranges, units, defaults and preconditions.
- Return meaning, empty/absent results, ownership and resource lifetime.
- Side effects, persistent changes, external calls and security assumptions.
- Errors, their conditions, and safe caller responses supported by the code.
- Concurrency, cancellation, retry, ordering and idempotency guarantees where real.
- Algorithm invariants, choice of approach, limits and important trade-offs.

Explain complex steps beside the implementation. Keep long operational procedures
in linked guides. Do not repeat each statement or duplicate types already visible
in a typed signature unless the documentation tool requires them.

For example, "Return the value" is not enough for an optional lookup. A useful
summary might be "Return the cached record, or None when the key is absent."
Only add expiry or concurrency guarantees if the implementation establishes them.

## Native conventions

Preserve the established convention and verify toolchain compatibility. This list
is guidance, not an exhaustive set of supported languages or automated checks.

| Language | Convention |
| --- | --- |
| Python | [PEP 257](https://peps.python.org/pep-0257/) structure plus the project's Google, NumPy or reStructuredText section style. PEP 257 does not prescribe section markup. |
| JavaScript | [JSDoc](https://jsdoc.app/about-getting-started), retaining type tags needed by the project. |
| TypeScript | [TSDoc](https://tsdoc.org/) or existing compatible JSDoc tooling; avoid duplicating declared types without a tooling reason. |
| Go | [Go doc comments](https://go.dev/doc/comment), including package and exported-declaration descriptions. |
| Rust | [rustdoc](https://doc.rust-lang.org/rustdoc/how-to-write-documentation.html), with examples and relevant error, panic or safety sections. |
| Java | [Javadoc](https://docs.oracle.com/en/java/javase/25/docs/specs/javadoc/doc-comment-spec.html), using syntax supported by the project's JDK. |
| C# | [XML documentation comments](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/xmldoc/). |
| C/C++ | The project's convention, such as [Doxygen](https://www.doxygen.nl/manual/docblocks.html); Doxygen is not a language requirement. |
| Other languages | The established ecosystem and repository convention, recorded with the configured validation command. |

For shell, SQL and infrastructure code, use supported comments and native
description fields. For formats that cannot contain comments, use adjacent
documentation. Never make JSON or another strict format invalid to add prose.

## Review and validation

Check required declarations, non-obvious algorithms and failure paths, not just
comment counts. Keep examples and parameter names synchronized with the code.
Run existing documentation lint, builds and example tests where configured.
Distinguish language coverage and syntax checks from a human assessment of meaning.

An empty block, "TODO", or a renamed signature is not useful documentation.
Conversely, an accurate one-line docstring can be enough for simple public code.

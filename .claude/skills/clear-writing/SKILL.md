---
name: clear-writing
description: Write and review clear, accurate documentation, docstrings, code comments, procedures, and technical explanations. Combine prose guidance with the repository's language-specific documentation conventions.
---

# Clear writing

Help a reader understand the behavior, decision or action without reconstructing
it from scattered context. Apply this skill to source documentation as well as
guides and explanations. It does not require a particular agent host, model,
network connection or personal installation.

## Establish the meaning

Identify the audience, purpose and main point before editing sentences. Read the
whole passage. Preserve the supplied meaning; flag missing facts rather than
inventing causes, symptoms, actors, measurements, guarantees or recovery steps.
User-requested voice and established technical terminology take precedence over
stylistic defaults.

## Organize around the reader's needs

- Lead with the answer or purpose when context permits. Put prerequisites and
  consequential warnings before the action they govern.
- Keep evidence close to a claim. Distinguish observations, recommendations and
  uncertainty; a plausible explanation is not a verified fact.
- Give each paragraph a purpose. Use headings and lists to expose structure, not
  to fragment a simple explanation. Number steps only when order matters.
- Explain what a reader needs to use, maintain or diagnose the system. Link to a
  durable detailed explanation instead of maintaining conflicting copies.

## Prefer direct, precise prose

Use familiar words when they retain the technical meaning. Remove filler and
stale metaphors. Prefer active voice when the responsible actor is known, but
never invent an actor to avoid passive voice. Keep necessary qualifications and
useful repetition. A shorter sentence is not automatically clearer.

Keep one stable term for one concept. Explain unfamiliar domain language rather
than replacing it with a misleading everyday synonym. Avoid promotional claims,
unnecessary idioms and claims that a reader's task is easy. Do not rewrite already
clear text merely to demonstrate editing.

## Apply the right technical format

For docstrings, API comments and algorithm explanations, read
[Source documentation](references/source-documentation.md). Follow the existing
language and toolchain conventions; writing guidance does not replace required
tags, type information, comment delimiters or executable examples.

Use code formatting for identifiers, commands and literal values. Make links
describe their destination. Keep instructions executable and examples synthetic.
Do not expose secrets, private records or machine-specific paths in examples.

## Check meaning and evidence

Compare the result with the source and implementation. Preserve negation,
conditions, exceptions, causal relationships, ordering, units, dates, bounds and
claim strength. For example, "retry at most twice" must not become "retry twice,"
and "may reduce latency" must not become a measured performance claim.

Retain distinctions such as authentication versus authorization. If an actor is
unknown, "the file was deleted" is more accurate than naming an administrator.
If the input says a fix resolved a problem but omits the problem's name, request
that name; do not invent a symptom or change the assertion into uncertainty.

Review documentation against actual behavior and tests. Structural lint cannot
prove accuracy, useful troubleshooting advice or invocation of this skill. Report
those evidence limits explicitly.

## Deliver the requested result

For a draft or rewrite, return the finished text and only necessary caveats. For
a review, prioritize meaning, structure and consequential omissions; give concrete
corrections. Do not add a catalogue of optional synonym changes.

See [Provenance](references/provenance.md) for sources and attribution. Routine
use is offline; consult current authoritative documentation when API or toolchain
details need verification.

# Security model

## Assets

- source code, history, releases, and package integrity;
- credentials and hosted-service authority;
- user, customer, and test data;
- developer machines and CI runners;
- agent instructions, skills, MCP servers, hooks, and generated evidence.

## Trust boundaries

Repository content crosses into agent context; agent output crosses into files and
commands; tools cross into the local machine and external services; pull requests
and dependencies cross from external contributors; CI crosses into protected
tokens and release systems.

## Primary threats

- prompt injection in issues, documentation, dependencies, web pages, or tool data;
- malicious or compromised skills, plugins, hooks, MCP servers, and actions;
- secret or private-data disclosure through logs, prompts, diffs, or evidence;
- excessive permissions and unauthorized external mutations;
- dependency substitution, mutable automation references, and generated-file drift;
- destructive commands, path traversal, shell injection, or unsafe target handling;
- false assurance from source reasoning, skipped tests, stale hosted state, or a
  pushed-but-unmerged artifact.

## Baseline controls

- human instructions and repository policy bound authority;
- canonical files are reviewable and protected with CODEOWNERS as the project grows;
- initializer refuses non-empty targets and never deletes existing content;
- adapters are generated and drift-checked;
- hooks are optional while CI repeats invariants;
- secrets remain outside Git and evidence is sanitized;
- MCP tools use strict schemas and least privilege;
- validation and delivery states are reported precisely;
- dependency, action, and plugin provenance is reviewed before adoption.

## Residual risk

PARK cannot control a client's hidden system instructions, model behavior, sandbox,
account permissions, context truncation, or support for a standard. Human review,
branch protection, CI, environment isolation, and least-privileged credentials
remain necessary.

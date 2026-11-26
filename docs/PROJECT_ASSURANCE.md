# Project assurance

Run `make init` in a fresh clone created from the template. The interview asks for the project name, description, languages, workload contexts, assurance level and license. Press Enter to accept a suggested level. Combining contexts chooses the strongest suggestion. A financial web service receives both web authorization and transaction integrity requirements. Use commas for multiple languages or contexts. Use `undecided` when selecting a language later. A second `make init` reports that setup is complete. The first project commit includes its own initialization handoff and executable acceptance cases.

To create a separate directory from a PARK Git checkout, run `python3 scripts/create_project.py ../my-project --interactive`. The generator uses Git's tracked file inventory to keep private workspace files out of the project. For automation, supply `--name`, `--description`, `--license`, `--languages`, `--context` and `--assurance`. Existing automation that supplies only identity and license gets the CLI context, undecided languages and low assurance. Use a fresh clean clone for in-place setup.

Each project starts with a profile in `.park/profile.json`, a constitution in `.specify/memory/constitution.md`, official Spec Kit document templates and a local Squad coordinator. `make feature NAME=example` scaffolds the spec, plan and tasks without a tool download. Before implementation, translate accepted outcomes into the executable cases described in the [handoff guide](SESSION_HANDOFF.md). Edit the constitution and profile together through review as project scope changes. Retain applicable tests when changing assurance levels.

The offline scaffold uses [Spec Kit v1.4.4](https://github.com/github/spec-kit/tree/v1.4.4) and local casting assets from [Squad v2.0.0](https://github.com/github/squad/tree/v2.0.0). Their licenses accompany the generated files. Install the corresponding CLI for its additional commands. Squad starts with an empty roster. Add members as work warrants and keep provider access, MCP servers and hosted automation opt-in.

## What each level requires

| Level | Controls added | Evidence |
| --- | --- | --- |
| Low | Gitleaks scans the committed files and the history reachable from the selected commit. Native Semgrep runs repository rules and Trivy checks dependencies and infrastructure. CI exercises the handoff's named acceptance cases. | Commit SHA, scanner results and individual test outcomes. The baseline uses free scanner CLIs. |
| Medium | Generate a CycloneDX software bill of materials (SBOM). | CI retains the inventory for the scanned revision after successful checks. |
| High | On a manual run from the default branch, package the source on a GitHub-hosted runner, attest the archive and verify its digest, source commit, repository and signing workflow. | A verified source archive and signed provenance. |
| Critical | Require a qualified reviewer distinct from the PR author, a protected release environment with self-review and admin bypass disabled, and a successful recovery exercise within 90 days. | Exact-head PR approval, environment approval and a dated recovery record. |

Run `make check` for the offline contract and test suite. Run `make assurance` to scan the current commit with the latest stable Gitleaks, native Semgrep and Trivy. Hosted CI verifies upstream artifact digests before extraction. See the [local installation guide](LOCAL_PUSH_GATE.md). Trivy needs vulnerability data. Scanner unavailability fails the job. Add language-specific checks to `make check` when adding a toolchain. Inspect the bundled Semgrep rules for coverage of your stack, especially when selecting a language without a dedicated rule.

## Activate hosted enforcement

Configure the generated repository's review identities, require pull requests and the `validate`, `assurance` and `Owner review gate` checks on its default branch. Protect changes to the profile, review policy, scanner rules and workflow files through trusted ownership and branch rules. Review the available protections on your GitHub plan. The generator writes local policy and has no GitHub administration access. See the [owner review setup](OWNER_REVIEW_POLICY.md).

For a critical release, create the `critical-release` environment, select qualified reviewers, enable prevention of self-review and disallow administrator bypass. Record an actual recovery exercise in `.park/recovery.json` with string fields `date` (YYYY-MM-DD), `environment`, `procedure`, `evidence`, `reviewer` and `result` (passed). Use a sanitized run identifier. Review the linked evidence before accepting the record. The readiness check validates these fields and the date. GitHub enforces the separate release approval.

The included workflow implements hosted signed provenance for its source archive, targeting [SLSA Build L2](https://slsa.dev/spec/v1.2/build-levels). For a shipped binary, container or package, feed its actual build output into attestation and verify that exact digest before publication or deployment. Record the builder and distribution evidence for each artifact before claiming a level. GitHub documents the plan and visibility requirements for [artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations).

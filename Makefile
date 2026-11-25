.PHONY: doctor validate-contract sync-agent-adapters check-agent-adapters check-code-documentation check

doctor:
	python3 scripts/agent/doctor.py

validate-contract:
	python3 scripts/agent/validate_contract.py

sync-agent-adapters:
	python3 scripts/agent/sync_adapters.py

check-agent-adapters:
	python3 scripts/agent/sync_adapters.py --check

check-code-documentation:
	python3 scripts/agent/check_code_documentation.py

check:
	python3 scripts/agent/check.py

.PHONY: init feature
init:
	@if test -f .portable-agent-template; then python3 scripts/configure_project.py --interactive; elif test -f .park/profile.json; then echo "Project initialized. See .specify/memory/constitution.md"; else echo "Project profile missing" >&2; exit 1; fi

export NAME
feature:
	python3 scripts/agent/feature.py

.PHONY: assurance
assurance:
	python3 scripts/ci/assurance.py scan

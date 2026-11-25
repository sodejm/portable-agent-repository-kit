.PHONY: init doctor validate-contract sync-agent-adapters check-agent-adapters check-code-documentation check

doctor:
	python3 scripts/agent/doctor.py

init:
	@test -f .portable-agent-template || { echo "make init requires an unconfigured PARK template (missing .portable-agent-template)." >&2; exit 1; }
	python3 scripts/configure_project.py --interactive

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

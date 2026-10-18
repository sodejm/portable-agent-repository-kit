#!/usr/bin/env python3
"""Private-index Git transactions. Python 3.11+, Git; no third-party packages."""
from __future__ import annotations
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import uuid

class CouncilError(RuntimeError):
    pass

def run(argv, cwd=None, env=None, input=None):
    p = subprocess.run([str(x) for x in argv], cwd=cwd, env=env, input=input,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise CouncilError(p.stderr.decode(errors="replace").strip() or f"Command failed: {argv[0]}")
    return p.stdout

def git(root, *args, env=None, input=None):
    return run(["git", "-c", "core.hooksPath=/dev/null", "-C", root, *args], env=env, input=input)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def write_json(path, obj):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as out:
        json.dump(obj, out, indent=2, sort_keys=True)
        out.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)

@contextlib.contextmanager
def lock(path):
    with open(path, "a+b") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CouncilError("Another council operation owns this lock; no changes made.")
        try:
            yield fh
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)

def paths(repo):
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    common = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip())
    state = common / "goblin-council"
    state.mkdir(mode=0o700, exist_ok=True)
    if state.is_symlink():
        raise CouncilError("State directory must not be a symlink")
    os.chmod(state, 0o700)
    return root, state

def supported(root):
    git(root, "rev-parse", "--verify", "HEAD")
    if git(root, "ls-files", "-u"):
        raise CouncilError("Resolve the existing index conflicts first")
    if any(line.startswith(b"160000 ") for line in git(root, "ls-files", "--stage").splitlines()):
        raise CouncilError("Submodules are not supported by this transaction implementation")
    p = subprocess.run(["git", "-C", str(root), "config", "--bool", "core.sparseCheckout"], capture_output=True)
    if p.stdout.strip() == b"true":
        raise CouncilError("Sparse checkouts are not supported")
    flags = git(root, "ls-files", "-v", "-z").split(b"\0")
    if any(x and (x[:1] == b"S" or x[:1].islower()) for x in flags):
        raise CouncilError("Clear skip-worktree/assume-unchanged flags before using a transaction")

def index_path(root):
    return Path(git(root, "rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())

def tree(root, state):
    """Snapshot tracked and nonignored untracked contents without changing the real index."""
    fd, name = tempfile.mkstemp(prefix="index-", dir=state)
    os.close(fd)
    p = Path(name)
    try:
        env = dict(os.environ, GIT_INDEX_FILE=str(p), GIT_OPTIONAL_LOCKS="0")
        # Preserve tracked-path membership (including staged/ignored additions),
        # but discard stat caches. Copying an index changes its mtime and can
        # defeat Git's racy-index protection for rapid same-size file edits.
        entries = git(root, "ls-files", "--stage", "-z")
        p.unlink()
        git(root, "read-tree", "--empty", env=env)
        git(root, "update-index", "--no-split-index", env=env)
        git(root, "update-index", "-z", "--index-info", env=env, input=entries)
        git(root, "add", "-A", "--", ".", env=env)
        return git(root, "write-tree", env=env).decode().strip()
    finally:
        p.unlink(missing_ok=True)
        Path(name + ".lock").unlink(missing_ok=True)

def fingerprint(root, state):
    for _ in range(3):
        head = git(root, "rev-parse", "HEAD").decode().strip()
        idx = index_path(root)
        before = sha(idx.read_bytes()) if idx.exists() else None
        raw = raw_manifest(root)
        content = tree(root, state)
        after = sha(idx.read_bytes()) if idx.exists() else None
        if before == after and head == git(root, "rev-parse", "HEAD").decode().strip() and content == tree(root, state) and raw == raw_manifest(root):
            return {"head": head, "index_sha256": before, "tree": content, "raw": raw}
    raise CouncilError("Workspace changed during snapshot; retry after the concurrent edit finishes")

def raw_manifest(root):
    """Detect byte changes hidden by Git normalization; omit ignored and absent paths."""
    names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    manifest = {}
    for name in sorted(set(names.split(b"\0")) - {b""}):
        path = Path(root) / os.fsdecode(name)
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            entry = ["symlink", sha(os.fsencode(os.readlink(path))) ]
        elif stat.S_ISREG(mode):
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            entry = ["file", bool(mode & 0o111), digest]
        else:
            raise CouncilError(f"Unsupported non-file path: {os.fsdecode(name)}")
        manifest[os.fsdecode(name)] = entry
    return manifest

def commit(root, tree_id, parent):
    env = dict(os.environ, GIT_AUTHOR_NAME="Goblin Council", GIT_AUTHOR_EMAIL="goblin@localhost",
               GIT_COMMITTER_NAME="Goblin Council", GIT_COMMITTER_EMAIL="goblin@localhost")
    return git(root, "commit-tree", tree_id, "-p", parent, env=env,
               input=b"Private Goblin Council snapshot; not a delivery commit\n").decode().strip()

def init(repo):
    root, state = paths(repo)
    supported(root)
    with lock(state / "promotion.lock"):
        baseline = fingerprint(root, state)
        rid = str(uuid.uuid4())
        run_dir = state / rid
        run_dir.mkdir(mode=0o700)
        base_commit = commit(root, baseline["tree"], baseline["head"])
        prefix = f"refs/goblin-council/{rid}"
        git(root, "update-ref", prefix + "/base", base_commit)
        container = Path(tempfile.mkdtemp(prefix=f"goblin-{rid}-")).resolve()
        candidate = container / "candidate"
        m = {"id": rid, "root": str(root), "run_dir": str(run_dir), "container": str(container),
             "candidate": str(candidate), "baseline": baseline, "base_commit": base_commit,
             "ref_prefix": prefix, "status": "INITIALIZING", "generation": 0, "reviews": [], "validation": None}
        write_json(run_dir / "state.json", m)
        try:
            git(root, "worktree", "add", "--detach", candidate, base_commit)
            if raw_manifest(candidate) != baseline["raw"]:
                raise CouncilError("Git checkout changed raw contents or modes (filters/EOL); snapshot retained, no drafting")
            if fingerprint(root, state) != baseline:
                raise CouncilError("Primary workspace changed while the candidate was created")
            m["status"] = "DRAFTING"
            write_json(run_dir / "state.json", m)
        except BaseException:
            m["status"] = "INIT_FAILED"
            write_json(run_dir / "state.json", m)
            raise
        return m

class Transaction:
    def __init__(self, repo, run_id):
        if str(uuid.UUID(run_id)) != run_id:
            raise CouncilError("Invalid run ID")
        _, self.state = paths(repo)
        self.directory = self.state / run_id
        self.file = self.directory / "state.json"
        self.m = json.loads(self.file.read_text())
        self.root = Path(self.m["root"])
        if paths(self.root)[1] != self.state:
            raise CouncilError("Run belongs to another repository")
        self.container = Path(self.m["container"])
        if self.container.is_symlink() or not self.container.name.startswith(f"goblin-{run_id}-"):
            raise CouncilError("Invalid run directory")
        self.candidate = self.container / "candidate"

    def lease(self):
        return lock(self.directory / "run.lock")

    def save(self):
        write_json(self.file, self.m)

    def trace(self, event, **fields):
        from datetime import datetime, timezone
        with open(self.directory / "trace.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"event": event, "run_id": self.m["id"],
                               "at": datetime.now(timezone.utc).isoformat(), **fields}, sort_keys=True) + "\n")

    def remove_checkout(self, path):
        path = Path(path)
        if path.parent != self.container or path.is_symlink():
            raise CouncilError("Refusing cleanup outside this run")
        registered = git(self.root, "worktree", "list", "--porcelain", "-z")
        marker = b"worktree " + os.fsencode(path) + b"\0"
        if marker in registered:
            git(self.root, "worktree", "remove", "--force", path)
        elif path.exists():
            raise CouncilError(f"Unregistered directory retained for inspection: {path}")

    def reset(self):
        self.remove_checkout(self.candidate)
        git(self.root, "worktree", "add", "--detach", self.candidate, self.m["base_commit"])
        if raw_manifest(self.candidate) != self.m["baseline"]["raw"]:
            raise CouncilError("Reset checkout differs from original raw snapshot; no drafting")
        self.m.update(status="DRAFTING", reviews=[], validation=None)
        self.save()
        self.trace("RESET_TO_ORIGINAL_BASELINE")

    def freeze(self):
        content = tree(self.candidate, self.state)
        candidate_commit = commit(self.root, content, self.m["base_commit"])
        changed = git(self.root, "diff", "--name-only", "-z", self.m["base_commit"], candidate_commit).split(b"\0")
        for name in changed:
            parts = os.fsdecode(name).split("/")
            if any(p.lower() in {".git", ".codex", ".agents"} for p in parts):
                raise CouncilError("Candidate modifies protected orchestration paths; use primary-thread implementation")
        self.m["generation"] += 1
        gen = self.m["generation"]
        review = self.container / f"review-{gen}"
        git(self.root, "update-ref", self.m["ref_prefix"] + f"/candidate-{gen}", candidate_commit)
        git(self.root, "worktree", "add", "--detach", review, candidate_commit)
        raw = raw_manifest(self.candidate)
        if raw_manifest(review) != raw:
            raise CouncilError("Git checkout changed candidate raw contents or modes; no review or promotion")
        patch = git(self.root, "diff", "--binary", "--full-index", "--no-ext-diff", "--no-textconv",
                    self.m["base_commit"], candidate_commit)
        patch_path = self.directory / f"candidate-{gen}.patch"
        patch_path.write_bytes(patch)
        self.m.update(status="FROZEN", candidate_id=content, candidate_commit=candidate_commit,
                      review=str(review), patch=str(patch_path), patch_sha256=sha(patch), candidate_raw=raw, reviews=[], validation=None)
        self.save()
        self.trace("FROZEN", candidate_id=content, generation=gen)
        return self.m

    def integrity(self):
        if "candidate_id" not in self.m:
            raise CouncilError("No frozen candidate")
        if sha(Path(self.m["patch"]).read_bytes()) != self.m["patch_sha256"]:
            raise CouncilError("Frozen patch changed")
        if tree(Path(self.m["review"]), self.state) != self.m["candidate_id"]:
            raise CouncilError("Review checkout changed")
        if tree(self.candidate, self.state) != self.m["candidate_id"]:
            raise CouncilError("Candidate changed after review")
        if any(raw_manifest(p) != self.m["candidate_raw"] for p in (self.candidate, Path(self.m["review"]))):
            raise CouncilError("Candidate or review raw contents changed")

    def record_review(self, role, report):
        self.integrity()
        allowed = {"candidate_id", "verdict", "defects", "repair_plan", "restart_required"}
        if set(report) != allowed or report["candidate_id"] != self.m["candidate_id"]:
            raise CouncilError("Malformed or stale review")
        if report["verdict"] not in {"PASS", "ESCALATE"} or type(report["restart_required"]) is not bool:
            raise CouncilError("Invalid verdict")
        if not isinstance(report["defects"], list) or not isinstance(report["repair_plan"], list):
            raise CouncilError("Invalid review arrays")
        for defect in report["defects"]:
            if not isinstance(defect, dict) or set(defect) != {"severity", "path", "line", "evidence", "fix"}:
                raise CouncilError("Malformed defect")
            if defect["severity"] not in {"blocking", "advisory"} or type(defect["line"]) is not int or defect["line"] < 0:
                raise CouncilError("Malformed defect severity/location")
            if not all(isinstance(defect[k], str) for k in ("path", "evidence", "fix")):
                raise CouncilError("Malformed defect evidence")
        if not all(isinstance(x, str) for x in report["repair_plan"]):
            raise CouncilError("Malformed repair plan")
        if report["verdict"] == "PASS" and (report["restart_required"] or any(d["severity"] == "blocking" for d in report["defects"])):
            raise CouncilError("PASS cannot contain blocking defects or request a restart")
        self.m["reviews"].append({"role": role, **report})
        self.save()
        self.trace("REVIEW", role=role, verdict=report["verdict"], candidate_id=report["candidate_id"])

    def promote(self):
        self.integrity()
        validation = self.m.get("validation") or {}
        judges = [r for r in self.m["reviews"] if r["role"] == "goblin-judge"]
        if not judges or judges[-1]["verdict"] != "PASS":
            raise CouncilError("Latest judge must PASS this candidate")
        if validation.get("candidate_id") != self.m["candidate_id"] or validation.get("passed") is not True:
            raise CouncilError("Validation has not passed for this candidate")
        with lock(self.state / "promotion.lock"):
            if fingerprint(self.root, self.state) != self.m["baseline"]:
                self.m["status"] = "PROMOTION_BLOCKED"
                self.save()
                raise CouncilError("Primary HEAD, index, or working contents changed; candidate retained")
            patch = Path(self.m["patch"]).read_bytes()
            if patch:
                git(self.root, "apply", "--check", "--binary", "--whitespace=nowarn", input=patch)
            self.m["status"] = "PROMOTING"
            self.save()  # Crash journal: never blindly repeat an interrupted apply.
            if patch:
                git(self.root, "apply", "--binary", "--whitespace=nowarn", input=patch)
            after = fingerprint(self.root, self.state)
            expected = {**self.m["baseline"], "tree": self.m["candidate_id"], "raw": self.m["candidate_raw"]}
            if after != expected:
                self.m["status"] = "PROMOTION_NEEDS_INSPECTION"
                self.save()
                raise CouncilError("Post-apply state differs; retained evidence; no destructive rollback attempted")
            self.m["status"] = "PROMOTED"
            self.save()
            self.trace("PROMOTED", candidate_id=self.m["candidate_id"])
        self.cleanup()

    def cleanup(self):
        for p in sorted(self.container.iterdir()) if self.container.exists() else []:
            if p.name == "candidate" or p.name.startswith(("review-", "validation-")):
                self.remove_checkout(p)
        # No recursive deletion fallback. Unknown files leave a recoverable directory.
        if self.container.exists() and not list(self.container.iterdir()):
            self.container.rmdir()
        refs = git(self.root, "for-each-ref", "--format=%(refname)", self.m["ref_prefix"] + "/").decode().splitlines()
        for ref in refs:
            git(self.root, "update-ref", "-d", ref)

    def abandon(self):
        if self.m["status"] in {"PROMOTING", "PROMOTION_NEEDS_INSPECTION"}:
            raise CouncilError("Inspect the interrupted promotion before cleanup; evidence retained")
        self.cleanup()
        self.m["status"] = "ABANDONED"
        self.save()
        self.trace("ABANDONED")

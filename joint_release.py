#!/usr/bin/env python3
"""Joint release and commit hygiene for the Agent Factory extension and plugin.

The extension and every plugin repository (plugin source plus each generated host)
must always release at one identical base version. MCP is released independently
and is only touched by the trailer commands. Commits must never carry AI
co-author trailers.

Commands (all default to read-only; nothing is pushed or published without --yes):

  doctor                Check tools, repositories, remotes, hooks and versions.
                        --fix sets host fetch URLs to HTTPS (push stays SSH),
                        installs hooks and gives the parent branch an upstream.
  hooks                 Install commit-msg (strip AI trailers) and pre-push
                        (reject AI trailers) hooks in every repository.
  scan                  Report AI co-author trailers in local and remote history.
  release [VERSION]     Confirm and run the joint release (VERSION defaults to
                        the next patch; summaries come from commit subjects;
                        --plan prints the plan, --yes skips the prompt):
                        tests -> plugin source + hosts commit/push -> version
                        preflight -> extension release (VSIX, stops before
                        Marketplace) -> GitHub releases for source, hosts and
                        extension -> parent submodule pointers -> final verify.
                        Every step detects completed work, so rerunning resumes.
  setup-token           Store the signed-in gh token as the RELEASE_TOKEN
                        secret; signs in through the browser when needed.
  strip-trailers        Plan removing AI co-author trailers from history; --yes
                        rewrites only affected commits, remaps parent gitlinks,
                        force-pushes with lease and fixes release-note hashes.

Repositories: the parent checkout (this file's directory), its `plugin`,
`extension` and `mcp` submodules, and one sibling clone per plugin host declared
in plugin/distribution/package.json. Host clones are discovered among the
parent's sibling directories by their origin URL; pass --checkout HOST=PATH to
override. See docs/skills/rule-release-management/SKILL.md for the procedure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "plugin"
EXTENSION = ROOT / "extension"
MCP = ROOT / "mcp"
HOST_NAMES = {"codex": "Codex", "claude": "Claude Code", "antigravity": "Antigravity"}
HOST_MANIFESTS = {"codex": ".codex-plugin/plugin.json", "claude": ".claude-plugin/plugin.json", "antigravity": "plugin.json"}
TRAILER = re.compile(r"^co-authored-by:.*(claude|anthropic\.com)|generated with \[claude code\]", re.I | re.M)
TRAILER_LINE = re.compile(rb"^(co-authored-by:[^\n]*(claude|anthropic\.com)[^\n]*|[^\n]*generated with \[claude code\][^\n]*)\n?", re.I | re.M)
HOOK_MARK = "# agent-factory-joint-release hook"
COMMIT_MSG_HOOK = f"""#!/bin/sh
{HOOK_MARK}: strip AI co-author trailers from every commit message.
tmp="$1.af-tmp"
grep -Eiv '^co-authored-by:.*(claude|anthropic\\.com)|generated with \\[claude code\\]' "$1" > "$tmp"
mv "$tmp" "$1"
"""
PRE_PUSH_HOOK = f"""#!/bin/sh
{HOOK_MARK}: refuse to push commits carrying AI co-author trailers.
zero=0000000000000000000000000000000000000000
while read -r lref lsha rref rsha; do
  [ "$lsha" = "$zero" ] && continue
  if [ "$rsha" = "$zero" ] || ! git cat-file -e "$rsha" 2>/dev/null; then
    set -- "$lsha" --not --remotes="$1"
  else
    set -- "$rsha..$lsha"
  fi
  if git log --format=%B "$@" | grep -Eiq '^co-authored-by:.*(claude|anthropic\\.com)|generated with \\[claude code\\]'; then
    echo "pre-push: $lref contains AI co-author trailers; run joint_release.py strip-trailers" >&2
    exit 1
  fi
done
"""


class Failure(SystemExit):
    def __init__(self, message: str):
        super().__init__(f"error: {message}")


# --------------------------------------------------------------------- helpers

def run(args, cwd=ROOT, check=True, env=None, capture=True, data=None):
    result = subprocess.run(args, cwd=cwd, env=env, input=data, capture_output=capture, text=data is None or isinstance(data, str))
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() if capture else ""
        raise Failure(f"{' '.join(map(str, args))} failed in {cwd}: {detail[-2000:]}")
    return result


def git(cwd, *args, check=True):
    return run(["git", "-C", str(cwd), *args], check=check).stdout.strip()


def step(title):
    print(f"\n== {title}", flush=True)


def clean_env():
    """The Main chat exports AGENT_FACTORY_* (e.g. CODEX_POOL); tests must not inherit them."""
    return {k: v for k, v in os.environ.items() if not k.startswith("AGENT_FACTORY_")}


def slug(cwd):
    url = git(cwd, "remote", "get-url", "origin")
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(\.git)?/?$", url)
    if not match:
        raise Failure(f"{cwd} origin is not a GitHub repository: {url}")
    return match.group(1)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def source_meta():
    return read_json(SOURCE / "distribution" / "package.json")


def discover_hosts(overrides):
    meta = source_meta()
    found = {}
    for pair in overrides or []:
        host, _, path = pair.partition("=")
        if host not in meta["hosts"] or not path:
            raise Failure(f"--checkout must be HOST=PATH for a declared host, got {pair}")
        found[host] = Path(path).expanduser().resolve()
    wanted = {h: v["repository"].rstrip("/").removesuffix(".git").split("github.com/")[-1]
              for h, v in meta["hosts"].items() if h not in found}
    for candidate in sorted(ROOT.parent.iterdir()):
        if not wanted or not (candidate / ".git").exists() or candidate == ROOT:
            continue
        try:
            name = slug(candidate)
        except (Failure, SystemExit):
            continue
        for host, repo in list(wanted.items()):
            if name.lower() == repo.lower():
                found[host] = candidate
                del wanted[host]
    if wanted:
        raise Failure(f"No sibling clone found for host(s) {', '.join(sorted(wanted))}; clone them next to "
                      f"{ROOT.name} or pass --checkout HOST=PATH.")
    return dict(sorted(found.items()))


def repositories(hosts, include_mcp=True):
    repos = {"parent": ROOT, "plugin": SOURCE, "extension": EXTENSION}
    if include_mcp and (MCP / ".git").exists():  # CI clones only the release repositories
        repos["mcp"] = MCP
    repos.update({f"host:{h}": p for h, p in hosts.items()})
    return repos


def hosts_repo_flags(hosts):
    return [a for h, p in hosts.items() for a in ("--checkout", f"{h}={p}")]


def remote_has_trailers(cwd, ref="origin/main"):
    return len(TRAILER.findall(git(cwd, "log", ref, "--format=%B", check=False)))


def base_version(value):
    return value.split("+", 1)[0]


# ---------------------------------------------------------------------- doctor

def cmd_doctor(args):
    hosts = discover_hosts(args.checkout)
    problems = []
    step("Tools")
    for tool in ("git", "gh", "node", "npm", "uv", "claude"):
        where = shutil.which(tool)
        print(f"{tool:8} {where or 'MISSING'}")
        if not where and tool != "claude":
            problems.append(f"{tool} is not installed")
    if shutil.which("gh") and run(["gh", "auth", "status"], check=False).returncode != 0:
        problems.append("gh is not authenticated")

    step("Repositories")
    for name, path in repositories(hosts).items():
        git(path, "fetch", "-q", "origin", "--tags", "--force", check=False)
        branch = git(path, "branch", "--show-current")
        upstream = git(path, "rev-parse", "--abbrev-ref", "@{upstream}", check=False)
        dirty = git(path, "status", "--porcelain")
        ahead = git(path, "rev-list", "--count", "origin/main..HEAD", check=False) or "?"
        behind = git(path, "rev-list", "--count", "HEAD..origin/main", check=False) or "?"
        hooks = hooks_state(path)
        print(f"{name:18} {branch or '(detached)':10} upstream={upstream or '-':12} ahead={ahead} behind={behind} "
              f"dirty={len(dirty.splitlines())} hooks={hooks}")
        if behind not in ("0", "?"):
            problems.append(f"{name} is behind origin/main")
        if hooks != "ok":
            problems.append(f"{name} hooks {hooks}")
        if name.startswith("host:"):
            fetch = git(path, "remote", "get-url", "origin")
            if not fetch.startswith("https://"):
                problems.append(f"{name} fetch URL must be HTTPS for distribution/release.py ({fetch})")
                if args.fix:
                    push = fetch
                    https = f"https://github.com/{slug(path)}"
                    git(path, "remote", "set-url", "origin", https)
                    git(path, "remote", "set-url", "--push", "origin", push)
                    print(f"  fixed: fetch {https}, push {push}")
        if name == "parent" and branch and not upstream and args.fix:
            git(path, "branch", "--set-upstream-to=origin/main")
            print("  fixed: upstream origin/main")
        unpushed = git(path, "log", "--format=%B", "HEAD", "--not", "--remotes=origin", check=False)
        if TRAILER.search(unpushed):
            problems.append(f"{name} has unpushed commits with AI co-author trailers")
    if args.fix:
        install_hooks(hosts)

    step("Versions")
    ext_version = read_json(EXTENSION / "package.json")["version"]
    print(f"extension          {ext_version}")
    print(f"plugin source      {source_meta()['version']}")
    for host, path in hosts.items():
        manifest = path / HOST_MANIFESTS.get(host, "plugin.json")
        version = read_json(manifest)["version"] if manifest.exists() else "?"
        print(f"host:{host:13} {version}")
        if base_version(version) != ext_version:
            problems.append(f"host {host} {version} does not match extension {ext_version}")
    if source_meta()["version"] != ext_version:
        problems.append(f"plugin source {source_meta()['version']} does not match extension {ext_version}")

    step("Result")
    for problem in dict.fromkeys(problems):
        print(f"- {problem}")
    print("OK" if not problems else f"{len(set(problems))} problem(s); rerun with --fix for remotes and hooks.")
    return 1 if problems else 0


# ----------------------------------------------------------------------- hooks

def hook_dir(path):
    return (path / git(path, "rev-parse", "--git-path", "hooks")).resolve()


def hooks_state(path):
    directory = hook_dir(path)
    states = []
    for name in ("commit-msg", "pre-push"):
        hook = directory / name
        if not hook.exists():
            states.append(f"{name}:missing")
        elif HOOK_MARK not in hook.read_text(errors="replace"):
            states.append(f"{name}:foreign")
    return "ok" if not states else ",".join(states)


def install_hooks(hosts):
    for name, path in repositories(hosts).items():
        directory = hook_dir(path)
        directory.mkdir(exist_ok=True)
        for hook, body in (("commit-msg", COMMIT_MSG_HOOK), ("pre-push", PRE_PUSH_HOOK)):
            target = directory / hook
            if target.exists() and HOOK_MARK not in target.read_text(errors="replace"):
                print(f"{name}: kept existing {hook} (not ours); merge the trailer rule into it manually")
                continue
            target.write_text(body)
            target.chmod(0o755)
        print(f"{name}: hooks {hooks_state(path)}")


def cmd_hooks(args):
    install_hooks(discover_hosts(args.checkout))
    return 0


# ------------------------------------------------------------------------ scan

def cmd_scan(args):
    hosts = discover_hosts(args.checkout)
    total = 0
    for name, path in repositories(hosts).items():
        git(path, "fetch", "-q", "origin", "--tags", "--force", check=False)
        local = len(TRAILER.findall(git(path, "log", "--branches", "--tags", "--format=%B", check=False)))
        remote = len(TRAILER.findall(git(path, "log", "--remotes=origin", "--format=%B", check=False)))
        total += local + remote
        print(f"{name:18} local={local} remote={remote}")
    print("clean" if not total else "AI co-author trailers found; run strip-trailers")
    return 1 if total else 0


# ------------------------------------------------------------- strip-trailers

class Rewriter:
    """Recreate only commits whose message, parents or submodule gitlinks change."""

    def __init__(self, path: Path, gitlinks: dict[str, str]):
        self.path, self.gitlinks, self.trees = path, gitlinks, {}
        self.cat = subprocess.Popen(["git", "-C", str(path), "cat-file", "--batch"],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def read(self, sha):
        self.cat.stdin.write(sha.encode() + b"\n")
        self.cat.stdin.flush()
        kind, size = self.cat.stdout.readline().split()[1:3]
        data = self.cat.stdout.read(int(size))
        self.cat.stdout.read(1)
        return kind.decode(), data

    def write(self, kind, data):
        return subprocess.run(["git", "-C", str(self.path), "hash-object", "-t", kind, "-w", "--stdin"],
                              input=data, capture_output=True, check=True).stdout.decode().strip()

    def tree(self, sha):
        if not self.gitlinks:
            return sha
        if sha not in self.trees:
            _, data = self.read(sha)
            out, i, changed = bytearray(), 0, False
            while i < len(data):
                nul = data.index(b"\0", i)
                mode = data[i:nul].split(b" ", 1)[0]
                oid = data[nul + 1:nul + 21].hex()
                new = self.gitlinks.get(oid, oid) if mode == b"160000" else self.tree(oid) if mode == b"40000" else oid
                changed |= new != oid
                out += data[i:nul + 1] + bytes.fromhex(new)
                i = nul + 21
            self.trees[sha] = self.write("tree", bytes(out)) if changed else sha
        return self.trees[sha]

    def plan(self):
        refs = [l.split() for l in git(self.path, "for-each-ref", "--format=%(refname) %(objectname) %(objecttype)",
                                        "refs/heads", "refs/tags").splitlines()]
        tips = sorted({oid for _, oid, _ in refs})
        commits = git(self.path, "rev-list", "--topo-order", "--reverse", *tips).split() if tips else []
        return refs, commits

    def rewrite(self):
        refs, commits = self.plan()
        mapping, rewritten = {}, 0
        for old in commits:
            _, raw = self.read(old)
            headers, _, message = raw.partition(b"\n\n")
            lines = headers.split(b"\n")
            for n, line in enumerate(lines):
                if line.startswith(b"tree "):
                    lines[n] = b"tree " + self.tree(line[5:].decode()).encode()
                elif line.startswith(b"parent "):
                    lines[n] = b"parent " + mapping[line[7:].decode()].encode()
            if TRAILER_LINE.search(message):
                message = TRAILER_LINE.sub(b"", message).rstrip(b"\n") + b"\n"
            if b"\n".join(lines) + b"\n\n" + message == raw:
                mapping[old] = old
                continue
            kept, skip = [], False  # a changed commit cannot keep its old signature
            for line in lines:
                if skip and line.startswith(b" "):
                    continue
                skip = line.startswith((b"gpgsig ", b"gpgsig-sha256 "))
                if not skip:
                    kept.append(line)
            mapping[old] = self.write("commit", b"\n".join(kept) + b"\n\n" + message)
            rewritten += 1
        moves = []
        for name, oid, kind in refs:
            if kind == "commit":
                new = mapping[oid]
            elif kind == "tag":
                _, raw = self.read(oid)
                target = re.match(rb"object ([0-9a-f]{40})", raw).group(1).decode()
                if mapping.get(target, target) == target:
                    continue
                body = raw.replace(target.encode(), mapping[target].encode(), 1)
                new = self.write("tag", re.sub(rb"-----BEGIN PGP SIGNATURE-----.*", b"", body, flags=re.S))
            else:
                continue
            if new != oid:
                moves.append((name, oid, new))
        return mapping, rewritten, len(commits), moves


def cmd_strip(args):
    hosts = discover_hosts(args.checkout)
    repos = repositories(hosts)
    order = [n for n in repos if n != "parent"] + ["parent"]  # gitlinks need submodule maps first
    submodule_maps: dict[str, str] = {}
    results = {}
    for name in order:
        path = repos[name]
        git(path, "fetch", "-q", "origin", "--tags", "--force", check=False)
        if args.yes and git(path, "status", "--porcelain", "--ignore-submodules=all"):
            raise Failure(f"{name} has uncommitted changes; commit or stash them first")
        affected = len(TRAILER.findall(git(path, "log", "--branches", "--tags", "--format=%B", check=False)))
        gitlinks = submodule_maps if name == "parent" else {}
        if not affected and not (name == "parent" and gitlinks):
            print(f"{name:18} clean")
            continue
        rewriter = Rewriter(path, gitlinks)
        if not args.yes:
            print(f"{name:18} {affected} trailer(s) would be removed")
            continue
        mapping, rewritten, total, moves = rewriter.rewrite()
        if name in ("plugin", "extension", "mcp"):
            submodule_maps.update({o: n for o, n in mapping.items() if o != n})
        results[name] = (path, mapping, moves)
        print(f"{name:18} rewrote {rewritten}/{total} commits")
    if not args.yes:
        print("\nPlan only. Rerun with --yes to rewrite, force-push with lease and fix release notes.")
        return 0
    for name, (path, mapping, moves) in results.items():
        backup = Path(git(path, "rev-parse", "--absolute-git-dir")) / "agent-factory-trailer-backup.txt"
        backup.write_text("".join(f"{r} {o} {n}\n" for r, o, n in moves))
        for ref, old, new in moves:
            git(path, "update-ref", ref, new, old)
        # Keep the index consistent with the moved branch; the tree is unchanged except gitlinks.
        git(path, "reset", "-q")
        verify_trees(name, path, moves)
        push_rewritten(name, path, moves)
    git(ROOT, "reset", "-q")
    fix_release_notes(repos, {o: n for _, (_, m, _) in results.items() for o, n in m.items() if o != n})
    print("\nDone. Other clones must run: git fetch && git reset --hard origin/main && git submodule update --init --recursive")
    return 0


def verify_trees(name, path, moves):
    for ref, old, new in moves:
        if ref.startswith("refs/heads/") and name != "parent":
            if git(path, "rev-parse", f"{old}^{{tree}}") != git(path, "rev-parse", f"{new}^{{tree}}"):
                raise Failure(f"{name} {ref} tree changed during rewrite; restore from the backup file")


def push_rewritten(name, path, moves):
    remote = dict(reversed(l.split()) for l in git(path, "ls-remote", "origin").splitlines() if not l.endswith("^{}"))
    for ref, old, new in moves:
        target = ref
        if ref.startswith("refs/heads/"):
            upstream = git(path, "rev-parse", "--symbolic-full-name", f"{ref}@{{upstream}}", check=False)
            if upstream.startswith("refs/remotes/origin/"):
                target = "refs/heads/" + upstream.removeprefix("refs/remotes/origin/")
        if remote.get(target) != old:
            print(f"  {name}: skip {ref} -> {target} (remote is not at the pre-rewrite commit)")
            continue
        run(["git", "-C", str(path), "push", f"--force-with-lease={target}:{old}", "origin", f"{new}:{target}"])
        print(f"  {name}: pushed {ref} -> {target} {old[:7]}..{new[:7]}")


def fix_release_notes(repos, mapping):
    if not mapping:
        return
    for name, path in repos.items():
        repo = slug(path)
        releases = json.loads(run(["gh", "api", "--paginate", f"repos/{repo}/releases"]).stdout or "[]")
        for release in releases:
            body = release.get("body") or ""

            def swap(match):
                short = match.group(0)
                candidates = [o for o in mapping if o.startswith(short)]
                return mapping[candidates[0]][:len(short)] if len(candidates) == 1 else short

            new = re.sub(r"\b[0-9a-f]{7,40}\b", swap, body)
            if new != body:
                run(["gh", "api", "-X", "PATCH", f"repos/{repo}/releases/{release['id']}", "-f", f"body={new}"])
                print(f"  {repo} {release['tag_name']}: release notes now reference rewritten commits")


# --------------------------------------------------------------------- release

def run_tests():
    step("Plugin source tests")
    result = run(["uv", "run", "--no-project", "--with-requirements", "requirements.txt", "python", "-m", "pytest",
                  "tests", "-n", "auto", "-q"], cwd=SOURCE, env=clean_env(), check=False)
    summary = (result.stdout.strip().splitlines() or [""])[-1]
    print(summary)
    if result.returncode != 0:
        print("\n".join(line for line in result.stdout.splitlines() if line.startswith(("FAILED", "ERROR", "E  "))))
        raise Failure(f"plugin tests failed: {summary}")
    plugin_passed = int(re.search(r"(\d+) passed", summary).group(1))
    step("Extension tests")
    result = run(["npm", "test"], cwd=EXTENSION, env=clean_env(), check=False)
    counts = dict(re.findall(r"^ℹ (\w+) (\d+)$", result.stdout, re.M))
    print(f"pass {counts.get('pass')} fail {counts.get('fail')}")
    if result.returncode != 0 or counts.get("fail") != "0":
        raise Failure("extension tests failed")
    return plugin_passed, int(counts["pass"])


def release_exists(repo, tag):
    return run(["gh", "release", "view", tag, "-R", repo, "--json", "tagName"], check=False).returncode == 0


def publish_plugins(version, hosts):
    step("Plugin source and hosts")
    state = SOURCE / ".git" / "agent-factory-plugin-release.json"
    flags = hosts_repo_flags(hosts)
    if state.exists():
        print("resuming saved plugin release")
    elif source_meta()["version"] == version:
        print(f"plugin source already at {version}; skipping commit")
    else:
        run(["python3", "distribution/release.py", "commit", "--version", version, *flags], cwd=SOURCE, capture=False)
    if state.exists():
        run(["python3", "distribution/release.py", "push", "--yes"], cwd=SOURCE, capture=False)
    for path in [SOURCE, *hosts.values()]:
        git(path, "fetch", "-q", "origin")
        if git(path, "rev-parse", "HEAD") != git(path, "rev-parse", "origin/main"):
            raise Failure(f"{path} HEAD is not on origin/main after the plugin push")
    step("Version preflight")
    run(["node", "scripts/check-plugin-versions.mjs", "--version", version, "--source", str(SOURCE), *flags],
        cwd=EXTENSION, capture=False)
    if shutil.which("claude") and "claude" in hosts:
        run(["claude", "plugin", "validate", str(hosts["claude"])], capture=False)


def publish_extension(version, message):
    step("Extension release (stops before Marketplace)")
    manifest = read_json(EXTENSION / "package.json")
    state_file = Path(git(EXTENSION, "rev-parse", "--absolute-git-dir")) / "agent-factory-release.json"
    state = read_json(state_file) if state_file.exists() else None
    if state and state.get("stage") != "completed" and state.get("version") != version:
        raise Failure(f"unfinished extension release {state.get('version')} at {state.get('stage')}; recover it first")
    if manifest["version"] != version and not (state and state.get("version") == version):
        run(["npm", "run", "-s", "release", "--", "--version", version, "--message", message],
            cwd=EXTENSION, capture=False, env=clean_env())
    elif state and state.get("version") == version and state.get("stage") not in ("awaiting-browser", "completed", "published"):
        run(["npm", "run", "-s", "release", "--", "--resume"], cwd=EXTENSION, capture=False, env=clean_env())
    git(EXTENSION, "fetch", "-q", "origin")
    commit = git(EXTENSION, "rev-parse", "HEAD")
    if read_json(EXTENSION / "package.json")["version"] != version or git(EXTENSION, "rev-parse", "origin/main") != commit:
        raise Failure("extension version commit is not on origin/main")
    vsix = EXTENSION / "releases" / f"{manifest['name']}-{version}.vsix"
    if not vsix.exists():
        raise Failure(f"missing {vsix}")
    return commit, vsix


def create_releases(version, hosts, summary_en, summary_ko, tests, ext_commit, vsix):
    step("GitHub releases")
    plugin_tests, ext_tests = tests
    tag = f"v{version}"
    source_commit = git(SOURCE, "rev-parse", "origin/main")
    host_commits = {h: git(p, "rev-parse", "origin/main") for h, p in hosts.items()}
    names = [HOST_NAMES.get(h, h) for h in hosts]
    joined = ", ".join(names[:-1]) + (", and " if len(names) > 2 else " and ") + names[-1] if len(names) > 1 else names[0]
    joined_ko = ", ".join(names)
    validation = (f"Validation: {plugin_tests} source tests passed; the extension version preflight confirmed source and all hosts at {version}.\n"
                  f"검증: 원본 테스트 {plugin_tests}개 통과, 익스텐션 버전 사전 점검에서 원본과 모든 호스트의 {version} 일치 확인.")
    items = [(slug(SOURCE), source_commit,
              f"Agent Factory Plugin Source {version} / Agent Factory 플러그인 원본 {version} 릴리스",
              f"Plugin source {version} is the single origin for the {joined} plugin {version} releases and matches Agent Factory extension {version}. {summary_en}\n"
              f"플러그인 원본 {version}은 {joined_ko} 플러그인 {version} 릴리스의 단일 원본이며 Agent Factory 익스텐션 {version}과 대응합니다. {summary_ko}\n\n"
              f"- Commit / 커밋: `{source_commit}`\n"
              f"- Generated hosts / 생성 호스트: " + ", ".join(f"{h} `{c[:7]}`" for h, c in host_commits.items()) + "\n"
              f"- Matching extension version / 대응 익스텐션 버전: `{version}`\n\n{validation}", None)]
    for host, path in hosts.items():
        display = HOST_NAMES.get(host, host)
        manifest = path / HOST_MANIFESTS.get(host, "plugin.json")
        items.append((slug(path), host_commits[host],
                      f"Agent Factory Plugin for {display} {version} / {display}용 Agent Factory 플러그인 {version}",
                      f"Release {version} is generated from agent-factory-plugin-source `{source_commit[:7]}` and matches Agent Factory extension {version}.\n"
                      f"{version} 릴리스는 agent-factory-plugin-source `{source_commit[:7]}`에서 생성했으며 Agent Factory 익스텐션 {version}과 대응합니다.\n\n"
                      f"- Commit / 커밋: `{host_commits[host]}`\n"
                      f"- Source commit / 원본 커밋: `{source_commit[:7]}` (agent-factory-plugin-source)\n"
                      f"- Manifest version / 매니페스트 버전: `{read_json(manifest)['version']}`\n"
                      f"- Matching extension version / 대응 익스텐션 버전: `{version}`\n\n{validation}", None))
    items.append((slug(EXTENSION), ext_commit, f"Agent Factory {version} / Agent Factory {version} 릴리스",
                  f"Agent Factory extension {version}: {summary_en} The attached VSIX was built from commit `{ext_commit}` and passed "
                  f"{ext_tests} extension tests, type checking, static checks, and build. Matching plugin source and {joined} plugins "
                  f"{version} are available on their `main` branches.\n\n"
                  f"Agent Factory 익스텐션 {version}: {summary_ko} 첨부한 VSIX는 커밋 `{ext_commit}`에서 빌드했으며 익스텐션 테스트 "
                  f"{ext_tests}건, 타입 검사, 정적 검사, 빌드를 통과했습니다. 동일 버전 {version}의 플러그인 원본과 {joined_ko} 플러그인은 "
                  f"각 저장소의 `main` 브랜치에서 사용할 수 있습니다.", vsix))
    for repo, commit, title, notes, asset in items:
        if release_exists(repo, tag):
            print(f"{repo}: {tag} already exists")
            continue
        if TRAILER.search(notes):
            raise Failure("release notes must not contain AI co-author lines")
        extra = [str(asset)] if asset else []
        url = run(["gh", "release", "create", tag, "-R", repo, "--target", commit, "--title", title, "--notes", notes, *extra]).stdout.strip()
        print(url)


def update_parent(version):
    step("Parent submodule pointers")
    git(ROOT, "fetch", "-q", "origin")
    if git(ROOT, "rev-list", "--count", "HEAD..origin/main") != "0":
        raise Failure("parent is behind origin/main; merge origin/main first")
    git(ROOT, "add", "plugin", "extension")
    if git(ROOT, "diff", "--cached", "--name-only"):
        git(ROOT, "commit", "-q", "-m", f"chore: reference plugin and extension {version} / 플러그인과 익스텐션 {version} 참조",
            "--", "plugin", "extension")
    if git(ROOT, "rev-parse", "HEAD") != git(ROOT, "rev-parse", "origin/main"):
        git(ROOT, "push", "-q", "origin", "HEAD:refs/heads/main")
    print(f"parent origin/main {git(ROOT, 'rev-parse', '--short', 'origin/main')}")


def final_verify(version, hosts):
    step("Final verification")
    tag, problems = f"v{version}", []
    for name, path in repositories(hosts, include_mcp=False).items():
        git(path, "fetch", "-q", "origin", "--tags", "--force")
        if remote_has_trailers(path):
            problems.append(f"{name} origin/main has AI co-author trailers")
        if name != "parent":
            target = run(["gh", "release", "view", tag, "-R", slug(path), "--json", "tagName,isDraft"], check=False)
            if target.returncode != 0 or json.loads(target.stdout).get("isDraft"):
                problems.append(f"{name} has no published {tag} release")
            elif git(path, "rev-parse", f"{tag}^{{commit}}", check=False) != git(path, "rev-parse", "origin/main"):
                problems.append(f"{name} {tag} does not point at origin/main")
    pointers = {p: git(ROOT, "rev-parse", f"origin/main:{p}") for p in ("plugin", "extension")}
    for sub, path in (("plugin", SOURCE), ("extension", EXTENSION)):
        if pointers[sub] != git(path, "rev-parse", "origin/main"):
            problems.append(f"parent does not reference {sub} origin/main")
    for problem in problems:
        print(f"- {problem}")
    if problems:
        raise Failure("final verification failed")
    print(f"All components released at {version}. Marketplace publication is a separate step (npm run release -- --resume).")


def next_version():
    major, minor, patch = map(int, read_json(EXTENSION / "package.json")["version"].split("+")[0].split("."))
    return f"{major}.{minor}.{patch + 1}"


NOISE = re.compile(r"^(chore|release|merge|test|ci|style|build)(\(.+\))?:|^Merge ", re.I)


def auto_summary():
    """Summarize feature/fix commits since the last release tag from their bilingual `en / ko` subjects."""
    english, korean = [], []
    for path in (EXTENSION, SOURCE):
        last = git(path, "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", "origin/main", check=False)
        span = f"{last}..origin/main" if last else "origin/main"
        for subject in git(path, "log", span, "--no-merges", "--format=%s", check=False).splitlines():
            if NOISE.search(subject):
                continue
            text = re.sub(r"^\w+(\(.+\))?!?:\s*", "", subject)
            en, _, ko = text.partition(" / ")
            if en and en not in english:
                english.append(en.strip())
                korean.append((ko or en).strip())
    if not english:
        return "Maintenance release with internal updates.", "내부 개선을 포함한 유지보수 릴리스입니다."
    shown = 6
    more_en = f" and {len(english) - shown} more" if len(english) > shown else ""
    more_ko = f" 외 {len(english) - shown}건" if len(english) > shown else ""
    return ("Changes: " + "; ".join(english[:shown]) + more_en + ".",
            "변경 사항: " + "; ".join(korean[:shown]) + more_ko + ".")


def cmd_release(args):
    version = (args.version or next_version()).removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise Failure(f"invalid version {args.version}")
    for path in (EXTENSION, SOURCE):
        git(path, "fetch", "-q", "origin", "--tags", "--force", check=False)
    if not (args.summary_en and args.summary_ko):
        summary_en, summary_ko = auto_summary()
        args.summary_en = args.summary_en or summary_en
        args.summary_ko = args.summary_ko or summary_ko
    hosts = discover_hosts(args.checkout)
    step("Plan")
    plan = {
        "version": version,
        "source": str(SOURCE), "hosts": {h: str(p) for h, p in hosts.items()}, "extension": str(EXTENSION),
        "steps": ["doctor", "plugin + extension tests", "plugin source/hosts commit and push (distribution/release.py)",
                  "check-plugin-versions.mjs", "extension npm run release (VSIX, stops before Marketplace)",
                  f"GitHub releases v{version} for source, {', '.join(hosts)}, extension",
                  "parent submodule pointers commit and push", "final verification"],
    }
    plan["summary"] = {"en": args.summary_en, "ko": args.summary_ko}
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    if args.plan:
        print("\nPlan only.")
        return 0
    if not args.yes:
        if not sys.stdin.isatty():
            raise Failure("pass --yes to release non-interactively")
        if input(f"\nRelease {version} to GitHub? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Cancelled.")
            return 1
    doctor = argparse.Namespace(checkout=args.checkout, fix=False)
    if cmd_doctor(doctor) != 0:
        # Version mismatches are expected before the release; everything else must be fixed first.
        blocking = [p for p in collect_blocking(hosts)]
        if blocking:
            raise Failure("doctor reported blocking problems: " + "; ".join(blocking))
    tests = run_tests()
    publish_plugins(version, hosts)
    ext_commit, vsix = publish_extension(version, f"release: prepare extension {version} / 익스텐션 {version} 준비")
    create_releases(version, hosts, args.summary_en, args.summary_ko, tests, ext_commit, vsix)
    update_parent(version)
    final_verify(version, hosts)
    return 0


def collect_blocking(hosts):
    blocking = []
    for name, path in repositories(hosts, include_mcp=False).items():
        if name != "parent" and git(path, "status", "--porcelain"):
            blocking.append(f"{name} has uncommitted changes")
        if git(path, "rev-list", "--count", "HEAD..origin/main", check=False) not in ("0", ""):
            blocking.append(f"{name} is behind origin/main")
        if hooks_state(path) != "ok":
            blocking.append(f"{name} hooks are not installed (run hooks)")
        if name.startswith("host:") and not git(path, "remote", "get-url", "origin").startswith("https://"):
            blocking.append(f"{name} fetch URL is not HTTPS (run doctor --fix)")
        if TRAILER.search(git(path, "log", "--format=%B", "HEAD", "--not", "--remotes=origin", check=False)):
            blocking.append(f"{name} has unpushed AI co-author trailers")
    if git(ROOT, "status", "--porcelain", "--ignore-submodules=all"):
        blocking.append("parent has uncommitted changes")
    return blocking


# ----------------------------------------------------------------- setup-token

def cmd_setup_token(args):
    """Store the signed-in gh token as RELEASE_TOKEN; sign in through the browser first when needed."""
    repo = slug(ROOT)
    token = run(["gh", "auth", "token"], check=False).stdout.strip()
    if not token:
        print("No gh token found; opening the browser to sign in to GitHub.")
        run(["gh", "auth", "login", "--hostname", "github.com", "--web", "--git-protocol", "https", "--scopes", "repo,workflow"], capture=False)
        token = run(["gh", "auth", "token"]).stdout.strip()
    run(["gh", "secret", "set", "RELEASE_TOKEN", "-R", repo], data=token)
    print(f"RELEASE_TOKEN set on {repo} from the signed-in gh account.")
    return 0


# ------------------------------------------------------------------------ main

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "hooks", "scan", "release", "strip-trailers", "setup-token"):
        command = sub.add_parser(name)
        command.add_argument("--checkout", action="append", metavar="HOST=PATH", help="Override a host clone path.")
        if name == "doctor":
            command.add_argument("--fix", action="store_true", help="Fix host fetch URLs, parent upstream and hooks.")
        if name == "release":
            command.add_argument("version", nargs="?", help="Defaults to the next patch of the extension version.")
            command.add_argument("--summary-en", help="Defaults to a summary of feature/fix commits since the last tag.")
            command.add_argument("--summary-ko", help="Korean counterpart; defaults like --summary-en.")
            command.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
            command.add_argument("--plan", action="store_true", help="Print the plan only.")
        if name == "strip-trailers":
            command.add_argument("--yes", action="store_true", help="Rewrite, force-push with lease and fix release notes.")
    args = parser.parse_args()
    handler = {"doctor": cmd_doctor, "hooks": cmd_hooks, "scan": cmd_scan, "setup-token": cmd_setup_token,
               "release": cmd_release, "strip-trailers": cmd_strip}[args.command]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())

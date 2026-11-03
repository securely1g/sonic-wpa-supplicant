#!/usr/bin/env python3
"""Retain native source-TAR acceptance and test a restored source edit."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = {"//:wpasupplicant_pkg": "wpasupplicant.tar",
           "//:wpasupplicant_pkg.debug_symbols": "wpasupplicant.debug.tar.gz",
           "//:runtime_packages.json": "runtime_packages.json"}
TESTS = ["//:package_test", "//:upstream_test", "//:build_flags_test", "//:make_flags_test"]


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checkout_identity(workspace, head_sha="", base_sha=""):
    subprocess.run(["git", "diff", "--exit-code", "HEAD"], cwd=workspace, check=True)
    require(not subprocess.check_output(["git", "status", "--porcelain"], cwd=workspace, text=True).strip(),
            "Acceptance requires a clean committed source checkout")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
    headers = subprocess.check_output(["git", "cat-file", "-p", "HEAD"], cwd=workspace, text=True).split("\n\n", 1)[0]
    # History traversal hides parents at a shallow checkout boundary; the raw
    # commit still binds GitHub's tested merge to both requested revisions.
    parents = [line.removeprefix("parent ") for line in headers.splitlines() if line.startswith("parent ")]
    if head_sha and revision != head_sha:
        require(head_sha in parents and base_sha and base_sha in parents,
                "Tested merge does not contain the requested PR head and base")
    return {"revision": revision, "parents": parents, "requested_head": head_sha,
            "requested_base": base_sha}


def retain_test_results(events, destination):
    """Copy logs from this accepted invocation, not a stale output symlink."""
    results = {}
    for line in events.read_text().splitlines():
        event = json.loads(line)
        label = event.get("id", {}).get("testResult", {}).get("label")
        if label in TESTS:
            require(label not in results, "Unexpected repeated test attempt: " + label)
            result = event["testResult"]
            require(result.get("status") == "PASSED", "Test result was not passed: " + label)
            files = {}
            for item in result.get("testActionOutput", []):
                if item.get("name") in ("test.log", "test.xml"):
                    uri = urlparse(item["uri"])
                    require(uri.scheme == "file" and not uri.netloc, "Expected a local test artifact")
                    files[item["name"]] = Path(unquote(uri.path))
            require(set(files) == {"test.log", "test.xml"}, "Missing accepted test logs: " + label)
            results[label] = files
    require(set(results) == set(TESTS), "Missing accepted test results")
    for label, files in results.items():
        directory = destination / label.removeprefix("//:")
        directory.mkdir(parents=True, exist_ok=True)
        for name, source in files.items():
            require(source.is_file(), "Missing accepted test artifact: " + str(source))
            shutil.copyfile(source, directory / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["audit", "build", "incremental", "collect"])
    parser.add_argument("--output", type=Path, default=ROOT / "bazel-evidence")
    parser.add_argument("--output-user-root", type=Path)
    parser.add_argument("--codeql", action="store_true", help="Include the private same-source traced build in the audit")
    parser.add_argument("--head-sha", default=os.environ.get("CI_HEAD_SHA", ""))
    parser.add_argument("--base-sha", default=os.environ.get("CI_BASE_SHA", ""))
    args = parser.parse_args()
    require(platform.machine() == "x86_64", "Native AMD64 execution is required")
    output = args.output.resolve()
    private = output / "private"
    private.mkdir(parents=True, exist_ok=True)
    prefix = [str(ROOT / "tools/bazel/draft_bazel.sh")]
    if args.output_user_root:
        prefix += ["--output_user_root=" + str(args.output_user_root.resolve())]
    flags = ["--jobs=2", "--local_test_jobs=1"]

    def bazel(command, *arguments, log=None):
        started = time.monotonic()
        if log:
            with (private / log).open("w") as stream:
                result = subprocess.run([*prefix, command, *arguments], cwd=ROOT, stdout=stream,
                                        stderr=subprocess.STDOUT)
            if result.returncode:
                print((private / log).read_text(errors="replace")[-20000:], file=sys.stderr)
                result.check_returncode()
            return time.monotonic() - started
        return subprocess.check_output([*prefix, command, *arguments], cwd=ROOT, text=True)


    def resolved_inputs():
        graph = bazel("mod", "graph")
        require("sonic-build-infra@0.0.26-51c838da6ff57295fde6e0bc3807841cb31a8568" in graph,
                "Selected shared tooling version differs from the reviewed source")
        infra = bazel("mod", "show_repo", "@sonic_build_infra")
        require("http_archive(" in infra and "51c838da6ff57295fde6e0bc3807841cb31a8568" in infra
                and "sha256-nYuM1ahKhqAJUXseWPs2LRNi9qKEAyAGLYVw7GbX750=" in infra,
                "Actual tooling source is not the reviewed immutable archive; local overrides are not acceptance")
        libnl = bazel("mod", "show_repo", "@libnl3")
        require("libnl3@3.7.0.sonic.7" in graph and "http_archive(" in libnl
                and "0001-build-libnl3-with-shared-native-rules.patch" in libnl
                and "0002-match-shared-output-sonames.patch" in libnl,
                "Actual libnl repository lacks the reviewed owner interface")
        common = bazel("mod", "show_repo", "@sonic_swss_common")
        require("sonic-swss-common@0.0.8-43598143ef4a46431eae0859915cd7d951dad1ed" in graph
                and "http_archive(" in common and "43598143ef4a46431eae0859915cd7d951dad1ed" in common
                and "sha256-a6PXXUxzW+0tTMaaOwypdZC/T6vvj7b1SiiEwLfhhpE=" in common,
                "Common differs from the registered owner source")
        (output / "common-repository.txt").write_text(common)
        record = {"common_repository_sha256": hashlib.sha256(common.encode()).hexdigest(),
                  "module_graph_sha256": hashlib.sha256(graph.encode()).hexdigest(),
                  "infra_repository_sha256": hashlib.sha256(infra.encode()).hexdigest(),
                  "libnl_repository_sha256": hashlib.sha256(libnl.encode()).hexdigest()}
        (output / "resolved-modules.txt").write_text(graph)
        (output / "infra-repository.txt").write_text(infra)
        (output / "libnl-repository.txt").write_text(libnl)
        return record

    def paths():
        result = {}
        for label, name in OUTPUTS.items():
            files = bazel("cquery", "--output=files", "config(" + label + ", target)").splitlines()
            require(len(files) == 1, "Expected one public output: " + label)
            result[name] = ROOT / files[0]
            require(result[name].is_file(), "Missing public output: " + name)
        return result

    def snapshot(files):
        return {name: sha(path) for name, path in files.items()}

    def binaries(archive):
        with tarfile.open(archive) as source:
            return {m.name.lstrip("./"): hashlib.sha256(source.extractfile(m).read()).hexdigest()
                    for m in source if m.isfile() and m.name.lstrip("./") in {
                        "usr/sbin/wpa_supplicant", "usr/sbin/wpa_cli", "usr/bin/wpa_passphrase"}}

    identity = checkout_identity(ROOT, args.head_sha, args.base_sha)
    if args.stage != "audit":
        require(json.loads((output / "source-identity.json").read_text()) == identity,
                "Source checkout changed since the accepted action audit")

    if args.stage == "audit":
        (output / "source-identity.json").write_text(json.dumps(identity, indent=2) + "\n")
        (output / "resolved-inputs.json").write_text(json.dumps(resolved_inputs(), indent=2) + "\n")
        graph_path = private / "configured-actions.json"
        targets = [*OUTPUTS, *TESTS] + (["//:codeql_build"] if args.codeql else [])
        expression = "deps(set(" + " ".join(targets) + "))"
        graph_path.write_text(bazel("aquery", "--output=jsonproto", "--include_commandline",
                                    *(["--compilation_mode=dbg"] if args.codeql else []), expression))
        graph = json.loads(graph_path.read_text())
        fragments = {item["id"]: item for item in graph.get("pathFragments", [])}

        def path(identifier):
            item = fragments[identifier]
            return (path(item["parentId"]) + "/" if item.get("parentId") else "") + item["label"]

        artifacts = {item["id"]: path(item["pathFragmentId"]) for item in graph.get("artifacts", [])}
        outputs = {artifacts[identifier] for action in graph["actions"] for identifier in action.get("outputIds", [])}
        require(not any(name.endswith((".deb", ".udeb", ".ddeb")) for name in outputs), "DEB output in configured graph")
        for action in graph["actions"]:
            command = " ".join(action.get("arguments", []))
            require(not re.search(r"dpkg-buildpackage|dpkg-deb\s+(?:--build|-b)(?:\s|$)|pkg_deb|p4rt_(?:dbg_)?deb", command),
                    "DEB-producing command in configured graph")
        record = {"status": "passed", "architecture": "amd64", "actions": len(graph["actions"]),
                  "outputs": len(outputs), "deb_outputs": 0, "targets": targets}
        (output / "action-audit.json").write_text(json.dumps(record, indent=2) + "\n")
    elif args.stage == "build":
        require(json.loads((output / "action-audit.json").read_text())["status"] == "passed", "Audit required")
        elapsed = bazel("test", *flags, "--test_timeout=600", "--test_output=errors",
                        "--build_event_json_file=" + str(private / "build-events.jsonl"),
                        *OUTPUTS, *TESTS, log="build.log")
        (output / "build.json").write_text(json.dumps({"status": "passed", "seconds": elapsed,
                                                       "tests": TESTS}, indent=2) + "\n")
    elif args.stage == "incremental":
        require(json.loads((output / "build.json").read_text())["status"] == "passed", "Accepted build required")
        files = paths()
        original = snapshot(files)
        native = binaries(files["wpasupplicant.tar"])
        require(len(native) == 3, "Expected all three installed source binaries")
        noop = bazel("build", *flags, *OUTPUTS, log="noop.log")
        require(snapshot(files) == original, "No-op changed exported outputs")
        source = ROOT / "wpa_supplicant/wpa_passphrase.c"
        before = source.read_bytes()
        token = b'printf("network={\\n");'
        require(before.count(token) == 1, "Source edit anchor changed")
        try:
            source.write_bytes(before.replace(token, b'printf("network={ # bazel-rebuild-probe\\n");'))
            changed_time = bazel("build", *flags, *OUTPUTS, log="changed.log")
            changed = snapshot(files)
            changed_native = binaries(files["wpasupplicant.tar"])
            require(changed["wpasupplicant.tar"] != original["wpasupplicant.tar"] and
                    changed["wpasupplicant.debug.tar.gz"] != original["wpasupplicant.debug.tar.gz"],
                    "Source edit did not change runtime/debug artifacts")
            require(changed_native["usr/bin/wpa_passphrase"] != native["usr/bin/wpa_passphrase"], "Source edit missed installed program")
            require(all(changed_native[name] == value for name, value in native.items()
                        if name != "usr/bin/wpa_passphrase"), "Unrelated source binaries changed")
        finally:
            source.write_bytes(before)
            restored_time = bazel("build", *flags, *OUTPUTS, log="restored.log")
            require(snapshot(files) == original, "Restored source did not restore original output bytes")
        record = {"status": "passed", "seconds": {"noop": noop, "changed": changed_time, "restored": restored_time},
                  "original": original, "changed": changed, "restored": snapshot(files),
                  "changed_installed_program": "usr/bin/wpa_passphrase",
                  "scope": "Same retained output base; Make recompiles its foreign action. No remote-cache-hit claim."}
        (output / "incremental.json").write_text(json.dumps(record, indent=2) + "\n")
    else:
        require(json.loads((output / "build.json").read_text())["status"] == "passed", "Accepted build required")
        incremental = json.loads((output / "incremental.json").read_text())
        require(incremental["status"] == "passed", "Accepted incremental check required")
        require(resolved_inputs() == json.loads((output / "resolved-inputs.json").read_text()),
                "Actual resolved source changed since the action audit")
        files = paths()
        require(snapshot(files) == incremental["original"] == incremental["restored"],
                "Exported artifacts differ from the accepted original/restored outputs")
        for name, source in files.items():
            shutil.copyfile(source, output / name)
        retain_test_results(private / "build-events.jsonl", output / "tests")
        lock = ROOT / "MODULE.bazel.lock"
        require(lock.is_file(), "Resolved module lock is missing")
        shutil.copyfile(lock, output / lock.name)
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        record = {**identity, "architecture": "amd64", "artifacts": snapshot(files),
                  "resolved_inputs": json.loads((output / "resolved-inputs.json").read_text()),
                  "registry_revision": "b5a92b67de1fa3b2ad6001f9f66e8308fb868a7a",
                  "infra_source": "51c838da6ff57295fde6e0bc3807841cb31a8568"}
        (output / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()

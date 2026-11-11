"""Exercise the real Make frontend with GCC and an over-limit include list."""

import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


def main():
    adapter, frontend = [Path(value).resolve() for value in sys.argv[1:]]
    tools = {name: shutil.which(name) for name in ("bash", "make", "gcc", "g++")}
    assert all(tools.values()), tools
    with tempfile.TemporaryDirectory(dir=os.environ.get("TEST_TMPDIR")) as temporary:
        root = Path(temporary)
        (root / "wpa_supplicant").mkdir()
        (root / "wpa_supplicant/.config").write_text("# retained fixture config\n")
        (root / "debian/config/wpasupplicant").mkdir(parents=True)
        (root / "debian/config/wpasupplicant/linux").write_text("# fixture config\n")
        for name, value in (("first", 13), ("second", 29)):
            (root / name).mkdir()
            (root / name / "selected.h").write_text("#define SELECTED " + str(value) + "\n")
        (root / "quoted include").mkdir()
        (root / "quoted include/quoted_path.h").write_text("#define SPACE_HEADER 31\n")
        program = ("#include <selected.h>\n#include <quoted_path.h>\n"
                   "static const char *text = STRING;\n"
                   "int main(void) { return VALUE + SELECTED != 20 || SPACE_HEADER != 31 || "
                   "text[0] != 'q' || text[6] != ' ' || text[7] != 'v'; }\n")
        for suffix in ("c", "cc"):
            (root / "wpa_supplicant" / ("unit." + suffix)).write_text(program)
        (root / "wpa_supplicant/Makefile").write_text(
            ".PHONY: all\nall:\n"
            "\t$(CC) $(CFLAGS) unit.c -o c-program\n"
            "\t$(CXX) $(CXXFLAGS) unit.cc -o cxx-program\n")
        common = shlex.join(["-DVALUE=1", "-UVALUE", "-DVALUE=7", '-DSTRING="quoted value"',
                             "-isystem", str(root / "first"), "-isystem", str(root / "second"),
                             "-I" + str(root / "quoted include")])
        # Unique nonexistent include directories preserve order and exceed the
        # Linux per-environment-string bound; they do not change header lookup.
        long_flags = " ".join("-I/nonexistent/" + str(i) + "/" + "x" * 180 for i in range(750)) + " " + common
        assert len(long_flags.encode()) > 131072

        def run(flags, prefix):
            assignments = {"CC": tools["gcc"], "CXX": tools["g++"], "CPPFLAGS": flags,
                           "CFLAGS": "-O2 -g -frandom-seed=fixture", "CXXFLAGS": "-O2 -g -frandom-seed=fixture",
                           "LDFLAGS": "", "SONIC_COMMON_LIBRARY": "/fixture/common.so",
                           "SONIC_NL_LIBRARY": "/fixture/nl.so", "SONIC_GENL_LIBRARY": "/fixture/genl.so",
                           "SONIC_ROUTE_LIBRARY": "/fixture/route.so"}
            command = " ".join(key + "=" + shlex.quote(value) for key, value in assignments.items())
            if prefix:
                command += " source " + shlex.quote(str(adapter))
            command += " " + shlex.join([tools["make"], "--no-print-directory", "-f", str(frontend), "all"])
            script = root / "invoke.sh"
            script.write_text(command + "\n")
            return subprocess.run([tools["bash"], script], cwd=root, capture_output=True, text=True)

        old = run(long_flags, False)
        assert old.returncode != 0 and "Argument list too long" in old.stderr, old.stderr
        hashes = []
        for flags in (common, long_flags):
            accepted = run(flags, True)
            assert accepted.returncode == 0, accepted.stdout + accepted.stderr
            assert (root / ".bazel-wpa-cppflags.rsp").read_text() == flags + "\n"
            row = {}
            for name in ("c-program", "cxx-program"):
                binary = root / "wpa_supplicant" / name
                subprocess.run([binary], check=True)
                row[name] = hashlib.sha256(binary.read_bytes()).hexdigest()
            hashes.append(row)
        assert hashes[0] == hashes[1], hashes
        rejected = run("-Wl,--as-needed", True)
        assert rejected.returncode != 0 and "CPPFLAGS must contain GCC preprocessor options" in rejected.stderr, rejected.stderr
    print("Over-limit exec rejection, ordered C/C++ flags, identical binaries and driver-option rejection passed")


if __name__ == "__main__":
    main()

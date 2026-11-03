# Native AMD64 WPA source build

The Bazel frontend builds this repository's selected WPA 2.9.0 source with
`debian/config/wpasupplicant/linux`, including the Linux and SONiC MACsec drivers.
It uses the existing Makefiles and declared GCC/tool inputs. It does not run
Debian package generation, maintainer scripts, host package installation, or
cross compilation. ARM and hardware-backed authentication are outside this phase.

During review, use the temporary registry wrapper:

```sh
tools/bazel/draft_bazel.sh build //:wpasupplicant_pkg //:wpasupplicant_pkg.debug_symbols //:runtime_packages.json
tools/bazel/draft_bazel.sh test //:package_test //:upstream_test //:build_flags_test //:make_flags_test
```

The normal `.bazelrc` retains the maintained registry and BCR. The wrapper selects
one immutable complete review catalog, registry commit
`b5a92b67de1fa3b2ad6001f9f66e8308fb868a7a`, composing the native Common
owner from [Common #41](https://github.com/securely1g/sonic-swss-common/pull/41),
non-executable debug symbols from [registry #179](https://github.com/securely1g/sonic-bazel-registry/pull/179),
and the native libnl SONAME fix in
[registry #181](https://github.com/securely1g/sonic-bazel-registry/pull/181), which retains
[registry #148](https://github.com/securely1g/sonic-bazel-registry/pull/148) in a new `.7` version.
The five shared output filenames now match their existing `.so.200` SONAMEs, so
ordinary Common and WPA links find every declared library without a private copy
or loader workaround. This consumer does not introduce another published-input exception. Shared
infrastructure `.26-51c838da...` and Common `.8-43598143...` now resolve together
without an infrastructure override. The public Distroless `.16` import and dotted
`tar.bzl` registration support ordinary `rules_cc` `.22` consumers, so the earlier
root-only C++ and TAR overrides are removed. Remove the temporary wrapper when
the required registrations are on the maintained registry.

Common, patched libnl and OpenSSL compile in their source-owning repositories.
This frontend consumes their existing C++ providers and shared-library outputs;
it does not define replacement Common or Rust compilations. The Common
`.8-43598143...` owner registration includes the native ZMQ repair and
Common-owned native libnl shared dependencies and runtime metadata. Ordinary
downstream consumers inherit that source change; no root-only Common patch is required. Target D-Bus, readline,
PCSC and terminal ABI libraries remain allowed Debian inputs. Execution tools,
including DocBook/OpenSP/Perl, come from the one shared `build_tools` package set.
The root RC carries the registry's targeted kernel-tool download policy so cached
Perl directory aliases are materialized before local metadata actions use them;
other trees retain the ordinary download policy and cache reads stay enabled.

The runtime TAR contains all three programs, the existing service/DBus units,
ifupdown hooks, example configurations and documentation. Six manuals, changelogs
and selected documentation larger than 4 KiB follow Debian's `dh_compress`
convention, including `README.modes.gz` pointing to `README.Debian.gz`. Compression
uses public `rules_gzip` and the existing shared no-name toolchain; filenames,
timestamps and package commands are not embedded. The separate debug TAR contains
the matching non-executable, root-owned symbols (mode `0644`).
`runtime_packages.json` derives actual package records from the existing Debian recipe and selected source/ABI dependencies.

`package_test` checks exact source/generated payload bytes, modes, links and epoch;
three AMD64 PIE/RELRO/NOW ELF/debug pairs; GDB source lookup for the C and SONiC C++
entry points; confined source-owned dynamic libraries; the IEEE PBKDF2 vector;
and a real private supplicant/control-client PING/PONG. It does not claim a
physical MACsec link test. The upstream test target compiles twelve maintained
programs and runs the nine self-contained suites, including six Base64 vectors.
HTTPS/X.509 programs have compile-only coverage because their external fixtures
are not supplied. `build_flags_test` checks the native-Make-unset path and strict
preservation of owner-added flag order when the Bazel baseline is removed once.

The larger native closure in [MACsec image #149](https://github.com/securely1g/sonic-buildimage/pull/149)
supplies a 133,110-byte `CPPFLAGS` value, exceeding Linux's 131,072-byte limit
for one environment entry before Make can start. The public `rules_foreign_cc`
`tool_prefix` sources `make_with_flags.sh` using Bash's builtin. It writes every
ordered preprocessing option to a response file before starting any external
program, then passes that file directly to GCC's preprocessor with `-Wp,@file`.
This also avoids expanding those paths back into GCC's internal environment
when it starts `cc1`. C/C++ compilation settings, link flags, source selection and
the original Make targets stay intact. Driver options in `CPPFLAGS` still fail
explicitly. `make_flags_test` reproduces the original exec failure and exercises
the actual frontend with recursive C and C++ builds, ordered header/macro inputs,
identical short/long-list binaries and the invalid-option negative control.

The native CI job audits its configured graph before execution, retains the
runtime/debug TARs and tests, and checks no-op, an observable `wpa_passphrase.c`
edit, and exact byte restoration using the same output base. The Make action is
the rebuild unit; this does not claim one-file native compilation or remote cache
hits. Raw action/build-event logs stay outside the public artifact upload.

The feature branch replaces the legacy C++ CodeQL path that generates Common
DEBs with an ordinary traced Bazel source compilation. A fresh output base first
prepares the declared tools with the production build, before CodeQL injects its
tracing library. Both commands run in foreground batch mode to avoid unreaped
daemon processes in the job container. A private target using the exact same
production settings forces a new owner compilation under tracing. Prepared local
tool actions remain cached; disk and remote action-cache reads stay disabled.
The finalized database must contain the C program entry points and SONiC
`sonic_db_set` definition, with archived source bytes equal to this checkout.
The evidence helper uses the action-provided pinned `CODEQL_DIST` bundle; it does
not require the action to add its CLI to `PATH`. Python scanning remains enabled.
Other branches' legacy language selection remains unchanged; broader workflow consolidation is
separate from this source-only feature.

The response-file regression is validated against the actual wide native image
closure: Distroless `.16`, Common `.8-43598143`, FIPS `.3-e910ec22`, and
build-infra `.26-51c838da`, with libnl `.7` refreshed to that infrastructure.
The temporary catalog above is registry PR #181; normal registry defaults
remain on maintained `main`. These are explicit Draft prerequisites.

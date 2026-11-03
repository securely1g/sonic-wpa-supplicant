"""Use one production recipe for the public and separately traced source actions."""

load("@rules_foreign_cc//foreign_cc:defs.bzl", "make")

def wpa_builds(name, **kwargs):
    """Prepare production tools before CodeQL, then trace a new owner action."""
    adapter = Label("//:tools/bazel/make_with_flags.sh")
    kwargs["data"] = kwargs.get("data", []) + [adapter]
    kwargs["tool_prefix"] = 'source "$$EXT_BUILD_ROOT$$/$(execpath {})"'.format(adapter)
    make(name = name, **kwargs)
    make(
        name = "codeql_" + name,
        testonly = True,
        visibility = ["//visibility:private"],
        **kwargs
    )

"""Use one production recipe for the public and separately traced source actions."""

load("@rules_foreign_cc//foreign_cc:defs.bzl", "make")

def wpa_builds(name, **kwargs):
    """Prepare production tools before CodeQL, then trace a new owner action."""
    make(name = name, **kwargs)
    make(
        name = "codeql_" + name,
        testonly = True,
        visibility = ["//visibility:private"],
        **kwargs
    )

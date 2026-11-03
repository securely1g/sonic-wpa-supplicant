# Sourced by rules_foreign_cc's public tool_prefix before starting Make.
# A shell builtin can receive CPPFLAGS even when its environment entry is too
# large for execve. Keep the complete ordered preprocessing list in GCC's
# response file; passing it to cc1 also avoids COLLECT_GCC_OPTIONS expansion.
(
    set -eu
    cppflags_file="$PWD/.bazel-wpa-cppflags.rsp"
    printf '%s\n' "${CPPFLAGS:-}" > "$cppflags_file"
    export CPPFLAGS="-Wp,@$cppflags_file"
    if ! $CC ${CFLAGS:-} "$CPPFLAGS" -x c -fsyntax-only /dev/null; then
        echo "WPA CPPFLAGS must contain GCC preprocessor options; use CFLAGS/LDFLAGS for driver options" >&2
        exit 1
    fi
    "$@"
)

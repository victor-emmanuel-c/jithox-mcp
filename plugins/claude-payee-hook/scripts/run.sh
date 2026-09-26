#!/bin/sh
# The shell remains able to request approval if Python is missing or crashes.
python_bin=${JITHOX_PAYEE_PYTHON:-}
if [ -z "$python_bin" ]; then
    for candidate in python3 python; do
        if "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 9))' </dev/null >/dev/null 2>&1; then
            python_bin=$candidate
            break
        fi
    done
fi
if [ -n "$python_bin" ]; then
    if output=$("$python_bin" -c 'import pathlib,runpy,sys; script=str(pathlib.Path(sys.argv.pop(1)).with_name("payee_hook.py")); sys.argv[0]=script; runpy.run_path(script,run_name="__main__")' "$0" "$1" 2>/dev/null) && [ -n "$output" ]; then
        printf '%s\n' "$output"
        exit 0
    fi
fi
if [ "$1" = PostToolUse ]; then
    printf '%s\n' '{"systemMessage":"Jithox runtime unavailable; no local account was remembered."}'
else
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Jithox runtime unavailable. Verify using your own supplier contact before approving."}}'
fi

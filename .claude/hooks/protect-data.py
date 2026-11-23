#!/usr/bin/env python3
"""Claude Code PreToolUse hook: protect raw data files under data/.

Blocks the file-writing tools (Edit, MultiEdit, Write, NotebookEdit) when the
target path is inside this project's data/ folder, except data/processed/.
Reads are never affected: the hook is only attached to the writing tools.

Protocol (Claude Code hooks):
  * The tool call arrives as JSON on stdin.
  * Exit code 0 = allow.  Exit code 2 = block; stderr is shown to Claude.

Fails closed: if the input cannot be understood, or a write has no file path,
the call is blocked (exit 2) because the target cannot be verified.

Only Claude's own edit tools are intercepted. Shell commands (Bash) and the
Flask app itself are not.
"""

import json
import os
import sys

WRITE_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit"}
BLOCK_MESSAGE = "Raw data files are protected.\n\nWrite changes only to data/processed."

# .claude/hooks/protect-data.py -> project root is two levels above this folder.
PROJECT_ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PROTECTED_DIR = os.path.join(PROJECT_ROOT, "data")
ALLOWED_DIR = os.path.join(PROTECTED_DIR, "processed")


def _normalise(path):
    """Absolute, symlink-free, '..'-free, case-normalised (Windows) path."""
    return os.path.normcase(os.path.realpath(path))


def _is_within(path, root):
    path, root = _normalise(path), _normalise(root)
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives
        return False


def _target_path(tool_input, cwd):
    raw = (tool_input.get("file_path") or tool_input.get("notebook_path")
           or tool_input.get("path"))
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw if os.path.isabs(raw) else os.path.join(cwd, raw)


def decide(payload):
    """Return (exit_code, message) for a parsed hook payload."""
    if payload.get("tool_name") not in WRITE_TOOLS:
        return 0, ""
    tool_input = payload.get("tool_input")
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else os.getcwd()
    target = _target_path(tool_input if isinstance(tool_input, dict) else {}, cwd)
    if target is None:
        return 2, "Blocked: no file path was supplied, so the write could not be checked."
    if _is_within(target, PROTECTED_DIR) and not _is_within(target, ALLOWED_DIR):
        return 2, BLOCK_MESSAGE
    return 0, ""


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook input is not a JSON object")
        code, message = decide(payload)
    except Exception as exc:  # fail closed: never allow what we cannot verify
        code, message = 2, f"Blocked: protect-data hook could not read the tool input ({exc})."
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())

"""Tests for the PreToolUse hook .claude/hooks/protect-data.py (run as a real subprocess)."""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".claude" / "hooks" / "protect-data.py"
SETTINGS = ROOT / ".claude" / "settings.json"
MESSAGE = "Raw data files are protected.\n\nWrite changes only to data/processed."

_spec = importlib.util.spec_from_file_location("protect_data", HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def run_hook(payload, raw=None):
    """Run the hook's main() in-process (fast); return (exit_code, stderr)."""
    text = raw if raw is not None else json.dumps(payload)
    old_stdin, stderr = sys.stdin, io.StringIO()
    sys.stdin = io.StringIO(text)
    try:
        with contextlib.redirect_stderr(stderr):
            code = hook.main()
    finally:
        sys.stdin = old_stdin
    return code, stderr.getvalue().strip()


def run_hook_process(payload, raw=None):
    """Run the hook as a real subprocess, as Claude Code does (slow; used sparingly)."""
    text = raw if raw is not None else json.dumps(payload)
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=text, capture_output=True,
        text=True, encoding="utf-8", check=False,
    )
    return result.returncode, result.stderr.strip()


def test_real_process_blocks_with_exit_code_2_and_message():
    code, err = run_hook_process(call("Write", ROOT / "data" / "tickets.db"))
    assert (code, err) == (2, MESSAGE)


def test_real_process_allows_other_files_silently():
    assert run_hook_process(call("Edit", ROOT / "app.py")) == (0, "")


def test_real_process_fails_closed_on_garbage_input():
    assert run_hook_process(None, raw="not json")[0] == 2


def call(tool, path, key="file_path", cwd=None):
    return {"tool_name": tool, "cwd": str(cwd or ROOT), "tool_input": {key: str(path)}}


# ---- protected: data/ ------------------------------------------------------

@pytest.mark.parametrize("tool", ["Edit", "MultiEdit", "Write"])
def test_blocks_writes_to_data_with_exact_message(tool):
    code, err = run_hook(call(tool, ROOT / "data" / "tickets.db"))
    assert code == 2
    assert err == MESSAGE


def test_blocks_notebook_edit_in_data():
    code, err = run_hook(call("NotebookEdit", ROOT / "data" / "n.ipynb", key="notebook_path"))
    assert code == 2 and err == MESSAGE


def test_blocks_new_file_and_nested_folder_in_data():
    assert run_hook(call("Write", ROOT / "data" / "new.csv"))[0] == 2
    assert run_hook(call("Write", ROOT / "data" / "raw" / "deep" / "x.csv"))[0] == 2


def test_blocks_relative_path_against_cwd():
    assert run_hook(call("Write", "data/tickets.db", cwd=ROOT))[0] == 2
    assert run_hook(call("Write", "tickets.db", cwd=ROOT / "data"))[0] == 2


def test_blocks_dotdot_traversal():
    assert run_hook(call("Write", ROOT / "static" / ".." / "data" / "tickets.db"))[0] == 2
    assert run_hook(call("Write", "static/../data/tickets.db"))[0] == 2


def test_blocks_case_variants_on_windows():
    if sys.platform != "win32":
        pytest.skip("case-insensitive file systems only")
    assert run_hook(call("Write", str(ROOT / "DATA" / "Tickets.DB")))[0] == 2


def test_blocks_the_data_folder_itself():
    assert run_hook(call("Write", ROOT / "data"))[0] == 2


# ---- allowed ---------------------------------------------------------------

@pytest.mark.parametrize("tool", ["Edit", "MultiEdit", "Write"])
def test_allows_data_processed(tool):
    assert run_hook(call(tool, ROOT / "data" / "processed" / "out.csv")) == (0, "")


def test_allows_data_processed_relative_and_nested():
    assert run_hook(call("Write", "data/processed/a/b.csv"))[0] == 0


@pytest.mark.parametrize("rel", ["app.py", "tests/test_x.py", "templates/index.html",
                                 "README.md", ".claude/hooks/protect-data.py"])
def test_allows_writes_elsewhere(rel):
    assert run_hook(call("Write", ROOT / rel)) == (0, "")


def test_does_not_confuse_similar_folder_names():
    assert run_hook(call("Write", ROOT / "data-backup" / "x.db"))[0] == 0
    assert run_hook(call("Write", ROOT / "mydata" / "x.db"))[0] == 0
    assert run_hook(call("Write", ROOT / "data.txt"))[0] == 0


def test_allows_paths_outside_the_project(tmp_path):
    assert run_hook(call("Write", tmp_path / "data" / "tickets.db"))[0] == 0


# ---- reads and other tools are never blocked -------------------------------

@pytest.mark.parametrize("tool", ["Read", "Grep", "Glob", "Bash"])
def test_other_tools_are_allowed(tool):
    payload = {"tool_name": tool, "cwd": str(ROOT),
               "tool_input": {"file_path": str(ROOT / "data" / "tickets.db")}}
    assert run_hook(payload) == (0, "")


# ---- fail closed -----------------------------------------------------------

@pytest.mark.parametrize("raw", ["", "not json", "[1, 2]", "null"])
def test_malformed_input_is_blocked(raw):
    code, err = run_hook(None, raw=raw)
    assert code == 2
    assert "could not read the tool input" in err


@pytest.mark.parametrize("tool_input", [{}, {"file_path": ""}, {"file_path": "   "}, {"file_path": 5}, None])
def test_write_without_usable_path_is_blocked(tool_input):
    code, err = run_hook({"tool_name": "Write", "cwd": str(ROOT), "tool_input": tool_input})
    assert code == 2
    assert "no file path" in err


# ---- configuration ---------------------------------------------------------

def test_settings_register_the_hook_for_all_write_tools():
    config = json.loads(SETTINGS.read_text(encoding="utf-8"))
    entries = config["hooks"]["PreToolUse"]
    assert len(entries) == 1
    assert set(entries[0]["matcher"].split("|")) == {"Edit", "MultiEdit", "Write", "NotebookEdit"}
    command = entries[0]["hooks"][0]["command"]
    assert entries[0]["hooks"][0]["type"] == "command"
    assert "$CLAUDE_PROJECT_DIR/.claude/hooks/protect-data.py" in command
    assert HOOK.is_file()

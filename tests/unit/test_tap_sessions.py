import json
import os
import pathlib
import subprocess
import sys

from agent_memory.adapters.tap_sessions import sync
from agent_memory.cli.main import main
from agent_memory.core.sessions import read

CID = "6aa65d1b-c3dc-83ed-bbee-571808223b21"


def _write(source: pathlib.Path, messages, active=None):
    mapping = {}
    for index, (role, text) in enumerate(messages):
        node_id = f"node-{index}"
        mapping[node_id] = {
            "parent": f"node-{index - 1}" if index else None,
            "message": {
                "author": {"role": role},
                "content": {"content_type": "text", "parts": [text]},
                "channel": "final",
            },
        }
    data = {"mapping": mapping, "current_node": active or f"node-{len(messages) - 1}"}
    name = f"{CID}.{len(messages):08x}.json"
    (source / name).write_text(json.dumps(data), encoding="utf-8")
    link = source / f"{CID}.json"
    link.unlink(missing_ok=True)
    link.symlink_to(name)


def test_imports_append_only_session_and_replay_is_idempotent(store, tmp_path):
    source = tmp_path / "chatgpt.sessions"
    source.mkdir()
    _write(source, [("user", "Привет"), ("assistant", "Ответ")])
    assert sync(store, source)["archived"] == 2
    assert sync(store, source)["archived"] == 0
    _write(source, [("user", "Привет"), ("assistant", "Ответ"), ("user", "Дальше")])
    assert sync(store, source)["archived"] == 1
    assert [item.text for item in read(store.layout, f"chatgpt-{CID}")] == [
        "Привет",
        "Ответ",
        "Дальше",
    ]


def test_changed_old_node_is_reported_without_archiving_a_false_suffix(store, tmp_path):
    source = tmp_path / "chatgpt.sessions"
    source.mkdir()
    _write(source, [("user", "Старое"), ("assistant", "Ответ")])
    sync(store, source)
    _write(source, [("user", "Новое"), ("assistant", "Ответ"), ("user", "Дальше")])
    result = sync(store, source)
    assert result["archived"] == 0
    assert result["divergent"] == [CID]
    assert [item.text for item in read(store.layout, f"chatgpt-{CID}")] == ["Старое", "Ответ"]


def test_same_text_on_an_alternate_branch_is_still_a_divergence(store, tmp_path):
    source = tmp_path / "chatgpt.sessions"
    source.mkdir()
    _write(source, [("user", "Вопрос"), ("assistant", "Ответ")])
    sync(store, source)
    latest = source / f"{CID}.json"
    data = json.loads(latest.read_text(encoding="utf-8"))
    data["mapping"]["alternate"] = {
        "parent": "node-0",
        "message": data["mapping"]["node-1"]["message"],
    }
    data["current_node"] = "alternate"
    version = source / f"{CID}.abcdef12.json"
    version.write_text(json.dumps(data), encoding="utf-8")
    latest.unlink()
    latest.symlink_to(version.name)
    assert sync(store, source)["divergent"] == [CID]


def test_cli_imports_pack_output(store, tmp_path, capsys):
    source = tmp_path / "chatgpt.sessions"
    source.mkdir()
    _write(source, [("user", "Через TAP")])
    assert main(["--store", str(store.root), "--json", "sync-tap-sessions", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["archived"] == 1


def test_tap_background_command_uses_profile_owned_session_output(tmp_path):
    command = pathlib.Path(__file__).parents[2] / "integrations" / "tap-memory" / "command.py"
    binary = tmp_path / "mem"
    binary.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
    binary.chmod(0o755)
    profile = tmp_path / "profile"
    store = tmp_path / "store"
    env = {
        **os.environ,
        "TAP_COMMAND_CONTEXT": json.dumps(
            {
                "profile": str(profile),
                "config": {"mem-bin": str(binary), "memory-store": str(store)},
            }
        ),
    }
    result = subprocess.run(
        [sys.executable, str(command)], env=env, capture_output=True, text=True, check=True
    )
    assert result.stdout.splitlines() == [
        "--store",
        str(store),
        "--json",
        "sync-tap-sessions",
        str(profile / "data" / "readers" / "chatgpt.sessions"),
    ]

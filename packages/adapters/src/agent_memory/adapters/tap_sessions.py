"""Conservative ingestion of TAP's versioned ChatGPT session output."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import tempfile

from agent_memory.core.errors import FieldError, ValidationError
from agent_memory.core.store import Store
from agent_memory.core.watermark import Watermark

from .capture import capture

CID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z")


def visible_nodes(data: dict[str, object]) -> list[tuple[str, str, str]]:
    mapping = data.get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError("mapping is missing")
    node_id = data.get("current_node")
    if not isinstance(node_id, str) or node_id not in mapping:
        raise ValueError("current_node is missing from mapping")
    path: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    while node_id is not None:
        if not isinstance(node_id, str) or node_id in seen or node_id not in mapping:
            raise ValueError("broken or cyclic active path")
        seen.add(node_id)
        node = mapping[node_id]
        if not isinstance(node, dict):
            raise ValueError("invalid node")
        message = node.get("message")
        if isinstance(message, dict):
            author = message.get("author")
            role = author.get("role") if isinstance(author, dict) else None
            content = message.get("content")
            channel = message.get("channel")
            metadata = message.get("metadata")
            hidden = isinstance(metadata, dict) and metadata.get(
                "is_visually_hidden_from_conversation"
            )
            if (
                role in {"user", "assistant"}
                and isinstance(content, dict)
                and content.get("content_type") in {"text", "multimodal_text"}
                and (role == "user" or channel in {None, "final"})
                and not hidden
            ):
                parts = content.get("parts")
                fragments = (
                    [
                        part if isinstance(part, str) else part.get("text", "")
                        for part in parts
                        if isinstance(part, (str, dict))
                    ]
                    if isinstance(parts, list)
                    else []
                )
                text = "\n\n".join(
                    piece.strip() for piece in fragments if isinstance(piece, str) and piece.strip()
                )
                if not text and isinstance(content.get("text"), str):
                    text = content["text"].strip()
                if text:
                    path.append((node_id, role, text))
        node_id = node.get("parent")
    return list(reversed(path))


def sync(store: Store, source: pathlib.Path) -> dict[str, object]:
    if not source.is_dir():
        raise ValidationError([FieldError("source", "TAP session directory is missing")])
    imported = 0
    divergences: list[str] = []
    observed = 0
    state_dir = store.layout.state_dir / "tap-sessions"
    state_dir.mkdir(parents=True, exist_ok=True)
    for latest in sorted(source.iterdir()):
        cid = latest.stem
        if not CID.fullmatch(cid) or latest.suffix != ".json":
            continue
        try:
            version = latest.resolve(strict=True)
            if version.parent != source.resolve() or not re.fullmatch(
                re.escape(cid) + r"\.[0-9a-f]{8}\.json", version.name
            ):
                raise ValueError("latest pointer is not a version in the source directory")
            raw = version.read_bytes()
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("invalid conversation body")
            nodes = visible_nodes(data)
            key = hashlib.sha256(raw).hexdigest()
            session = f"chatgpt-{cid}"
            state_path = state_dir / f"{cid}.json"
            saved = (
                json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
            )
            previous = saved.get("nodes", [])
            current = [
                [node_id, hashlib.sha256((role + "\0" + text).encode()).hexdigest()]
                for node_id, role, text in nodes
            ]
            consumed = Watermark(store.layout).read(session).consumed
            if (
                not isinstance(previous, list)
                or previous != current[: len(previous)]
                or consumed != len(previous)
            ):
                divergences.append(cid)
                continue
            observed += 1
            if len(current) == len(previous):
                continue
            result = capture(
                store, session, [f"{role}: {text}" for _, role, text in nodes], source=f"tap:{key}"
            )
            imported += len(result.increment)
            state = {"nodes": current, "version": version.name, "digest": key}
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=state_dir, delete=False
            ) as handle:
                temporary = pathlib.Path(handle.name)
                json.dump(state, handle)
                handle.flush()
            os.replace(temporary, state_path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            divergences.append(f"{cid}: {error}")
    return {"observed": observed, "archived": imported, "divergent": divergences}

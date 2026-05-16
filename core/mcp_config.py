from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import yaml

from core.mcp_client import MCPServerConfig

logger = logging.getLogger("model-chat.mcp")

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _resolve_env(value: str) -> str:
    def _replace(match):
        var_name = match.group(1)
        return os.environ.get(var_name, "")

    return _ENV_VAR_RE.sub(_replace, value)


def _resolve_env_dict(env: dict[str, str] | None) -> dict[str, str] | None:
    if env is None:
        return None
    return {k: _resolve_env(v) for k, v in env.items()}


def load_mcp_config(path: Path) -> list[MCPServerConfig]:
    if not path.exists():
        return []

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or not isinstance(data.get("servers"), dict):
        return []

    configs: list[MCPServerConfig] = []
    for name, server in data["servers"].items():
        if not server:
            continue
        enabled = server.get("enabled", True)
        if not enabled:
            continue
        configs.append(
            MCPServerConfig(
                name=name,
                command=server.get("command", ""),
                args=server.get("args", []),
                env=_resolve_env_dict(server.get("env")),
                enabled=True,
            )
        )

    return configs


def load_mcp_configs_merged(
    bundled_path: Path | None = None,
    user_path: Path | None = None,
) -> list[MCPServerConfig]:
    bundled_servers: dict[str, dict] = {}
    user_servers: dict[str, dict] = {}

    if bundled_path and bundled_path.exists():
        with open(bundled_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and isinstance(data.get("servers"), dict):
            bundled_servers = data["servers"]

    if user_path and user_path.exists():
        with open(user_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and isinstance(data.get("servers"), dict):
            user_servers = data["servers"]

    merged = {**bundled_servers, **user_servers}

    configs: list[MCPServerConfig] = []
    for name, server in merged.items():
        if not server:
            continue
        enabled = server.get("enabled", True)
        if not enabled:
            continue
        configs.append(
            MCPServerConfig(
                name=name,
                command=server.get("command", ""),
                args=server.get("args", []),
                env=_resolve_env_dict(server.get("env")),
                enabled=True,
            )
        )

    return configs

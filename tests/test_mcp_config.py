import os
from unittest.mock import patch

from core.mcp_config import load_mcp_config, load_mcp_configs_merged

# ---------------------------------------------------------------------------
# Tests: load_mcp_config
# ---------------------------------------------------------------------------


class TestLoadMcpConfig:
    def test_parses_basic_config(self, tmp_path):
        cfg = tmp_path / "mcp.yaml"
        cfg.write_text(
            """
servers:
  filesystem:
    command: npx
    args: ["-y", "@anthropic/mcp-server-filesystem", "/tmp"]
    enabled: true
"""
        )
        configs = load_mcp_config(cfg)
        assert len(configs) == 1
        assert configs[0].name == "filesystem"
        assert configs[0].command == "npx"
        assert configs[0].args == ["-y", "@anthropic/mcp-server-filesystem", "/tmp"]
        assert configs[0].enabled is True

    def test_skips_disabled_servers(self, tmp_path):
        cfg = tmp_path / "mcp.yaml"
        cfg.write_text(
            """
servers:
  active:
    command: python
    args: ["-m", "server"]
    enabled: true
  inactive:
    command: python
    args: ["-m", "other"]
    enabled: false
"""
        )
        configs = load_mcp_config(cfg)
        assert len(configs) == 1
        assert configs[0].name == "active"

    def test_enabled_defaults_to_true(self, tmp_path):
        cfg = tmp_path / "mcp.yaml"
        cfg.write_text(
            """
servers:
  myserver:
    command: node
    args: ["server.js"]
"""
        )
        configs = load_mcp_config(cfg)
        assert len(configs) == 1
        assert configs[0].enabled is True

    def test_resolves_env_vars(self, tmp_path):
        cfg = tmp_path / "mcp.yaml"
        cfg.write_text(
            """
servers:
  github:
    command: npx
    args: ["-y", "@anthropic/mcp-server-github"]
    env:
      GITHUB_TOKEN: "${MY_GH_TOKEN}"
      PLAIN_VAR: "hello"
"""
        )
        with patch.dict(os.environ, {"MY_GH_TOKEN": "ghp_secret123"}):
            configs = load_mcp_config(cfg)

        assert configs[0].env == {"GITHUB_TOKEN": "ghp_secret123", "PLAIN_VAR": "hello"}

    def test_env_var_missing_keeps_placeholder(self, tmp_path):
        cfg = tmp_path / "mcp.yaml"
        cfg.write_text(
            """
servers:
  svc:
    command: python
    args: []
    env:
      TOKEN: "${NONEXISTENT_VAR_XYZ}"
"""
        )
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NONEXISTENT_VAR_XYZ", None)
            configs = load_mcp_config(cfg)

        assert configs[0].env == {"TOKEN": ""}

    def test_missing_file_returns_empty(self, tmp_path):
        missing = tmp_path / "does_not_exist.yaml"
        configs = load_mcp_config(missing)
        assert configs == []

    def test_empty_servers_returns_empty(self, tmp_path):
        cfg = tmp_path / "mcp.yaml"
        cfg.write_text("servers:\n")
        configs = load_mcp_config(cfg)
        assert configs == []

    def test_no_servers_key_returns_empty(self, tmp_path):
        cfg = tmp_path / "mcp.yaml"
        cfg.write_text("something_else: true\n")
        configs = load_mcp_config(cfg)
        assert configs == []

    def test_args_defaults_to_empty_list(self, tmp_path):
        cfg = tmp_path / "mcp.yaml"
        cfg.write_text(
            """
servers:
  simple:
    command: mybin
"""
        )
        configs = load_mcp_config(cfg)
        assert configs[0].args == []

    def test_env_defaults_to_none(self, tmp_path):
        cfg = tmp_path / "mcp.yaml"
        cfg.write_text(
            """
servers:
  simple:
    command: mybin
    args: []
"""
        )
        configs = load_mcp_config(cfg)
        assert configs[0].env is None


# ---------------------------------------------------------------------------
# Tests: load_mcp_configs_merged
# ---------------------------------------------------------------------------


class TestLoadMcpConfigsMerged:
    def test_user_config_overrides_bundled(self, tmp_path):
        bundled = tmp_path / "bundled" / "mcp.yaml"
        bundled.parent.mkdir()
        bundled.write_text(
            """
servers:
  fs:
    command: npx
    args: ["--old"]
    enabled: true
"""
        )

        user = tmp_path / "user" / "mcp.yaml"
        user.parent.mkdir()
        user.write_text(
            """
servers:
  fs:
    command: npx
    args: ["--new"]
    enabled: true
"""
        )

        configs = load_mcp_configs_merged(bundled_path=bundled, user_path=user)
        assert len(configs) == 1
        assert configs[0].args == ["--new"]

    def test_user_adds_new_servers(self, tmp_path):
        bundled = tmp_path / "bundled" / "mcp.yaml"
        bundled.parent.mkdir()
        bundled.write_text(
            """
servers:
  fs:
    command: npx
    args: ["fs"]
"""
        )

        user = tmp_path / "user" / "mcp.yaml"
        user.parent.mkdir()
        user.write_text(
            """
servers:
  github:
    command: npx
    args: ["gh"]
"""
        )

        configs = load_mcp_configs_merged(bundled_path=bundled, user_path=user)
        names = {c.name for c in configs}
        assert names == {"fs", "github"}

    def test_user_can_disable_bundled_server(self, tmp_path):
        bundled = tmp_path / "bundled" / "mcp.yaml"
        bundled.parent.mkdir()
        bundled.write_text(
            """
servers:
  fs:
    command: npx
    args: ["fs"]
    enabled: true
"""
        )

        user = tmp_path / "user" / "mcp.yaml"
        user.parent.mkdir()
        user.write_text(
            """
servers:
  fs:
    enabled: false
    command: npx
    args: ["fs"]
"""
        )

        configs = load_mcp_configs_merged(bundled_path=bundled, user_path=user)
        assert len(configs) == 0

    def test_missing_user_config_uses_bundled_only(self, tmp_path):
        bundled = tmp_path / "bundled" / "mcp.yaml"
        bundled.parent.mkdir()
        bundled.write_text(
            """
servers:
  fs:
    command: npx
    args: ["fs"]
"""
        )

        user = tmp_path / "user" / "mcp.yaml"  # does not exist

        configs = load_mcp_configs_merged(bundled_path=bundled, user_path=user)
        assert len(configs) == 1
        assert configs[0].name == "fs"

    def test_both_missing_returns_empty(self, tmp_path):
        bundled = tmp_path / "nope1.yaml"
        user = tmp_path / "nope2.yaml"
        configs = load_mcp_configs_merged(bundled_path=bundled, user_path=user)
        assert configs == []

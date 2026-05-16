"""Tests for MCP-specific policy integration and env sanitization."""

from core.mcp_client import MCPServerConfig
from core.policy import PolicyEngine, PolicyRule
from core.safety import get_tool_timeout, sanitize_env

# ---------------------------------------------------------------------------
# Tests: policy engine with MCP tool name patterns
# ---------------------------------------------------------------------------


class TestMcpPolicyMatching:
    def test_wildcard_matches_mcp_tools(self):
        rule = PolicyRule(id="mcp-prompt", tool="mcp_*", action="prompt")
        assert rule.matches("mcp_filesystem_read_file", {})
        assert rule.matches("mcp_github_create_issue", {})
        assert not rule.matches("shell", {})
        assert not rule.matches("read_file", {})

    def test_exact_mcp_tool_name_matches(self):
        rule = PolicyRule(id="allow-mcp-read", tool="mcp_filesystem_read_file", action="allow")
        assert rule.matches("mcp_filesystem_read_file", {})
        assert not rule.matches("mcp_filesystem_write_file", {})

    def test_star_matches_everything(self):
        rule = PolicyRule(id="catch-all", tool="*", action="prompt")
        assert rule.matches("mcp_anything", {})
        assert rule.matches("shell", {})

    def test_mcp_pattern_with_server_name(self):
        rule = PolicyRule(id="allow-fs", tool="mcp_filesystem_*", action="allow")
        assert rule.matches("mcp_filesystem_read_file", {})
        assert rule.matches("mcp_filesystem_write_file", {})
        assert not rule.matches("mcp_github_read_file", {})

    def test_policy_engine_evaluates_mcp_wildcard(self):
        rules = [
            PolicyRule(
                id="allow-fs-read", tool="mcp_filesystem_read*", action="allow", priority=10
            ),
            PolicyRule(id="mcp-default-prompt", tool="mcp_*", action="prompt", priority=5),
        ]
        engine = PolicyEngine(rules, default_action="deny")

        decision = engine.evaluate("mcp_filesystem_read_file", {})
        assert decision.action == "allow"
        assert decision.rule_id == "allow-fs-read"

        decision = engine.evaluate("mcp_filesystem_write_file", {})
        assert decision.action == "prompt"
        assert decision.rule_id == "mcp-default-prompt"

        decision = engine.evaluate("native_tool", {})
        assert decision.action == "deny"

    def test_policy_from_yaml_with_mcp_rules(self, tmp_path):
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            """
default_action: deny

rules:
  - id: mcp-prompt-all
    tool: "mcp_*"
    action: prompt
    priority: 5

  - id: allow-mcp-fs-read
    tool: "mcp_filesystem_read_file"
    action: allow
    priority: 10
"""
        )
        engine = PolicyEngine.from_yaml(policy_file)

        assert engine.evaluate("mcp_filesystem_read_file", {}).action == "allow"
        assert engine.evaluate("mcp_github_create_issue", {}).action == "prompt"
        assert engine.evaluate("shell", {}).action == "deny"


# ---------------------------------------------------------------------------
# Tests: env sanitization for MCP servers
# ---------------------------------------------------------------------------


class TestMcpEnvSanitization:
    def test_sanitize_env_strips_secrets(self):
        env = {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "OPENROUTER_API_KEY": "sk-secret",
            "GITHUB_TOKEN": "ghp_abc123",
            "AWS_SECRET_ACCESS_KEY": "aws-secret",
            "NORMAL_VAR": "safe",
        }
        cleaned = sanitize_env(env)
        assert "PATH" in cleaned
        assert "HOME" in cleaned
        assert "NORMAL_VAR" in cleaned
        assert "OPENROUTER_API_KEY" not in cleaned
        assert "GITHUB_TOKEN" not in cleaned
        assert "AWS_SECRET_ACCESS_KEY" not in cleaned

    def test_sanitize_env_allows_explicitly_permitted(self):
        env = {
            "GITHUB_TOKEN": "ghp_abc123",
            "OTHER_TOKEN": "xyz",
        }
        cleaned = sanitize_env(env, allow_patterns=["GITHUB_TOKEN"])
        assert "GITHUB_TOKEN" in cleaned
        assert "OTHER_TOKEN" not in cleaned

    def test_mcp_config_env_passes_through_sanitize(self):
        config = MCPServerConfig(
            name="test",
            command="python",
            args=[],
            env={"GITHUB_TOKEN": "ghp_secret", "CUSTOM_VAR": "value"},
        )
        if config.env:
            cleaned = sanitize_env(config.env)
            assert "GITHUB_TOKEN" not in cleaned
            assert "CUSTOM_VAR" in cleaned


# ---------------------------------------------------------------------------
# Tests: MCP tool timeout
# ---------------------------------------------------------------------------


class TestMcpTimeout:
    def test_mcp_tool_gets_default_timeout(self):
        timeout = get_tool_timeout("mcp_filesystem_read_file")
        assert timeout == 30

    def test_native_tools_unchanged(self):
        assert get_tool_timeout("shell") == 120
        assert get_tool_timeout("web_search") == 15

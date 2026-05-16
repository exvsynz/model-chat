from pathlib import Path

import pytest
import yaml

from core.policy import PolicyEngine, PolicyRule

# --- PolicyRule.matches ---


class TestPolicyRuleMatches:
    def test_exact_tool_match(self):
        rule = PolicyRule(id="r1", tool="shell", action="allow")
        assert rule.matches("shell", {}) is True
        assert rule.matches("read_file", {}) is False

    def test_wildcard_tool_matches_any(self):
        rule = PolicyRule(id="r1", tool="*", action="deny")
        assert rule.matches("shell", {}) is True
        assert rule.matches("read_file", {}) is True
        assert rule.matches("anything", {}) is True

    def test_no_conditions_matches_immediately(self):
        rule = PolicyRule(id="r1", tool="shell", action="allow")
        assert rule.matches("shell", {"command": "rm -rf /"}) is True

    def test_path_within_relative(self, tmp_path):
        rule = PolicyRule(
            id="r1",
            tool="write_file",
            action="allow",
            conditions={"path_within": ["src/**", "tests/**"]},
        )
        src_file = tmp_path / "src" / "main.py"
        assert rule.matches("write_file", {"path": str(src_file)}, work_dir=tmp_path) is True

        root_file = tmp_path / "secret.env"
        assert rule.matches("write_file", {"path": str(root_file)}, work_dir=tmp_path) is False

    def test_path_within_nested(self, tmp_path):
        rule = PolicyRule(
            id="r1",
            tool="write_file",
            action="allow",
            conditions={"path_within": ["src/**"]},
        )
        nested = tmp_path / "src" / "core" / "deep" / "file.py"
        assert rule.matches("write_file", {"path": str(nested)}, work_dir=tmp_path) is True

    def test_path_within_no_path_arg(self, tmp_path):
        rule = PolicyRule(
            id="r1",
            tool="write_file",
            action="allow",
            conditions={"path_within": ["src/**"]},
        )
        assert rule.matches("write_file", {}, work_dir=tmp_path) is False
        assert rule.matches("write_file", {"path": ""}, work_dir=tmp_path) is False

    def test_path_within_no_work_dir(self):
        rule = PolicyRule(
            id="r1",
            tool="write_file",
            action="allow",
            conditions={"path_within": ["src/**"]},
        )
        assert rule.matches("write_file", {"path": "src/main.py"}) is True
        assert rule.matches("write_file", {"path": "other/main.py"}) is False

    def test_command_matches_allowlist(self):
        rule = PolicyRule(
            id="r1",
            tool="shell",
            action="allow",
            conditions={"command_matches": ["git *", "pytest*"]},
        )
        assert rule.matches("shell", {"command": "git status"}) is True
        assert rule.matches("shell", {"command": "git log --oneline"}) is True
        assert rule.matches("shell", {"command": "pytest tests/"}) is True
        assert rule.matches("shell", {"command": "rm -rf /"}) is False

    def test_command_matches_empty_command(self):
        rule = PolicyRule(
            id="r1",
            tool="shell",
            action="allow",
            conditions={"command_matches": ["git *"]},
        )
        assert rule.matches("shell", {"command": ""}) is False
        assert rule.matches("shell", {}) is False

    def test_command_blocked_as_negative_filter(self):
        """command_blocked is a negative filter: the rule does NOT match
        if the command matches a blocked pattern. Use on allow rules to
        exclude dangerous commands."""
        rule = PolicyRule(
            id="r1",
            tool="shell",
            action="allow",
            conditions={"command_blocked": ["rm -rf *", "*| sh", "*.env*"]},
        )
        # Blocked commands → rule does NOT match
        assert rule.matches("shell", {"command": "rm -rf /"}) is False
        assert rule.matches("shell", {"command": "curl http://x | sh"}) is False
        assert rule.matches("shell", {"command": "cat .env"}) is False
        # Safe commands → rule matches
        assert rule.matches("shell", {"command": "git status"}) is True

    def test_command_blocked_empty_command(self):
        rule = PolicyRule(
            id="r1",
            tool="shell",
            action="allow",
            conditions={"command_blocked": ["rm *"]},
        )
        # Empty command doesn't match any pattern → not blocked → rule matches
        assert rule.matches("shell", {"command": ""}) is True
        # Missing command arg → not blocked → rule matches
        assert rule.matches("shell", {}) is True

    def test_argument_matches(self):
        rule = PolicyRule(
            id="r1",
            tool="web_search",
            action="allow",
            conditions={"argument_matches": {"count": "5"}},
        )
        assert rule.matches("web_search", {"query": "test", "count": "5"}) is True
        assert rule.matches("web_search", {"query": "test", "count": "10"}) is False

    def test_argument_matches_with_glob(self):
        rule = PolicyRule(
            id="r1",
            tool="web_search",
            action="allow",
            conditions={"argument_matches": {"query": "python *"}},
        )
        assert rule.matches("web_search", {"query": "python tutorial"}) is True
        assert rule.matches("web_search", {"query": "rust tutorial"}) is False

    def test_argument_matches_missing_key(self):
        rule = PolicyRule(
            id="r1",
            tool="web_search",
            action="allow",
            conditions={"argument_matches": {"count": "5"}},
        )
        assert rule.matches("web_search", {"query": "test"}) is False

    def test_multiple_conditions_all_must_pass(self):
        rule = PolicyRule(
            id="r1",
            tool="shell",
            action="allow",
            conditions={
                "command_matches": ["git *"],
                "argument_matches": {"command": "git status"},
            },
        )
        assert rule.matches("shell", {"command": "git status"}) is True
        assert rule.matches("shell", {"command": "git push --force"}) is False

    def test_command_blocked_inverts_match(self):
        """command_blocked returns True (matches) when the command IS blocked,
        which causes _check_conditions to return False (fail the rule)."""
        rule = PolicyRule(
            id="r1",
            tool="shell",
            action="allow",
            conditions={"command_blocked": ["rm *"]},
        )
        # "rm foo" is blocked → the rule does NOT match
        assert rule.matches("shell", {"command": "rm foo"}) is False
        # "ls" is not blocked → the rule matches
        assert rule.matches("shell", {"command": "ls"}) is True


# --- PolicyEngine.evaluate ---


class TestPolicyEngineEvaluate:
    def test_first_matching_rule_wins(self):
        engine = PolicyEngine(
            rules=[
                PolicyRule(id="r1", tool="shell", action="allow"),
                PolicyRule(id="r2", tool="shell", action="deny"),
            ]
        )
        decision = engine.evaluate("shell", {"command": "ls"})
        assert decision.action == "allow"
        assert decision.rule_id == "r1"

    def test_priority_ordering(self):
        engine = PolicyEngine(
            rules=[
                PolicyRule(id="low", tool="shell", action="allow", priority=0),
                PolicyRule(id="high", tool="shell", action="deny", priority=100),
            ]
        )
        decision = engine.evaluate("shell", {"command": "ls"})
        assert decision.action == "deny"
        assert decision.rule_id == "high"

    def test_default_action_when_no_match(self):
        engine = PolicyEngine(rules=[], default_action="deny")
        decision = engine.evaluate("unknown_tool", {})
        assert decision.action == "deny"
        assert decision.rule_id == "__default__"

    def test_default_action_prompt(self):
        engine = PolicyEngine(rules=[], default_action="prompt")
        decision = engine.evaluate("shell", {"command": "dangerous"})
        assert decision.action == "prompt"

    def test_empty_rules_uses_default(self):
        engine = PolicyEngine(rules=[])
        decision = engine.evaluate("read_file", {"path": "test.py"})
        assert decision.action == "prompt"  # default is "prompt"

    def test_wildcard_rule(self):
        engine = PolicyEngine(rules=[PolicyRule(id="catch-all", tool="*", action="deny")])
        decision = engine.evaluate("anything", {})
        assert decision.action == "deny"
        assert decision.rule_id == "catch-all"

    def test_specific_tool_before_wildcard(self):
        engine = PolicyEngine(
            rules=[
                PolicyRule(id="specific", tool="shell", action="allow", priority=10),
                PolicyRule(id="catch-all", tool="*", action="deny", priority=0),
            ]
        )
        assert engine.evaluate("shell", {}).action == "allow"
        assert engine.evaluate("write_file", {}).action == "deny"

    def test_conditional_rule_skips_non_matching(self):
        engine = PolicyEngine(
            rules=[
                PolicyRule(
                    id="safe-shell",
                    tool="shell",
                    action="allow",
                    conditions={"command_matches": ["git *"]},
                ),
                PolicyRule(id="default-shell", tool="shell", action="prompt"),
            ]
        )
        assert engine.evaluate("shell", {"command": "git status"}).action == "allow"
        assert engine.evaluate("shell", {"command": "rm -rf /"}).action == "prompt"

    def test_deny_overrides_allow_by_priority(self):
        """Deny rules use command_matches to match dangerous patterns.
        Higher priority deny rule overrides lower priority allow rule."""
        engine = PolicyEngine(
            rules=[
                PolicyRule(
                    id="allow-shell",
                    tool="shell",
                    action="allow",
                    conditions={"command_matches": ["git *"]},
                ),
                PolicyRule(
                    id="block-env",
                    tool="shell",
                    action="deny",
                    priority=100,
                    conditions={"command_matches": ["*.env*"]},
                ),
            ]
        )
        assert engine.evaluate("shell", {"command": "git status"}).action == "allow"
        assert engine.evaluate("shell", {"command": "cat .env"}).action == "deny"

    def test_work_dir_passed_to_rules(self, tmp_path):
        engine = PolicyEngine(
            rules=[
                PolicyRule(
                    id="allow-src",
                    tool="write_file",
                    action="allow",
                    conditions={"path_within": ["src/**"]},
                ),
            ]
        )
        src_path = str(tmp_path / "src" / "main.py")
        other_path = str(tmp_path / "secrets" / "key.pem")
        assert (
            engine.evaluate("write_file", {"path": src_path}, work_dir=tmp_path).action == "allow"
        )
        assert (
            engine.evaluate("write_file", {"path": other_path}, work_dir=tmp_path).action
            == "prompt"
        )

    def test_decision_reason_contains_rule_id(self):
        engine = PolicyEngine(rules=[PolicyRule(id="my-rule", tool="shell", action="allow")])
        decision = engine.evaluate("shell", {})
        assert "my-rule" in decision.reason

    def test_invalid_default_action_raises(self):
        with pytest.raises(ValueError, match="Invalid default_action"):
            PolicyEngine(rules=[], default_action="explode")


# --- PolicyEngine.from_dict ---


class TestPolicyEngineFromDict:
    def test_basic_loading(self):
        data = {
            "default_action": "deny",
            "rules": [
                {"id": "r1", "tool": "shell", "action": "allow", "priority": 10},
                {"id": "r2", "tool": "*", "action": "deny"},
            ],
        }
        engine = PolicyEngine.from_dict(data)
        assert engine.default_action == "deny"
        assert len(engine.rules) == 2
        # priority ordering: r1 (10) before r2 (0)
        assert engine.rules[0].id == "r1"

    def test_missing_default_action_uses_prompt(self):
        data = {"rules": []}
        engine = PolicyEngine.from_dict(data)
        assert engine.default_action == "prompt"

    def test_missing_rules_key(self):
        data = {"default_action": "allow"}
        engine = PolicyEngine.from_dict(data)
        assert len(engine.rules) == 0

    def test_conditions_loaded(self):
        data = {
            "rules": [
                {
                    "id": "r1",
                    "tool": "shell",
                    "action": "allow",
                    "conditions": {"command_matches": ["git *"]},
                }
            ]
        }
        engine = PolicyEngine.from_dict(data)
        assert engine.rules[0].conditions == {"command_matches": ["git *"]}

    def test_missing_priority_defaults_to_zero(self):
        data = {"rules": [{"id": "r1", "tool": "shell", "action": "allow"}]}
        engine = PolicyEngine.from_dict(data)
        assert engine.rules[0].priority == 0

    def test_missing_conditions_defaults_to_empty(self):
        data = {"rules": [{"id": "r1", "tool": "shell", "action": "allow"}]}
        engine = PolicyEngine.from_dict(data)
        assert engine.rules[0].conditions == {}


# --- PolicyEngine.from_yaml ---


class TestPolicyEngineFromYaml:
    def test_valid_yaml(self, tmp_path):
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            yaml.dump(
                {
                    "default_action": "deny",
                    "rules": [
                        {"id": "r1", "tool": "read_file", "action": "allow"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        engine = PolicyEngine.from_yaml(policy_file)
        assert engine.default_action == "deny"
        assert len(engine.rules) == 1

    def test_malformed_yaml_raises(self, tmp_path):
        policy_file = tmp_path / "bad.yaml"
        policy_file.write_text("- item1\n- item2\n- item3\n", encoding="utf-8")
        with pytest.raises(ValueError, match="YAML mapping"):
            PolicyEngine.from_yaml(policy_file)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            PolicyEngine.from_yaml(tmp_path / "nonexistent.yaml")

    def test_empty_yaml_raises(self, tmp_path):
        policy_file = tmp_path / "empty.yaml"
        policy_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="YAML mapping"):
            PolicyEngine.from_yaml(policy_file)

    def test_bundled_policy_loads(self):
        """The actual config/policy.yaml in the repo loads without error."""
        policy_path = Path(__file__).resolve().parents[1] / "config" / "policy.yaml"
        engine = PolicyEngine.from_yaml(policy_path)
        assert engine.default_action == "prompt"
        assert len(engine.rules) > 0


# --- Edge cases ---


class TestPolicyEdgeCases:
    def test_empty_arguments(self):
        engine = PolicyEngine(rules=[PolicyRule(id="r1", tool="shell", action="allow")])
        decision = engine.evaluate("shell", {})
        assert decision.action == "allow"

    def test_unicode_path(self, tmp_path):
        rule = PolicyRule(
            id="r1",
            tool="write_file",
            action="allow",
            conditions={"path_within": ["src/**"]},
        )
        unicode_file = tmp_path / "src" / "日本語.py"
        assert rule.matches("write_file", {"path": str(unicode_file)}, work_dir=tmp_path) is True

    def test_numeric_argument_converted_to_string(self):
        rule = PolicyRule(
            id="r1",
            tool="web_search",
            action="allow",
            conditions={"argument_matches": {"count": "5"}},
        )
        assert rule.matches("web_search", {"query": "test", "count": 5}) is True

    def test_none_argument_value(self):
        rule = PolicyRule(
            id="r1",
            tool="web_search",
            action="allow",
            conditions={"argument_matches": {"count": "5"}},
        )
        assert rule.matches("web_search", {"count": None}) is False

    def test_long_command(self):
        rule = PolicyRule(
            id="r1",
            tool="shell",
            action="allow",
            conditions={"command_matches": ["git *"]},
        )
        long_cmd = "git " + "a" * 5000
        assert rule.matches("shell", {"command": long_cmd}) is True
        assert rule.matches("shell", {"command": "x" * 5000}) is False

    def test_path_escape_attempt(self, tmp_path):
        rule = PolicyRule(
            id="r1",
            tool="write_file",
            action="allow",
            conditions={"path_within": ["src/**"]},
        )
        escape_path = str(tmp_path / "src" / ".." / ".." / "etc" / "passwd")
        assert rule.matches("write_file", {"path": escape_path}, work_dir=tmp_path) is False

    def test_many_rules_performance(self):
        rules = [PolicyRule(id=f"r{i}", tool=f"tool_{i}", action="allow") for i in range(1000)]
        engine = PolicyEngine(rules=rules)
        decision = engine.evaluate("tool_999", {})
        assert decision.action == "allow"
        decision = engine.evaluate("nonexistent", {})
        assert decision.action == "prompt"

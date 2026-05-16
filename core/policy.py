from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import yaml

logger = logging.getLogger("model-chat.policy")


@dataclass
class PolicyDecision:
    action: str  # "allow" | "deny" | "prompt"
    reason: str
    rule_id: str


@dataclass
class PolicyRule:
    id: str
    tool: str  # tool name or "*"
    action: str  # "allow" | "deny" | "prompt"
    priority: int = 0
    conditions: dict = field(default_factory=dict)

    def matches(self, tool_name: str, arguments: dict, work_dir: Path | None = None) -> bool:
        if self.tool != "*" and not fnmatch.fnmatch(tool_name, self.tool):
            return False
        if not self.conditions:
            return True
        return self._check_conditions(arguments, work_dir)

    def _check_conditions(self, arguments: dict, work_dir: Path | None) -> bool:
        for cond_type, cond_value in self.conditions.items():
            if cond_type == "path_within":
                if not self._check_path_within(arguments, cond_value, work_dir):
                    return False
            elif cond_type == "command_matches":
                if not self._check_command_matches(arguments, cond_value):
                    return False
            elif cond_type == "command_blocked":
                if self._check_command_blocked(arguments, cond_value):
                    return False
            elif cond_type == "argument_matches" and not self._check_argument_matches(
                arguments, cond_value
            ):
                return False
        return True

    def _check_path_within(
        self, arguments: dict, patterns: list[str], work_dir: Path | None
    ) -> bool:
        raw_path = arguments.get("path", "")
        if not raw_path:
            return False
        if work_dir:
            try:
                abs_path = Path(raw_path).resolve()
                rel = abs_path.relative_to(work_dir.resolve())
                check_path = str(PurePosixPath(rel))
            except (ValueError, OSError):
                check_path = raw_path
        else:
            check_path = raw_path
        return any(fnmatch.fnmatch(check_path, p) for p in patterns)

    def _check_command_matches(self, arguments: dict, patterns: list[str]) -> bool:
        command = arguments.get("command", "")
        if not command:
            return False
        return any(fnmatch.fnmatch(command, p) for p in patterns)

    def _check_command_blocked(self, arguments: dict, patterns: list[str]) -> bool:
        command = arguments.get("command", "")
        if not command:
            return False
        return any(fnmatch.fnmatch(command, p) for p in patterns)

    def _check_argument_matches(self, arguments: dict, matchers: dict[str, str]) -> bool:
        for key, pattern in matchers.items():
            value = arguments.get(key)
            if value is None:
                return False
            if not fnmatch.fnmatch(str(value), pattern):
                return False
        return True


class PolicyEngine:
    def __init__(self, rules: list[PolicyRule], default_action: str = "prompt"):
        if default_action not in ("allow", "deny", "prompt"):
            raise ValueError(f"Invalid default_action: {default_action}")
        self.default_action = default_action
        self.rules = sorted(rules, key=lambda r: r.priority, reverse=True)

    def evaluate(
        self, tool_name: str, arguments: dict, work_dir: Path | None = None
    ) -> PolicyDecision:
        for rule in self.rules:
            if rule.matches(tool_name, arguments, work_dir):
                logger.debug("policy: %s matched rule %s → %s", tool_name, rule.id, rule.action)
                return PolicyDecision(
                    action=rule.action,
                    reason=f"matched rule '{rule.id}'",
                    rule_id=rule.id,
                )
        return PolicyDecision(
            action=self.default_action,
            reason="no matching rule, using default",
            rule_id="__default__",
        )

    @classmethod
    def from_dict(cls, data: dict) -> PolicyEngine:
        default_action = data.get("default_action", "prompt")
        raw_rules = data.get("rules", [])
        rules = []
        for r in raw_rules:
            rules.append(
                PolicyRule(
                    id=r["id"],
                    tool=r["tool"],
                    action=r["action"],
                    priority=r.get("priority", 0),
                    conditions=r.get("conditions", {}),
                )
            )
        return cls(rules=rules, default_action=default_action)

    @classmethod
    def from_yaml(cls, path: Path) -> PolicyEngine:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Policy file must be a YAML mapping, got {type(data).__name__}")
        return cls.from_dict(data)

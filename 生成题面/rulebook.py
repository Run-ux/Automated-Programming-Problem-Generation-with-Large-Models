from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL_KEYS = {
    "global_constraints",
    "global_redlines",
    "modes",
}

CANONICAL_MODE_NAMES = (
    "single_seed_extension",
    "same_family_fusion",
    "cross_family_fusion",
)

MODE_NAME_ALIASES = {
    "single": "single_seed_extension",
    "single_seed_extension": "single_seed_extension",
    "same_family": "same_family_fusion",
    "same_family_fusion": "same_family_fusion",
    "cross_family_fusion": "cross_family_fusion",
}


def normalize_mode_name(mode: str) -> str:
    normalized = str(mode).strip()
    try:
        return MODE_NAME_ALIASES[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported mode: {mode}") from exc


def normalize_rule_id(rule_id: str) -> str:
    return str(rule_id).strip()


def _normalize_rule_entry(rule: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(rule)
    normalized["id"] = normalize_rule_id(normalized.get("id", ""))
    core_transformation = normalized.get("core_transformation")
    if isinstance(core_transformation, dict) and core_transformation.get("primary_operator"):
        core_transformation["primary_operator"] = normalize_rule_id(core_transformation["primary_operator"])
    return normalized


@dataclass
class RuleBook:
    path: Path
    payload: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "RuleBook":
        target = Path(path)
        payload = json.loads(target.read_text(encoding="utf-8"))
        missing = REQUIRED_TOP_LEVEL_KEYS - set(payload)
        if missing:
            raise ValueError(f"Rule file missing keys: {', '.join(sorted(missing))}")
        raw_modes = payload.get("modes", {})
        modes: dict[str, dict[str, Any]] = {}
        for raw_mode_name, raw_mode_config in raw_modes.items():
            if not isinstance(raw_mode_config, dict):
                continue
            mode_name = normalize_mode_name(raw_mode_name)
            mode_config = dict(raw_mode_config)
            mode_config["rules"] = [
                _normalize_rule_entry(rule)
                for rule in mode_config.get("rules", [])
                if isinstance(rule, dict)
            ]
            modes[mode_name] = mode_config
        for mode in CANONICAL_MODE_NAMES:
            modes.setdefault(mode, {"enabled": False, "rules": []})
        payload["modes"] = modes
        return cls(path=target, payload=payload)

    def global_constraints(self) -> dict[str, Any]:
        return dict(self.payload.get("global_constraints", {}))

    def global_redlines(self) -> list[str]:
        redlines = self.payload.get("global_redlines", {}).get("items", [])
        return [str(item) for item in redlines]

    def mode_config(self, mode: str) -> dict[str, Any]:
        return dict(self.payload.get("modes", {}).get(normalize_mode_name(mode), {}))

    def enabled_rules(self, mode: str, allowed_rule_ids: set[str] | None = None) -> list[dict[str, Any]]:
        config = self.mode_config(mode)
        if not config.get("enabled", False):
            return []
        normalized_allowed_ids = (
            {normalize_rule_id(rule_id) for rule_id in allowed_rule_ids}
            if allowed_rule_ids is not None
            else None
        )
        rules = []
        for rule in config.get("rules", []):
            if not isinstance(rule, dict) or not rule.get("enabled", False):
                continue
            rule_id = normalize_rule_id(rule.get("id", ""))
            if not rule_id:
                continue
            if normalized_allowed_ids is not None and rule_id not in normalized_allowed_ids:
                continue
            rules.append(dict(rule))
        return rules

    def rule(self, mode: str, rule_id: str) -> dict[str, Any]:
        target_rule_id = normalize_rule_id(rule_id)
        for rule in self.mode_config(mode).get("rules", []):
            if normalize_rule_id(rule.get("id", "")) == target_rule_id:
                return dict(rule)
        raise KeyError(f"Rule {rule_id!r} not found for mode {mode!r}")

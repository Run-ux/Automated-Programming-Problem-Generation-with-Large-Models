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


def _normalize_helper_entry(helper: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(helper)
    helper_id = normalize_rule_id(normalized.get("id", ""))
    if not helper_id:
        raise ValueError("Rule helper missing id")
    normalized["id"] = helper_id
    normalized["summary"] = str(normalized.get("summary", "")).strip()
    normalized["semantic_purpose"] = str(normalized.get("semantic_purpose", "")).strip()
    normalized["innovation_role"] = str(normalized.get("innovation_role", "")).strip()
    normalized["difficulty_role"] = str(normalized.get("difficulty_role", "")).strip()
    normalized["must_realize_in"] = [
        str(item).strip()
        for item in normalized.get("must_realize_in", [])
        if str(item).strip()
    ]
    normalized["target_axes"] = [
        str(item).strip()
        for item in normalized.get("target_axes", [])
        if str(item).strip()
    ]
    normalized["prompt_guidance"] = [
        str(item).strip()
        for item in normalized.get("prompt_guidance", [])
        if str(item).strip()
    ]
    normalized["redlines"] = [
        str(item).strip()
        for item in normalized.get("redlines", [])
        if str(item).strip()
    ]
    missing_fields = [
        field_name
        for field_name, present in (
            ("summary", bool(normalized["summary"])),
            ("semantic_purpose", bool(normalized["semantic_purpose"])),
            ("must_realize_in", bool(normalized["must_realize_in"])),
            ("target_axes", bool(normalized["target_axes"])),
            ("innovation_role", bool(normalized["innovation_role"])),
            ("difficulty_role", bool(normalized["difficulty_role"])),
            ("prompt_guidance", bool(normalized["prompt_guidance"])),
            ("redlines", bool(normalized["redlines"])),
        )
        if not present
    ]
    if missing_fields:
        raise ValueError(
            f"Rule helper {helper_id} missing required fields: {', '.join(missing_fields)}"
        )
    return normalized


def _merge_required_fields(defaults: dict[str, Any], rule_level: dict[str, Any]) -> dict[str, Any]:
    default_fields = [
        str(field).strip()
        for field in defaults.get("required_fields", [])
        if str(field).strip()
    ]
    rule_fields = [
        str(field).strip()
        for field in rule_level.get("required_fields", [])
        if str(field).strip()
    ]
    merged_fields: list[str] = []
    for field in default_fields + rule_fields:
        if field not in merged_fields:
            merged_fields.append(field)
    return {"required_fields": merged_fields}


def _normalize_rule_entry(rule: dict[str, Any], *, mode_defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = copy.deepcopy(rule)
    normalized["id"] = normalize_rule_id(normalized.get("id", ""))
    normalized["family"] = str(normalized.get("family", "")).strip()
    normalized["handler"] = normalize_rule_id(normalized.get("handler", ""))
    normalized["audit_tags"] = [str(item).strip() for item in normalized.get("audit_tags", []) if str(item).strip()]
    helpers = [
        _normalize_helper_entry(helper)
        for helper in normalized.get("helpers", [])
        if isinstance(helper, dict)
    ]
    helper_ids = [helper["id"] for helper in helpers]
    if len(helper_ids) != len(set(helper_ids)):
        duplicate_ids = sorted({helper_id for helper_id in helper_ids if helper_ids.count(helper_id) > 1})
        raise ValueError(f"Rule {normalized['id'] or '<unknown>'} has duplicate helper ids: {', '.join(duplicate_ids)}")
    normalized["helpers"] = helpers
    normalized["planner_output_contract"] = _merge_required_fields(
        dict((mode_defaults or {}).get("planner_output_contract", {})),
        dict(normalized.get("planner_output_contract", {})),
    )
    core_transformation = normalized.get("core_transformation")
    if isinstance(core_transformation, dict) and core_transformation.get("primary_operator"):
        core_transformation["primary_operator"] = normalize_rule_id(core_transformation["primary_operator"])
    if normalized.get("enabled", False):
        missing_fields = []
        if not normalized["id"]:
            missing_fields.append("id")
        if not normalized["family"]:
            missing_fields.append("family")
        if not normalized["handler"]:
            missing_fields.append("handler")
        if not helpers:
            missing_fields.append("helpers")
        if not normalized.get("required_axis_changes", {}).get("must_change", []):
            missing_fields.append("required_axis_changes.must_change")
        if not normalized["planner_output_contract"].get("required_fields", []):
            missing_fields.append("planner_output_contract.required_fields")
        if missing_fields:
            raise ValueError(
                f"Rule {normalized['id'] or '<unknown>'} missing required execution fields: {', '.join(missing_fields)}"
            )
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
        payload.setdefault("version", "legacy")
        raw_modes = payload.get("modes", {})
        modes: dict[str, dict[str, Any]] = {}
        for raw_mode_name, raw_mode_config in raw_modes.items():
            if not isinstance(raw_mode_config, dict):
                continue
            mode_name = normalize_mode_name(raw_mode_name)
            mode_config = dict(raw_mode_config)
            mode_defaults = {
                "planner_output_contract": _merge_required_fields(
                    {},
                    dict(mode_config.get("planner_output_contract", {})),
                )
            }
            mode_config["rules"] = [
                _normalize_rule_entry(rule, mode_defaults=mode_defaults)
                for rule in mode_config.get("rules", [])
                if isinstance(rule, dict)
            ]
            mode_config["planner_output_contract"] = mode_defaults["planner_output_contract"]
            modes[mode_name] = mode_config
        for mode in CANONICAL_MODE_NAMES:
            modes.setdefault(mode, {"enabled": False, "rules": []})
        payload["modes"] = modes
        return cls(path=target, payload=payload)

    def version(self) -> str:
        return str(self.payload.get("version", "legacy")).strip() or "legacy"

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

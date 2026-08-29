from __future__ import annotations

import json

import pytest

from app.cli import _adaptation_plans, _market_profile, build_parser


def test_create_cli_builds_complete_localization_profile(tmp_path):
    terminology = tmp_path / "terms.json"
    terminology.write_text(
        json.dumps({"编制": "stable institutional career"}), encoding="utf-8"
    )
    args = build_parser().parse_args(
        [
            "create",
            "script.txt",
            "--market",
            "United States",
            "--audience",
            "18-30",
            "--target-language",
            "Spanish",
            "--target-locale",
            "es-MX",
            "--style-guide",
            "Mexican streaming drama",
            "--terminology-map",
            str(terminology),
        ]
    )

    profile = _market_profile(args)
    assert profile.target_language == "Spanish"
    assert profile.target_locale == "es-MX"
    assert profile.terminology_map == {"编制": "stable institutional career"}


def test_render_cli_supports_text_or_structured_output():
    parser = build_parser()
    text_args = parser.parse_args(["render", "abcd"])
    json_args = parser.parse_args(["render", "abcd", "--json", "--out", "target.json"])

    assert text_args.json is False
    assert json_args.json is True
    assert json_args.out == "target.json"


def test_baseline_cli_rejects_malformed_plan():
    with pytest.raises(ValueError, match="MECHANISM_ID:OPTION_LABEL"):
        _adaptation_plans(["CM01"])

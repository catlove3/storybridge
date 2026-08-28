from __future__ import annotations

import json

from app.schemas import StoryState
from app.storage import MarketProfile, ProjectStore
from tests.fixtures import sample_story_state_dict


def test_load_state_corrupted_json(tmp_path):
    store = ProjectStore(tmp_path / "p")
    meta = store.create_project("bad", "script", MarketProfile())
    (tmp_path / "p" / meta.id / "state.json").write_text("{broken json!!", encoding="utf-8")

    loaded = store.load_state(meta.id)
    assert loaded is None


def test_load_state_wrong_schema(tmp_path):
    store = ProjectStore(tmp_path / "p")
    meta = store.create_project("wrong", "script", MarketProfile())
    (tmp_path / "p" / meta.id / "state.json").write_text(
        json.dumps({"hello": "world"}), encoding="utf-8"
    )
    assert store.load_state(meta.id) is None


def test_corrupted_revisions_ignored(tmp_path):
    store = ProjectStore(tmp_path / "p")
    meta = store.create_project("rev", "script", MarketProfile())
    state = StoryState.model_validate(sample_story_state_dict())
    store.save_state(meta.id, state, "initial_parse")

    rev_path = tmp_path / "p" / meta.id / "revisions.json"
    rev_path.write_text("not json at all", encoding="utf-8")

    assert store.list_revisions(meta.id) == []
    store.save_state(meta.id, state, "adaptation_applied")
    assert len(store.list_revisions(meta.id)) == 1


def test_empty_projects_dir_listing(tmp_path):
    store = ProjectStore(tmp_path / "p")
    assert store.list_projects() == []


def test_stray_directory_in_projects_ignored(tmp_path):
    store = ProjectStore(tmp_path / "p")
    (tmp_path / "p" / "not-a-project").mkdir(parents=True)
    assert store.list_projects() == []


def test_plan_survives_corrupted_plans_file(tmp_path):
    store = ProjectStore(tmp_path / "p")
    meta = store.create_project("plans", "script", MarketProfile())
    (tmp_path / "p" / meta.id / "plans.json").write_text("garbage", encoding="utf-8")

    assert store.load_plans(meta.id) == []
    try:
        from app.schemas import AdaptationOption, AdaptationPlan

        plan = AdaptationPlan(
            culture_mechanism_id="CM01",
            original_name="编制",
            options=[
                AdaptationOption(
                    option_label="A",
                    strategy="preserve",
                    title="a",
                    replacement_definition="a",
                    rationale="a",
                ),
                AdaptationOption(
                    option_label="B",
                    strategy="functional_replacement",
                    title="t",
                    replacement_definition="d",
                    rationale="r",
                ),
                AdaptationOption(
                    option_label="C",
                    strategy="plot_reconstruction",
                    title="c",
                    replacement_definition="c",
                    rationale="c",
                ),
            ],
        )
        store.save_plan(meta.id, plan)
        assert store.load_plan(meta.id, "CM01") is not None
    except json.JSONDecodeError:
        raise AssertionError("save_plan should not re-read corrupted file as JSON")


def test_history_snapshot_written(tmp_path):
    store = ProjectStore(tmp_path / "p")
    meta = store.create_project("hist", "script", MarketProfile())
    state = StoryState.model_validate(sample_story_state_dict())
    store.save_state(meta.id, state, "initial_parse")
    store.save_state(meta.id, state, "repair")

    history = tmp_path / "p" / meta.id / "history"
    files = sorted(f.name for f in history.iterdir())
    assert files == ["rev001.json", "rev002.json"]

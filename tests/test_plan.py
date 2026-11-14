"""Test the plan, review and apply steps."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image

from classify.exception import ClassifyException
from classify.plan import check_folder, resolve_decisions
from tests.conftest import ClassifyFactory, make_picture, write_config

PARTY_DAY = datetime(2026, 3, 14, 10)


@pytest.fixture
def config(config_home: Path) -> Path:
    """Write a configuration without metadata, for any exiftool installation."""
    return write_config(config_home, language="en", write_metadata=False)


@pytest.fixture
def party(input_dir: Path) -> list[Path]:
    """Add pictures of a party, a burst of files on a single day."""
    return [
        make_picture(
            input_dir / f"party/IMG_{index}.jpg",
            PARTY_DAY + index * timedelta(minutes=10),
        )
        for index in range(15)
    ]


def snapshot(directory: Path) -> list[str]:
    """Return the files of a directory."""
    return sorted(
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file()
    )


def write_plan(
    make_classify: ClassifyFactory, output_dir: Path, plan_path: Path
) -> dict:
    """Write and return the plan of the sample files."""
    make_classify("--output", str(output_dir), "--plan", str(plan_path)).run()
    return json.loads(plan_path.read_text(encoding="utf-8"))


@pytest.mark.usefixtures("config", "party")
def test_plan_lists_groups_without_changing_files(
    make_classify: ClassifyFactory, input_dir: Path, output_dir: Path, tmp_path: Path
) -> None:
    """The plan lists the events and the other days, the files stay in place."""
    (output_dir / "2025" / "Friends").mkdir(parents=True)
    (output_dir / "2025" / "Friends" / "a.jpg").touch()
    before = snapshot(input_dir)

    plan = write_plan(make_classify, output_dir, tmp_path / "plan.json")

    assert snapshot(input_dir) == before
    assert snapshot(output_dir) == ["2025/Friends/a.jpg"]
    assert plan["folders"] == {"2025": {"Friends": 1}}
    assert plan["default_folder"] == "Misc"
    kinds = [group["kind"] for group in plan["groups"]]
    assert kinds == ["day", "day", "day", "burst"]
    burst = plan["groups"][-1]
    assert burst["id"] == "g004"
    assert burst["suggestion"] is None
    assert len(burst["files"]) == 15
    assert burst["files"][0]["path"] == "party/IMG_0.jpg"
    assert burst["files"][0]["date"] == "2026-03-14T10:00:00"


@pytest.mark.usefixtures("party")
def test_plan_suggests_rule_folders(
    make_classify: ClassifyFactory,
    config_home: Path,
    input_dir: Path,
    output_dir: Path,
    tmp_path: Path,
) -> None:
    """Recurring dates get their age, sources name the folder of single files."""
    write_config(
        config_home,
        language="en",
        write_metadata=False,
        recurring={"Birthday Lea {age}": {"date": "03-14", "since": 2020}},
        sources=[{"folder": "School", "camera": "none", "name": r"^school-\d+"}],
    )
    make_picture(input_dir / "school-1.jpg", datetime(2026, 5, 4, 9))

    plan = write_plan(make_classify, output_dir, tmp_path / "plan.json")

    by_kind = {group["kind"]: group for group in plan["groups"]}
    assert by_kind["recurring"]["suggestion"] == "2026/Birthday Lea 6"
    school = next(
        file
        for group in plan["groups"]
        for file in group["files"]
        if file["path"] == "school-1.jpg"
    )
    assert school["suggestion"] == "2026/School"
    assert school["camera"] is None


@pytest.mark.usefixtures("config", "party")
def test_review_page_embeds_plan_and_thumbnails(
    make_classify: ClassifyFactory, output_dir: Path, tmp_path: Path
) -> None:
    """The review page holds the plan, its extra fields and the thumbnails."""
    plan_path = tmp_path / "plan.json"
    plan = write_plan(make_classify, output_dir, plan_path)
    plan["groups"][-1]["proposal"] = "2026/Party </script>"
    plan["groups"][-1]["files"][0]["people"] = ["Lea"]
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    make_classify("--review", str(plan_path)).run()

    page = (tmp_path / "plan.html").read_text(encoding="utf-8")
    assert "data:image/jpeg;base64," in page
    assert '"people": ["Lea"]' in page
    assert "Party <\\/script>" in page
    # Pictures and the video have a thumbnail
    embedded = json.loads(
        page.split('<script id="plan" type="application/json">')[1]
        .split("</script>")[0]
        .replace("<\\/", "</")
    )
    assert len(embedded["thumbnails"]) == 19
    assert embedded["thumbnails"]["dir1/video.mp4"].startswith("data:image/jpeg")


@pytest.mark.usefixtures("config", "party")
def test_apply_sorts_only_decided_files(
    make_classify: ClassifyFactory, input_dir: Path, output_dir: Path, tmp_path: Path
) -> None:
    """Decided files go to their folder, the others stay in place."""
    # Without EXIF date nor date in its name
    Image.new("RGB", (8, 8)).save(input_dir / "drawing.png")
    decisions = tmp_path / "decisions.json"
    decisions.write_text(
        json.dumps(
            {
                "decisions": {
                    "party/IMG_0.jpg": "2026/Party",
                    "party/IMG_1.jpg": "2026/Us",
                    "drawing.png": "2026/School",
                    "missing.jpg": "2026/Party",
                    "party/IMG_2.jpg": "",
                }
            }
        ),
        encoding="utf-8",
    )

    make_classify("--output", str(output_dir), "--apply", str(decisions)).run()

    assert snapshot(output_dir) == [
        "2026/Party/2026-03-14-10h00m00.jpg",
        "2026/School/drawing.png",
        "2026/Us/2026-03-14-10h10m00.jpg",
    ]
    assert (input_dir / "party" / "IMG_2.jpg").exists()
    assert (input_dir / "dir1" / "IMG_1001.jpg").exists()


@pytest.mark.usefixtures("config", "party")
def test_apply_plan_uses_proposals_then_suggestions(
    make_classify: ClassifyFactory, output_dir: Path, tmp_path: Path
) -> None:
    """A plan is applied with its proposals, files without folder stay in place."""
    plan_path = tmp_path / "plan.json"
    plan = write_plan(make_classify, output_dir, plan_path)
    burst = plan["groups"][-1]
    burst["proposal"] = "2026/Party"
    burst["files"][0]["proposal"] = "2026/Us"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    make_classify("--output", str(output_dir), "--apply", str(plan_path)).run()

    files = snapshot(output_dir)
    assert len(files) == 15
    assert "2026/Us/2026-03-14-10h00m00.jpg" in files
    assert sum(file.startswith("2026/Party/") for file in files) == 14


def test_resolve_decisions_priority() -> None:
    """The file proposal wins, then the group one, then the suggestions."""
    plan = {
        "groups": [
            {
                "proposal": "2026/Group",
                "suggestion": "2026/Event",
                "files": [
                    {"path": "a.jpg", "proposal": "2026/File", "suggestion": None},
                    {"path": "b.jpg", "suggestion": "2026/Rule"},
                ],
            },
            {
                "suggestion": None,
                "files": [
                    {"path": "c.jpg", "suggestion": "2026/Rule"},
                    {"path": "d.jpg", "suggestion": None},
                ],
            },
        ]
    }
    assert resolve_decisions(plan) == {
        "a.jpg": "2026/File",
        "b.jpg": "2026/Group",
        "c.jpg": "2026/Rule",
    }


@pytest.mark.parametrize("folder", ["../2026", "/etc", "2026//x", "", 3, "2026/.."])
def test_check_folder_rejects_unsafe_paths(folder: object) -> None:
    """Folders must stay inside the output directory."""
    with pytest.raises(ClassifyException):
        check_folder(folder)


def test_check_folder_sanitizes_names() -> None:
    """Folder names are cleaned like the event names."""
    assert check_folder("2026/Party. ") == "2026/Party"

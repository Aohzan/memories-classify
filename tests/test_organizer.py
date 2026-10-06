"""Test organizer module, sorting the files by event."""

import builtins
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from classify import organizer
from classify.config import load_config
from classify.const import EVENTS_STATE_FILE_NAME
from classify.events import Event, EventKind, MediaInfo
from classify.geo import Location
from classify.organizer import EventsState, sanitize_name
from tests.conftest import ClassifyFactory, make_picture, write_config

PARTY_DAY = datetime(2026, 3, 14, 10)
PARTY_FILES = [
    f"{(PARTY_DAY + index * timedelta(minutes=10)):%Y-%m-%d-%Hh%Mm%S}.jpg"
    for index in range(15)
]
# Folders of the sample files, out of any event
MISC_FILES = [
    "2015/Misc/2015-08-07-09h13m02.mp4",
    "2017/Misc/2017-11-11-15h18m17.jpg",
    "2020/Misc/2020-02-24-12h29m52.jpg",
]


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


@pytest.fixture
def config(config_home: Path) -> Path:
    """Write a configuration without metadata, for any exiftool installation."""
    return write_config(config_home, language="en", write_metadata=False)


def set_answers(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> list[str]:
    """Answer the questions with the given answers, recording the prompts."""
    prompts: list[str] = []
    answers_iterator: Iterator[str] = iter(answers)

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        try:
            return next(answers_iterator)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr(organizer, "is_interactive", lambda: True)
    monkeypatch.setattr(builtins, "input", fake_input)
    return prompts


def output_files(output_dir: Path) -> list[str]:
    """Return the media files of the output directory."""
    return sorted(
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file() and path.name != EVENTS_STATE_FILE_NAME
    )


@pytest.mark.usefixtures("party", "config")
def test_events_interactive(
    make_classify: ClassifyFactory,
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    opened_folders: list[list[str]],
) -> None:
    """Named events and other files are sorted in year folders."""
    prompts = set_answers(monkeypatch, ["Léa's birthday"])

    make_classify("--output", str(output_dir), "--keep-original", "--events").run()

    assert len(prompts) == 1
    assert output_files(output_dir) == sorted(
        [
            *MISC_FILES,
            *(f"2026/Léa's birthday/{name}" for name in PARTY_FILES),
        ]
    )
    # The preview shows pictures spread over the event
    assert len(opened_folders) == 1
    assert len(opened_folders[0]) == 12
    assert opened_folders[0][0] == "00-IMG_0.jpg"
    assert opened_folders[0][-1] == "11-IMG_14.jpg"


@pytest.mark.usefixtures("party", "config")
def test_events_skipped(
    make_classify: ClassifyFactory,
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Files of a skipped event go to the default folder."""
    set_answers(monkeypatch, ["-"])

    make_classify("--output", str(output_dir), "--keep-original", "--events").run()

    assert all((output_dir / "2026/Misc" / name).exists() for name in PARTY_FILES)


@pytest.mark.usefixtures("party", "config")
def test_events_non_interactive(
    make_classify: ClassifyFactory,
    output_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Events are not sorted without answers, only reported."""
    make_classify(
        "--output", str(output_dir), "--keep-original", "--events", "--no-interactive"
    ).run()

    assert "1 events detected, run interactively to name them" in caplog.text
    # Files of the event to name are left untouched until named
    assert not (output_dir / "party").exists()
    assert all((output_dir / path).exists() for path in MISC_FILES)


@pytest.mark.usefixtures("party", "config")
def test_events_second_run(
    make_classify: ClassifyFactory,
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second run reuses the names given and does not move the files."""
    set_answers(monkeypatch, ["Party"])
    make_classify("--output", str(output_dir), "--keep-original", "--events").run()
    files_after_first_run = output_files(output_dir)

    prompts = set_answers(monkeypatch, [])
    make_classify(
        "--output", str(output_dir), "--keep-original", "--events", "--no-interactive"
    ).run()

    assert prompts == []
    assert output_files(output_dir) == files_after_first_run
    assert (output_dir / "2026/Party").is_dir()


@pytest.mark.usefixtures("party", "config")
def test_events_in_place(
    make_classify: ClassifyFactory,
    input_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Files are moved to the year folders, and stay there on a second run."""
    set_answers(monkeypatch, ["Party"])
    make_classify("--events").run()
    files_after_first_run = output_files(input_dir)

    set_answers(monkeypatch, [])
    make_classify("--events").run()

    assert output_files(input_dir) == files_after_first_run
    assert "2026/Party/2026-03-14-10h00m00.jpg" in files_after_first_run
    assert "2015/Misc/2015-08-07-09h13m02.mp4" in files_after_first_run
    assert not list((input_dir / "party").iterdir())


@pytest.mark.usefixtures("party", "config")
def test_pending_events_not_moved(
    make_classify: ClassifyFactory,
    input_dir: Path,
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Moved files of events to name stay in the input, to be named later."""
    make_classify("--output", str(output_dir), "--events", "--no-interactive").run()

    assert len(list((input_dir / "party").iterdir())) == len(PARTY_FILES)
    assert (output_dir / MISC_FILES[1]).exists()

    set_answers(monkeypatch, ["Party"])
    make_classify("--output", str(output_dir), "--events").run()

    assert not list((input_dir / "party").iterdir())
    assert len(list((output_dir / "2026/Party").iterdir())) == len(PARTY_FILES)


@pytest.mark.usefixtures("party")
def test_events_dry_run(
    make_classify: ClassifyFactory,
    output_dir: Path,
    config_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dry run only writes the configuration and the answers, reused next run."""
    set_answers(monkeypatch, ["Party"])

    make_classify("--output", str(output_dir), "--events", "--dry-run").run()

    assert [path.name for path in output_dir.rglob("*")] == [EVENTS_STATE_FILE_NAME]
    assert (config_home / "memories-classify.yaml").exists()

    prompts = set_answers(monkeypatch, [])
    make_classify("--output", str(output_dir), "--keep-original", "--events").run()
    assert prompts == []
    assert len(list((output_dir / "2026/Party").iterdir())) == len(PARTY_FILES)


def test_default_folder_name(
    make_classify: ClassifyFactory,
    output_dir: Path,
    config_home: Path,
) -> None:
    """The default folder name can be configured."""
    write_config(
        config_home, language="fr", write_metadata=False, names={"default": "Autres"}
    )

    make_classify(
        "--output", str(output_dir), "--keep-original", "--events", "--no-interactive"
    ).run()

    assert (output_dir / "2020/Autres/2020-02-24-12h29m52.jpg").exists()


def test_home_confirmed_and_trip(
    make_classify: ClassifyFactory,
    input_dir: Path,
    output_dir: Path,
    config_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Home is guessed then saved, and trips are named from their city."""
    config_path = write_config(config_home, language="fr", write_metadata=False)
    for day in range(10):
        make_picture(
            input_dir / f"home/{day}.jpg",
            datetime(2025, 6, 1 + day, 12),
            Location(45.7640, 4.8357),
        )
    for index in range(12):
        make_picture(
            input_dir / f"trip/{index}.jpg",
            datetime(2025, 7, 1, 10) + index * timedelta(hours=10),
            Location(43.4832, -1.5586),
        )
    prompts = set_answers(monkeypatch, ["", ""])

    make_classify(
        "--output", str(output_dir), "--keep-original", "--events", "--language", "en"
    ).run()

    assert prompts[0].startswith("Home detected near")
    assert "[Holidays in Biarritz 2025]" in prompts[1]
    assert len(list((output_dir / "2025/Holidays in Biarritz 2025").iterdir())) == 12
    assert len(list((output_dir / "2025/Misc").iterdir())) == 10
    config = load_config(config_path)
    assert config.home == Location(45.76, 4.84)
    # The language given on the command line is not saved
    assert config.language == "fr"


def test_home_entered_manually(
    make_classify: ClassifyFactory,
    input_dir: Path,
    config_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wrong home guess is replaced by the location entered."""
    config_path = write_config(config_home, write_metadata=False)
    make_picture(input_dir / "home.jpg", datetime(2025, 6, 1), Location(45.76, 4.83))
    set_answers(monkeypatch, ["n", "not a location", "48.85, 2.35"])

    make_classify("--events", "--dry-run").run()

    # Saved even in dry run
    assert load_config(config_path).home == Location(48.85, 2.35)


@pytest.mark.usefixtures("party", "config")
def test_no_answer_stops_questions(
    make_classify: ClassifyFactory,
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without more answers, the remaining events are only reported."""
    set_answers(monkeypatch, [])

    make_classify("--output", str(output_dir), "--keep-original", "--events").run()

    assert "No more answers" in caplog.text
    assert not (output_dir / "party").exists()


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Vacances à Biarritz 2025", "Vacances à Biarritz 2025"),
        ("AC/DC concert", "AC-DC concert"),
        ("  Party\t\n ", "Party"),
        ("Trip...", "Trip"),
    ],
)
def test_sanitize_name(name: str, expected: str) -> None:
    """Names are usable as folder names."""
    assert sanitize_name(name) == expected


def test_decision_matches_same_kind(tmp_path: Path) -> None:
    """A decision is reused for events of the same kind only, and is saved."""
    path = tmp_path / EVENTS_STATE_FILE_NAME
    burst = Event(EventKind.BURST, [MediaInfo("burst.jpg", datetime(2025, 7, 3, 12))])
    trip = Event(
        EventKind.TRIP,
        [
            MediaInfo("first.jpg", datetime(2025, 7, 1, 12)),
            MediaInfo("last.jpg", datetime(2025, 7, 10, 12)),
        ],
    )
    state = EventsState(path)
    state.add(burst, None)
    state.save()

    state = EventsState(path)
    assert state.find(trip) is None
    decision = state.find(burst)
    assert decision is not None
    assert decision.name is None


def test_no_answer_for_home(
    make_classify: ClassifyFactory,
    input_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without answer to the home question, trips are not detected."""
    make_picture(input_dir / "home.jpg", datetime(2025, 6, 1), Location(45.76, 4.83))
    set_answers(monkeypatch, [])

    make_classify("--events", "--dry-run").run()

    assert "No more answers, trips are not detected" in caplog.text


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("../../outside", "..-..-outside"),
        ("/tmp/outside", "-tmp-outside"),
        ("..", None),
    ],
)
def test_saved_names_sanitized(tmp_path: Path, name: str, expected: str | None) -> None:
    """Names read from the events file cannot escape the output directory."""
    path = tmp_path / EVENTS_STATE_FILE_NAME
    path.write_text(
        f"- kind: burst\n  start: '2025-07-03T12:00:00'\n"
        f"  end: '2025-07-03T12:00:00'\n  name: '{name}'\n",
        encoding="utf-8",
    )
    burst = Event(EventKind.BURST, [MediaInfo("burst.jpg", datetime(2025, 7, 3, 12))])

    decision = EventsState(path).find(burst)

    assert decision is not None
    assert decision.name == expected


@pytest.mark.usefixtures("config")
def test_answers_saved_when_interrupted(
    make_classify: ClassifyFactory,
    input_dir: Path,
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answers given before an interruption are kept for the next run."""
    for day, hour in ((14, 10), (21, 10)):
        for index in range(15):
            make_picture(
                input_dir / f"party{day}/IMG_{index}.jpg",
                datetime(2026, 3, day, hour) + index * timedelta(minutes=10),
            )
    answers = iter(["First party"])

    def interrupted_input(_prompt: str = "") -> str:
        try:
            return next(answers)
        except StopIteration:
            raise KeyboardInterrupt from None

    monkeypatch.setattr(organizer, "is_interactive", lambda: True)
    monkeypatch.setattr(builtins, "input", interrupted_input)
    with pytest.raises(KeyboardInterrupt):
        make_classify("--output", str(output_dir), "--keep-original", "--events").run()

    prompts = set_answers(monkeypatch, ["Second party"])
    make_classify("--output", str(output_dir), "--keep-original", "--events").run()

    assert len(prompts) == 1
    assert len(list((output_dir / "2026/First party").iterdir())) == 15
    assert len(list((output_dir / "2026/Second party").iterdir())) == 15

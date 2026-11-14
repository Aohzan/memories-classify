# Memories Classify

Helping you to keep your personal photo and video memories organized.

## Features

- **Photo and video renamer**: Rename to a standard format with local timezone using the date and time the file was taken (e.g. `PXL_20241014_165237438.jpg` → `2024-10-14-18h52m37.jpg`).
- **Video encoder**: Convert videos to HEVC to reduce file size using ffmpeg (e.g. `PXL_20241010_174118780.TS.mp4` 94 MB → `2024-10-10-19h41m18.mp4` 8 MB).
- **Event organizer** (`--events`): Sort files into year folders by detected event (trips, holidays, birthdays…), from their date and GPS location (e.g. `2025/Holidays in Biarritz 2025/`, `2025/Christmas 2025/`, `2025/Misc/`).

## TODO list

- Check video encoding quality

## Installation

```bash
pipx install memories-classify
# or
uv tool install memories-classify
```

## Usage

[ffmpeg](https://ffmpeg.org/) and ffprobe must be installed.

```bash
memories-classify --directory "~/path/to/my/pics" --dry-run
```

Main options (see `memories-classify --help` for all of them):

- `--output`: write the classified files to another directory, keeping the folder structure
- `--keep-original`: copy the files instead of moving them, a second run does not copy them again
- `--exclude`: regular expressions matched against the start of the paths relative to the directory (e.g. `--exclude "custom/" ".*\.gif$"`)
- `--timezone`: timezone of the dates (e.g. `Europe/Paris`), the system one by default (from `TZ`, `/etc/timezone` or `/etc/localtime`)
- `--ffmpeg-input-extra-args` / `--ffmpeg-output-extra-args`: extra ffmpeg arguments, use the `=` form for values starting with a dash (e.g. `--ffmpeg-input-extra-args="-hwaccel auto"`)

Dates are read from the EXIF data of pictures and the metadata of videos, then from file names: `PXL_20241014_165237438.jpg` (UTC time), `20241014_165237.jpg`, `IMG20241014165237.jpg` (local time) or `IMG-20241014-WA0001.jpg` (WhatsApp, noon). Videos already named by the tool keep the date of their name, and a wrong creation time written by older versions is fixed without encoding (except with `--keep-original`). Name conflicts get a letter suffix (`a`, `b`…).

```bash
my/pics
├── Vacation
│   ├── IMG_1001.jpg
│   ├── IMG_1002.jpg
│   ├── IMG_1003.jpg
│   └── video.mp4
└── Dogs and cats
    └── IMG_2201.jpg
```

will become

```bash
my/pics
├── Vacation
│   ├── 2017-11-11-15h18m17.jpg
│   ├── 2017-11-11-15h18m17a.jpg
│   ├── 2017-11-11-17h21m46.mp4 # 15 MB instead of 94 MB
│   └── 2017-11-11-19h30m01.jpg
└── Dogs and cats
    └── 2020-02-24-12h29m52.jpg
```

## Sort by event

With `--events`, files are sorted into `<year>/<event>/` folders, and the files out of any event into `<year>/Misc/`. Events are detected from the date and the GPS location of the files, without any image analysis:

- **Trips**: series of files far from home during several days, named from the nearest city (offline reverse geocoding). Winter trips in the mountains are skiing trips, short trips from Friday are weekends, trips through several cities are road trips.
- **Holidays**: Christmas, New Year, Easter, Mother's day, Halloween… with enough files on their days.
- **Recurring dates**: your own dates, like birthdays, set in the configuration.
- **Places and sources**: files taken at a known place (a stadium, a school…) or coming from a known source (camera model, file name) go to a folder of their own, without being asked.
- **Bursts**: many files taken in a few hours on a single day, like a party.

For each new event, a preview of its pictures opens in the file manager and its name is asked, with a suggestion. Press Enter to accept the suggestion, type another name, or `-` to skip the event (its files go to the default folder). Answers are saved in `.memories-classify-events.yaml` in the output directory as soon as they are given, even with `--dry-run`: next runs reuse them without asking.

Without a terminal, or with `--no-interactive`, nothing is asked: the new events are only reported in a warning and their files stay in their folder until they are named on an interactive run.

On the first run, home is guessed as the location found on the most days, and saved in the configuration once confirmed, even with `--dry-run`.

When [exiftool](https://exiftool.org/) is installed, the event name is also written in the metadata of the files (keywords and IPTC event, read by photo managers like digiKam or Immich). The originals are never modified with `--keep-original`.

```bash
memories-classify --directory "~/path/to/my/pics" --output "~/Pictures" --keep-original --events
```

### Configuration

The configuration file `~/.config/memories-classify.yaml` (or `$XDG_CONFIG_HOME/memories-classify.yaml`, or the `--config` option) is created with its default values and comments on the first run. It holds the language of the folder names and holidays (`en` or `fr`, the system one by default, `--language` overrides it), home, the detection thresholds, and:

```yaml
language: fr
home: [45.764, 4.8357]
# Override the folder names of the language preset
names:
  default: Autres
  trip: Séjour à {city} {year}
# Holidays naming the events on their days, remove the unwanted ones
holidays:
  Noël: 12-24..12-25
  Pâques: easter..easter+1
  Fête des mères: last-sun-05
# Your own recurring dates, {age} is the number of years since the given year
recurring:
  Anniversaire de mariage: "06-21"
  Anniversaire Léa {age} ans: { date: "03-14", since: 2020 }
# Folders of the files taken near a place, out of any trip or calendar event
places:
  Rugby: { location: [45.7235, 4.8321], radius_km: 0.3 }
# Folders of the files out of any event, from their camera model ("none" for
# files without one) and a regular expression searched in their name
sources:
  - { folder: École, camera: none, name: '^\d{8}_\d{6}_\w+\.jpg$' }
```

Date rules are a fixed date `MM-DD`, a range `MM-DD..MM-DD` (it may span two years, like `12-31..01-01`), a day relative to Easter `easter`, `easter+N` or `easter-N`, or a weekday of a month like `2nd-sun-05` or `last-sun-05`.

The file is rewritten when home is saved: the comments you added are lost.

### Plan, review, apply

Instead of answering questions in a terminal, the sorting can be reviewed in a web page, for example when the files are on a server:

```bash
# 1. Write the plan: detected events, suggested folders, existing folders. No file is changed
memories-classify --directory "~/inbox" --output "~/Pictures" --plan "~/inbox/plan.json"
# 2. Write the review page ~/inbox/plan.html, with the thumbnails of the files
memories-classify --directory "~/inbox" --review "~/inbox/plan.json"
# 3. Open the page, set the folders, download decisions.json, then sort the files
memories-classify --directory "~/inbox" --output "~/Pictures" --apply "~/inbox/decisions.json"
```

The plan lists groups of files: the detected events, and the other files by day. In the review page, a folder is set for a whole group or for a single file, relative to the output directory (like `2025/Christmas 2025`), from the existing folders or a new name. Files without folder are left in place, to be sorted later.

The plan is a JSON file made to be completed before the review, by a script or an AI assistant: a `proposal` on a group or on a file replaces the suggested folder, a `reason` on a group and `people` or `tags` lists on a file are shown in the page. `--apply` also accepts the plan itself, using the proposals then the suggestions.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

```bash
uv sync
pre-commit install
uv run pytest
```

## License

This project is licensed under the GNU General Public License v3.0, see [LICENSE](LICENSE).

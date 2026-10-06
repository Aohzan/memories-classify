# Memories Classify

Helping you to keep your personal photo and video memories organized.

## Features

- **Photo and video renamer**: Rename to a standard format with local timezone using the date and time the file was taken (e.g. `PXL_20241014_165237438.jpg` → `2024-10-14-18h52m37.jpg`).
- **Video encoder**: Convert videos to HEVC to reduce file size using ffmpeg (e.g. `PXL_20241010_174118780.TS.mp4` 94 MB → `2024-10-10-19h41m18.mp4` 8 MB).

## TODO list

- **Photo Organizer**: Automatically organize photos into folders by date or event (vacation, birthday…)
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
- `--timezone`: timezone of the file names (e.g. `Europe/Paris`), the system one by default
- `--ffmpeg-input-extra-args` / `--ffmpeg-output-extra-args`: extra ffmpeg arguments, use the `=` form for values starting with a dash (e.g. `--ffmpeg-input-extra-args="-hwaccel auto"`)

Dates are read from the EXIF data of pictures and the metadata of videos, then from file names like `PXL_20241014_165237438.jpg` (UTC time). Name conflicts get a letter suffix (`a`, `b`…).

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

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

```bash
uv sync
pre-commit install
uv run pytest
```

## License

This project is licensed under the GNU General Public License v3.0, see [LICENSE](LICENSE).

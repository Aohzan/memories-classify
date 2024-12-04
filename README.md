# Memories Classify

Helping you to keep your personal photo and video memories organized.

## Features

- **Photo and video renamer**: Rename to a standard format with local timezone using the date and time the file was taken (e.g. `PXL_20241014_165237438.jpg` → `2024-10-14-18h52m37.jpg`).
- **Video encoder**: Convert videos to HEVC to reduce file size using ffmpeg (e.g. `PXL_20241010_174118780.TS.mp4` 94 MB → `2024-10-10-19h41m18.mp4` 8 MB).

## TODO list

- **Photo Organizer**: Automatically organize photos into folders by date or event (vacation, birthday…)
- Check video encoding quality
- Complete test coverage
- Output directory option
- Keep original file option

## Installation

`pipx install git+https://github.com/Aohzan/memories-classify.git`

## Usage

```bash
memories-classify --directory "~/path/to/my/pics" --dry-run
```

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
│   └── 2017-11-11-17h21m46.mp4 # 15 MB instead of 94 MB
│   ├── 2017-11-11-19h30m01.jpg
└── Dogs and cats
    └── 2020-02-24-12h29m52.jpg
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

```bash
uv venv
source .venv/bin/activate
uv sync
```

## License

This project is licensed under the MIT License.

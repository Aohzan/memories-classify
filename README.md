# Personal Photo Tools

This repository provides a tool names Classify that provides a set of features to automatically organize, rename, and convert photos/videos.

## Features

- **Photo and video renamer**: Rename to a standard format using the date and time the file was taken.
- **Video encoder**: Convert videos to HEVC to reduce file size using ffmpeg.

- **Photo Organizer**: Automatically organize photos into folders by dateor event # TODO

## Installation

`pipx install git+https://github.com/Aohzan/memories-classify.git`

## Usage

```bash
memories-classify --directory "~/path/to/my/pics" --dry-run
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

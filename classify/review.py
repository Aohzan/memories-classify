"""Review page of a plan: a single HTML file to check and change the folders."""

import base64
import io
import json
import logging
import os
import subprocess
from typing import Any

from PIL import Image, ImageOps
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from .const import (
    PICTURE_EXTENSIONS,
    REVIEW_THUMBNAIL_QUALITY,
    REVIEW_THUMBNAIL_SIZE,
)
from .plan import read_json
from .settings import ClassifySettings

_LOGGER = logging.getLogger("classify")

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Memories Classify review</title>
<style>
:root { color-scheme: light dark; --line: #8884; --accent: #2a7ae2; }
body { font: 15px/1.4 system-ui, sans-serif; margin: 0; padding: 0 16px 80px; }
header { position: sticky; top: 0; z-index: 2; background: Canvas; padding: 12px 0;
  border-bottom: 1px solid var(--line); display: flex; gap: 12px; flex-wrap: wrap;
  align-items: center; }
header h1 { font-size: 18px; margin: 0; flex: 1 1 200px; }
button { font: inherit; padding: 6px 12px; cursor: pointer; }
section { border: 1px solid var(--line); border-radius: 8px; margin: 16px 0;
  padding: 12px; }
section.empty { border-color: #d80; }
.head { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
.head b { flex: 1 1 260px; }
.meta { opacity: .75; font-size: 13px; margin: 4px 0 8px; }
input { font: inherit; padding: 4px 6px; min-width: 0; }
.head input { flex: 1 1 280px; }
.files { display: grid; gap: 8px;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
figure { margin: 0; font-size: 12px; overflow: hidden; }
figure img, figure .none { width: 100%; aspect-ratio: 1; object-fit: cover;
  border-radius: 6px; background: #8882; display: block; }
figure.changed img { outline: 3px solid var(--accent); }
figure input { width: 100%; box-sizing: border-box; font-size: 12px; }
figcaption { word-break: break-all; }
.tag { opacity: .75; }
</style>
</head>
<body>
<header>
<h1>Memories Classify review</h1>
<span id="count"></span>
<button id="download">Download decisions.json</button>
<button id="copy">Copy decisions</button>
</header>
<datalist id="folders"></datalist>
<main id="groups"></main>
<script id="plan" type="application/json">__PLAN__</script>
<script>
const plan = JSON.parse(document.getElementById("plan").textContent);
const thumbnails = plan.thumbnails || {};
const element = (tag, properties = {}, children = []) => {
  const node = Object.assign(document.createElement(tag), properties);
  node.append(...children);
  return node;
};
const known = new Set();
for (const [year, names] of Object.entries(plan.folders || {}))
  for (const name of Object.keys(names)) known.add(`${year}/${name}`);
const groupInputs = new Map();
const fileInputs = new Map();
for (const group of plan.groups) {
  const groupFolder = group.proposal || group.suggestion || "";
  if (groupFolder) known.add(groupFolder);
  const input = element("input", {
    value: groupFolder, placeholder: "Folder, empty to leave the files in place",
  });
  input.setAttribute("list", "folders");
  groupInputs.set(group, input);
  const dates = group.start
    ? group.start.replace("T", " ").slice(0, 16) +
      (group.end && group.end.slice(0, 10) !== group.start.slice(0, 10)
        ? " to " + group.end.slice(0, 10) : "")
    : "No date";
  const details = [group.kind, group.place, `${group.files.length} files`]
    .filter(Boolean).join(" - ");
  const files = element("div", { className: "files" });
  for (const file of group.files) {
    const own = file.proposal || file.suggestion || "";
    if (own) known.add(own);
    const fileInput = element("input", { value: own === groupFolder ? "" : own });
    fileInput.setAttribute("list", "folders");
    fileInputs.set(file, fileInput);
    const source = thumbnails[file.path];
    const picture = source
      ? element("img", { src: source, loading: "lazy", title: file.path })
      : element("div", { className: "none" });
    const tags = [
      file.video ? "video" : null, file.city, file.camera,
      ...(file.people || []), ...(file.tags || []),
    ].filter(Boolean).join(", ");
    const figure = element("figure", {}, [
      picture,
      element("figcaption", {}, [
        file.path.split("/").pop(), element("div", { className: "tag", textContent: tags }),
      ]),
      fileInput,
    ]);
    fileInput.addEventListener("input", () => refresh());
    fileInput.figure = figure;
    files.append(figure);
  }
  const section = element("section", {}, [
    element("div", { className: "head" }, [element("b", { textContent: dates }), input]),
    element("div", { className: "meta", textContent:
      details + (group.reason ? " - " + group.reason : "") }),
    files,
  ]);
  input.section = section;
  input.addEventListener("input", () => refresh());
  document.getElementById("groups").append(section);
}
document.getElementById("folders").append(
  ...[...known].sort().reverse().map((value) => element("option", { value })));
const decisions = () => {
  const result = {};
  for (const group of plan.groups)
    for (const file of group.files) {
      const folder = fileInputs.get(file).value.trim()
        || groupInputs.get(group).value.trim();
      if (folder) result[file.path] = folder;
    }
  return { decisions: result };
};
function refresh() {
  let total = 0, decided = 0;
  for (const group of plan.groups) {
    const groupInput = groupInputs.get(group);
    let missing = false;
    for (const file of group.files) {
      const fileInput = fileInputs.get(file);
      fileInput.placeholder = groupInput.value.trim() || "left in place";
      fileInput.figure.classList.toggle("changed", fileInput.value.trim() !== "");
      total += 1;
      if (fileInput.value.trim() || groupInput.value.trim()) decided += 1;
      else missing = true;
    }
    groupInput.section.classList.toggle("empty", missing);
  }
  document.getElementById("count").textContent = `${decided}/${total} files decided`;
}
refresh();
document.getElementById("download").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(decisions(), null, 1)],
    { type: "application/json" });
  const link = element("a", { href: URL.createObjectURL(blob), download: "decisions.json" });
  link.click();
  URL.revokeObjectURL(link.href);
});
document.getElementById("copy").addEventListener("click", async (event) => {
  await navigator.clipboard.writeText(JSON.stringify(decisions(), null, 1));
  event.target.textContent = "Copied";
});
</script>
</body>
</html>
"""


def encode_thumbnail(image: Image.Image) -> str:
    """Return a small JPEG of an image as a data URL."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((REVIEW_THUMBNAIL_SIZE, REVIEW_THUMBNAIL_SIZE))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=REVIEW_THUMBNAIL_QUALITY)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def video_frame(settings: ClassifySettings, path: str, seconds: float) -> bytes:
    """Return a frame of a video as an image file content."""
    result = subprocess.run(
        [
            settings.ffmpeg_path,
            "-v",
            "error",
            "-ss",
            str(seconds),
            "-i",
            path,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else b""


def thumbnail(settings: ClassifySettings, path: str) -> str | None:
    """Return the thumbnail of a picture or a video, None when it cannot be read."""
    try:
        if os.path.splitext(path)[1].lower() in PICTURE_EXTENSIONS:
            with Image.open(path) as image:
                return encode_thumbnail(image)
        # Short videos have no frame after the first second
        frame = video_frame(settings, path, 1) or video_frame(settings, path, 0)
        if not frame:
            return None
        with Image.open(io.BytesIO(frame)) as image:
            return encode_thumbnail(image)
    except Exception:
        _LOGGER.debug("Cannot make the thumbnail of %s", path, exc_info=True)
        return None


def render_review(plan: dict[str, Any]) -> str:
    """Return the review page of a plan holding its thumbnails."""
    # "</" would close the script element holding the plan
    return PAGE.replace(
        "__PLAN__", json.dumps(plan, ensure_ascii=False).replace("</", "<\\/")
    )


def write_review(settings: ClassifySettings, plan_path: str) -> str:
    """Write the review page of a plan next to it, and return its path."""
    plan = read_json(plan_path)
    files = [file for group in plan.get("groups", []) for file in group["files"]]
    thumbnails: dict[str, str] = {}
    with (
        logging_redirect_tqdm(loggers=[_LOGGER]),
        tqdm(files, desc="Thumbnails", unit="file") as progress,
    ):
        for file in progress:
            path = os.path.join(settings.directory, file["path"])
            file["video"] = os.path.splitext(path)[1].lower() not in PICTURE_EXTENSIONS
            if not os.path.exists(path):
                _LOGGER.warning("File %s of the plan not found", file["path"])
            elif data := thumbnail(settings, path):
                thumbnails[file["path"]] = data
    plan["thumbnails"] = thumbnails

    output = os.path.splitext(plan_path)[0] + ".html"
    with open(output, "w", encoding="utf-8") as file:
        file.write(render_review(plan))
    return output

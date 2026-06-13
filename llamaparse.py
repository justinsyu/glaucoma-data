#!/usr/bin/env python3
"""Batch-convert PDFs to Markdown with LlamaParse and local image links."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Iterable

import requests
from dotenv import dotenv_values
from llama_cloud_services import LlamaParse

try:
    import fitz
except ImportError:  # pragma: no cover - only used when local fallback is requested
    fitz = None


DEFAULT_INPUT_DIR = Path("regenxbio_abbv_rgx_314")
IMAGE_LINK_RE = re.compile(r"(!\[[^\]]*]\()([^)\n]+)(\))")
IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".webp"}


def llama_key_names(values: dict[str, str | None]) -> list[str]:
    known_order = [
        "LLAMA_CLOUD_API_KEY",
        "LLAMACLOUD_API_KEY",
        "llamacloud_api_key",
        "lamacloud_api_key",
    ]
    keys: list[str] = []
    for key in known_order:
        if key in os.environ or values.get(key):
            keys.append(key)

    discovered = sorted(
        key
        for key in set(os.environ) | set(values)
        if ("llama" in key.lower() or "lama" in key.lower())
        and "key" in key.lower()
    )
    for key in discovered:
        if key not in keys:
            keys.append(key)
    return keys


def load_api_keys(
    env_path: Path, preferred_key: str | None = None
) -> list[tuple[str, str]]:
    values = dotenv_values(env_path) if env_path.exists() else {}
    if preferred_key:
        value = os.environ.get(preferred_key) or values.get(preferred_key)
        if value:
            return [(preferred_key, value)]
        raise RuntimeError(f"Missing LlamaCloud API key: {preferred_key}")

    keys: list[tuple[str, str]] = []
    for key in llama_key_names(values):
        value = os.environ.get(key) or values.get(key)
        if value:
            keys.append((key, value))
    if keys:
        return keys
    raise RuntimeError(
        "Missing LlamaCloud API key. Add LLAMA_CLOUD_API_KEY or "
        "lamacloud_api_key to .env."
    )


def load_api_key(env_path: Path, preferred_key: str | None = None) -> str:
    return load_api_keys(env_path, preferred_key)[0][1]


def create_parser(api_key: str, args: argparse.Namespace) -> LlamaParse:
    return LlamaParse(
        api_key=api_key,
        result_type="markdown",
        save_images=True,
        disable_image_extraction=False,
        tier=args.tier,
        version=args.version,
        verbose=True,
        show_progress=True,
        num_workers=2,
        max_timeout=2400,
    )


def iter_pdfs(input_dir: Path) -> Iterable[Path]:
    return sorted(input_dir.glob("*.pdf"), key=lambda path: path.name.lower())


def image_name(image: object) -> str:
    if isinstance(image, dict):
        return str(image.get("name", ""))
    return str(getattr(image, "name", ""))


def page_number(page: object) -> int | None:
    if isinstance(page, dict):
        value = page.get("page")
    else:
        value = getattr(page, "page", None)
    return int(value) if value is not None else None


def page_markdown(page: object) -> str:
    if isinstance(page, dict):
        return str(page.get("md") or "")
    return str(getattr(page, "md", None) or "")


def page_images(page: object) -> list[object]:
    if isinstance(page, dict):
        return list(page.get("images") or [])
    return list(getattr(page, "images", None) or [])


def linked_image_names(markdown: str) -> set[str]:
    names = set()
    for match in IMAGE_LINK_RE.finditer(markdown):
        target = match.group(2).strip()
        if target.startswith(("http://", "https://", "data:")):
            continue
        names.add(Path(target).name)
    return names


def markdown_image_asset_names(markdown: str) -> set[str]:
    return {
        name
        for name in linked_image_names(markdown)
        if Path(name).suffix.lower() in IMAGE_SUFFIXES
    }


def rewrite_image_links(
    markdown: str, image_dir_name: str, available_image_names: set[str]
) -> str:
    def replace(match: re.Match[str]) -> str:
        target = match.group(2).strip()
        if target.startswith(("http://", "https://", "data:", "/", "#")):
            return match.group(0)
        target_path = Path(target)
        if target_path.suffix.lower() not in IMAGE_SUFFIXES:
            return ""
        if target_path.name not in available_image_names:
            return ""
        if target_path.parts and target_path.parts[0] == image_dir_name:
            return match.group(0)
        return f"{match.group(1)}{image_dir_name}/{target_path.name}{match.group(3)}"

    return IMAGE_LINK_RE.sub(replace, markdown)


def build_markdown(
    job_result: object, image_dir_name: str, available_image_names: set[str]
) -> str:
    pages = list(getattr(job_result, "pages", []) or [])
    if not pages and isinstance(job_result, dict):
        pages = list(job_result.get("pages") or [])

    chunks: list[str] = []
    for page in pages:
        markdown = rewrite_image_links(
            page_markdown(page), image_dir_name, available_image_names
        ).strip()
        already_linked = linked_image_names(markdown)

        missing_links = []
        for image in page_images(page):
            name = image_name(image)
            if name and name in available_image_names and name not in already_linked:
                alt = f"Extracted image from page {page_number(page) or ''}".strip()
                missing_links.append(f"![{alt}]({image_dir_name}/{name})")

        if missing_links:
            markdown = "\n\n".join(part for part in [markdown, *missing_links] if part)
        if markdown:
            chunks.append(markdown)

    return "\n\n".join(chunks).rstrip() + "\n"


def local_pdf_to_markdown(pdf_path: Path, markdown_path: Path, image_dir: Path) -> int:
    if fitz is None:
        raise RuntimeError("PyMuPDF is required for local fallback conversion.")

    image_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    image_count = 0

    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            page_image_name = f"page_{page_index}.jpg"
            page_image_path = image_dir / page_image_name

            if not page_image_path.exists() or page_image_path.stat().st_size == 0:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                pixmap.save(str(page_image_path), jpg_quality=88)
            image_count += 1

            page_parts = [
                f"# Page {page_index}",
                text,
                f"![Page {page_index}]({image_dir.name}/{page_image_name})",
            ]

            for image_index, image in enumerate(page.get_images(full=True), start=1):
                xref = image[0]
                extracted = document.extract_image(xref)
                extension = extracted.get("ext") or "png"
                image_name = f"page_{page_index}_image_{image_index}.{extension}"
                output_path = image_dir / image_name
                if not output_path.exists() or output_path.stat().st_size == 0:
                    output_path.write_bytes(extracted["image"])
                image_count += 1
                page_parts.append(
                    f"![Page {page_index} image {image_index}]({image_dir.name}/{image_name})"
                )

            chunks.append("\n\n".join(part for part in page_parts if part))

    markdown_path.write_text("\n\n".join(chunks).rstrip() + "\n", encoding="utf-8")
    return image_count


def download_image(
    job_result: object,
    image_name: str,
    output_path: Path,
    *,
    attempts: int = 5,
    timeout: int = 30,
) -> None:
    job_id = getattr(job_result, "job_id")
    base_url = str(getattr(job_result, "_base_url"))
    api_key = str(getattr(job_result, "_api_key", None) or getattr(job_result, "api_key"))
    url = f"{base_url}/api/v1/parsing/job/{job_id}/result/image/{image_name}"
    headers = {"Authorization": f"Bearer {api_key}"}

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            output_path.write_bytes(response.content)
            return
        except requests.RequestException as error:
            last_error = error
            if attempt < attempts:
                time.sleep(min(2**attempt, 10))

    raise RuntimeError(f"Could not download image {image_name}: {last_error}")


def download_images(job_result: object, image_dir: Path) -> set[str]:
    pages = list(getattr(job_result, "pages", []) or [])
    image_names = {
        image_name(image)
        for page in pages
        for image in page_images(page)
        if image_name(image)
    }
    for page in pages:
        image_names.update(markdown_image_asset_names(page_markdown(page)))
    if not image_names:
        return set()

    downloaded_names = set()
    image_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(image_names):
        output_path = image_dir / name
        if output_path.exists() and output_path.stat().st_size > 0:
            downloaded_names.add(name)
            continue
        try:
            download_image(job_result, name, output_path)
        except RuntimeError as error:
            print(f"  warning: {error}", file=sys.stderr)
            continue
        downloaded_names.add(name)
    return downloaded_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a directory of PDFs to Markdown and extracted images."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=str(DEFAULT_INPUT_DIR),
        help="Directory containing PDFs. Defaults to regenxbio_abbv_rgx_314.",
    )
    parser.add_argument(
        "--tier",
        default="agentic",
        help="LlamaParse tier to use. Defaults to agentic.",
    )
    parser.add_argument(
        "--version",
        default="latest",
        help="LlamaParse tier version. Defaults to latest.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-parse PDFs even when the Markdown file already exists.",
    )
    parser.add_argument(
        "--fallback",
        choices=("local", "none"),
        default="local",
        help="Fallback when LlamaParse fails. Defaults to local PyMuPDF conversion.",
    )
    parser.add_argument(
        "--api-key-name",
        help="Name of the .env or environment variable containing the LlamaCloud key.",
    )
    parser.add_argument(
        "--start-at",
        help="PDF filename or stem to start at, skipping earlier PDFs in sorted order.",
    )
    parser.add_argument(
        "--clean-images",
        action="store_true",
        help="Delete each output image directory before regenerating it.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent
    input_dir = Path(args.input_dir)
    if not input_dir.is_absolute():
        input_dir = repo_root / input_dir
    if not input_dir.exists():
        raise RuntimeError(f"Input directory does not exist: {input_dir}")

    api_keys = load_api_keys(repo_root / ".env", args.api_key_name)
    parser_index = 0
    parser = create_parser(api_keys[parser_index][1], args)
    print(f"Using {len(api_keys)} LlamaCloud API key(s).")

    pdfs = list(iter_pdfs(input_dir))
    if not pdfs:
        print(f"No PDFs found in {input_dir}", file=sys.stderr)
        return 1

    started = args.start_at is None
    for index, pdf_path in enumerate(pdfs, start=1):
        if not started:
            if args.start_at in {pdf_path.name, pdf_path.stem}:
                started = True
            else:
                print(f"[{index}/{len(pdfs)}] Skipping before start {pdf_path.name}")
                continue

        markdown_path = pdf_path.with_suffix(".md")
        image_dir = pdf_path.with_name(f"{pdf_path.stem}_images")
        if markdown_path.exists() and not args.overwrite:
            print(f"[{index}/{len(pdfs)}] Skipping existing {markdown_path.name}")
            continue
        if args.clean_images and image_dir.exists():
            shutil.rmtree(image_dir)

        print(f"[{index}/{len(pdfs)}] Parsing {pdf_path.name}")
        last_error: Exception | None = None
        parsed = False
        for attempt in range(len(api_keys)):
            key_name, _key_value = api_keys[parser_index]
            try:
                if attempt > 0:
                    print(f"  retrying with API key {key_name}")
                job_result = parser.parse(str(pdf_path))
                if isinstance(job_result, list):
                    if len(job_result) != 1:
                        raise RuntimeError(f"Expected one job result for {pdf_path}")
                    job_result = job_result[0]

                downloaded_images = download_images(job_result, image_dir)
                markdown = build_markdown(job_result, image_dir.name, downloaded_images)
                markdown_path.write_text(markdown, encoding="utf-8")
                print(f"  wrote {markdown_path.name} and {len(downloaded_images)} images")
                parsed = True
                break
            except Exception as error:
                last_error = error
                if len(api_keys) == 1:
                    break
                print(
                    f"  warning: LlamaParse failed with API key {key_name}: {error}",
                    file=sys.stderr,
                )
                parser_index = (parser_index + 1) % len(api_keys)
                parser = create_parser(api_keys[parser_index][1], args)
                time.sleep(2)

        if not parsed:
            if args.fallback == "none":
                raise RuntimeError(f"LlamaParse failed for {pdf_path}: {last_error}")
            print(f"  warning: LlamaParse failed: {last_error}", file=sys.stderr)
            print("  using local PyMuPDF fallback", file=sys.stderr)
            image_count = local_pdf_to_markdown(pdf_path, markdown_path, image_dir)
            print(f"  wrote {markdown_path.name} and {image_count} local images")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env bash

set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  printf 'Usage: %s [output-directory]\n' "${0##*/}"
  printf 'Convert docs/*.md and their Mermaid diagrams to PDF (default: output/pdf).\n'
}

if (( $# > 1 )); then
  usage >&2
  exit 2
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

output_dir="${1:-$repo_dir/output/pdf}"

if [[ "$output_dir" != /* ]]; then
  output_dir="$repo_dir/$output_dir"
fi

for tool in pandoc mmdc typst; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'error: required command not found: %s\n' "$tool" >&2
    exit 1
  fi
done

markdown_files=()
while IFS= read -r file; do
  markdown_files+=("$file")
done < <(
  git -C "$repo_dir" ls-files --cached --others --exclude-standard -- 'docs/*.md' |
    LC_ALL=C sort
)

if (( ${#markdown_files[@]} == 0 )); then
  printf 'error: no Markdown files found below %s/docs\n' "$repo_dir" >&2
  exit 1
fi

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/build-docs-pdf.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT

mermaid_filter="$work_dir/mermaid.lua"
cat >"$mermaid_filter" <<'LUA'
local diagram_number = 0

local function has_class(block, class_name)
  for _, class in ipairs(block.classes) do
    if class == class_name then
      return true
    end
  end
  return false
end

function CodeBlock(block)
  if not has_class(block, "mermaid") then
    return nil
  end

  diagram_number = diagram_number + 1
  local diagram_dir = os.getenv("MERMAID_OUTPUT_DIR")
  if not diagram_dir then
    error("MERMAID_OUTPUT_DIR is not set")
  end
  local pdf_output_dir = os.getenv("MERMAID_PDF_OUTPUT_DIR")
  if not pdf_output_dir then
    error("MERMAID_PDF_OUTPUT_DIR is not set")
  end
  local document_stem = os.getenv("MERMAID_DOCUMENT_STEM")
  if not document_stem then
    error("MERMAID_DOCUMENT_STEM is not set")
  end

  local stem = string.format("diagram-%03d", diagram_number)
  local source_path = diagram_dir .. "/" .. stem .. ".mmd"
  local image_path = diagram_dir .. "/" .. stem .. ".png"
  local pdf_path = string.format(
    "%s/%s-diagram-%03d.pdf",
    pdf_output_dir,
    document_stem,
    diagram_number
  )

  local source_file, open_error = io.open(source_path, "w")
  if not source_file then
    error("could not write Mermaid source: " .. open_error)
  end
  source_file:write(block.text)
  source_file:close()

  local ok, render_error = pcall(
    pandoc.pipe,
    "mmdc",
    {
      "--input", source_path,
      "--output", image_path,
      "--backgroundColor", "transparent",
      "--scale", "2"
    },
    ""
  )
  if not ok then
    error("could not render Mermaid diagram: " .. tostring(render_error))
  end

  local pdf_ok, pdf_render_error = pcall(
    pandoc.pipe,
    "mmdc",
    {
      "--input", source_path,
      "--output", pdf_path,
      "--pdfFit"
    },
    ""
  )
  if not pdf_ok then
    error("could not render standalone Mermaid PDF: " .. tostring(pdf_render_error))
  end

  local alt_text = block.attributes.title or "Mermaid diagram"
  local image = pandoc.Image(
    alt_text,
    image_path,
    "",
    pandoc.Attr("", {"mermaid-diagram"}, {{"width", "100%"}})
  )
  return pandoc.Para({image})
end
LUA

mkdir -p "$output_dir"

for markdown_file in "${markdown_files[@]}"; do
  source_path="$repo_dir/$markdown_file"
  relative_path="${markdown_file#docs/}"
  pdf_path="$output_dir/${relative_path%.md}.pdf"
  diagram_dir="$(mktemp -d "$work_dir/mermaid.XXXXXX")"
  diagram_output_dir="$(dirname "$pdf_path")"
  document_stem="$(basename "${relative_path%.md}")"

  mkdir -p "$diagram_output_dir"

  MERMAID_OUTPUT_DIR="$diagram_dir" \
    MERMAID_PDF_OUTPUT_DIR="$diagram_output_dir" \
    MERMAID_DOCUMENT_STEM="$document_stem" \
    pandoc \
    "$source_path" \
    --from=gfm \
    --standalone \
    --lua-filter="$mermaid_filter" \
    --pdf-engine=typst \
    --variable=papersize:a4 \
    --resource-path="$(dirname "$source_path"):$repo_dir" \
    --output="$pdf_path"

  printf 'created %s\n' "$pdf_path"

  shopt -s nullglob
  diagram_pdfs=("$diagram_output_dir/$document_stem"-diagram-*.pdf)
  shopt -u nullglob
  for diagram_pdf in "${diagram_pdfs[@]}"; do
    printf 'created %s\n' "$diagram_pdf"
  done
done

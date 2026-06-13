#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "yaml"

ROOT = File.expand_path("..", __dir__)
SOURCE_DIR = File.join(ROOT, "4dmt")
OUTPUT_DIR = File.join(ROOT, "4dmt-cleaned")
DATA_DIR = File.join(ROOT, "_data")
DATA_FILE = File.join(DATA_DIR, "documents.yml")
PDF_LINKS_FILE = File.join(DATA_DIR, "pdf_links.yml")
PLAIN_TEXT_DIR = File.join(ROOT, "plain-text", "4dmt")

PROGRAMS = %w[4D-150 4D-175 4D-310 4D-710].freeze
DEFAULT_COMPANY = "4DMT"
CONFERENCES = %w[
  Angiogenesis ASGCT ASRS ARVO ATS ECFS EURETINA FDMT WORLD Retina-Society
  Gene-Tx-for-Ophthalmic-Disorders-Summit Clinical-Trials-at-the-Summit
].freeze

def slugify(value)
  value.downcase.gsub(/[^a-z0-9]+/, "-").gsub(/^-|-$/, "")
end

def yaml_string(value)
  value.to_s
end

def first_heading(markdown)
  heading = markdown.lines.find { |line| line.match?(/^#\s+\S/) }
  return nil unless heading

  clean_title(heading.sub(/^#\s+/, "").strip)
end

def clean_title(value)
  value
    .gsub(/<[^>]+>/, "")
    .gsub(/\*\*([^*]+)\*\*/, "\\1")
    .gsub(/\*([^*]+)\*/, "\\1")
    .gsub(/__([^_]+)__/, "\\1")
    .gsub(/_([^_]+)_/, "\\1")
    .strip
end

def superscript(value)
  map = {
    "0" => "⁰", "1" => "¹", "2" => "²", "3" => "³", "4" => "⁴",
    "5" => "⁵", "6" => "⁶", "7" => "⁷", "8" => "⁸", "9" => "⁹",
    "+" => "⁺", "-" => "⁻"
  }
  value.chars.map { |char| map.fetch(char, char) }.join
end

def subscript(value)
  map = {
    "0" => "₀", "1" => "₁", "2" => "₂", "3" => "₃", "4" => "₄",
    "5" => "₅", "6" => "₆", "7" => "₇", "8" => "₈", "9" => "₉",
    "+" => "₊", "-" => "₋"
  }
  value.chars.map { |char| map.fetch(char, char) }.join
end

def normalize_inline_math(value)
  value
    .gsub(/\\times/, "×")
    .gsub(/\\leq/, "≤")
    .gsub(/\\geq/, "≥")
    .gsub(/\\pm/, "±")
    .gsub(/\\alpha/, "α")
    .gsub(/\\beta/, "β")
    .gsub(/\\gamma/, "γ")
    .gsub(/\\delta/, "δ")
    .gsub(/\\mu/, "μ")
    .gsub(/\^\{([^}]+)\}/) { superscript(Regexp.last_match(1)) }
    .gsub(/\^([0-9+\-]+)/) { superscript(Regexp.last_match(1)) }
    .gsub(/_\{([^}]+)\}/) { subscript(Regexp.last_match(1)) }
    .gsub(/_([0-9+\-]+)/) { subscript(Regexp.last_match(1)) }
    .strip
end

def normalize_latex_fragments(line)
  line.gsub(/\$([^$\n]+)\$/) { normalize_inline_math(Regexp.last_match(1)) }
end

def normalize_plain_scientific_notation(line)
  line
    .gsub(/(\d+(?:\.\d+)?)\s*[xX]\s*10<sup>([0-9+\-]+)<\/sup>/i) do
      "#{Regexp.last_match(1)}×10#{superscript(Regexp.last_match(2))}"
    end
    .gsub(/(\d+(?:\.\d+)?)\s*[xX]\s*10\^([0-9+\-]+)/) do
      "#{Regexp.last_match(1)}×10#{superscript(Regexp.last_match(2))}"
    end
    .gsub(/(\d+(?:\.\d+)?)\s*[xX]\s*10([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+)/) do
      "#{Regexp.last_match(1)}×10#{Regexp.last_match(2)}"
    end
    .gsub(/10\^([0-9+\-]+)/) do
      "10#{superscript(Regexp.last_match(1))}"
    end
end

def normalize_text_fragments(line)
  normalize_plain_scientific_notation(normalize_latex_fragments(line))
end

def remove_image_references(markdown)
  in_code_block = false

  cleaned = markdown.lines.map do |line|
    in_code_block = !in_code_block if line.start_with?("```")
    stripped = line
      .gsub(/!\[[^\]]*\]\([^)]+\)/, "")
      .gsub(/<img\b[^>]*>/i, "")
      .rstrip

    in_code_block ? stripped : normalize_text_fragments(stripped)
  end

  output = []
  blank_count = 0

  cleaned.each do |line|
    if line.empty?
      blank_count += 1
      output << line if blank_count <= 2
    else
      blank_count = 0
      output << line
    end
  end

  "#{output.join("\n").strip}\n"
end

def remove_duplicate_title_heading(markdown, title)
  lines = markdown.lines
  heading_index = lines.each_with_index.first(40).find do |line, _index|
    line.match?(/^#\s+\S/) && clean_title(line.sub(/^#\s+/, "").strip) == title
  end&.last
  return markdown unless heading_index

  lines.delete_at(heading_index)
  lines.delete_at(heading_index) while lines[heading_index]&.strip == ""

  "#{lines.join.strip}\n"
end

def infer_program(text)
  PROGRAMS.find { |program| text.include?(program) } || "Uncategorized"
end

def infer_year(*texts)
  texts.each do |text|
    compact_date_match = text.match(/(?:^|[^0-9])(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])(20\d{2})(?![0-9])/)
    return compact_date_match[1] if compact_date_match

    year_match = text.match(/(?:^|[^0-9])(20[12]\d|202[0-6])(?![0-9])/)
    year = year_match && year_match[1]
    return year if year
  end

  nil
end

def infer_conference(*texts)
  texts.each do |text|
    normalized = text.tr("_", "-")
    conference = CONFERENCES.find { |name| normalized.downcase.include?(name.downcase) }
    return conference if conference
  end

  nil
end

def infer_document_type(text)
  lower = text.downcase
  return "Poster" if lower.include?("poster")
  return "Presentation" if lower.include?("presentation") || lower.include?("pres_")

  "Document"
end

def infer_indication(text)
  lower = text.downcase
  return "Diabetic macular edema" if lower.include?("spectra") || lower.include?("adults with diabetic macular edema")
  return "Wet AMD" if lower.include?("amd") || lower.include?("wamd") || lower.include?("neovascular age-related macular degeneration")
  return "Fabry disease" if lower.include?("fabry")
  return "Cystic fibrosis" if lower.include?("cftr") || lower.include?("cystic fibrosis")
  return "Retinitis pigmentosa" if lower.include?("retinitis pigmentosa") || lower.include?("r100")

  "Uncategorized"
end

FileUtils.rm_rf(OUTPUT_DIR)
FileUtils.rm_rf(PLAIN_TEXT_DIR)
FileUtils.mkdir_p(OUTPUT_DIR)
FileUtils.mkdir_p(DATA_DIR)
FileUtils.mkdir_p(PLAIN_TEXT_DIR)

pdf_links = File.exist?(PDF_LINKS_FILE) ? YAML.load_file(PDF_LINKS_FILE) : {}

documents = Dir.glob(File.join(SOURCE_DIR, "*.md")).sort.map do |source_path|
  source_name = File.basename(source_path)
  slug = slugify(File.basename(source_name, ".md"))
  raw = File.read(source_path)
  cleaned_body = remove_image_references(raw)
  title = first_heading(cleaned_body) || File.basename(source_name, ".md").tr("_-", " ")
  cleaned_body = remove_duplicate_title_heading(cleaned_body, title)
  searchable_text = [source_name, title, cleaned_body].join("\n")
  plain_text_url = "/plain-text/4dmt/#{slug}.txt"

  metadata = {
    "layout" => "document",
    "title" => title,
    "source_file" => source_name,
    "pdf_url" => pdf_links[source_name],
    "plain_text_url" => plain_text_url,
    "slug" => slug,
    "company" => DEFAULT_COMPANY,
    "program" => infer_program(searchable_text),
    "indication" => infer_indication(searchable_text),
    "conference" => infer_conference(source_name, title, cleaned_body),
    "year" => infer_year(source_name, title, cleaned_body),
    "document_type" => infer_document_type(searchable_text),
    "permalink" => "/4dmt/#{slug}/"
  }.compact

  output_path = File.join(OUTPUT_DIR, source_name)
  File.write(output_path, "#{metadata.to_yaml}---\n\n#{cleaned_body}")

  plain_text = [
    title,
    "",
    "Company: #{metadata["company"]}",
    "Program: #{metadata["program"]}",
    "Indication: #{metadata["indication"]}",
    ("Conference: #{metadata["conference"]}" if metadata["conference"]),
    ("Year: #{metadata["year"]}" if metadata["year"]),
    ("Document type: #{metadata["document_type"]}" if metadata["document_type"]),
    "",
    cleaned_body
  ].compact.join("\n")
  File.write(File.join(PLAIN_TEXT_DIR, "#{slug}.txt"), plain_text)

  {
    "title" => title,
    "url" => metadata["permalink"],
    "source_file" => source_name,
    "pdf_url" => metadata["pdf_url"],
    "plain_text_url" => metadata["plain_text_url"],
    "company" => metadata["company"],
    "program" => metadata["program"],
    "indication" => metadata["indication"],
    "conference" => metadata["conference"],
    "year" => metadata["year"],
    "document_type" => metadata["document_type"]
  }.compact
end

File.write(DATA_FILE, documents.to_yaml)

puts "Wrote #{documents.length} cleaned documents to #{OUTPUT_DIR}"
puts "Wrote manifest to #{DATA_FILE}"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

try:
    import pdfplumber
    from PIL import Image
except ImportError:
    print("Erro: dependências ausentes. Execute: pip install pdfplumber pillow")
    sys.exit(1)


OBSIDIAN_FRONTMATTER = """---
Date: "2026-03-08"
tags:
  - filosofia
aliases:
List:
Tipo: Permanente
Categoria: Filosofia
Link:
---
"""

AULA_RE = re.compile(r"(AULA\s*\d+)", re.IGNORECASE)

# Títulos explícitos. A separação de blocos exige obrigatoriamente a palavra
# "TEMA" seguida do número; listas como "1. Item" continuam dentro do tema.
THEME_HEADING_RE = re.compile(
    r"^TEMA\s+\d+\s*(?:[:–-]\s*.*)?$",
    re.IGNORECASE
)
THEME_WITH_TITLE_ON_NEXT_LINE_RE = re.compile(
    r"^TEMA\s+\d+\s*[:–-]?\s*$",
    re.IGNORECASE
)

# Subtítulos internos
SUBTITLE_RE = re.compile(r"^(\d+\.\d+\s+.+)$")


@dataclass
class ThemeBlock:
    number: int
    title: str
    content: str


@dataclass
class ConversionResult:
    document_title: str
    output_dir: Path
    themes: List[ThemeBlock]
    report_path: Path
    image_count: int


def is_repeated_header_image(image_info: dict) -> bool:
    return float(image_info.get("top", 0)) <= 115


def save_pdf_image(image_info: dict, image_path: Path, page=None) -> None:
    stream = image_info["stream"]
    attrs = stream.attrs
    data = stream.get_data()
    image_filter = str(attrs.get("Filter", ""))

    try:
        if "DCTDecode" in image_filter:
            image = Image.open(BytesIO(data))
        else:
            width = int(attrs["Width"])
            height = int(attrs["Height"])
            color_space = str(attrs.get("ColorSpace", ""))
            mode = "L" if "DeviceGray" in color_space else "RGB"
            image = Image.frombytes(mode, (width, height), data)

        image.save(image_path)
    except Exception:
        if page is None:
            raise

        bbox = (
            float(image_info["x0"]),
            float(image_info["top"]),
            float(image_info["x1"]),
            float(image_info["bottom"]),
        )
        cropped = page.crop(bbox)
        cropped.to_image(resolution=144).save(str(image_path), format="PNG")


def read_pdf_text(pdf_path: Path, images_dir: Path) -> tuple[str, int]:
    pages_text = []
    image_count = 0

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            events = []

            for line in page.extract_text_lines(x_tolerance=2, y_tolerance=3) or []:
                text = line.get("text", "").strip()
                if text:
                    events.append((float(line.get("top", 0)), text))

            for page_image_index, image_info in enumerate(page.images, start=1):
                if is_repeated_header_image(image_info):
                    continue

                image_count += 1
                images_dir.mkdir(parents=True, exist_ok=True)
                image_filename = f"pagina-{page_number:03d}-imagem-{page_image_index:02d}.png"
                save_pdf_image(image_info, images_dir / image_filename, page=page)
                marker = f"![Imagem da página {page_number}](imagens/{image_filename})"
                events.append((float(image_info.get("top", 0)), marker))

            page_text = "\n".join(text for _, text in sorted(events, key=lambda item: item[0]))
            pages_text.append(page_text)

    return "\n".join(pages_text), image_count


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def fix_common_pdf_hyphenation(text: str) -> str:
    return re.sub(r"([A-Za-zÀ-ÿ])-\n([A-Za-zÀ-ÿ])", r"\1\2", text)


def remove_page_number_lines(text: str) -> str:
    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.fullmatch(r"\d+", stripped):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def normalize_spacing(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


YOUTUBE_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s<>)]+",
    re.IGNORECASE
)


def extract_youtube_video_id(url: str) -> Optional[str]:
    parsed = urlparse(url.strip().rstrip(".,;"))
    host = parsed.netloc.lower().removeprefix("www.")

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host == "youtube.com":
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif path_parts and path_parts[0] in {"embed", "shorts", "live"}:
            video_id = path_parts[1] if len(path_parts) > 1 else ""
        else:
            video_id = ""
    else:
        video_id = ""

    if re.fullmatch(r"[A-Za-z0-9_-]{6,}", video_id):
        return video_id
    return None


def build_youtube_embed(video_id: str) -> str:
    return (
        '<iframe width="560" height="315" '
        f'src="https://www.youtube.com/embed/{video_id}" '
        'title="YouTube video player" frameborder="0" '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
        'allowfullscreen></iframe>'
    )


def embed_youtube_videos(content: str) -> str:
    output: List[str] = []
    embedded_ids: set[str] = set()

    for line in content.splitlines():
        output.append(line)

        for match in YOUTUBE_URL_RE.finditer(line):
            video_id = extract_youtube_video_id(match.group(0))
            if not video_id or video_id in embedded_ids:
                continue

            if output and output[-1] != "":
                output.append("")
            output.append(build_youtube_embed(video_id))
            output.append("")
            embedded_ids.add(video_id)

    return "\n".join(output)


def is_markdown_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+", line.strip()))


def is_markdown_image(line: str) -> bool:
    return bool(re.match(r"^!\[[^\]]*\]\([^)]+\)$", line.strip()))


def is_bullet_or_numbered_item(line: str) -> bool:
    stripped = line.strip()
    return bool(
        re.match(r"^[-*+]\s+", stripped)
        or re.match(r"^\d+[.)]\s+", stripped)
    )


def is_numbered_subheading(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^\d+\.\s+[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]", stripped))


def is_all_caps_subheading(line: str) -> bool:
    stripped = line.strip()
    return (
        len(stripped) > 3
        and stripped == stripped.upper()
        and any(c.isalpha() for c in stripped)
        and not stripped.startswith("CCDD")
    )


def is_repeated_pdf_footer(line: str) -> bool:
    return line.strip() == "CCDD – Centro de Criação e Desenvolvimento Dialógico"


def ends_sentence_or_block(line: str) -> bool:
    stripped = line.strip()
    return bool(re.search(r'[:.!?]["”’)\]]?$', stripped))


def should_keep_as_standalone_line(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or is_markdown_heading(stripped)
        or is_markdown_image(stripped)
        or is_numbered_subheading(stripped)
        or is_all_caps_subheading(stripped)
    )


def reflow_pdf_line_breaks(content: str) -> str:
    """
    Une quebras de linha artificiais criadas pela extração do PDF sem mexer em
    títulos Markdown, subtítulos numerados e listas.
    """
    output: List[str] = []
    paragraph: List[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            output.append(" ".join(paragraph))
            paragraph = []

    for raw_line in content.splitlines():
        stripped = raw_line.strip()

        if is_repeated_pdf_footer(stripped):
            continue

        if not stripped:
            flush_paragraph()
            if output and output[-1] != "":
                output.append("")
            continue

        if should_keep_as_standalone_line(stripped):
            flush_paragraph()
            if output and output[-1] != "":
                output.append("")
            output.append(stripped)
            output.append("")
            continue

        if is_bullet_or_numbered_item(stripped):
            flush_paragraph()
            output.append(stripped)
            continue

        if output and output[-1] != "" and is_bullet_or_numbered_item(output[-1]):
            output.append("")

        paragraph.append(stripped)
        if ends_sentence_or_block(stripped):
            flush_paragraph()
            output.append("")

    flush_paragraph()

    return "\n".join(output)


def get_pdf_base_name(pdf_path: Path) -> str:
    return pdf_path.stem.strip()


def extract_aula_number(full_text: str, pdf_path: Path) -> str:
    m = AULA_RE.search(full_text)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).upper().strip()

    m2 = AULA_RE.search(pdf_path.stem)
    if m2:
        return re.sub(r"\s+", " ", m2.group(1)).upper().strip()

    return "AULA"


def slugify_filename(text: str) -> str:
    text = text.strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^A-Za-z0-9\s\-]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().upper()


def cleanup_bullets_and_lists(content: str) -> str:
    lines = content.splitlines()
    result = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("•"):
            result.append("- " + stripped[1:].strip())
            continue

        result.append(line)

    return "\n".join(result)


def promote_subtitles_to_md(content: str) -> str:
    lines = content.splitlines()
    converted = []

    for line in lines:
        stripped = line.strip()
        if SUBTITLE_RE.fullmatch(stripped):
            converted.append(f"## {stripped}")
        else:
            converted.append(line)

    return "\n".join(converted)


def is_probable_section_line(line: str, next_line: Optional[str] = None) -> bool:
    s = line.strip()
    if not s:
        return False

    # Caso explícito: TEMA 1, TEMA 2: Título, TEMA 3 - Título, etc.
    if THEME_HEADING_RE.match(s):
        return True

    # Caso "TEMA 1 –" e o título vem na linha seguinte
    if THEME_WITH_TITLE_ON_NEXT_LINE_RE.match(s):
        return True

    return False


def normalize_section_title(line: str, next_line: Optional[str] = None) -> str:
    """
    Junta títulos quebrados em duas linhas, ex:
    TEMA 1 –
    FUNDAMENTOS TEÓRICOS
    """
    s = line.strip()

    if THEME_WITH_TITLE_ON_NEXT_LINE_RE.match(s):
        if next_line and next_line.strip():
            return f"{s} {next_line.strip()}"

    return s


def find_section_starts(text: str) -> List[int]:
    lines = text.splitlines()
    starts: List[int] = []

    # mapear posição absoluta de cada linha no texto
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1  # +1 pelo \n

    i = 0
    while i < len(lines):
        line = lines[i]
        next_line = lines[i + 1] if i + 1 < len(lines) else None

        if is_probable_section_line(line, next_line):
            starts.append(offsets[i])
            # se for o caso "TEMA 1 -" sozinho, o título real usa a próxima linha,
            # mas o bloco começa aqui mesmo
        i += 1

    # remover duplicatas e ordenar
    return sorted(set(starts))


def remove_pre_theme_intro(text: str) -> str:
    starts = find_section_starts(text)
    if not starts:
        return text

    intro = text[:starts[0]]
    text_from_first_theme = text[starts[0]:]
    intro_image_markers = [
        line.strip()
        for line in intro.splitlines()
        if is_markdown_image(line.strip())
    ]
    if not intro_image_markers:
        return text_from_first_theme

    lines = text_from_first_theme.splitlines()
    if not lines:
        return text_from_first_theme

    return "\n".join([lines[0], *intro_image_markers, *lines[1:]])


def split_themes(text: str) -> List[ThemeBlock]:
    starts = find_section_starts(text)
    themes: List[ThemeBlock] = []

    if not starts:
        return themes

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        block = text[start:end].strip()
        if not block:
            continue

        lines = block.splitlines()
        if not lines:
            continue

        first_line = lines[0].strip()
        second_line = lines[1].strip() if len(lines) > 1 else None

        title = normalize_section_title(first_line, second_line)

        # se o título usou a segunda linha, removemos ela do conteúdo
        content_start_index = 1
        if title != first_line and len(lines) > 1:
            content_start_index = 2

        content = "\n".join(lines[content_start_index:]).strip()

        num_match = re.search(r"(\d+)", title)
        number = int(num_match.group(1)) if num_match else i + 1

        themes.append(ThemeBlock(number=number, title=title, content=content))

    return themes


def extract_theme_label_and_title(theme_title: str, fallback_number: int) -> tuple[str, str]:
    theme_title = theme_title.strip()

    m = re.match(
        r"^TEMA\s+(\d+)\s*[:–-]?\s*(.*)$",
        theme_title,
        flags=re.IGNORECASE
    )
    if m:
        number = m.group(1)
        rest = m.group(2).strip()
        label = f"TEMA {number}"
        return label, rest if rest else f"BLOCO {number}"

    return f"TEMA {fallback_number}", theme_title


def build_full_title(pdf_base_name: str, aula_label: str, theme: ThemeBlock) -> str:
    theme_label, theme_name = extract_theme_label_and_title(theme.title, theme.number)

    pdf_upper = pdf_base_name.upper()
    aula_upper = aula_label.upper()

    if aula_upper in pdf_upper:
        return f"{pdf_base_name} - {theme_label} - {theme_name}"

    return f"{pdf_base_name} - {aula_label} - {theme_label} - {theme_name}"


def render_theme_markdown(pdf_base_name: str, aula_label: str, theme: ThemeBlock) -> str:
    title_line = build_full_title(pdf_base_name, aula_label, theme).upper()
    body = theme.content

    body = promote_subtitles_to_md(body)
    body = cleanup_bullets_and_lists(body)
    body = reflow_pdf_line_breaks(body)
    body = normalize_spacing(body)
    body = embed_youtube_videos(body)
    body = normalize_spacing(body)

    return (
        f"{OBSIDIAN_FRONTMATTER}\n"
        f"# **{title_line}**\n\n"
        f"{body}\n"
    )


def write_theme_files(output_dir: Path, pdf_base_name: str, aula_label: str, themes: List[ThemeBlock]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for theme in themes:
        full_title = build_full_title(pdf_base_name, aula_label, theme)
        filename = f"{slugify_filename(full_title)}.md"
        md_text = render_theme_markdown(pdf_base_name, aula_label, theme)
        (output_dir / filename).write_text(md_text, encoding="utf-8")


def clean_existing_markdown_files(output_dir: Path) -> int:
    if not output_dir.exists():
        return 0

    removed = 0
    for path in output_dir.glob("*.md"):
        if path.is_file():
            path.unlink()
            removed += 1
    images_dir = output_dir / "imagens"
    if images_dir.exists():
        for path in images_dir.glob("*"):
            if path.is_file():
                path.unlink()
                removed += 1
    return removed


def generate_report(
    output_dir: Path,
    pdf_path: Path,
    pdf_base_name: str,
    aula_label: str,
    themes: List[ThemeBlock],
    image_count: int
) -> Path:
    report_path = output_dir / "_RELATORIO DE INTEGRIDADE.md"

    lines = [
        "# RELATÓRIO DE INTEGRIDADE",
        "",
        f"Documento de origem: `{pdf_path.name}`",
        f"Nome-base do PDF: `{pdf_base_name}`",
        f"Aula identificada: `{aula_label}`",
        f"Imagens extraídas: `{image_count}`",
        "",
        "## Temas convertidos",
        "",
    ]

    for theme in themes:
        lines.append(f"- Tema {theme.number}: {theme.title}")

    lines.extend([
        "",
        "## Verificações aplicadas",
        "",
        "- Separação automática somente por marcadores explícitos no formato TEMA + número",
        "- Frontmatter padrão Obsidian",
        "- Título em heading nível 1",
        "- Nome do arquivo no padrão: Nome do PDF - AULA X - TEMA X - TÍTULO DO TEMA",
        "- Tentativa de correção de hifenização de fim de linha",
        "- Reunião de quebras de linha artificiais criadas pela extração do PDF",
        "- Remoção do rodapé repetido CCDD",
        "- Extração de imagens de conteúdo para a pasta imagens com links Markdown nos documentos",
        "- Inserção de player incorporado para links do YouTube",
        "- Rejeição de listas numeradas, subtítulos numerados e linhas em caixa alta como falsos temas",
        "- Fallback para arquivo único quando não houver seções detectadas",
        "",
        "## Observação",
        "",
        "A revisão final lado a lado com o PDF continua recomendada para garantir fidelidade absoluta.",
        "",
    ])

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def convert_pdf_to_md(pdf_path: Path, output_base_dir: Path, clean_output: bool = False) -> ConversionResult:
    pdf_base_name = get_pdf_base_name(pdf_path)
    output_dir = output_base_dir / slugify_filename(pdf_base_name)

    if clean_output:
        clean_existing_markdown_files(output_dir)

    raw_text, image_count = read_pdf_text(pdf_path, output_dir / "imagens")
    raw_text = normalize_line_endings(raw_text)
    raw_text = fix_common_pdf_hyphenation(raw_text)
    raw_text = remove_page_number_lines(raw_text)
    raw_text = normalize_spacing(raw_text)

    aula_label = extract_aula_number(raw_text, pdf_path)

    text_from_first_theme = remove_pre_theme_intro(raw_text)
    themes = split_themes(text_from_first_theme)

    if not themes:
        themes = [ThemeBlock(number=1, title="TEXTO COMPLETO", content=text_from_first_theme)]

    write_theme_files(output_dir, pdf_base_name, aula_label, themes)
    report_path = generate_report(output_dir, pdf_path, pdf_base_name, aula_label, themes, image_count)

    return ConversionResult(
        document_title=pdf_base_name,
        output_dir=output_dir,
        themes=themes,
        report_path=report_path,
        image_count=image_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Converte PDF em arquivos Markdown separados por tema/seção."
    )
    parser.add_argument("pdf", help="Caminho do arquivo PDF")
    parser.add_argument(
        "-o", "--output",
        default="saida_md",
        help="Pasta base de saída"
    )
    parser.add_argument(
        "--clean-output",
        action="store_true",
        help="Remove arquivos .md existentes na pasta de saída deste PDF antes de converter"
    )

    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    output_base_dir = Path(args.output).expanduser().resolve()

    if not pdf_path.exists():
        print(f"Erro: arquivo não encontrado: {pdf_path}")
        sys.exit(1)

    try:
        result = convert_pdf_to_md(pdf_path, output_base_dir, clean_output=args.clean_output)
    except Exception as e:
        print(f"Erro durante a conversão: {e}")
        sys.exit(1)

    print("\nConversão concluída com sucesso.")
    print(f"Documento: {result.document_title}")
    print(f"Saída: {result.output_dir}")
    print(f"Relatório: {result.report_path}")
    print(f"Blocos convertidos: {len(result.themes)}")
    print(f"Imagens extraídas: {result.image_count}")
    for theme in result.themes:
        print(f"  - Bloco {theme.number}: {theme.title}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
build_chunks.py
Lee los .docx de backend/knowledge/fuentes/ y genera algebra_chunks.json
con chunks semánticos de ~300-500 palabras.

Uso:
    cd backend
    python utils/build_chunks.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    from docx import Document
except ImportError:
    print("ERROR: python-docx no instalado. Ejecutá: pip install python-docx")
    sys.exit(1)

# ── Rutas ───────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent
FUENTES_DIR = SCRIPT_DIR.parent / "knowledge" / "fuentes"
OUTPUT_FILE = SCRIPT_DIR.parent / "knowledge" / "algebra_chunks.json"

# ── Parámetros de chunking ───────────────────────────────────────────────────
CHUNK_TARGET = 380   # palabras objetivo por chunk
CHUNK_MAX    = 530   # máximo antes de forzar corte
MIN_TAIL     = 80    # mínimo para crear chunk propio (si es menor, se fusiona)

STOPWORDS = {
    "el", "la", "los", "las", "de", "del", "en", "un", "una", "que",
    "es", "son", "se", "con", "por", "para", "como", "qué", "cómo",
    "a", "al", "y", "o", "si", "no", "me", "te", "le", "su", "sus",
    "lo", "ya", "más", "pero", "este", "esta", "estos", "estas",
    "ese", "esa", "esos", "esas", "hay", "ser", "estar", "tiene",
    "tienen", "pueden", "puede", "caso", "forma", "tipo", "tipos",
    "dos", "tres", "cada", "todo", "toda", "todos", "todas",
    "tanto", "también", "cuando", "donde", "dado", "sea", "cual",
    "dicho", "dicha", "mismo", "misma", "entre", "sobre", "sin",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convierte texto a slug ASCII apto para IDs."""
    _ACCENT_MAP = {
        "\u00e1": "a", "\u00e0": "a", "\u00e4": "a",
        "\u00e9": "e", "\u00e8": "e", "\u00eb": "e",
        "\u00ed": "i", "\u00ec": "i", "\u00ef": "i",
        "\u00f3": "o", "\u00f2": "o", "\u00f6": "o",
        "\u00fa": "u", "\u00f9": "u", "\u00fc": "u",
        "\u00f1": "n",
        "\u00c1": "a", "\u00c0": "a", "\u00c4": "a",
        "\u00c9": "e", "\u00c8": "e", "\u00cb": "e",
        "\u00cd": "i", "\u00cc": "i", "\u00cf": "i",
        "\u00d3": "o", "\u00d2": "o", "\u00d6": "o",
        "\u00da": "u", "\u00d9": "u", "\u00dc": "u",
        "\u00d1": "n",
    }
    text = "".join(_ACCENT_MAP.get(c, c) for c in text).lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:28]


def extract_keywords(text: str, max_kw: int = 8) -> list[str]:
    """Extrae las palabras más frecuentes y significativas del texto."""
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    freq: dict[str, int] = {}
    for w in words:
        if len(w) > 3 and w not in STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    return sorted(freq, key=lambda k: freq[k], reverse=True)[:max_kw]


def parse_filename(filename: str) -> tuple[int, str]:
    """
    'Clase 1 - CONJUNTOS NUMERICOS.docx' → (1, 'Clase 1 - Conjuntos Numéricos')
    'Clase 10 INTRODUCCIÓN A LAS FUNCIONES.docx' → (10, 'Clase 10 - Introducción A Las Funciones')
    """
    name = filename.replace(".docx", "")
    m = re.match(r"Clase\s+(\d+)\s*[-–]?\s*(.+)", name, re.IGNORECASE)
    if m:
        num   = int(m.group(1))
        title = m.group(2).strip().title()
        return num, f"Clase {num} - {title}"
    return 0, name.title()


# ── Parseo del .docx ─────────────────────────────────────────────────────────

def _is_heading(para) -> bool:
    """Detecta si un párrafo es un encabezado."""
    style = para.style.name.lower() if para.style else ""
    if "heading" in style:
        return True
    # Heurística: texto corto, todo en negrita, sin ser una fórmula
    runs = [r for r in para.runs if r.text.strip()]
    if not runs:
        return False
    text = para.text.strip()
    if len(text) < 4 or len(text) > 120:
        return False
    return all(r.bold for r in runs)


def extract_sections(doc) -> list[dict]:
    """
    Devuelve lista de secciones: [{'heading': str, 'paragraphs': [str]}]
    Preserva estructura de títulos y agrupa párrafos bajo cada sección.
    """
    sections: list[dict] = []
    current_heading = "Introducción"
    current_paragraphs: list[str] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        if _is_heading(para) and len(text) > 2:
            if current_paragraphs:
                sections.append({
                    "heading": current_heading,
                    "paragraphs": current_paragraphs[:]
                })
                current_paragraphs = []
            current_heading = text
        else:
            current_paragraphs.append(text)

    if current_paragraphs:
        sections.append({
            "heading": current_heading,
            "paragraphs": current_paragraphs[:]
        })

    return sections


# ── Chunking ─────────────────────────────────────────────────────────────────

def make_chunk(
    content: str,
    clase_name: str,
    clase_slug: str,
    topic_slug: str,
    heading: str,
    section_idx: int,
    chunk_idx: int,
) -> dict:
    chunk_id = f"{clase_slug}_{topic_slug}_{section_idx:02d}_{chunk_idx:03d}"
    return {
        "id":        chunk_id,
        "clase":     clase_name,
        "tema":      heading,
        "contenido": content,
        "keywords":  extract_keywords(content),
    }


def chunk_section(
    section: dict,
    clase_name: str,
    class_num: int,
    section_idx: int,
) -> list[dict]:
    """Divide una sección en chunks de ~CHUNK_TARGET palabras."""
    heading     = section["heading"]
    paragraphs  = section["paragraphs"]
    clase_slug  = f"clase_{class_num:02d}"
    topic_slug  = slugify(heading)

    chunks: list[dict]   = []
    current_words: list[str] = []
    chunk_idx = 1

    for para in paragraphs:
        para_words = para.split()

        # Si sumar este párrafo supera el máximo → flush antes
        if current_words and len(current_words) + len(para_words) > CHUNK_MAX:
            chunks.append(make_chunk(
                " ".join(current_words),
                clase_name, clase_slug, topic_slug,
                heading, section_idx, chunk_idx,
            ))
            chunk_idx += 1
            current_words = []

        current_words.extend(para_words)

        # Si alcanzamos el target → flush
        if len(current_words) >= CHUNK_TARGET:
            chunks.append(make_chunk(
                " ".join(current_words),
                clase_name, clase_slug, topic_slug,
                heading, section_idx, chunk_idx,
            ))
            chunk_idx += 1
            current_words = []

    # Resto final
    if current_words:
        if chunks and len(current_words) < MIN_TAIL:
            # Demasiado pequeño → fusionar con el último chunk
            chunks[-1]["contenido"] += " " + " ".join(current_words)
            chunks[-1]["keywords"]   = extract_keywords(chunks[-1]["contenido"])
        else:
            chunks.append(make_chunk(
                " ".join(current_words),
                clase_name, clase_slug, topic_slug,
                heading, section_idx, chunk_idx,
            ))

    return chunks


# ── Procesamiento por archivo ─────────────────────────────────────────────────

def process_docx(filepath: Path) -> list[dict]:
    class_num, clase_name = parse_filename(filepath.name)
    print(f"  {filepath.name}")
    print(f"     -> {clase_name}")

    doc      = Document(str(filepath))
    sections = extract_sections(doc)

    if not sections:
        print(f"     [WARN] Sin secciones detectadas")
        return []

    all_chunks: list[dict] = []
    for i, section in enumerate(sections):
        section_chunks = chunk_section(section, clase_name, class_num, i)
        all_chunks.extend(section_chunks)

    print(f"     [OK] {len(sections)} secciones -> {len(all_chunks)} chunks")
    return all_chunks


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[INFO] Leyendo .docx desde: {FUENTES_DIR}\n")

    docx_files = sorted(FUENTES_DIR.glob("*.docx"))
    if not docx_files:
        print(f"ERROR: No hay archivos .docx en {FUENTES_DIR}")
        sys.exit(1)

    print(f"Encontrados {len(docx_files)} archivos\n" + "-"*50)

    all_chunks: list[dict] = []
    for docx_file in docx_files:
        chunks = process_docx(docx_file)
        all_chunks.extend(chunks)
        print()

    # Escribir JSON
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print("-"*50)
    print(f"[OK] Total chunks generados: {len(all_chunks)}")
    print(f"[OK] Guardado en:            {OUTPUT_FILE}\n")

    # Resumen por clase
    print("Resumen por clase:")
    clase_counts = Counter(c["clase"] for c in all_chunks)
    for clase, count in sorted(clase_counts.items()):
        print(f"  {clase}: {count} chunks")

    # Verificar IDs unicos
    ids = [c["id"] for c in all_chunks]
    dupes = [id_ for id_, cnt in Counter(ids).items() if cnt > 1]
    if dupes:
        print(f"\n[WARN] IDs duplicados detectados: {dupes}")
    else:
        print(f"\n[OK] Todos los IDs son unicos")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
build_chunks.py (v2 — chunking semántico con metadata enriquecida)

Lee los .docx de las 14 clases en knowledge/fuentes/ y genera
knowledge/algebra_chunks_v2.json con chunks semánticos compatibles
con utils/rag.py (campos: id, contenido, tema).

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
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph
except ImportError:
    print("ERROR: python-docx no instalado. Ejecutá: pip install python-docx")
    sys.exit(1)

# ── Rutas ───────────────────────────────────────────────────────────────────
FUENTES_DIR = Path("knowledge") / "fuentes"
OUTPUT_FILE = Path("knowledge") / "algebra_chunks_v2.json"

# ── Parámetros de chunking ──────────────────────────────────────────────────
CHUNK_FLUSH = 800       # flush buffer cuando supera este largo en chars
CHUNK_MAX = 1200        # máximo absoluto por chunk antes de subdividir
CHUNK_MIN = 80          # descartar chunks menores a esto

# ── Regex para filtrar solo archivos de clase ────────────────────────────────
CLASE_RE = re.compile(r'[Cc]lase[\s_-]*(\d{1,2})\s*[-_]?\s*(.*)')

# ── Heading styles ──────────────────────────────────────────────────────────
HEADING_MAP = {
    'heading 1': 1, 'heading 2': 2, 'heading 3': 3,
    'título 1': 1,  'título 2': 2,  'título 3': 3,
    'titulo 1': 1,  'titulo 2': 2,  'titulo 3': 3,
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def parse_filename(filename: str):
    """
    'Clase 8 - MATRICES.docx' -> (8, 'MATRICES')
    'Clase 14 FUNCIONES ESPECIALES Y TRIGONOMETRICAS.docx' -> (14, 'FUNCIONES ESPECIALES Y TRIGONOMETRICAS')
    """
    name = filename.replace('.docx', '')
    m = CLASE_RE.match(name)
    if not m:
        return None, None
    num = int(m.group(1))
    tema = m.group(2).strip().strip('-').strip('_').strip()
    return num, tema


def iter_block_items(parent):
    """
    Itera párrafos y tablas en orden de documento.
    Devuelve objetos Paragraph o Table.
    """
    for child in parent.element.body.iterchildren():
        if child.tag == qn('w:p'):
            yield Paragraph(child, parent)
        elif child.tag == qn('w:tbl'):
            yield Table(child, parent)


def table_to_text(table) -> str:
    """Convierte una tabla Word a texto plano con | como separador."""
    lines = []
    for row in table.rows:
        cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
        lines.append(' | '.join(cells))
    return '\n'.join(lines)


def get_heading_level(para) -> int | None:
    """Devuelve 1/2/3 si es heading, None si no."""
    if not para.style:
        return None
    style_name = para.style.name.lower()
    return HEADING_MAP.get(style_name)


def detect_tipo(text: str) -> str:
    """Heurística para clasificar el tipo de chunk."""
    prefix = text[:250].lower()
    if re.search(r'\bej\)', prefix) or 'ejemplo:' in prefix or 'por ejemplo' in prefix:
        return 'ejemplo'
    if re.search(r'\bdefinici[oó]n\b', prefix) or 'def.' in prefix or 'se define' in prefix:
        return 'definicion'
    if re.search(r'\bejercicio\s+\d', prefix) or 'resolver' in prefix or 'calcular' in prefix or 'demostrar' in prefix:
        return 'ejercicio'
    return 'teoria'


def split_long_chunk(text: str) -> list[str]:
    """
    Divide texto > CHUNK_MAX respetando oraciones.
    Último recurso: corte por palabras.
    """
    if len(text) <= CHUNK_MAX:
        return [text]

    # Intentar split por oraciones (punto + espacio + mayúscula)
    sentences = re.split(r'(?<=\.)\s+(?=[A-ZÁÉÍÓÚÑ])', text)

    parts = []
    current = ''
    for sent in sentences:
        if current and len(current) + len(sent) + 1 > CHUNK_MAX:
            parts.append(current.strip())
            current = sent
        else:
            current = current + ' ' + sent if current else sent

    if current.strip():
        parts.append(current.strip())

    # Si algún fragmento sigue siendo > CHUNK_MAX, cortar por palabras
    final = []
    for part in parts:
        if len(part) <= CHUNK_MAX:
            final.append(part)
        else:
            words = part.split()
            buf = ''
            for w in words:
                if buf and len(buf) + len(w) + 1 > CHUNK_MAX:
                    final.append(buf.strip())
                    buf = w
                else:
                    buf = buf + ' ' + w if buf else w
            if buf.strip():
                final.append(buf.strip())

    return final


# ── Procesamiento de un archivo ─────────────────────────────────────────────

def process_docx(filepath: Path) -> list[dict]:
    clase_num, tema_clase = parse_filename(filepath.name)
    if clase_num is None:
        return []

    print(f"  {filepath.name}")
    print(f"     Clase {clase_num} — {tema_clase}")

    doc = Document(str(filepath))

    # Estado del parser
    h1 = None
    h2 = None
    h3 = None
    buffer = ''
    chunks = []
    chunk_counter = 0

    def flush_buffer():
        nonlocal buffer, chunk_counter
        text = buffer.strip()
        buffer = ''
        if len(text) < CHUNK_MIN:
            return

        fragments = split_long_chunk(text)
        for frag in fragments:
            if len(frag) < CHUNK_MIN:
                continue
            chunk_counter += 1
            tema = h2 or h1 or tema_clase
            chunks.append({
                'id': f'clase_{clase_num:02d}_chunk_{chunk_counter:03d}',
                'contenido': frag,
                'tema': tema,
                'topic': tema,
                'clase': clase_num,
                'tema_clase': tema_clase,
                'seccion': h1,
                'subseccion': h2,
                'subsubseccion': h3,
                'tipo': detect_tipo(frag),
                'longitud_chars': len(frag),
                'fuente': filepath.name,
            })

    for block in iter_block_items(doc):
        if isinstance(block, Table):
            table_text = table_to_text(block)
            if table_text.strip():
                buffer += '\n[Tabla]:\n' + table_text + '\n'
                if len(buffer) > CHUNK_FLUSH:
                    flush_buffer()
            continue

        # Es un Paragraph
        text = block.text.strip()
        if not text:
            continue

        level = get_heading_level(block)
        if level is not None:
            # Nuevo heading: flush lo acumulado
            flush_buffer()
            if level == 1:
                h1 = text
                h2 = None
                h3 = None
            elif level == 2:
                h2 = text
                h3 = None
            elif level == 3:
                h3 = text
            continue

        buffer += text + '\n'
        if len(buffer) > CHUNK_FLUSH:
            flush_buffer()

    # Flush final
    flush_buffer()

    print(f"     [OK] {chunk_counter} chunks generados")
    return chunks


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if not FUENTES_DIR.exists():
        print(f"ERROR: No existe el directorio {FUENTES_DIR}")
        sys.exit(1)

    docx_files = sorted(FUENTES_DIR.glob('*.docx'))

    # Filtrar solo archivos de clase
    clase_files = []
    for f in docx_files:
        num, _ = parse_filename(f.name)
        if num is not None:
            clase_files.append(f)

    if not clase_files:
        print(f"ERROR: No se encontraron archivos de clase en {FUENTES_DIR}")
        sys.exit(1)

    print(f"[INFO] Leyendo .docx desde: {FUENTES_DIR}")
    print(f"[INFO] Archivos de clase encontrados: {len(clase_files)}")
    skipped = len(docx_files) - len(clase_files)
    if skipped:
        print(f"[INFO] Archivos ignorados (no son clase): {skipped}")
    print('-' * 60)

    all_chunks = []
    for docx_file in clase_files:
        chunks = process_docx(docx_file)
        all_chunks.extend(chunks)
        print()

    # Escribir JSON
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print('=' * 60)
    print(f'Total chunks generados: {len(all_chunks)}')
    print(f'Guardado en: {OUTPUT_FILE}')
    print('=' * 60)

    # ── Estadísticas ────────────────────────────────────────────────────────

    # Por clase
    print('\nChunks por clase:')
    clase_counts = Counter(c['clase'] for c in all_chunks)
    for clase_num in sorted(clase_counts):
        print(f'  Clase {clase_num:2d}: {clase_counts[clase_num]:3d} chunks')

    # Distribución de tamaños
    buckets = {'<200': 0, '200-400': 0, '400-800': 0, '800-1200': 0, '>1200': 0}
    lengths = [c['longitud_chars'] for c in all_chunks]
    for l in lengths:
        if l < 200:
            buckets['<200'] += 1
        elif l < 400:
            buckets['200-400'] += 1
        elif l < 800:
            buckets['400-800'] += 1
        elif l <= 1200:
            buckets['800-1200'] += 1
        else:
            buckets['>1200'] += 1

    print('\nDistribución de tamaños:')
    for bucket, count in buckets.items():
        print(f'  {bucket:>8s}: {count:3d}')

    # Tipos
    tipo_counts = Counter(c['tipo'] for c in all_chunks)
    print('\nTipos detectados:')
    for tipo, count in sorted(tipo_counts.items()):
        print(f'  {tipo:>12s}: {count:3d}')

    # Min/max/promedio
    if lengths:
        print(f'\nLongitud promedio: {sum(lengths) / len(lengths):.0f} chars')
        print(f'Longitud mínima:  {min(lengths)} chars')
        print(f'Longitud máxima:  {max(lengths)} chars')

    # IDs únicos
    ids = [c['id'] for c in all_chunks]
    dupes = [id_ for id_, cnt in Counter(ids).items() if cnt > 1]
    if dupes:
        print(f'\n[WARN] IDs duplicados: {dupes}')
    else:
        print(f'\n[OK] Todos los IDs son únicos')


if __name__ == '__main__':
    main()

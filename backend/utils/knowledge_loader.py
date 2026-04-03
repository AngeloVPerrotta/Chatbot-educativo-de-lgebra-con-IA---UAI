from pathlib import Path


DATA_DIR = Path(__file__).parent.parent.parent / "data"


def list_pdfs() -> list[str]:
    pdf_dir = DATA_DIR / "pdfs"
    return [f.name for f in pdf_dir.glob("*.pdf")] if pdf_dir.exists() else []


def list_ejercicios() -> list[str]:
    ejercicios_dir = DATA_DIR / "ejercicios"
    return [f.name for f in ejercicios_dir.iterdir() if f.is_file() and f.suffix != ".md"] if ejercicios_dir.exists() else []

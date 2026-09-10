"""Genera la publicación estática del comparador Mantua sin depender de la API de GitHub en el navegador."""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "proyectos"
OUTPUT = ROOT / "dist"
INDEX = ROOT / "index.html"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
CATALOG_RE = re.compile(
    r'(<script id="project-catalog" type="application/json">).*?(</script>)',
    re.DOTALL,
)

# Ajuste visual final del comparador publicado. Se inyecta en la salida para no
# modificar la lógica de interacción ni el sistema de carga ya estable.
ELEGANT_STYLE = """
<style id="mantua-elegant-compare">
/* Línea divisoria fina y discreta */
.divider::before{
  left:-.5px;
  width:1px;
  background:rgba(255,255,255,.72);
  box-shadow:0 0 2px rgba(0,0,0,.16);
}

/* Control central redondo, ligero y traslúcido */
.handle{
  width:42px;
  height:42px;
  border-radius:50%;
  background:rgba(255,255,255,.20);
  border:0;
  box-shadow:0 4px 14px rgba(0,0,0,.14);
  color:rgba(20,24,30,.72);
  -webkit-backdrop-filter:blur(9px) saturate(115%);
  backdrop-filter:blur(9px) saturate(115%);
}
.handle svg{
  width:27px;
  height:15px;
  stroke:currentColor;
  stroke-width:1.55;
  filter:none;
}

/* Cápsulas Antes / Después con efecto vidrio, menos sólidas */
.label{
  padding:6px 11px;
  background:rgba(18,18,18,.43);
  border:0;
  border-radius:999px;
  color:rgba(255,255,255,.96);
  box-shadow:0 2px 8px rgba(0,0,0,.10);
  -webkit-backdrop-filter:blur(8px) saturate(115%);
  backdrop-filter:blur(8px) saturate(115%);
}

@media(max-width:700px){
  .handle{
    width:40px;
    height:40px;
  }
  .handle svg{width:25px}
}
</style>
"""


def natural_key(value: str):
    return [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", value)
    ]


def folded(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()


def relative_posix(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def choose_pair(files: list[Path]) -> tuple[Path, Path] | None:
    if len(files) < 2:
        return None

    before = next((p for p in files if "antes" in folded(p.stem)), None)
    after = next((p for p in files if "despues" in folded(p.stem)), None)

    if before and after and before != after:
        return before, after

    return files[0], files[1]


def build_catalog() -> list[dict]:
    categories: list[dict] = []
    if not PROJECTS.exists():
        return categories

    for category_dir in sorted(
        (p for p in PROJECTS.iterdir() if p.is_dir()),
        key=lambda p: natural_key(p.name),
    ):
        projects: list[dict] = []

        for project_dir in sorted(
            (p for p in category_dir.iterdir() if p.is_dir()),
            key=lambda p: natural_key(p.name),
        ):
            images = sorted(
                (
                    p
                    for p in project_dir.iterdir()
                    if p.is_file()
                    and p.suffix.casefold() in IMAGE_EXTENSIONS
                    and p.stat().st_size > 128
                ),
                key=lambda p: natural_key(p.name),
            )
            pair = choose_pair(images)
            if not pair:
                continue

            before, after = pair
            projects.append(
                {
                    "name": project_dir.name,
                    "before": relative_posix(before),
                    "after": relative_posix(after),
                }
            )

        if projects:
            categories.append({"name": category_dir.name, "projects": projects})

    return categories


def main() -> None:
    catalog = build_catalog()
    if not catalog:
        raise SystemExit("No se encontraron comparativos válidos.")

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    html = INDEX.read_text(encoding="utf-8")
    payload = json.dumps(catalog, ensure_ascii=False, indent=2).replace("</script>", "<\\/script>")
    html, replacements = CATALOG_RE.subn(
        lambda match: f'{match.group(1)}\n{payload}\n{match.group(2)}',
        html,
        count=1,
    )
    if replacements != 1:
        raise SystemExit("No se encontró el bloque project-catalog en index.html.")

    if "</head>" not in html:
        raise SystemExit("No se encontró el cierre </head> en index.html.")
    html = html.replace("</head>", f"{ELEGANT_STYLE}\n</head>", 1)

    (OUTPUT / "index.html").write_text(html, encoding="utf-8")
    shutil.copytree(PROJECTS, OUTPUT / "proyectos", ignore=shutil.ignore_patterns(".*"))

    count = sum(len(category["projects"]) for category in catalog)
    print(f"Comparador Mantua preparado: {count} comparativos en {len(catalog)} categorías.")


if __name__ == "__main__":
    main()

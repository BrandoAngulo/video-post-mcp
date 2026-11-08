"""inventario: qué hay en el proyecto antes de planear cortes."""

from __future__ import annotations

from .. import rutas
from ..errores import ErrorHerramienta
from ..ffmpeg import sondear, tipo_por_extension


def inventario(proyecto: str) -> str:
    carpeta = rutas.carpeta_proyecto(proyecto)
    lineas = [f"Proyecto '{proyecto}'"]
    total = 0
    for sub in ("fuentes", "trabajo", "salida"):
        archivos = sorted(p for p in (carpeta / sub).rglob("*") if p.is_file())
        total += len(archivos)
        lineas.append(f"\n{sub}/ ({len(archivos)})")
        for archivo in archivos:
            rel = rutas.relativa_a(carpeta, archivo)
            tipo = tipo_por_extension(archivo)
            if tipo in ("video", "imagen", "audio"):
                try:
                    detalle = sondear(archivo).resumen()
                except ErrorHerramienta as e:
                    detalle = f"ilegible: {e}"
            else:
                detalle = tipo
            lineas.append(f"- {rel} — {detalle}")
    n_cuadros = sum(1 for p in (carpeta / "cuadros").glob("*.jpg"))
    lineas.append(f"\ncuadros/ ({n_cuadros} imágenes de QA)")
    if total == 0:
        lineas.append("\nEl proyecto está vacío: copia clips, fotos y música en fuentes/.")
    return "\n".join(lineas)

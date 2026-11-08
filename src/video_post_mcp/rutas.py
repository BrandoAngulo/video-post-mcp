"""Resolución y validación de rutas dentro de la carpeta de medios.

Toda ruta que llega de una herramienta es relativa al proyecto. Aquí se
garantiza que nunca salga de /media/<proyecto> (ni con `..`, ni con rutas
absolutas, ni con enlaces simbólicos) y que nunca se escriba en `fuentes/`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath

from .errores import ErrorHerramienta

SUBCARPETAS = ("fuentes", "cuadros", "trabajo", "salida")
CARPETAS_ESCRITURA = ("cuadros", "trabajo", "salida")
_NOMBRE_PROYECTO = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def raiz_medios() -> Path:
    """Carpeta raíz de medios (montada desde el host en el contenedor)."""
    return Path(os.environ.get("MEDIA_ROOT", "/media"))


def carpeta_proyecto(proyecto: str, crear: bool = True) -> Path:
    """Devuelve la carpeta del proyecto, creando sus subcarpetas si hace falta."""
    if not _NOMBRE_PROYECTO.match(proyecto or ""):
        raise ErrorHerramienta(
            f"Nombre de proyecto inválido: {proyecto!r}. Usa minúsculas, números, '-' o '_' "
            "(ej. 'perfume-oud')."
        )
    carpeta = raiz_medios() / proyecto
    if crear:
        for sub in SUBCARPETAS:
            (carpeta / sub).mkdir(parents=True, exist_ok=True)
    elif not carpeta.is_dir():
        raise ErrorHerramienta(f"El proyecto {proyecto!r} no existe en la carpeta de medios.")
    return carpeta


def _validar_relativa(relativa: str) -> PurePosixPath:
    if not relativa or "\x00" in relativa:
        raise ErrorHerramienta("Ruta vacía o con caracteres inválidos.")
    normal = relativa.replace("\\", "/")
    ruta = PurePosixPath(normal)
    if ruta.is_absolute() or re.match(r"^[A-Za-z]:", normal):
        raise ErrorHerramienta(
            f"Usa rutas relativas al proyecto (ej. 'fuentes/toma1.mp4'), no {relativa!r}."
        )
    if ".." in ruta.parts:
        raise ErrorHerramienta(f"La ruta {relativa!r} no puede contener '..'.")
    return ruta


def _dentro_de(base: Path, ruta: Path) -> Path:
    real = ruta.resolve()
    if not real.is_relative_to(base.resolve()):
        raise ErrorHerramienta("La ruta apunta fuera del proyecto.")
    return real


def entrada(proyecto_dir: Path, relativa: str) -> Path:
    """Ruta de un archivo existente del proyecto (para leer)."""
    ruta = _dentro_de(proyecto_dir, proyecto_dir / _validar_relativa(relativa))
    if not ruta.is_file():
        raise ErrorHerramienta(
            f"No existe {relativa!r} en el proyecto. Usa 'inventario' para ver los archivos."
        )
    return ruta


def salida(
    proyecto_dir: Path,
    relativa: str,
    sobrescribir: bool = False,
    extension: str | None = None,
) -> Path:
    """Ruta de escritura dentro de cuadros/, trabajo/ o salida/.

    Si el archivo ya existe y no se pide sobrescribir, se versiona:
    montaje.mp4 -> montaje-2.mp4 -> montaje-3.mp4 ...
    """
    rel = _validar_relativa(relativa)
    if rel.parts[0] not in CARPETAS_ESCRITURA:
        raise ErrorHerramienta(
            f"Las salidas van en {', '.join(CARPETAS_ESCRITURA)}/; 'fuentes/' es de solo lectura."
        )
    if extension and rel.suffix.lower() != extension:
        rel = rel.with_suffix(extension)
    # La subcarpeta de primer nivel podría ser un enlace simbólico hacia fuera:
    # se verifica antes de crear nada.
    _dentro_de(proyecto_dir, proyecto_dir / rel.parts[0])
    ruta = proyecto_dir / rel
    ruta.parent.mkdir(parents=True, exist_ok=True)
    _dentro_de(proyecto_dir, ruta.parent)
    if sobrescribir or not ruta.exists():
        return ruta
    n = 2
    while True:
        candidata = ruta.with_name(f"{ruta.stem}-{n}{ruta.suffix}")
        if not candidata.exists():
            return candidata
        n += 1


def relativa_a(proyecto_dir: Path, ruta: Path) -> str:
    """Ruta relativa al proyecto, con '/' (para mostrar en las respuestas)."""
    return ruta.resolve().relative_to(proyecto_dir.resolve()).as_posix()

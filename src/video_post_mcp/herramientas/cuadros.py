"""extraer_cuadros: imágenes de segundos concretos para revisión visual."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import rutas
from ..errores import ErrorHerramienta
from ..ffmpeg import ejecutar, sondear

MAX_CUADROS = 8


@dataclass(frozen=True)
class Cuadro:
    segundo: float | None
    ruta: Path
    relativa: str


def extraer_cuadros(proyecto: str, archivo: str, segundos: list[float],
                    ancho: int = 512) -> list[Cuadro]:
    carpeta = rutas.carpeta_proyecto(proyecto)
    origen = rutas.entrada(carpeta, archivo)
    if not 256 <= ancho <= 1080:
        raise ErrorHerramienta("ancho debe estar entre 256 y 1080 px.")
    medio = sondear(origen)

    if medio.tipo == "imagen":
        destino = rutas.salida(carpeta, f"cuadros/{origen.stem}.jpg", sobrescribir=True)
        ejecutar(["-i", str(origen), "-vf", _filtro_jpg(ancho), "-q:v", "3", str(destino)])
        return [Cuadro(None, destino, rutas.relativa_a(carpeta, destino))]

    if medio.tipo != "video" or not medio.duracion:
        raise ErrorHerramienta(f"{archivo} no es un video o imagen legible.")
    if not 1 <= len(segundos) <= MAX_CUADROS:
        raise ErrorHerramienta(f"Pide entre 1 y {MAX_CUADROS} segundos por llamada.")
    fuera = [s for s in segundos if s < 0 or s > medio.duracion]
    if fuera:
        raise ErrorHerramienta(
            f"Segundos fuera del video (dura {medio.duracion:.2f} s): {fuera}."
        )

    cuadros = []
    for s in segundos:
        # Último cuadro: retroceder un poco, en el final exacto no hay imagen.
        t = min(s, max(medio.duracion - 0.05, 0))
        destino = rutas.salida(carpeta, f"cuadros/{origen.stem}_t{s:06.2f}.jpg", sobrescribir=True)
        ejecutar(["-ss", f"{t:.3f}", "-i", str(origen), "-frames:v", "1",
                  "-vf", _filtro_jpg(ancho), "-q:v", "3", str(destino)])
        cuadros.append(Cuadro(s, destino, rutas.relativa_a(carpeta, destino)))
    return cuadros


def _filtro_jpg(ancho: int) -> str:
    """Escala y pasa a rango completo: el codificador JPEG de FFmpeg 7.x (Debian)
    rechaza el rango limitado (TV) que traen los videos de Veo."""
    return f"scale={ancho}:-2:out_range=pc,format=yuvj420p"

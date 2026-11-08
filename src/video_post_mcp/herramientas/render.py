"""render: único encode final, listo para publicar."""

from __future__ import annotations

from .. import formato, rutas
from ..errores import ErrorHerramienta
from ..ffmpeg import ejecutar, nvenc_disponible, sondear

PRESETS = ("reels",)

_X264 = ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-maxrate", "12M",
         "-bufsize", "24M", "-profile:v", "high", "-level", "4.2"]
_NVENC = ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0",
          "-maxrate", "12M", "-bufsize", "24M", "-profile:v", "high"]


def render(proyecto: str, video: str, preset: str = "reels", lut: str | None = None,
           salida: str | None = None, sobrescribir: bool = False) -> str:
    if preset not in PRESETS:
        raise ErrorHerramienta(f"preset debe ser uno de {PRESETS}.")
    carpeta = rutas.carpeta_proyecto(proyecto)
    origen = rutas.entrada(carpeta, video)
    medio = sondear(origen)
    if medio.tipo != "video" or not medio.duracion:
        raise ErrorHerramienta(f"{video} no es un video legible.")

    filtros = []
    if lut:
        ruta_lut = rutas.entrada(carpeta, lut)
        if ruta_lut.suffix.lower() != ".cube":
            raise ErrorHerramienta("El LUT debe ser un archivo .cube.")
        if "'" in str(ruta_lut):
            raise ErrorHerramienta("El nombre del LUT no puede contener comillas simples.")
        filtros.append(f"lut3d=file='{ruta_lut}'")
    filtros += [f"fps={formato.FPS}", "format=yuv420p"]

    usa_nvenc = nvenc_disponible()
    destino = rutas.salida(carpeta, salida or f"salida/{origen.stem}_final.mp4", sobrescribir,
                           extension=".mp4")
    args = ["-i", str(origen), "-vf", ",".join(filtros), *formato.SALIDA_CFR,
            *(_NVENC if usa_nvenc else _X264)]
    if medio.tiene_audio:
        args += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        args += ["-an"]
    ejecutar([*args, "-movflags", "+faststart", str(destino)])

    real = sondear(destino)
    mb = destino.stat().st_size / 1_000_000
    encoder = "h264_nvenc (GPU)" if usa_nvenc else "libx264 (CPU)"
    return (f"Final: {rutas.relativa_a(carpeta, destino)} — {real.resumen()}, {mb:.1f} MB, "
            f"encoder {encoder}{', LUT ' + lut if lut else ''}.")

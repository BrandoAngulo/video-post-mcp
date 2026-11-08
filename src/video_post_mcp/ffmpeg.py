"""Ejecución de ffmpeg/ffprobe con errores legibles.

Nunca se usa shell: los argumentos van como lista, así un nombre de archivo
o un texto no pueden inyectar comandos.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .errores import ErrorHerramienta

log = logging.getLogger(__name__)

TIMEOUT_S = int(os.environ.get("FFMPEG_TIMEOUT", "300"))

EXT_VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
EXT_IMAGEN = {".jpg", ".jpeg", ".png", ".webp"}
EXT_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
EXT_LUT = {".cube"}
EXT_FUENTE = {".ttf", ".otf"}


def tipo_por_extension(ruta: Path) -> str:
    ext = ruta.suffix.lower()
    if ext in EXT_VIDEO:
        return "video"
    if ext in EXT_IMAGEN:
        return "imagen"
    if ext in EXT_AUDIO:
        return "audio"
    if ext in EXT_LUT:
        return "lut"
    if ext in EXT_FUENTE:
        return "fuente"
    return "otro"


def ejecutar(args: list[str], timeout: int = TIMEOUT_S) -> None:
    """Corre ffmpeg con los argumentos dados. Lanza ErrorHerramienta si falla."""
    comando = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *args]
    log.info("ffmpeg %s", " ".join(args))
    try:
        r = subprocess.run(comando, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise ErrorHerramienta(f"FFmpeg superó el límite de {timeout} s.") from e
    if r.returncode != 0:
        cola = "\n".join(r.stderr.strip().splitlines()[-15:])
        raise ErrorHerramienta(f"FFmpeg falló (código {r.returncode}):\n{cola}")


@dataclass(frozen=True)
class Medio:
    tipo: str
    duracion: float | None
    ancho: int | None
    alto: int | None
    fps: float | None
    tiene_audio: bool
    codec_video: str | None

    def resumen(self) -> str:
        partes = [self.tipo]
        if self.duracion is not None and self.tipo in ("video", "audio"):
            partes.append(f"{self.duracion:.2f} s")
        if self.ancho and self.alto:
            partes.append(f"{self.ancho}x{self.alto}")
        if self.fps and self.tipo == "video":
            partes.append(f"{self.fps:g} fps")
        if self.tipo == "video":
            partes.append("con audio" if self.tiene_audio else "sin audio")
        return ", ".join(partes)


def _fps(texto: str | None) -> float | None:
    if not texto or texto in ("0/0", "0"):
        return None
    if "/" in texto:
        num, den = texto.split("/")
        return round(float(num) / float(den), 3) if float(den) else None
    return float(texto)


def sondear(ruta: Path) -> Medio:
    """Lee duración, resolución, fps y audio con ffprobe."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
             str(ruta)],
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired as e:
        raise ErrorHerramienta(f"ffprobe tardó demasiado con {ruta.name}.") from e
    if r.returncode != 0:
        raise ErrorHerramienta(f"No se pudo leer {ruta.name}: ¿archivo dañado o formato no soportado?")
    datos = json.loads(r.stdout or "{}")
    streams = datos.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = datos.get("format", {}).get("duration")
    tipo = tipo_por_extension(ruta)
    return Medio(
        tipo=tipo,
        duracion=float(dur) if dur not in (None, "N/A") else None,
        ancho=int(video["width"]) if video else None,
        alto=int(video["height"]) if video else None,
        fps=_fps(video.get("avg_frame_rate")) if video else None,
        tiene_audio=audio is not None,
        codec_video=video.get("codec_name") if video else None,
    )


@lru_cache(maxsize=1)
def nvenc_disponible() -> bool:
    """True si se pidió NVENC (USE_NVENC=1) y la GPU responde de verdad.

    Se prueba codificando un cuadro: que el encoder exista en la lista no
    garantiza que el contenedor tenga acceso a la GPU.
    """
    if os.environ.get("USE_NVENC") != "1":
        return False
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    if r.returncode != 0:
        log.warning("USE_NVENC=1 pero NVENC no responde; se usará libx264. %s", r.stderr[-300:])
    return r.returncode == 0

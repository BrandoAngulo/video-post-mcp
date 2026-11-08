"""Constantes de formato vertical y filtros de normalización compartidos."""

from __future__ import annotations

import os
from pathlib import Path

from .errores import ErrorHerramienta

ANCHO = 1080
ALTO = 1920
FPS = 30

# Franjas que tapa la interfaz de Reels/TikTok (perfil, botones, descripción).
MARGEN_SUPERIOR = 250
MARGEN_INFERIOR = 480
MARGEN_LATERAL = 60
ANCHO_SEGURO = ANCHO - 2 * MARGEN_LATERAL

AJUSTES = ("recortar", "difuminar")

# Salida a cuadros constantes: cada cuadro dura 1/FPS, también el último. Sin esto,
# algunas versiones de FFmpeg (p. ej. la 7.1 de Debian) pierden la duración del
# último cuadro tras trim/concat y el MP4 queda a 30.288 fps y un cuadro más corto.
SALIDA_CFR = ["-fps_mode", "cfr", "-r", str(FPS)]

# Intermedios casi sin pérdida: la calidad final la decide solo `render`.
CODEC_INTERMEDIO = [*SALIDA_CFR, "-c:v", "libx264", "-preset", "medium", "-crf", "14",
                    "-pix_fmt", "yuv420p"]
AUDIO_INTERMEDIO = ["-c:a", "aac", "-b:a", "256k", "-ar", "48000"]

DIR_FUENTES_INCLUIDAS = Path(os.environ.get("FONTS_DIR", Path(__file__).resolve().parents[2] / "fonts"))
FUENTE_DEFECTO = "Montserrat-SemiBold"


def validar_ajuste(ajuste: str) -> str:
    if ajuste not in AJUSTES:
        raise ErrorHerramienta(f"ajuste debe ser uno de {AJUSTES}, no {ajuste!r}.")
    return ajuste


def validar_foco(foco_x: float, foco_y: float) -> None:
    if not (0 <= foco_x <= 1 and 0 <= foco_y <= 1):
        raise ErrorHerramienta("foco_x y foco_y van de 0 (izquierda/arriba) a 1 (derecha/abajo).")


def cadena_normalizar(entrada: str, salida: str, ajuste: str, ancho: int = ANCHO,
                      alto: int = ALTO, fps: int | None = FPS, foco_x: float = 0.5,
                      foco_y: float = 0.5) -> str:
    """Cadena de filtros que lleva una entrada de video a ancho x alto.

    recortar:  llena el lienzo y recorta alrededor del foco (0.5, 0.5 = centro).
    difuminar: encaja la imagen completa sobre una copia ampliada y desenfocada.
    """
    final = f"setsar=1{f',fps={fps}' if fps else ''},format=yuv420p"
    if ajuste == "recortar":
        return (f"[{entrada}]scale={ancho}:{alto}:force_original_aspect_ratio=increase,"
                f"crop={ancho}:{alto}:(iw-ow)*{foco_x}:(ih-oh)*{foco_y},{final}[{salida}]")
    fondo, frente = f"{salida}_bg", f"{salida}_fg"
    return (f"[{entrada}]split=2[{fondo}0][{frente}0];"
            f"[{fondo}0]scale={ancho}:{alto}:force_original_aspect_ratio=increase,"
            f"crop={ancho}:{alto},boxblur=30:2[{fondo}];"
            f"[{frente}0]scale={ancho}:{alto}:force_original_aspect_ratio=decrease[{frente}];"
            f"[{fondo}][{frente}]overlay=(W-w)/2:(H-h)/2,{final}[{salida}]")

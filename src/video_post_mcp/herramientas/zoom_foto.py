"""zoom_foto: convierte una foto real en un clip vertical con zoom lento.

Sirve para tomas donde la IA no debe tocar el producto (logos, etiquetas).
"""

from __future__ import annotations

from .. import formato, rutas
from ..errores import ErrorHerramienta
from ..ffmpeg import ejecutar, sondear

# zoompan tiembla si trabaja a la resolución de salida: se amplía x2 antes.
_FACTOR = 2


def zoom_foto(proyecto: str, imagen: str, duracion: float, zoom_inicial: float = 1.0,
              zoom_final: float = 1.1, ajuste: str = "recortar",
              salida: str | None = None, foco_x: float = 0.5, foco_y: float = 0.5,
              sobrescribir: bool = False) -> str:
    """El foco (0–1) decide qué parte de la foto queda en el recorte vertical y hacia
    dónde va el zoom: una foto 3:4 con el producto arriba necesita foco_y bajo (~0.2)."""
    carpeta = rutas.carpeta_proyecto(proyecto)
    origen = rutas.entrada(carpeta, imagen)
    if sondear(origen).tipo != "imagen":
        raise ErrorHerramienta(f"{imagen} no es una imagen (jpg, png, webp).")
    if not 1 <= duracion <= 15:
        raise ErrorHerramienta("duracion debe estar entre 1 y 15 segundos.")
    for z in (zoom_inicial, zoom_final):
        if not 1.0 <= z <= 2.0:
            raise ErrorHerramienta("zoom_inicial y zoom_final deben estar entre 1.0 y 2.0.")
    formato.validar_ajuste(ajuste)
    formato.validar_foco(foco_x, foco_y)

    destino = rutas.salida(carpeta, salida or f"trabajo/{origen.stem}_zoom.mp4",
                           sobrescribir, extension=".mp4")
    cuadros = round(duracion * formato.FPS)
    ancho_g, alto_g = formato.ANCHO * _FACTOR, formato.ALTO * _FACTOR
    paso = (zoom_final - zoom_inicial) / max(cuadros - 1, 1)
    filtro = (
        formato.cadena_normalizar("0:v", "lienzo", ajuste, ancho_g, alto_g, fps=None,
                                  foco_x=foco_x, foco_y=foco_y) + ";"
        f"[lienzo]zoompan=z='{zoom_inicial}+{paso}*on'"
        f":x='(iw-iw/zoom)*{foco_x}':y='(ih-ih/zoom)*{foco_y}'"
        f":d={cuadros}:s={formato.ANCHO}x{formato.ALTO}:fps={formato.FPS},"
        f"setsar=1,format=yuv420p[v]"
    )
    ejecutar(["-i", str(origen), "-filter_complex", filtro, "-map", "[v]",
              "-frames:v", str(cuadros), *formato.CODEC_INTERMEDIO, "-an", str(destino)])
    real = sondear(destino)
    return (f"Clip creado: {rutas.relativa_a(carpeta, destino)} — {real.resumen()} "
            f"(zoom {zoom_inicial}→{zoom_final}, foco {foco_x},{foco_y}).")

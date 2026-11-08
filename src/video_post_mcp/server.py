"""Servidor MCP (stdio). Solo define el contrato de cada herramienta y delega.

SDK: mcp 2.x — `FastMCP` pasó a llamarse `MCPServer`.
Todo log va a stderr: stdout es el canal del protocolo.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal

from mcp.server.mcpserver import Image, MCPServer
from pydantic import BaseModel, Field

from . import __version__
from .herramientas.audio import audio as _audio
from .herramientas.cuadros import extraer_cuadros as _extraer_cuadros
from .herramientas.inventario import inventario as _inventario
from .herramientas.montar import Corte as _Corte
from .herramientas.montar import montar as _montar
from .herramientas.render import render as _render
from .herramientas.texto_logo import Logo as _Logo
from .herramientas.texto_logo import Texto as _Texto
from .herramientas.texto_logo import texto_y_logo as _texto_y_logo
from .herramientas.zoom_foto import zoom_foto as _zoom_foto

INSTRUCCIONES = """\
Postproducción local de reels verticales (1080x1920, 30 fps) con FFmpeg.
Cada proyecto es una carpeta con fuentes/ (entradas, solo lectura), cuadros/, trabajo/ y salida/.
Las rutas siempre son relativas al proyecto (ej. 'fuentes/toma1.mp4').
Flujo típico: inventario → extraer_cuadros (QA) → zoom_foto (fotos de producto) → montar
→ texto_y_logo → audio → render. Revisa con extraer_cuadros antes de render.
Nunca se sobrescribe: si la salida existe se crea una versión -2, -3..."""

servidor = MCPServer("video-post", instructions=INSTRUCCIONES, version=__version__)

Proyecto = Field(description="Nombre de la carpeta del proyecto (minúsculas, números, - o _).")
Sobrescribir = Field(
    False,
    description="Reemplazar la salida si ya existe. Por defecto se crea una versión -2, -3...: "
    "usa siempre la ruta que devuelve la respuesta para el siguiente paso.",
)


class CorteIn(BaseModel):
    archivo: str = Field(description="Clip relativo al proyecto, ej. 'fuentes/toma1.mp4'.")
    inicio: float = Field(ge=0, description="Segundo de inicio dentro del clip.")
    fin: float = Field(gt=0, description="Segundo final dentro del clip (exclusivo).")


class TextoIn(BaseModel):
    texto: str = Field(description="Texto a mostrar. Usa \\n para partir en líneas.")
    inicio: float = Field(ge=0, description="Segundo del video en que aparece.")
    fin: float = Field(gt=0, description="Segundo del video en que desaparece.")
    posicion: Literal["arriba", "centro", "abajo"] = "abajo"
    tamano: int = Field(64, description="Tamaño en px (16–200).")
    color: str = Field("#FFFFFF", description="Color #RRGGBB.")
    sombra: bool = True
    fundido: float = Field(0.3, ge=0, description="Segundos de fundido de entrada y salida.")
    fuente: str | None = Field(
        None,
        description="Fuente incluida (Montserrat-SemiBold, Montserrat-Bold, Montserrat-Regular) "
        "o archivo del proyecto (ej. 'fuentes/marca.otf'). Por defecto Montserrat-SemiBold.",
    )
    desplazamiento: int = Field(
        0,
        description="Píxeles para mover el texto desde su posición (positivo baja, negativo sube). "
        "Útil para apilar dos textos o esquivar el producto; no puede salir de la zona segura.",
    )


class LogoIn(BaseModel):
    archivo: str = Field(description="Imagen del logo (PNG con transparencia ideal).")
    inicio: float = Field(ge=0)
    fin: float = Field(gt=0)
    posicion: Literal["arriba_izq", "arriba_der", "abajo_izq", "abajo_der", "centro"] = "abajo_der"
    ancho: int = Field(220, description="Ancho del logo en px.")


@servidor.tool()
def inventario(proyecto: str = Proyecto) -> str:
    """Lista los archivos del proyecto (fuentes, trabajo, salida) con tipo, duración,
    resolución, fps y si tienen audio. Crea las carpetas del proyecto si no existen."""
    return _inventario(proyecto)


@servidor.tool()
def extraer_cuadros(
    proyecto: str = Proyecto,
    archivo: str = Field(description="Video o imagen relativo al proyecto."),
    segundos: list[float] = Field(
        default_factory=list, description="Hasta 8 segundos a extraer (se ignora en imágenes)."
    ),
    ancho: int = Field(512, description="Ancho de las imágenes devueltas (256–1080)."),
) -> list:
    """Devuelve imágenes de segundos concretos de un video para revisión visual (QA):
    texto o logos deformados, manos, saltos, encuadre. También guarda los JPG en cuadros/."""
    cuadros = _extraer_cuadros(proyecto, archivo, segundos, ancho)
    contenido: list = []
    for c in cuadros:
        etiqueta = f"{archivo} @ {c.segundo:.2f} s" if c.segundo is not None else archivo
        contenido.append(f"{etiqueta} → {c.relativa}")
        contenido.append(Image(path=c.ruta))
    return contenido


@servidor.tool()
def zoom_foto(
    proyecto: str = Proyecto,
    imagen: str = Field(description="Foto relativa al proyecto, ej. 'fuentes/tapa.jpg'."),
    duracion: float = Field(description="Duración del clip en segundos (1–15)."),
    zoom_inicial: float = Field(1.0, description="Zoom al inicio (1.0–2.0)."),
    zoom_final: float = Field(1.1, description="Zoom al final (1.0–2.0)."),
    ajuste: Literal["recortar", "difuminar"] = Field(
        "recortar", description="recortar llena el cuadro; difuminar muestra la foto completa."
    ),
    salida: str | None = Field(None, description="Ruta de salida en trabajo/ o salida/."),
    foco_x: float = Field(0.5, description="Foco horizontal 0 (izq) – 1 (der)."),
    foco_y: float = Field(
        0.5, description="Foco vertical 0 (arriba) – 1 (abajo). Producto arriba en la foto → ~0.2."
    ),
    sobrescribir: bool = Sobrescribir,
) -> str:
    """Convierte una foto real en un clip vertical con zoom lento hacia el foco. Úsalo para
    tomas de producto donde la IA no debe tocar logos ni etiquetas. Revisa el encuadre con
    extraer_cuadros: si el producto queda cortado o fuera, ajusta foco_x/foco_y."""
    return _zoom_foto(proyecto, imagen, duracion, zoom_inicial, zoom_final, ajuste, salida,
                      foco_x, foco_y, sobrescribir)


@servidor.tool()
def montar(
    proyecto: str = Proyecto,
    cortes: list[CorteIn] = Field(description="Cortes en orden de aparición."),
    salida: str = Field("trabajo/montaje.mp4", description="Ruta de salida."),
    ajuste: Literal["recortar", "difuminar"] = "recortar",
    conservar_audio: bool = Field(
        False, description="Conservar el audio de los clips (por defecto se descarta)."
    ),
    sobrescribir: bool = Sobrescribir,
) -> str:
    """Recorta y une clips en un video vertical 1080x1920 a 30 fps, con cortes exactos al
    cuadro. Devuelve la línea de tiempo con el segundo en que empieza cada corte."""
    return _montar(
        proyecto, [_Corte(c.archivo, c.inicio, c.fin) for c in cortes], salida, ajuste,
        conservar_audio, sobrescribir,
    )


@servidor.tool()
def texto_y_logo(
    proyecto: str = Proyecto,
    video: str = Field(description="Video relativo al proyecto."),
    textos: list[TextoIn] = Field(default_factory=list),
    logo: LogoIn | None = None,
    salida: str | None = None,
    sobrescribir: bool = Sobrescribir,
) -> str:
    """Superpone textos (con fundido) y un logo en tiempos exactos, dentro de las zonas
    seguras de Reels/TikTok. Mide el texto con la fuente real y avisa si no cabe."""
    return _texto_y_logo(
        proyecto, video,
        [_Texto(**t.model_dump()) for t in textos],
        _Logo(**logo.model_dump()) if logo else None,
        salida, sobrescribir,
    )


@servidor.tool()
def audio(
    proyecto: str = Proyecto,
    video: str = Field(description="Video relativo al proyecto."),
    musica: str = Field(description="Archivo de música relativo al proyecto."),
    inicio_musica: float = Field(0.0, description="Segundo de la canción desde el que arranca."),
    volumen: float = Field(1.0, description="Volumen de la música (0–2)."),
    fundido_entrada: float = 0.5,
    fundido_salida: float = 1.0,
    conservar_original: bool = Field(False, description="Mezclar con el audio del video."),
    volumen_original: float = Field(0.3, description="Volumen del audio original (0–2)."),
    salida: str | None = None,
    sobrescribir: bool = Sobrescribir,
) -> str:
    """Pone música al video (recortada a su duración, con fundidos) y opcionalmente la
    mezcla con el audio original. El video no se recodifica."""
    return _audio(proyecto, video, musica, inicio_musica, volumen, fundido_entrada,
                  fundido_salida, conservar_original, volumen_original, salida, sobrescribir)


@servidor.tool()
def render(
    proyecto: str = Proyecto,
    video: str = Field(description="Video relativo al proyecto."),
    preset: Literal["reels"] = "reels",
    lut: str | None = Field(None, description="LUT .cube opcional, ej. 'fuentes/calido.cube'."),
    salida: str | None = None,
    sobrescribir: bool = Sobrescribir,
) -> str:
    """Exporta el MP4 final para Reels/TikTok (H.264, 30 fps, AAC, faststart). Usa la GPU
    (NVENC) si está habilitada y disponible; si no, CPU."""
    return _render(proyecto, video, preset, lut, salida, sobrescribir)


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    servidor.run("stdio")


if __name__ == "__main__":
    main()

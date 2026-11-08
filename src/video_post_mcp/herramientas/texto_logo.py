"""texto_y_logo: textos y logo en tiempos exactos, dentro de las zonas seguras."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import ImageFont

from .. import formato, rutas
from ..errores import ErrorHerramienta
from ..ffmpeg import ejecutar, sondear

POSICIONES_TEXTO = ("arriba", "centro", "abajo")
POSICIONES_LOGO = ("arriba_izq", "arriba_der", "abajo_izq", "abajo_der", "centro")
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class Texto:
    texto: str
    inicio: float
    fin: float
    posicion: str = "abajo"
    tamano: int = 64
    color: str = "#FFFFFF"
    sombra: bool = True
    fundido: float = 0.3
    fuente: str | None = None
    desplazamiento: int = 0  # px; positivo baja el texto, negativo lo sube


@dataclass(frozen=True)
class Logo:
    archivo: str
    inicio: float
    fin: float
    posicion: str = "abajo_der"
    ancho: int = 220


def resolver_fuente(carpeta: Path, fuente: str | None) -> Path:
    """Fuente incluida por nombre (ej. 'Montserrat-Bold') o .ttf/.otf del proyecto."""
    nombre = fuente or formato.FUENTE_DEFECTO
    if "/" in nombre or "\\" in nombre:
        ruta = rutas.entrada(carpeta, nombre)
        if ruta.suffix.lower() not in (".ttf", ".otf"):
            raise ErrorHerramienta(f"La fuente {nombre} debe ser .ttf u .otf.")
        return ruta
    incluida = formato.DIR_FUENTES_INCLUIDAS / f"{nombre}.ttf"
    if not incluida.is_file():
        disponibles = sorted(p.stem for p in formato.DIR_FUENTES_INCLUIDAS.glob("*.ttf"))
        raise ErrorHerramienta(
            f"Fuente {nombre!r} no encontrada. Incluidas: {disponibles}, "
            "o usa un archivo del proyecto (ej. 'fuentes/marca.otf')."
        )
    return incluida


def _ancho_texto(fuente: Path, tamano: int, texto: str) -> int:
    ft = ImageFont.truetype(str(fuente), tamano)
    return max(int(ft.getlength(linea)) for linea in texto.splitlines() or [""])


def _alpha(t: Texto) -> str:
    """Expresión de opacidad con fundido de entrada y salida."""
    f = max(min(t.fundido, (t.fin - t.inicio) / 2), 0.001)
    a, b = t.inicio, t.fin
    return (f"if(lt(t,{a}),0,if(lt(t,{a + f}),(t-{a})/{f},"
            f"if(lt(t,{b - f}),1,if(lt(t,{b}),({b}-t)/{f},0))))")


def _y_lineas(posicion: str, n_lineas: int, tamano: int, desplazamiento: int = 0) -> list[int]:
    """Y de cada línea. Cada línea se dibuja aparte para centrarla por separado
    (drawtext alinea a la izquierda dentro de un bloque multilínea).

    `desplazamiento` mueve el bloque sin salir de las zonas seguras: sirve para
    apilar dos textos (p. ej. nombre y CTA arriba) o esquivar el producto."""
    alto_linea = round(tamano * 1.25)
    alto_bloque = n_lineas * alto_linea
    inicio = {
        "arriba": formato.MARGEN_SUPERIOR,
        "centro": (formato.ALTO - alto_bloque) // 2,
        "abajo": formato.ALTO - formato.MARGEN_INFERIOR - alto_bloque,
    }[posicion] + desplazamiento
    minimo = formato.MARGEN_SUPERIOR
    maximo = formato.ALTO - formato.MARGEN_INFERIOR - alto_bloque
    if not minimo <= inicio <= maximo:
        raise ErrorHerramienta(
            f"Con desplazamiento={desplazamiento} el texto sale de la zona segura "
            f"(su borde superior debe quedar entre {minimo} y {maximo} px)."
        )
    return [inicio + k * alto_linea for k in range(n_lineas)]


def _xy_logo(posicion: str) -> tuple[str, str]:
    m, sup, inf = formato.MARGEN_LATERAL, formato.MARGEN_SUPERIOR, formato.MARGEN_INFERIOR
    return {
        "arriba_izq": (str(m), str(sup)),
        "arriba_der": (f"W-w-{m}", str(sup)),
        "abajo_izq": (str(m), f"H-h-{inf}"),
        "abajo_der": (f"W-w-{m}", f"H-h-{inf}"),
        "centro": ("(W-w)/2", "(H-h)/2"),
    }[posicion]


def _validar_tiempos(nombre: str, inicio: float, fin: float, duracion: float) -> None:
    if inicio < 0 or fin <= inicio:
        raise ErrorHerramienta(f"{nombre}: inicio debe ser ≥ 0 y menor que fin.")
    if fin > duracion + 0.05:
        raise ErrorHerramienta(f"{nombre}: fin={fin} pasa el final del video ({duracion:.2f} s).")


def texto_y_logo(proyecto: str, video: str, textos: list[Texto] | None = None,
                 logo: Logo | None = None, salida: str | None = None,
                 sobrescribir: bool = False) -> str:
    textos = textos or []
    if not textos and logo is None:
        raise ErrorHerramienta("Envía al menos un texto o un logo.")
    carpeta = rutas.carpeta_proyecto(proyecto)
    origen = rutas.entrada(carpeta, video)
    medio = sondear(origen)
    if medio.tipo != "video" or not medio.duracion:
        raise ErrorHerramienta(f"{video} no es un video legible.")

    filtros: list[str] = []
    actual = "0:v"
    entradas = ["-i", str(origen)]

    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(textos):
            nombre = f"Texto {i + 1}"
            if not t.texto.strip():
                raise ErrorHerramienta(f"{nombre}: está vacío.")
            if t.posicion not in POSICIONES_TEXTO:
                raise ErrorHerramienta(f"{nombre}: posicion debe ser una de {POSICIONES_TEXTO}.")
            if not 16 <= t.tamano <= 200:
                raise ErrorHerramienta(f"{nombre}: tamano debe estar entre 16 y 200.")
            if not _COLOR.match(t.color):
                raise ErrorHerramienta(f"{nombre}: color debe ser #RRGGBB.")
            _validar_tiempos(nombre, t.inicio, t.fin, medio.duracion)

            fuente = resolver_fuente(carpeta, t.fuente)
            ancho = _ancho_texto(fuente, t.tamano, t.texto)
            if ancho > formato.ANCHO_SEGURO:
                maximo = int(t.tamano * formato.ANCHO_SEGURO / ancho)
                raise ErrorHerramienta(
                    f"{nombre}: mide {ancho}px y el ancho seguro es {formato.ANCHO_SEGURO}px. "
                    f"Usa tamano ≤ {maximo} o parte el texto en líneas con \\n."
                )

            lineas = [linea.strip() for linea in t.texto.splitlines() if linea.strip()]
            sombra = ":shadowcolor=black@0.6:shadowx=3:shadowy=3" if t.sombra else ""
            ys = _y_lineas(t.posicion, len(lineas), t.tamano, t.desplazamiento)
            for k, (linea, y) in enumerate(zip(lineas, ys)):
                # Archivo de texto: evita el escape frágil de drawtext con tildes y signos.
                archivo_txt = Path(tmp) / f"t{i}_{k}.txt"
                archivo_txt.write_text(linea, encoding="utf-8")
                etiqueta = f"t{i}_{k}"
                filtros.append(
                    f"[{actual}]drawtext=fontfile='{fuente}':textfile='{archivo_txt}'"
                    f":fontsize={t.tamano}:fontcolor={t.color}"
                    f":x=(w-text_w)/2:y={y}{sombra}"
                    f":alpha='{_alpha(t)}':enable='between(t,{t.inicio},{t.fin})'[{etiqueta}]"
                )
                actual = etiqueta

        if logo is not None:
            ruta_logo = rutas.entrada(carpeta, logo.archivo)
            if sondear(ruta_logo).tipo != "imagen":
                raise ErrorHerramienta("El logo debe ser una imagen (ideal PNG con transparencia).")
            if logo.posicion not in POSICIONES_LOGO:
                raise ErrorHerramienta(f"Logo: posicion debe ser una de {POSICIONES_LOGO}.")
            if not 40 <= logo.ancho <= formato.ANCHO_SEGURO:
                raise ErrorHerramienta(f"Logo: ancho debe estar entre 40 y {formato.ANCHO_SEGURO}.")
            _validar_tiempos("Logo", logo.inicio, logo.fin, medio.duracion)
            entradas += ["-i", str(ruta_logo)]
            x, y = _xy_logo(logo.posicion)
            filtros.append(f"[1:v]scale={logo.ancho}:-1,format=rgba[lg]")
            filtros.append(
                f"[{actual}][lg]overlay={x}:{y}:enable='between(t,{logo.inicio},{logo.fin})'"
                f",format=yuv420p[final]"
            )
            actual = "final"

        destino = rutas.salida(carpeta, salida or f"trabajo/{origen.stem}_texto.mp4",
                               sobrescribir, extension=".mp4")
        args = [*entradas, "-filter_complex", ";".join(filtros), "-map", f"[{actual}]",
                *formato.CODEC_INTERMEDIO]
        args += ["-map", "0:a", "-c:a", "copy"] if medio.tiene_audio else ["-an"]
        ejecutar([*args, str(destino)])

    real = sondear(destino)
    partes = [f"{len(textos)} texto(s)"] + (["logo"] if logo else [])
    return f"Listo: {rutas.relativa_a(carpeta, destino)} — {real.resumen()} ({', '.join(partes)})."

"""montar: une cortes de varios clips en un solo video vertical."""

from __future__ import annotations

from dataclasses import dataclass

from .. import formato, rutas
from ..errores import ErrorHerramienta
from ..ffmpeg import ejecutar, sondear

MAX_CORTES = 50
_TOLERANCIA = 0.05  # los metadatos de duración no son exactos al milisegundo


@dataclass(frozen=True)
class Corte:
    archivo: str
    inicio: float
    fin: float


def montar(proyecto: str, cortes: list[Corte], salida: str = "trabajo/montaje.mp4",
           ajuste: str = "recortar", conservar_audio: bool = False,
           sobrescribir: bool = False) -> str:
    carpeta = rutas.carpeta_proyecto(proyecto)
    formato.validar_ajuste(ajuste)
    if not 1 <= len(cortes) <= MAX_CORTES:
        raise ErrorHerramienta(f"Envía entre 1 y {MAX_CORTES} cortes.")

    entradas: list[str] = []
    filtros: list[str] = []
    etiquetas: list[str] = []
    linea_tiempo: list[str] = []
    acumulado = 0.0

    for i, corte in enumerate(cortes):
        origen = rutas.entrada(carpeta, corte.archivo)
        medio = sondear(origen)
        if medio.tipo == "imagen":
            raise ErrorHerramienta(
                f"Corte {i + 1}: {corte.archivo} es una imagen. Conviértela antes con zoom_foto."
            )
        if medio.tipo != "video" or not medio.duracion:
            raise ErrorHerramienta(f"Corte {i + 1}: {corte.archivo} no es un video legible.")
        if corte.inicio < 0 or corte.fin <= corte.inicio:
            raise ErrorHerramienta(f"Corte {i + 1}: inicio debe ser ≥ 0 y menor que fin.")
        if corte.fin > medio.duracion + _TOLERANCIA:
            raise ErrorHerramienta(
                f"Corte {i + 1}: fin={corte.fin} pasa el final de {corte.archivo} "
                f"({medio.duracion:.2f} s)."
            )
        fin = min(corte.fin, medio.duracion)
        largo = round(fin - corte.inicio, 3)

        # -ss/-t en la entrada + recodificación = corte exacto al cuadro.
        entradas += ["-ss", f"{corte.inicio:.3f}", "-t", f"{largo:.3f}", "-i", str(origen)]
        filtros.append(formato.cadena_normalizar(f"{i}:v", f"v{i}", ajuste))
        etiqueta = f"[v{i}]"
        if conservar_audio:
            if medio.tiene_audio:
                filtros.append(
                    f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                    f"apad,atrim=0:{largo},asetpts=PTS-STARTPTS[a{i}]"
                )
            else:
                filtros.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{largo}[a{i}]")
            etiqueta += f"[a{i}]"
        etiquetas.append(etiqueta)
        linea_tiempo.append(
            f"{i + 1}. {acumulado:6.2f}–{acumulado + largo:6.2f} s ← {corte.archivo} "
            f"[{corte.inicio:.2f}–{fin:.2f}]"
        )
        acumulado += largo

    n = len(cortes)
    audio_flag = 1 if conservar_audio else 0
    filtros.append(f"{''.join(etiquetas)}concat=n={n}:v=1:a={audio_flag}[v]"
                   + ("[a]" if conservar_audio else ""))
    destino = rutas.salida(carpeta, salida, sobrescribir, extension=".mp4")
    args = [*entradas, "-filter_complex", ";".join(filtros), "-map", "[v]",
            *formato.CODEC_INTERMEDIO]
    args += ["-map", "[a]", *formato.AUDIO_INTERMEDIO] if conservar_audio else ["-an"]
    ejecutar([*args, str(destino)])

    real = sondear(destino)
    return "\n".join([
        f"Montaje: {rutas.relativa_a(carpeta, destino)} — {real.resumen()}",
        "Línea de tiempo (montaje ← clip [tramo]):",
        *linea_tiempo,
    ])

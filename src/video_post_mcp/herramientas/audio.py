"""audio: música con fundidos, opcionalmente mezclada con el audio original."""

from __future__ import annotations

from .. import formato, rutas
from ..errores import ErrorHerramienta
from ..ffmpeg import ejecutar, sondear


def audio(proyecto: str, video: str, musica: str, inicio_musica: float = 0.0,
          volumen: float = 1.0, fundido_entrada: float = 0.5, fundido_salida: float = 1.0,
          conservar_original: bool = False, volumen_original: float = 0.3,
          salida: str | None = None, sobrescribir: bool = False) -> str:
    carpeta = rutas.carpeta_proyecto(proyecto)
    ruta_video = rutas.entrada(carpeta, video)
    ruta_musica = rutas.entrada(carpeta, musica)
    mv, mm = sondear(ruta_video), sondear(ruta_musica)
    if mv.tipo != "video" or not mv.duracion:
        raise ErrorHerramienta(f"{video} no es un video legible.")
    if not mm.tiene_audio or not mm.duracion:
        raise ErrorHerramienta(f"{musica} no tiene pista de audio.")
    if inicio_musica < 0 or inicio_musica >= mm.duracion:
        raise ErrorHerramienta(
            f"inicio_musica debe estar entre 0 y {mm.duracion:.2f} s (duración de la música)."
        )
    for nombre, v in (("volumen", volumen), ("volumen_original", volumen_original)):
        if not 0 <= v <= 2:
            raise ErrorHerramienta(f"{nombre} debe estar entre 0 y 2.")
    dur = mv.duracion
    fi = max(0.0, min(fundido_entrada, dur / 2))
    fo = max(0.0, min(fundido_salida, dur / 2))

    disponible = mm.duracion - inicio_musica
    aviso = ""
    if disponible < dur:
        aviso = (f" Aviso: la música alcanza {disponible:.2f} s y el video dura {dur:.2f} s; "
                 "el final queda en silencio.")

    # apad + atrim: la música siempre dura exactamente lo mismo que el video.
    cadena = (f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
              f"apad,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS")
    if fi:
        cadena += f",afade=t=in:st=0:d={fi}"
    if fo:
        cadena += f",afade=t=out:st={dur - fo:.3f}:d={fo}"
    cadena += f",volume={volumen}"

    if conservar_original and mv.tiene_audio:
        filtros = [
            cadena + "[m]",
            f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"apad,atrim=0:{dur:.3f},volume={volumen_original}[o]",
            "[m][o]amix=inputs=2:duration=first:normalize=0[a]",
        ]
        modo = "música + audio original"
    else:
        filtros = [cadena + "[a]"]
        modo = "solo música"
        if conservar_original:
            aviso += " El video no tenía audio original."

    destino = rutas.salida(carpeta, salida or f"trabajo/{ruta_video.stem}_audio.mp4",
                           sobrescribir, extension=".mp4")
    ejecutar(["-i", str(ruta_video), "-ss", f"{inicio_musica:.3f}", "-i", str(ruta_musica),
              "-filter_complex", ";".join(filtros), "-map", "0:v", "-map", "[a]",
              "-c:v", "copy", *formato.AUDIO_INTERMEDIO, "-t", f"{dur:.3f}", str(destino)])
    real = sondear(destino)
    return f"Listo: {rutas.relativa_a(carpeta, destino)} — {real.resumen()} ({modo}).{aviso}"

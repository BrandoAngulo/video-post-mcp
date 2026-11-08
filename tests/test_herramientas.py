from pathlib import Path

import pytest

from video_post_mcp.errores import ErrorHerramienta
from video_post_mcp.ffmpeg import sondear
from video_post_mcp.herramientas.audio import audio
from video_post_mcp.herramientas.cuadros import extraer_cuadros
from video_post_mcp.herramientas.inventario import inventario
from video_post_mcp.herramientas.montar import Corte, montar
from video_post_mcp.herramientas.render import render
from video_post_mcp.herramientas.texto_logo import Logo, Texto, texto_y_logo
from video_post_mcp.herramientas.zoom_foto import zoom_foto

P = "prueba"


def _medio(proyecto: Path, rel: str):
    return sondear(proyecto / rel)


def _vertical(m) -> None:
    assert (m.ancho, m.alto) == (1080, 1920)
    assert m.fps == 30


def test_inventario_lista_fuentes(proyecto):
    texto = inventario(P)
    assert "fuentes/horizontal.mp4" in texto and "con audio" in texto
    assert "fuentes/vertical.mp4" in texto and "sin audio" in texto
    assert (proyecto / "cuadros").is_dir() and (proyecto / "salida").is_dir()


def test_inventario_proyecto_vacio(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    assert "vacío" in inventario("nuevo")


def test_extraer_cuadros(proyecto):
    cuadros = extraer_cuadros(P, "fuentes/horizontal.mp4", [0, 2.5, 5], ancho=320)
    assert len(cuadros) == 3
    for c in cuadros:
        assert c.ruta.is_file() and c.ruta.stat().st_size > 0
        assert sondear(c.ruta).ancho == 320


def test_extraer_cuadros_de_imagen(proyecto):
    [c] = extraer_cuadros(P, "fuentes/foto.jpg", [])
    assert c.segundo is None and sondear(c.ruta).ancho == 512


@pytest.mark.parametrize("segundos", [[], [9.0], list(range(9))])
def test_extraer_cuadros_valida(proyecto, segundos):
    with pytest.raises(ErrorHerramienta):
        extraer_cuadros(P, "fuentes/horizontal.mp4", segundos)


def test_zoom_foto(proyecto):
    zoom_foto(P, "fuentes/foto.jpg", 2.0, 1.0, 1.1, salida="trabajo/tapa.mp4")
    m = _medio(proyecto, "trabajo/tapa.mp4")
    _vertical(m)
    assert m.duracion == pytest.approx(2.0, abs=0.05)
    assert not m.tiene_audio


def test_zoom_foto_difuminar(proyecto):
    zoom_foto(P, "fuentes/foto.jpg", 1.0, ajuste="difuminar", salida="trabajo/dif.mp4")
    _vertical(_medio(proyecto, "trabajo/dif.mp4"))


def test_zoom_foto_con_foco(proyecto):
    texto = zoom_foto(P, "fuentes/foto.jpg", 1.0, foco_x=0.5, foco_y=0.2,
                      salida="trabajo/foco.mp4")
    assert "foco 0.5,0.2" in texto
    _vertical(_medio(proyecto, "trabajo/foco.mp4"))


def test_zoom_foto_foco_invalido(proyecto):
    with pytest.raises(ErrorHerramienta, match="foco"):
        zoom_foto(P, "fuentes/foto.jpg", 1.0, foco_y=1.5)


def test_zoom_foto_rechaza_video(proyecto):
    with pytest.raises(ErrorHerramienta, match="no es una imagen"):
        zoom_foto(P, "fuentes/vertical.mp4", 2.0)


def test_montar_normaliza_y_corta_exacto(proyecto):
    resumen = montar(P, [
        Corte("fuentes/horizontal.mp4", 1.0, 3.0),   # 2 s, 16:9 a 24 fps
        Corte("fuentes/vertical.mp4", 0.5, 2.0),     # 1.5 s, ya vertical
    ])
    m = _medio(proyecto, "trabajo/montaje.mp4")
    _vertical(m)
    assert m.duracion == pytest.approx(3.5, abs=0.07)
    assert not m.tiene_audio
    assert "2.00–  3.50" in resumen  # el segundo corte arranca en 2.00 s


def test_montar_no_acumula_desfase_al_cambiar_fps(proyecto):
    # Clip fuente a 24 fps con cortes que no caen en su rejilla de cuadros:
    # la duración total debe ser la suma pedida, sin el redondeo acumulado.
    largos = [2.07, 1.99, 2.25, 1.99, 2.93]
    cortes = [Corte("fuentes/horizontal.mp4", 0.1, 0.1 + largo) for largo in largos]
    resumen = montar(P, cortes)
    m = _medio(proyecto, "trabajo/montaje.mp4")
    assert m.duracion == pytest.approx(sum(largos), abs=1 / 30 + 0.01)
    assert "8.30– 11.23" in resumen  # el último corte arranca en la suma de los anteriores


def test_montar_conservando_audio_con_clip_mudo(proyecto):
    montar(P, [Corte("fuentes/horizontal.mp4", 0, 1), Corte("fuentes/vertical.mp4", 0, 1)],
           conservar_audio=True)
    m = _medio(proyecto, "trabajo/montaje.mp4")
    assert m.tiene_audio and m.duracion == pytest.approx(2.0, abs=0.07)


@pytest.mark.parametrize("corte, error", [
    (Corte("fuentes/horizontal.mp4", 3, 2), "menor que fin"),
    (Corte("fuentes/horizontal.mp4", 0, 9), "pasa el final"),
    (Corte("fuentes/foto.jpg", 0, 1), "zoom_foto"),
])
def test_montar_valida(proyecto, corte, error):
    with pytest.raises(ErrorHerramienta, match=error):
        montar(P, [corte])


def test_texto_y_logo(proyecto):
    texto_y_logo(P, "fuentes/vertical.mp4", [
        Texto("Hay aromas que llegan\nantes que tú", 0.2, 2.0, "arriba", 60),
        Texto("Pídelo por WhatsApp: ¡ya!", 2.0, 4.0, "abajo", 56, "#E8CC7A",
              fuente="Montserrat-Bold"),
    ], Logo("fuentes/logo.png", 2.0, 4.0, "arriba_der", 200), salida="trabajo/texto.mp4")
    m = _medio(proyecto, "trabajo/texto.mp4")
    _vertical(m)
    assert m.duracion == pytest.approx(4.0, abs=0.07)


def test_texto_demasiado_ancho_sugiere_tamano(proyecto):
    with pytest.raises(ErrorHerramienta, match="tamano ≤"):
        texto_y_logo(P, "fuentes/vertical.mp4",
                     [Texto("Un texto larguísimo que no cabe en una sola línea", 0, 1, tamano=120)])


def test_texto_con_fuente_del_proyecto(proyecto):
    from video_post_mcp import formato
    fuente = formato.DIR_FUENTES_INCLUIDAS / "Montserrat-Regular.ttf"
    (proyecto / "fuentes" / "marca.ttf").write_bytes(fuente.read_bytes())
    texto_y_logo(P, "fuentes/vertical.mp4",
                 [Texto("Vantedge", 0, 1, fuente="fuentes/marca.ttf")], salida="trabajo/marca.mp4")
    assert (proyecto / "trabajo" / "marca.mp4").is_file()


def test_texto_apilado_con_desplazamiento(proyecto):
    texto_y_logo(P, "fuentes/vertical.mp4", [
        Texto("Oud for Glory", 0, 2, "arriba", 72),
        Texto("Pídelo por WhatsApp", 0, 2, "arriba", 56, desplazamiento=100),
    ], salida="trabajo/apilado.mp4")
    assert (proyecto / "trabajo" / "apilado.mp4").is_file()


def test_texto_desplazamiento_fuera_de_zona_segura(proyecto):
    with pytest.raises(ErrorHerramienta, match="zona segura"):
        texto_y_logo(P, "fuentes/vertical.mp4", [Texto("x", 0, 1, "arriba", desplazamiento=-100)])


def test_texto_fuente_inexistente(proyecto):
    with pytest.raises(ErrorHerramienta, match="no encontrada"):
        texto_y_logo(P, "fuentes/vertical.mp4", [Texto("x", 0, 1, fuente="Comic-Sans")])


def test_audio_musica_exacta_y_mezcla(proyecto):
    audio(P, "fuentes/vertical.mp4", "fuentes/musica.mp3", inicio_musica=2,
          salida="trabajo/con_musica.mp4")
    m = _medio(proyecto, "trabajo/con_musica.mp4")
    assert m.tiene_audio and m.duracion == pytest.approx(4.0, abs=0.07)

    texto = audio(P, "fuentes/horizontal.mp4", "fuentes/musica.mp3", conservar_original=True,
                  salida="trabajo/mezcla.mp4")
    assert "música + audio original" in texto


def test_audio_avisa_musica_corta(proyecto):
    texto = audio(P, "fuentes/vertical.mp4", "fuentes/musica.mp3", inicio_musica=8)
    assert "silencio" in texto


def test_render_final_con_lut(proyecto):
    montar(P, [Corte("fuentes/horizontal.mp4", 0, 2)], conservar_audio=True)
    texto = render(P, "trabajo/montaje.mp4", lut="fuentes/neutro.cube", salida="salida/final.mp4")
    m = _medio(proyecto, "salida/final.mp4")
    _vertical(m)
    assert m.codec_video == "h264" and m.tiene_audio
    assert "libx264" in texto


def test_render_no_escribe_en_fuentes(proyecto):
    with pytest.raises(ErrorHerramienta, match="solo lectura"):
        render(P, "fuentes/vertical.mp4", salida="fuentes/x.mp4")

import pytest

from video_post_mcp import rutas
from video_post_mcp.errores import ErrorHerramienta


@pytest.mark.parametrize("nombre", ["", "Perfume", "../x", "a b", "x" * 70, "con/barra"])
def test_nombre_de_proyecto_invalido(nombre, proyecto):
    with pytest.raises(ErrorHerramienta):
        rutas.carpeta_proyecto(nombre)


@pytest.mark.parametrize("ruta", ["../fuera.mp4", "/etc/passwd", "C:\\Windows\\x.mp4",
                                  "fuentes/../../x.mp4", "fuentes/\x00.mp4"])
def test_rutas_fuera_del_proyecto(ruta, proyecto):
    with pytest.raises(ErrorHerramienta):
        rutas.entrada(proyecto, ruta)


def test_enlace_simbolico_hacia_fuera(proyecto, tmp_path):
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("x")
    (proyecto / "fuentes" / "enlace.mp4").symlink_to(secreto)
    with pytest.raises(ErrorHerramienta, match="fuera del proyecto"):
        rutas.entrada(proyecto, "fuentes/enlace.mp4")


def test_fuentes_es_solo_lectura(proyecto):
    with pytest.raises(ErrorHerramienta, match="solo lectura"):
        rutas.salida(proyecto, "fuentes/nuevo.mp4")


def test_salida_se_versiona(proyecto):
    primera = rutas.salida(proyecto, "trabajo/montaje.mp4")
    primera.write_bytes(b"x")
    segunda = rutas.salida(proyecto, "trabajo/montaje.mp4")
    assert segunda.name == "montaje-2.mp4"
    assert rutas.salida(proyecto, "trabajo/montaje.mp4", sobrescribir=True) == primera


def test_rutas_estilo_windows_relativas(proyecto):
    assert rutas.entrada(proyecto, "fuentes\\foto.jpg").name == "foto.jpg"

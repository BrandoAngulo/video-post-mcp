"""Prueba de punta a punta por stdio, como lo usa Claude Desktop."""

import os
import sys

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def _sesion(media_root):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "video_post_mcp.server"],
        env={**os.environ, "MEDIA_ROOT": str(media_root), "PYTHONPATH": "src"},
    )
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            herramientas = {t.name for t in (await s.list_tools()).tools}
            cuadros = await s.call_tool("extraer_cuadros", {
                "proyecto": "prueba", "archivo": "fuentes/horizontal.mp4", "segundos": [1, 2],
            })
            maliciosa = await s.call_tool("montar", {
                "proyecto": "prueba",
                "cortes": [{"archivo": "../../etc/passwd", "inicio": 0, "fin": 1}],
            })
            return herramientas, cuadros, maliciosa


def test_stdio_devuelve_imagenes_y_errores_legibles(proyecto):
    herramientas, cuadros, maliciosa = anyio.run(_sesion, proyecto.parent)
    assert herramientas == {"inventario", "extraer_cuadros", "zoom_foto", "montar",
                            "texto_y_logo", "audio", "render"}
    tipos = [c.type for c in cuadros.content]
    assert tipos.count("image") == 2 and not cuadros.is_error
    assert maliciosa.is_error
    assert "no puede contener '..'" in maliciosa.content[0].text

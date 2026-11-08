"""Error único que las herramientas lanzan hacia el cliente MCP.

El mensaje debe decir qué falló y cómo corregirlo, porque lo lee Claude
para decidir el siguiente intento.

Hereda de `ToolError` porque el SDK de MCP 2.x solo entrega al cliente el
texto de los errores esperados (`ToolError`); cualquier otra excepción la
reduce a "Error executing tool <nombre>" y Claude no sabría qué corregir.
"""

from mcp.server.mcpserver.exceptions import ToolError


class ErrorHerramienta(ToolError):
    """Error esperado de una herramienta (entrada inválida, FFmpeg falló, etc.)."""

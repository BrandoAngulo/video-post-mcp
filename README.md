# video-post-mcp

Servidor MCP local de **postproducción de reels** (1080×1920, 30 fps) con FFmpeg. Le da a Claude herramientas para revisar cuadros, montar clips, poner textos, logo y música, y exportar listo para Reels/TikTok. Corre en Docker, sin red y sin APIs de pago.

Arquitectura y decisiones: [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

## Herramientas

| Herramienta | Qué hace |
|---|---|
| `inventario` | Lista los archivos del proyecto con duración, resolución, fps y audio |
| `extraer_cuadros` | Devuelve imágenes de segundos concretos para revisión visual (QA) |
| `zoom_foto` | Convierte una foto real en clip vertical con zoom lento hacia un foco |
| `montar` | Recorta y une clips en orden, normalizados a 9:16 y 30 fps, con cortes exactos |
| `texto_y_logo` | Textos con fundido y logo en tiempos exactos, dentro de las zonas seguras |
| `audio` | Música con fundidos, opcionalmente mezclada con el audio original |
| `render` | MP4 final (H.264, AAC, faststart), con LUT opcional y GPU si está disponible |

## Carpeta de medios

Un proyecto por carpeta dentro de la carpeta de medios (en este PC: `C:\Users\stivn\Documents\audiovisual`):

```
audiovisual/
└── perfume-oud/
    ├── fuentes/   ← aquí copias clips, fotos, música, logo, LUT y fuentes de marca
    ├── cuadros/   ← imágenes de QA
    ├── trabajo/   ← intermedios
    └── salida/    ← finales
```

Las herramientas crean las subcarpetas solas, nunca escriben en `fuentes/` y nunca sobrescriben: si una salida existe crean `-2`, `-3`…

## Instalación en Windows 11

1. **Docker Desktop** con el motor WSL2 (Windows 11 Home sirve).
2. **Limitar la RAM de WSL2** (recomendado con 8 GB): crea `%UserProfile%\.wslconfig` con
   ```ini
   [wsl2]
   memory=3GB
   ```
   y reinicia WSL con `wsl --shutdown`.
3. **Construir la imagen** (en la carpeta del repositorio):
   ```powershell
   docker build --target pruebas -t video-post-mcp:pruebas .   # corre las pruebas
   docker build -t video-post-mcp .
   ```
4. **Conectar a Claude Desktop**: abre el archivo con *Configuración → Desarrollador → Editar configuración*, que siempre lleva al archivo que la app lee. La ruta cambia según la instalación:
   - Instalador clásico: `%APPDATA%\Claude\claude_desktop_config.json`
   - Versión empaquetada (MSIX), en este PC: `%LOCALAPPDATA%\Claude-Data\claude_pzs8sxrjxfjjc\claude_desktop_config.json`. Ignora `%LOCALAPPDATA%\Packages\Claude_*\...\Claude-3p`: es el modo de proveedores externos.

   Si el archivo ya tiene contenido, no lo reemplaces: agrega solo la clave `mcpServers` (si la carpeta de medios está en otro lugar, cambia la ruta del `-v`):
   ```json
   {
     "mcpServers": {
       "video-post": {
         "command": "docker",
         "args": [
           "run", "-i", "--rm", "--network", "none", "--memory", "1536m",
           "-v", "C:\\Users\\stivn\\Documents\\audiovisual:/media",
           "video-post-mcp"
         ]
       }
     }
   }
   ```
5. Cierra Claude Desktop por completo (también desde el ícono junto al reloj) con Docker Desktop abierto, y vuelve a abrirlo; solo lee la configuración al arrancar. Las herramientas aparecen como `video-post`. También quedan disponibles desde el chat del celular mientras el PC y Claude Desktop estén abiertos.

### GPU (opcional)

Para codificar con la GTX (NVENC) agrega a `args`, antes de `video-post-mcp`: `"--gpus", "all", "-e", "USE_NVENC=1"`. Si la GPU no responde dentro del contenedor, `render` usa la CPU automáticamente y lo informa.

## Fuentes

- Incluidas: `Montserrat-SemiBold` (por defecto), `Montserrat-Bold`, `Montserrat-Regular` (licencia OFL, ver `fonts/OFL.txt`).
- Tipografía de marca: copia el `.ttf`/`.otf` a `fuentes/` del proyecto y úsalo en cada texto con `"fuente": "fuentes/marca.otf"`.

## Flujo típico

```
inventario → extraer_cuadros (QA de clips) → zoom_foto (fotos de producto)
→ montar → texto_y_logo → audio → extraer_cuadros (QA del montaje) → render
```

## Desarrollo sin Docker

Requiere Python 3.12+ y FFmpeg en el PATH.

```bash
pip install -e ".[dev]"
pytest
```

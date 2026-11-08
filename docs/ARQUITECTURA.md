# video-post-mcp — Arquitectura v1

Servidor MCP local de **postproducción de video** para el pipeline de Vantedge. Le da a Claude herramientas para revisar, montar y exportar reels a partir de clips generados (Flow, Veo, Kling…) y fotos reales, usando FFmpeg. Sin APIs de pago, sin red, 100 % local.

Estado: **v1 implementada** — arquitectura aprobada el 2026-11-07 con las decisiones de la sección 10.

---

## 1. Alcance

**Dentro de v1**
- Inventario de medios de un proyecto.
- Extracción de cuadros para QA visual (Claude los ve como imágenes).
- Foto → clip con zoom lento.
- Montaje desde una lista de cortes, normalizado a 9:16.
- Textos y logo en tiempos exactos.
- Audio: silenciar clips, música, volumen y fundidos.
- Render final para Reels/TikTok, con LUT opcional.

**Fuera de v1** (candidatos a v1.1+)
- Generación de imágenes/video (adaptadores de API: Gemini/Omni, agregadores).
- Transiciones, subtítulos automáticos, reencuadre inteligente.
- Integración con el MCP de DaVinci Resolve (acabado manual, opcional).

---

## 2. Decisiones y por qué

| Decisión | Por qué |
|---|---|
| Python 3.12 + SDK oficial `mcp` **2.3** (`from mcp.server.mcpserver import MCPServer`) | Es el SDK oficial vigente. En la v2 `FastMCP` pasó a llamarse `MCPServer`; documentarlo evita copiar ejemplos viejos que ya no corren. |
| Transporte **stdio**, contenedor lanzado por Claude Desktop con `docker run -i --rm` | Sin puertos, sin servidor siempre encendido, sin HTTPS. Claude Desktop lo arranca al abrirse y lo mata al cerrarse. Funciona desde el chat del celular mientras el PC y la app estén abiertos. |
| `--network none` | El servidor solo toca archivos locales. Sin red, un bug o un prompt malicioso no puede sacar nada del PC. |
| FFmpeg por subprocess con lista de argumentos (nunca `shell=True`) | Evita inyección de comandos desde nombres de archivo o textos. |
| Codificación **libx264 (CPU) por defecto**; NVENC opcional con `USE_NVENC=1` + `--gpus all` | NVENC en Docker sobre WSL2 exige NVIDIA Container Toolkit y drivers alineados: si falla, el servidor no debe romperse. Un reel de 15 s en CPU tarda segundos; la GPU es una optimización, no un requisito. Si NVENC no está disponible, cae a libx264 y lo informa. |
| **Siempre recodificar** al cortar (no `-c copy`) | Copiar flujos solo corta en keyframes: los cortes quedarían corridos hasta 1–2 s. En reels de tomas de 2–3 s eso es inaceptable. |
| Intermedios en alta calidad (CRF 14) y un solo encode final en `render` | Cada paso (montar → texto → audio) recodifica; con intermedios casi sin pérdida, la calidad final la define solo `render`. Fusionar todo en un paso es una optimización para v1.1. |
| `montar` descarta el audio de los clips | Los modelos generan audio aunque se pida que no; la música va en `audio`. Opción para conservarlo cuando haga falta. |
| Logs a **stderr** | stdout es el canal del protocolo MCP; escribir ahí corrompe la comunicación. |
| Textos con `drawtext` vía **archivo de texto** (`textfile=`), no inline | Tildes, ñ, comillas y dos puntos rompen el escape de `drawtext`. Con archivo no hay escape que fallar. |
| Fuente incluida en la imagen (Montserrat, licencia OFL) | Mismo resultado en cualquier PC; no depende de fuentes del sistema. |

---

## 3. Estructura del repositorio

```
video-post-mcp/
├── Dockerfile
├── pyproject.toml
├── README.md                 # instalación y conexión a Claude Desktop
├── docs/ARQUITECTURA.md      # este documento
├── src/video_post_mcp/
│   ├── server.py             # MCPServer y registro de herramientas (solo orquesta)
│   ├── rutas.py              # resolución y validación de rutas dentro de /media
│   ├── ffmpeg.py             # ejecutar ffmpeg/ffprobe, timeouts, errores legibles
│   ├── formato.py            # constantes 9:16, fps, zonas seguras, presets
│   └── herramientas/         # una función pura por herramienta
│       ├── inventario.py
│       ├── cuadros.py
│       ├── zoom_foto.py
│       ├── montar.py
│       ├── texto_logo.py
│       ├── audio.py
│       └── render.py
├── fonts/Montserrat-*.ttf
└── tests/                    # pytest; genera medios de prueba con ffmpeg (testsrc, sine)
```

Regla: `server.py` no tiene lógica; cada herramienta es una función que recibe parámetros validados y devuelve un resultado. Así se prueban sin MCP y se pueden reutilizar desde n8n.

---

## 4. Carpeta de medios

Carpeta del host montada en `/media` (configurable; en el PC de Brando: la carpeta `audiovisual` de Documentos). Un proyecto por carpeta:

```
/media/<proyecto>/
├── fuentes/    # lo que entra: clips descargados de Flow, fotos, música, logo, LUT
├── cuadros/    # JPG extraídos para QA
├── trabajo/    # intermedios (montaje, con texto, con audio)
└── salida/     # finales listos para publicar
```

- Todas las rutas de las herramientas son **relativas al proyecto** (ej. `fuentes/toma1.mp4`).
- `rutas.py` rechaza rutas absolutas, `..`, enlaces simbólicos que salgan del proyecto y nombres de proyecto con caracteres fuera de `[a-z0-9-_]`.
- Las herramientas **nunca sobrescriben** `fuentes/`; las salidas existentes se versionan (`montaje.mp4`, `montaje-2.mp4`…) salvo `sobrescribir=true`.
- Por el versionado, **el paso siguiente debe usar la ruta que devuelve la respuesta**, no la que se pidió. (Error real encontrado en la prueba: encadenar con el nombre pedido usó el clip anterior.)
- Textos de varias líneas: cada línea se dibuja con su propio `drawtext` para centrarla por separado (dentro de un bloque, `drawtext` alinea a la izquierda).

---

## 5. Formato de video

Constantes en `formato.py`:
- Lienzo: **1080×1920, 30 fps, SAR 1:1, yuv420p**.
- Ajuste de fuentes con otra proporción: `recortar` (llenar y recortar al centro, por defecto) o `difuminar` (encajar sobre fondo del mismo video desenfocado).
- **Zonas seguras de Reels/TikTok** (la interfaz tapa esas franjas): margen superior 250 px, inferior 480 px, laterales 60 px. Las posiciones `arriba` / `centro` / `abajo` de los textos ya las respetan.

---

## 6. Contrato de herramientas

Toda herramienta devuelve un texto breve con el resultado (`archivo`, `duración`, `resolución`, avisos). En error, devuelve un error MCP con: qué falló, el parámetro culpable y las últimas líneas de FFmpeg.

### 6.1 `inventario(proyecto)`
Lista archivos de `fuentes/`, `trabajo/` y `salida/` con: tipo (video/imagen/audio/lut), duración, resolución, fps, si tiene audio. Usa `ffprobe`.
Para qué: que Claude sepa qué hay antes de planear cortes.

### 6.2 `extraer_cuadros(proyecto, archivo, segundos: list[float], ancho=512)`
- Máximo **8 cuadros** por llamada; `ancho` entre 256 y 1080.
- Guarda JPG en `cuadros/` y **devuelve las imágenes en la respuesta** (contenido de imagen MCP) junto con el tiempo de cada una.
- Valida que cada segundo esté dentro de la duración.
Para qué: QA cuadro a cuadro (texto deformado, manos, saltos) sin abrir el video. Ancho bajo por defecto para no llenar el contexto.

### 6.3 `zoom_foto(proyecto, imagen, duracion, zoom_inicial=1.0, zoom_final=1.1, ajuste="recortar", salida=None, foco_x=0.5, foco_y=0.5)`
- `duracion` 1–15 s; zoom 1.0–2.0.
- Convierte una foto en clip 1080×1920 con zoom lento (`zoompan`) hacia el **foco**. Escala la imagen ×2 antes del zoom para evitar el temblor típico de `zoompan`.
- **Foco** (0–1): decide qué parte de una foto no vertical queda en el recorte y hacia dónde va el zoom. Añadido tras la prueba con la foto cenital del perfume: con el foco al centro, el recorte mostraba superficie vacía y dejaba la tapa fuera.
Para qué: tomas con producto real donde la IA no debe tocar el logo (toma 4 del perfume).

### 6.4 `montar(proyecto, cortes, salida="trabajo/montaje.mp4", ajuste="recortar", conservar_audio=false)`
`cortes`: lista ordenada de `{archivo, inicio, fin}` (segundos dentro de cada clip).
- Valida que `inicio < fin` y que estén dentro de la duración de cada clip.
- Un solo comando FFmpeg con `filter_complex`: `trim` por corte → normalizar (escala, recorte/difuminado, 30 fps, SAR) → `concat`.
- Devuelve la duración total y el tiempo de inicio de cada corte en el montaje (lo que se necesita para ubicar textos y verificar ritmo).

### 6.5 `texto_y_logo(proyecto, video, textos=[], logo=None, salida=None)`
- `textos`: `{texto, inicio, fin, posicion: arriba|centro|abajo, tamano=64, color="#FFFFFF", sombra=true, fundido=0.3, fuente=None}`.
- `fuente` (por texto, o `fuente_defecto` para todo el video): nombre de una fuente incluida (`Montserrat-SemiBold`, `Montserrat-Bold`, `Montserrat-Regular`) o un `.ttf`/`.otf` del proyecto (`fuentes/marca-vantedge.otf`). Así los reels de Vantedge usan la tipografía de marca y los personales otra, sin cambiar el servidor.
- El ancho del texto se **mide con la fuente real** (Pillow) antes de renderizar; si no cabe en el ancho seguro, error con el tamaño máximo que sí cabe.
- `logo`: `{archivo, posicion: arriba_izq|arriba_der|abajo_izq|abajo_der|centro, ancho=220, inicio, fin}`.
- Valida que los tiempos caigan dentro del video y que el texto quepa en el ancho seguro (si no, error con sugerencia de tamaño).

### 6.6 `audio(proyecto, video, musica, inicio_musica=0, volumen=1.0, fundido_entrada=0.5, fundido_salida=1.0, conservar_original=false, volumen_original=0.3, salida=None)`
- Recorta la música a la duración del video desde `inicio_musica`, aplica fundidos y volumen.
- Si `conservar_original`, mezcla el audio de los clips debajo de la música.

### 6.7 `render(proyecto, video, preset="reels", lut=None, salida=None)`
- Preset `reels`: H.264 High, CRF 18, tope 12 Mbps, 30 fps, yuv420p, AAC 192 kbps 48 kHz, `+faststart`.
- `lut`: ruta a `.cube` en `fuentes/`, aplicado con `lut3d` antes de codificar.
- Encoder: `h264_nvenc` si `USE_NVENC=1` y está disponible; si no, `libx264 -preset slow`. Informa cuál usó.
- Devuelve ruta final, tamaño en MB, duración y encoder.

---

## 7. Ejecución y recursos (laptop con 8 GB de RAM)

- `docker run -i --rm --network none --memory 1536m --cpus 4 -v C:\Vantedge\media:/media video-post-mcp`
- Timeout por comando FFmpeg: 300 s.
- Recomendado: `%UserProfile%\.wslconfig` con `memory=3GB` para que WSL2 no consuma la RAM de Windows.
- Windows 11 Home es suficiente (Docker Desktop corre sobre WSL2).

Configuración en Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "video-post": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--network", "none", "--memory", "1536m",
               "-v", "C:\\Vantedge\\media:/media", "video-post-mcp"]
    }
  }
}
```

---

## 8. Pruebas

- **Unitarias (pytest, dentro del contenedor):** generan clips de prueba con `testsrc`/`sine` de duraciones conocidas y verifican con `ffprobe` duración, resolución, fps y presencia de audio de cada salida. Casos de error: rutas fuera del proyecto, tiempos fuera de rango, archivo inexistente.
- **Aceptación:** montar el comercial del perfume con la lista de cortes ya definida (6 tomas, 15 s), textos de gancho y CTA, música y render. Criterio: 15 s ±0,1, 1080×1920, cortes en los segundos pedidos (verificado con `extraer_cuadros`), texto dentro de zonas seguras.

---

## 9. Riesgos conocidos

| Riesgo | Mitigación |
|---|---|
| Clips descargados de Flow con fps o resolución distintos | `montar` normaliza todo a 1080×1920 / 30 fps. |
| 8 GB de RAM con Docker + Chrome + Resolve abiertos | Límite de memoria del contenedor y `.wslconfig`; los renders de reels son cortos. |
| NVENC no disponible en el contenedor | Caída automática a libx264. |
| Sobrescribir trabajo previo | Versionado automático de salidas; `fuentes/` es de solo lectura para las herramientas. |
| Bajar clips de Flow sigue siendo manual (o con el agente y tu aprobación) | Fuera de v1; se resuelve con el adaptador de API cuando decidas pagarla. |

---

## 10. Decisiones de la auditoría (2026-11-07)

1. **Carpeta de medios:** `audiovisual` dentro de Documentos, en el disco C.
2. **Fuente:** Montserrat SemiBold por defecto; la tipografía de marca de Vantedge solo en piezas de Vantedge, cargada como archivo del proyecto. No todo será Vantedge (también reels personales), por eso la fuente es un parámetro y no una constante.
3. **Repositorio:** GitHub `brandoAngulo/video-post-mcp`, Conventional Commits en español, sin atribuciones ni firmas.

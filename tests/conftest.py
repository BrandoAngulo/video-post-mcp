"""Medios de prueba generados con FFmpeg (duraciones y formatos conocidos)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PROYECTO = "prueba"


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture(scope="session")
def medios_base(tmp_path_factory) -> Path:
    """Genera una vez los medios fuente; cada prueba los copia a su proyecto."""
    d = tmp_path_factory.mktemp("base")
    # Horizontal 16:9 con audio, 5 s, 24 fps (fps distinto a propósito).
    _ff("-f", "lavfi", "-i", "testsrc2=s=1280x720:r=24:d=5",
        "-f", "lavfi", "-i", "sine=f=440:d=5", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(d / "horizontal.mp4"))
    # Vertical sin audio, 4 s, 30 fps.
    _ff("-f", "lavfi", "-i", "testsrc=s=1080x1920:r=30:d=4",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "vertical.mp4"))
    # Foto 3:4 como la del frasco.
    _ff("-f", "lavfi", "-i", "testsrc2=s=1500x2000", "-frames:v", "1", str(d / "foto.jpg"))
    # Logo PNG con transparencia.
    _ff("-f", "lavfi", "-i", "color=c=red@0.8:s=400x200,format=rgba", "-frames:v", "1",
        str(d / "logo.png"))
    # Música de 10 s.
    _ff("-f", "lavfi", "-i", "sine=f=220:d=10", "-c:a", "libmp3lame", str(d / "musica.mp3"))
    # LUT identidad 2x2x2.
    (d / "neutro.cube").write_text(
        "LUT_3D_SIZE 2\n" + "".join(
            f"{r} {g} {b}\n" for b in (0, 1) for g in (0, 1) for r in (0, 1)
        )
    )
    return d


@pytest.fixture
def proyecto(tmp_path, monkeypatch, medios_base) -> Path:
    """Proyecto nuevo en una carpeta de medios temporal, con las fuentes copiadas."""
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    fuentes = tmp_path / PROYECTO / "fuentes"
    fuentes.mkdir(parents=True)
    for archivo in medios_base.iterdir():
        (fuentes / archivo.name).write_bytes(archivo.read_bytes())
    return tmp_path / PROYECTO

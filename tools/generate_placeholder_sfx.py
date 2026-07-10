"""Genera efectos de sonido placeholder estilo 8-bit en assets/audio/sfx/.

Son ondas cuadradas y ruido sintetizados con la librería estándar (sin
dependencias), pensados para que el sistema de audio funcione de inmediato.
Cualquier .wav/.ogg con el mismo nombre puesto en assets/audio/sfx/ los
reemplaza sin tocar código. Ejecutar desde la raíz del proyecto:

    python tools/generate_placeholder_sfx.py
"""
import math
import os
import random
import struct
import wave

SAMPLE_RATE = 22050
OUT_DIR = os.path.join("assets", "audio", "sfx")


def write_wav(name, samples):
    path = os.path.join(OUT_DIR, name + ".wav")
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        frames = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples
        )
        f.writeframes(frames)
    print(f"  {path} ({len(samples) / SAMPLE_RATE * 1000:.0f} ms)")


def square(phase):
    return 1.0 if (phase % 1.0) < 0.5 else -1.0


def tone(freq_start, freq_end, duration_s, volume=0.5, decay=4.0, wave_fn=square):
    """Onda con barrido lineal de frecuencia y decaimiento exponencial."""
    n = int(SAMPLE_RATE * duration_s)
    samples = []
    phase = 0.0
    for i in range(n):
        t = i / n
        freq = freq_start + (freq_end - freq_start) * t
        phase += freq / SAMPLE_RATE
        env = math.exp(-decay * t)
        samples.append(wave_fn(phase) * volume * env)
    return samples


def noise(duration_s, volume=0.5, decay=5.0, grain=1):
    """Ruido tipo NES; grain > 1 lo hace más grave/carrasposo."""
    n = int(SAMPLE_RATE * duration_s)
    samples = []
    value = 0.0
    for i in range(n):
        if i % grain == 0:
            value = random.uniform(-1.0, 1.0)
        env = math.exp(-decay * (i / n))
        samples.append(value * volume * env)
    return samples


def mix(*layers):
    n = max(len(layer) for layer in layers)
    out = [0.0] * n
    for layer in layers:
        for i, s in enumerate(layer):
            out[i] += s
    peak = max(1.0, max(abs(s) for s in out))
    return [s / peak for s in out]


def sequence(notes, note_s, volume=0.45, decay=6.0):
    """Arpegio: una lista de frecuencias tocadas en secuencia."""
    samples = []
    for freq in notes:
        samples.extend(tone(freq, freq, note_s, volume=volume, decay=decay))
    return samples


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    random.seed(2024)  # placeholders reproducibles
    print("Generando efectos placeholder en", OUT_DIR)

    write_wav("click", tone(1300, 1100, 0.035, volume=0.35, decay=8.0))
    write_wav("pause", sequence([660, 880], 0.055, volume=0.35, decay=5.0))
    write_wav("shoot", tone(950, 480, 0.09, volume=0.30, decay=6.0))
    write_wav("hit", mix(
        tone(180, 140, 0.07, volume=0.5, decay=7.0),
        noise(0.06, volume=0.35, decay=9.0, grain=2),
    ))
    write_wav("hurt", tone(420, 120, 0.22, volume=0.5, decay=4.5))
    write_wav("enemy_die", mix(
        noise(0.28, volume=0.55, decay=6.0, grain=3),
        tone(300, 60, 0.26, volume=0.35, decay=5.0),
    ))
    # Do mayor ascendente (victoria) / la menor descendente (derrota).
    write_wav("level_clear", sequence([523, 659, 784, 1047], 0.11, decay=5.0))
    write_wav("level_failed", sequence([440, 349, 294, 220], 0.16, decay=4.0))

    print("Listo. Reemplázalos poniendo tus propios .wav/.ogg con el mismo nombre.")


if __name__ == "__main__":
    main()

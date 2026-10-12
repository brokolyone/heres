"""Synthesize the mod's sounds (mono, 44.1 kHz) and encode them to Ogg Vorbis.

    python3 tools/audio/make_sounds.py src/main/resources/assets/heres/sounds

Needs ffmpeg with libvorbis. Everything is generated from noise and oscillators,
so there are no third-party samples to license.
"""
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

SR = 44100
rng = np.random.default_rng(42)


def t(seconds):
    return np.arange(int(SR * seconds)) / SR


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


def reverb(x, seconds=1.2, mix=0.35):
    ir_t = t(seconds)
    ir = rng.normal(0, 1, len(ir_t)) * np.exp(-ir_t * 5.0)
    ir = lowpass(ir, 3000)
    wet = np.convolve(x, ir)[: len(x) + len(ir_t)]
    out = np.zeros(len(wet))
    out[: len(x)] += x
    return out + mix * wet / np.max(np.abs(wet)) * np.max(np.abs(x))


def normalize(x, peak=0.95):
    return x / np.max(np.abs(x)) * peak


def sniper_shot():
    tt = t(0.6)
    crack = rng.normal(0, 1, len(tt)) * np.exp(-tt * 90)          # supersonic crack
    blast = lowpass(rng.normal(0, 1, len(tt)), 1800) * np.exp(-tt * 14)
    boom = np.sin(2 * np.pi * (55 + 40 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 9)
    x = 0.9 * highpass(crack, 1500) + 1.3 * blast + 1.4 * boom
    x = np.tanh(2.5 * normalize(x))                                  # a bit of saturation
    return normalize(reverb(x, 1.6, 0.5))


def click(length, freq, decay):
    tt = t(length)
    body = np.sin(2 * np.pi * freq * tt) + 0.5 * np.sin(2 * np.pi * freq * 2.7 * tt)
    return (body + 0.6 * rng.normal(0, 1, len(tt))) * np.exp(-tt * decay)


def sniper_bolt():
    out = np.zeros(int(SR * 0.55))

    def place(sound, at):
        i = int(SR * at)
        out[i:i + len(sound)] += sound[: len(out) - i]

    place(click(0.06, 1800, 120), 0.00)                               # bolt up
    place(0.5 * lowpass(rng.normal(0, 1, int(SR * 0.12)), 4000) * np.linspace(1, 0.3, int(SR * 0.12)), 0.05)
    place(1.2 * click(0.05, 2400, 140), 0.18)                         # case ejects / bolt back
    place(0.4 * lowpass(rng.normal(0, 1, int(SR * 0.1)), 4000) * np.linspace(0.3, 1, int(SR * 0.1)), 0.26)
    place(1.4 * click(0.07, 1500, 110), 0.37)                         # bolt home
    return normalize(reverb(out, 0.4, 0.15), 0.8)


def skate_pop():
    tt = t(0.35)
    knock = np.sin(2 * np.pi * 420 * tt) * np.exp(-tt * 40) + 0.6 * np.sin(2 * np.pi * 950 * tt) * np.exp(-tt * 60)
    snap = highpass(rng.normal(0, 1, len(tt)), 2000) * np.exp(-tt * 120)
    return normalize(reverb(knock + 0.5 * snap, 0.3, 0.2), 0.9)


def skate_land():
    tt = t(0.5)
    thud = np.sin(2 * np.pi * 120 * tt) * np.exp(-tt * 22)
    slap = np.sin(2 * np.pi * 330 * tt) * np.exp(-tt * 35) + lowpass(rng.normal(0, 1, len(tt)), 2500) * np.exp(-tt * 30)
    rattle = highpass(rng.normal(0, 1, len(tt)), 3000) * np.exp(-tt * 18) * 0.25
    return normalize(reverb(thud + 0.8 * slap + rattle, 0.3, 0.2), 0.9)


def skate_roll():
    # seamless 2 s loop: rumble + gritty wheel hiss, faded at both ends by a crossfade
    length = int(SR * 2.0)
    fade = int(SR * 0.2)
    raw = lowpass(rng.normal(0, 1, length + fade), 700) + 0.25 * highpass(lowpass(rng.normal(0, 1, length + fade), 6000), 2000)
    tt = np.arange(length + fade) / SR
    raw *= 1 + 0.15 * np.sin(2 * np.pi * 9 * tt)                      # wheel flutter
    loop = raw[:length].copy()
    ramp = np.linspace(0, 1, fade)
    loop[:fade] = loop[:fade] * ramp + raw[length:] * (1 - ramp)
    return normalize(loop, 0.7)


def write_ogg(samples, path):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path, "-c:a", "libvorbis", "-q:a", "5", path], check=True)
    os.remove(wav_path)


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name, fn in (("sniper_shot", sniper_shot), ("sniper_bolt", sniper_bolt), ("skate_pop", skate_pop),
                     ("skate_land", skate_land), ("skate_roll", skate_roll)):
        write_ogg(fn(), os.path.join(out, name + ".ogg"))
        print("wrote", name)

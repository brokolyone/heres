"""Soundtrack for the animated Samorost scene: a seamless 48 s loop (four 12 s animation cycles).

usage: python3 sound.py <sourcesDir> <out.wav>

Most sounds are synthesised here and timed to the CSS animations (beast breathing, bubbles,
nose drip, lantern and ladder creaks, gear ticks, the beetle's propeller, the shooting star...).
Field recordings from Wikimedia Commons are layered in when present in <sourcesDir>
(see art/samorost/animated/CREDITS.md); without them the track still builds from synthesis alone.
"""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000
LOOP = 48.0
N = int(SR * LOOP)
rng = np.random.default_rng(12)
src_dir, out = Path(sys.argv[1]), Path(sys.argv[2])

mix = np.zeros((2, N))   # dry mix
send = np.zeros((2, N))  # reverb send


# ---------------- helpers ----------------
def t_(dur):
    return np.arange(int(dur * SR)) / SR


def spectral(x, fn):
    """Filter x by multiplying its spectrum with fn(freqs)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X * fn(f), len(x))


def lowpass(x, fc, order=2):
    return spectral(x, lambda f: 1 / np.sqrt(1 + (f / fc) ** (2 * order)))


def highpass(x, fc, order=2):
    return spectral(x, lambda f: 1 / np.sqrt(1 + (fc / np.maximum(f, 1e-3)) ** (2 * order)))


def bandpass(x, fc, q=4.0):
    return spectral(x, lambda f: 1 / np.sqrt(1 + (q * (f / fc - fc / np.maximum(f, 1e-3))) ** 2))


def pan_gains(p):
    p = np.clip(p, -1, 1)
    a = (p + 1) * np.pi / 4
    return np.cos(a), np.sin(a)


def place(sig, at, pan=0.0, gain=1.0, wet=0.3):
    """Add a mono signal at time `at` (s), wrapping around the loop end so the loop stays seamless."""
    sig = np.asarray(sig) * gain
    l, r = pan_gains(pan) if np.isscalar(pan) else pan_gains(np.asarray(pan))
    st = np.stack([sig * l, sig * r])
    i0 = int(at * SR) % N
    idx = (i0 + np.arange(sig.shape[-1])) % N
    np.add.at(mix, (slice(None), idx), st * (1 - wet * 0.5))
    np.add.at(send, (slice(None), idx), st * wet)


def env(n, a, d, shape=4.0):
    """Attack (s) then exponential decay to silence over the rest of n samples."""
    tt = np.arange(n) / SR
    e = np.minimum(tt / max(a, 1e-4), 1.0)
    return e * np.exp(-shape * np.maximum(tt - a, 0) / max(d, 1e-4))


def adsr(n, a, r):
    tt = np.arange(n) / SR
    dur = n / SR
    return np.clip(np.minimum(tt / a, (dur - tt) / r), 0, 1)


def note_hz(name):
    names = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
    n, o = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[n] + 12 * (o + 1) - 69) / 12)


def load_clip(pattern, seconds=None, start=0.0):
    """Decode the first matching downloaded file to mono float at SR via ffmpeg; None if missing."""
    files = sorted(src_dir.glob(pattern)) if src_dir.exists() else []
    if not files or files[0].stat().st_size == 0:
        print(f'  (no source for {pattern}, synthesis only)')
        return None
    cmd = ['ffmpeg', '-v', 'error', '-ss', str(start)] + (['-t', str(seconds)] if seconds else []) + \
          ['-i', str(files[0]), '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-']
    data = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32).astype(float)
    return data / (np.abs(data).max() + 1e-9)


def loop_bed(x, xfade=2.0):
    """Turn a clip into a seamless LOOP-long bed (tiling it with crossfades if it is short)."""
    xf = int(xfade * SR)
    out_ = np.zeros(N + xf)
    pos = 0
    ramp = np.linspace(0, 1, xf)
    while pos < N + xf:
        seg = x.copy()
        seg[:xf] *= ramp
        seg[-xf:] *= ramp[::-1]
        end = min(pos + len(seg), len(out_))
        out_[pos:end] += seg[:end - pos]
        pos += len(seg) - xf
    bed = out_[:N].copy()
    bed[:xf] += out_[N:N + xf]  # fold the tail onto the head
    return bed


# ---------------- ambient pad (synth) ----------------
def pad():
    chords = [['D3', 'A3', 'F4', 'C5'], ['A#2', 'F3', 'D4', 'A4'], ['G2', 'D3', 'A#3', 'F4'], ['A2', 'E3', 'C#4', 'G4']]
    seg = LOOP / len(chords)
    for k, ch in enumerate(chords):
        n = int((seg + 3.0) * SR)
        tt = np.arange(n) / SR
        e = adsr(n, 2.5, 3.0)
        for j, nm in enumerate(ch):
            f = note_hz(nm)
            s = np.zeros(n)
            for det in (-0.12, 0.0, 0.11):  # slightly detuned, soft saw-ish via few harmonics
                ph = rng.uniform(0, 2 * np.pi)
                for h, amp in ((1, 1.0), (2, 0.35), (3, 0.15)):
                    s += amp * np.sin(2 * np.pi * (f * h + det) * tt + ph)
            s *= e * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * tt + j))  # slow shimmer
            s = lowpass(s, 900)
            place(s, k * seg - 1.5, pan=(-0.4 + 0.27 * j), gain=0.010, wet=0.6)


# ---------------- music box melody (synth) ----------------
def musicbox(f, dur=2.5):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    s = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * f * 2.0 * tt) * np.exp(-tt * 6)
         + 0.18 * np.sin(2 * np.pi * f * 3.01 * tt) * np.exp(-tt * 9) + 0.08 * np.sin(2 * np.pi * f * 5.43 * tt) * np.exp(-tt * 14))
    return s * env(n, 0.003, dur * 0.55, 3.0)


def melody():
    beat = 0.75  # 80 bpm, 64 beats = 48 s
    phrase = [('D5', 0), ('F5', 1), ('A5', 2), ('G5', 3.5), ('F5', 4), ('E5', 5), ('D5', 6),
              ('A4', 8), ('C5', 9), ('D5', 10), ('E5', 11.5), ('F5', 12), ('E5', 13), ('C5', 14),
              ('D5', 16), ('F5', 17), ('A5', 18), ('C6', 19.5), ('A#5', 20), ('A5', 21), ('G5', 22),
              ('F5', 24), ('E5', 25), ('C#5', 26), ('E5', 27.5), ('D5', 28)]
    for nm, b in phrase:
        for rep in (0, 32):
            if rep and b >= 28:
                continue
            f = note_hz(nm) * (1 if rep == 0 else 0.5 if b < 8 else 1)
            place(musicbox(f), (b + rep) * beat + 0.02, pan=0.15 * np.sin(b), gain=0.05, wet=0.45)
    for nm, b in [('D6', 30.5), ('A5', 62.0), ('F6', 63.0)]:
        place(musicbox(note_hz(nm), 3.0), b * beat, pan=0.3, gain=0.03, wet=0.7)


# ---------------- scene sounds (synth, synced to the animation) ----------------
def snore():
    """Beast breathes every 4 s: inhale 0-1.8 s, exhale 1.8-4 s (animation 'breathe')."""
    for k in range(12):
        t0 = k * 4.0
        n = int(1.8 * SR)
        tt = np.arange(n) / SR
        inh = bandpass(rng.standard_normal(n), 380, 2.5) * np.sin(np.pi * tt / 1.8) ** 2
        rumble = np.sin(2 * np.pi * (55 + 6 * np.sin(2 * np.pi * 23 * tt)) * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * 27 * tt))
        rumble *= np.sin(np.pi * tt / 1.8) ** 3
        place(inh * 0.6 + lowpass(rumble, 300) * 0.9, t0, pan=0.62, gain=0.11, wet=0.2)
        n2 = int(2.1 * SR)
        t2 = np.arange(n2) / SR
        exh = lowpass(rng.standard_normal(n2), 700) * np.sin(np.pi * t2 / 2.1) ** 2 * np.exp(-t2 * 0.8)
        place(exh, t0 + 1.8, pan=0.6, gain=0.08, wet=0.2)


def bubble(f0=600):
    n = int(0.09 * SR)
    tt = np.arange(n) / SR
    f = f0 * (1 + 2.5 * tt / 0.09)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.07, 3)


def bubbles_and_drip():
    for k in range(16):  # bubbles rise every 3 s and pop near the end
        t0 = k * 3.0
        for j, (dt, f0) in enumerate(((2.55, 520), (2.72, 700), (2.86, 880))):
            place(bubble(f0 * rng.uniform(0.9, 1.1)), t0 + dt, pan=0.7 + 0.05 * j, gain=0.045, wet=0.35)
    for k in range(12):  # nose drip lands every 4 s (falls 72-90 % of the cycle)
        t0 = k * 4.0 + 3.55
        n = int(0.5 * SR)
        tt = np.arange(n) / SR
        f = 1400 * np.exp(-tt * 9) + 900
        plink = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.25, 4)
        place(plink, t0, pan=0.68, gain=0.08, wet=0.6)


def creak_synth(dur=0.45, f=170):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    rate = f * (1 + 0.3 * np.sin(2 * np.pi * 3 * tt))
    clicks = (np.sin(2 * np.pi * np.cumsum(rate) / SR) > 0.97).astype(float)
    return bandpass(clicks + 0.05 * rng.standard_normal(n), 900, 2) * np.sin(np.pi * tt / dur)


def creaks(clip):
    def creak(i):
        if clip is None:
            return creak_synth(rng.uniform(0.35, 0.6), rng.uniform(140, 220))
        L = int(rng.uniform(0.35, 0.6) * SR)
        a = int(rng.uniform(0, max(1, len(clip) - L)))
        c = clip[a:a + L] * np.sin(np.linspace(0, np.pi, L))
        return highpass(c, 300)
    for k in range(24):  # lantern swings every 4 s: extremes at 0 and 2 s
        place(creak(k), k * 2.0 - 0.15, pan=0.5, gain=0.10, wet=0.3)
    for k in range(16):  # rope ladder, extremes at 0 and 3 s
        place(creak(k), k * 3.0 - 0.2, pan=0.15, gain=0.05, wet=0.5)


def tick(f):
    n = int(0.03 * SR)
    return highpass(rng.standard_normal(n), 2500) * env(n, 0.0005, 0.012, 5) + \
        np.sin(2 * np.pi * f * np.arange(n) / SR) * env(n, 0.0005, 0.02, 5) * 0.6


def machine(clasp):
    for k in range(int(LOOP / 0.375)):  # clockwork gears
        place(tick(2400 if k % 2 else 1800), k * 0.375, pan=0.32, gain=0.022, wet=0.2)
    n = int(LOOP * SR)
    tt = np.arange(n) / SR
    whoosh = bandpass(rng.standard_normal(n), 500, 1.5) * (0.4 + 0.6 * np.abs(np.sin(np.pi * tt / 0.75)))  # 2 blades / 1.5 s
    place(whoosh, 0, pan=0.35, gain=0.012, wet=0.3)
    for k in range(4):  # one clunk per cycle when the gauge needle jumps
        if clasp is not None:
            L = int(0.7 * SR)
            c = clasp[:L] * np.linspace(1, 0, L) ** 2
            place(c, k * 12 + 6.45, pan=0.3, gain=0.12, wet=0.35)
        else:
            place(lowpass(rng.standard_normal(int(0.2 * SR)), 1200) * env(int(0.2 * SR), 0.002, 0.15), k * 12 + 6.45, pan=0.3, gain=0.1)


def beetle():
    n = N
    tt = np.arange(n) / SR
    # flight path of the beetle (12 s loop): x 650 -> 698 -> 730 -> 680 -> 650
    xs = np.interp((tt % 12) / 12, [0, .25, .5, .75, 1], [650, 698, 730, 680, 650])
    pan = (xs - 800) / 800 * 1.6
    f = 150 + 8 * np.sin(2 * np.pi * tt / 3)
    buzz = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * (0.6 + 0.4 * np.sin(2 * np.pi * 8.33 * tt))
    buzz = bandpass(buzz, 600, 1.2)
    place(buzz, 0, pan=pan, gain=0.006, wet=0.15)
    # moth wings: soft flutter puffs, 2.5 per second
    flutter = lowpass(rng.standard_normal(n), 1500) * np.maximum(np.sin(2 * np.pi * 2.5 * tt), 0) ** 4
    place(flutter, 0, pan=0.12, gain=0.02, wet=0.2)


def fire():
    n = N
    crackle = np.zeros(n)
    for _ in range(int(LOOP * 9)):
        i = rng.integers(0, n - 2000)
        L = rng.integers(60, 400)
        crackle[i:i + L] += rng.standard_normal(L) * np.exp(-np.arange(L) / (L / 4)) * rng.uniform(0.2, 1)
    hum = lowpass(rng.standard_normal(n), 250) * 0.4
    place(bandpass(crackle, 2500, 0.8) + hum, 0, pan=-0.3, gain=0.05, wet=0.15)


def sparkles():
    for _ in range(40):  # firefly / bulb shimmer
        f = rng.choice([note_hz(x) for x in ('D6', 'F6', 'A6', 'C7', 'E7')])
        n = int(1.2 * SR)
        tt = np.arange(n) / SR
        s = np.sin(2 * np.pi * f * tt) * env(n, 0.01, 0.6, 4) * (0.6 + 0.4 * np.sin(2 * np.pi * 7 * tt))
        place(s, rng.uniform(0, LOOP), pan=rng.uniform(-0.8, 0.8), gain=0.012, wet=0.8)


def shooting_star():
    for k in range(4):  # crosses the sky at 71-76 % of every 12 s cycle
        n = int(1.6 * SR)
        tt = np.arange(n) / SR
        f = 3200 * np.exp(-tt * 1.2) + 700
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.05, 0.9, 3)
        s += 0.3 * highpass(rng.standard_normal(n), 5000) * env(n, 0.05, 0.4, 3)
        place(s, k * 12 + 8.52, pan=np.linspace(-0.8, -0.3, n), gain=0.03, wet=0.7)


# ---------------- field recordings ----------------
def field():
    peepers = load_clip('Spring_Peeper*', 60)
    if peepers is not None:
        bed = highpass(loop_bed(peepers), 1200)
        place(bed, 0, pan=-0.2, gain=0.022, wet=0.3)
        place(np.roll(bed, N // 3), 0, pan=0.5, gain=0.015, wet=0.4)
    wind = load_clip('Howling_wind*', 60)
    if wind is not None:
        place(lowpass(loop_bed(wind, 3.0), 1600), 0, pan=0.0, gain=0.06, wet=0.2)
    else:
        place(bandpass(rng.standard_normal(N), 400, 0.8) * (0.6 + 0.4 * np.sin(2 * np.pi * np.arange(N) / N * 3)), 0, gain=0.02)
    for k, (t0, f) in enumerate(((29.0, 330), (29.55, 300), (30.4, 330), (30.75, 295))):  # distant owl: hoo-hoo, hoo-hoooo
        n = int((0.32 if k % 2 == 0 else 0.6) * SR)
        tt = np.arange(n) / SR
        hoot = np.sin(2 * np.pi * (f * (1 - 0.05 * tt / (n / SR))) * tt) + 0.2 * np.sin(4 * np.pi * f * tt)
        hoot = hoot * np.sin(np.pi * tt / (n / SR)) ** 1.5 + 0.08 * lowpass(rng.standard_normal(n), 900)
        place(hoot, t0, pan=-0.7, gain=0.03, wet=0.85)
    clasp = load_clip('Rusty_metal_door_clasp*')
    if clasp is not None:  # start at the loudest clank
        clasp = clasp[max(0, int(np.argmax(np.abs(clasp))) - int(0.03 * SR)):]
    return load_clip('Door_handle_creaking*'), clasp


# ---------------- reverb + master ----------------
def reverb(x, decay=2.6):
    n = int(decay * SR)
    tt = np.arange(n) / SR
    out_ = np.zeros_like(x)
    for ch in range(2):
        ir = rng.standard_normal(n) * np.exp(-tt * 6.9 / decay)
        ir = lowpass(ir, 5000)
        ir /= np.sqrt((ir ** 2).sum())
        # circular convolution keeps the loop seamless
        out_[ch] = np.fft.irfft(np.fft.rfft(x[ch]) * np.fft.rfft(ir, N), N)
    return out_


print('synthesising...')
creak_clip, clasp_clip = field()
pad(); melody(); snore(); bubbles_and_drip(); creaks(creak_clip); machine(clasp_clip); beetle(); fire(); sparkles(); shooting_star()
master = mix + reverb(send) * 0.8
master = np.stack([highpass(master[0], 30), highpass(master[1], 30)])
peak = np.abs(master).max()
master = np.tanh(master / peak * 1.3) / np.tanh(1.3) * 0.89  # gentle limiting
pcm = (master.T * 32767).astype('<i2')
with wave.open(str(out), 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print(f'{out} {LOOP:.0f}s')

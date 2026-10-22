package ru.ostrovpen;

import android.content.res.AssetFileDescriptor;
import android.content.res.AssetManager;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.media.SoundPool;

import java.util.HashMap;
import java.util.Map;

/**
 * Sound effects (pre-rendered from the web version's synth) through a SoundPool, and the soundtrack:
 * the open-air mix and its muffled indoor twin play together and crossfade with the scene,
 * with the stove crackle bed heard only inside.
 */
final class Sound {
    private final SoundPool pool;
    private final Map<String, Integer> ids = new HashMap<>();
    private MediaPlayer outM, inM, crackle;
    private float vOut, vIn, vCr;
    private boolean inside, muted, started, paused;

    Sound(AssetManager am, String[] names) {
        AudioAttributes aa = new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_GAME)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build();
        pool = new SoundPool.Builder().setMaxStreams(12).setAudioAttributes(aa).build();
        for (String n : names) {
            try (AssetFileDescriptor fd = am.openFd("sfx/" + n + ".wav")) {
                ids.put(n, pool.load(fd, 1));
            } catch (Exception e) {
                // a missing effect just stays silent
            }
        }
        outM = player(am, "music_out.ogg");
        inM = player(am, "music_in.ogg");
        crackle = player(am, "crackle.ogg");
    }

    private static MediaPlayer player(AssetManager am, String name) {
        try (AssetFileDescriptor fd = am.openFd(name)) {
            MediaPlayer mp = new MediaPlayer();
            mp.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_GAME)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build());
            mp.setDataSource(fd.getFileDescriptor(), fd.getStartOffset(), fd.getLength());
            mp.setLooping(true);
            mp.setVolume(0, 0);
            mp.prepare();
            return mp;
        } catch (Exception e) {
            return null;
        }
    }

    void play(String name) {
        play(name, 1, 1);
    }

    void play(String name, float vol, float rate) {
        if (muted || paused) return;
        Integer id = ids.get(name);
        if (id != null) pool.play(id, vol, vol, 1, 0, Math.max(.5f, Math.min(2, rate)));
    }

    /** Starts the soundtrack (after the first tap, like the web version). */
    void start() {
        if (started) return;
        started = true;
        for (MediaPlayer mp : new MediaPlayer[]{outM, inM, crackle}) if (mp != null) mp.start();
    }

    void setInside(boolean in) {
        inside = in;
    }

    boolean muted() {
        return muted;
    }

    void setMuted(boolean m) {
        muted = m;
        if (m) pool.autoPause();
        else pool.autoResume();
    }

    /** Volume glides, called every tick (dt ms). */
    void tick(float dt) {
        if (!started) return;
        float k = 1 - (float) Math.exp(-dt / 400.0), km = 1 - (float) Math.exp(-dt / 1200.0);
        float mute = muted ? 0 : 1;
        vOut += ((inside ? 0 : .75f) * mute - vOut) * (vOut < .3f && !inside ? km : k);
        vIn += ((inside ? .75f : 0) * mute - vIn) * k;
        vCr += ((inside ? .22f : 0) * mute - vCr) * k;
        if (outM != null) outM.setVolume(vOut, vOut);
        if (inM != null) inM.setVolume(vIn, vIn);
        if (crackle != null) crackle.setVolume(vCr, vCr);
    }

    void pause() {
        paused = true;
        pool.autoPause();
        for (MediaPlayer mp : new MediaPlayer[]{outM, inM, crackle}) if (mp != null && started) mp.pause();
    }

    void resume() {
        paused = false;
        if (!muted) pool.autoResume();
        for (MediaPlayer mp : new MediaPlayer[]{outM, inM, crackle}) if (mp != null && started) mp.start();
    }

    void release() {
        pool.release();
        for (MediaPlayer mp : new MediaPlayer[]{outM, inM, crackle}) if (mp != null) mp.release();
        outM = inM = crackle = null;
    }
}

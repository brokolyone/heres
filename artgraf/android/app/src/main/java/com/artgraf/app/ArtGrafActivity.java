package com.artgraf.app;

import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.provider.OpenableColumns;

import org.libsdl.app.SDLActivity;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * ArtGraf on Android: the editor itself is native (SDL2 + Dear ImGui). This activity only adds
 * the system file picker and saving exports to the photo gallery.
 */
public class ArtGrafActivity extends SDLActivity {
    private static final int PICK_FILE = 4242;

    /** Called on the SDL thread's JNI side with a readable local copy of the picked file. */
    static native void nativeOnFilePicked(String path);

    @Override
    protected String[] getLibraries() {
        return new String[] {"SDL2", "main"};
    }

    /** Opens the system picker (gallery, Files, Drive...). Called from native code. */
    public static void pickFile(final boolean imagesOnly) {
        final ArtGrafActivity a = (ArtGrafActivity) mSingleton;
        if (a == null) return;
        a.runOnUiThread(() -> {
            Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            i.addCategory(Intent.CATEGORY_OPENABLE);
            i.setType(imagesOnly ? "image/*" : "*/*");
            try {
                a.startActivityForResult(i, PICK_FILE);
            } catch (Exception e) {
                nativeOnFilePicked("");
            }
        });
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != PICK_FILE) {
            super.onActivityResult(requestCode, resultCode, data);
            return;
        }
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            nativeOnFilePicked("");
            return;
        }
        Uri uri = data.getData();
        String name = displayName(uri);
        File dir = new File(getCacheDir(), "picked");
        dir.mkdirs();
        File out = new File(dir, name);
        try (InputStream in = getContentResolver().openInputStream(uri); OutputStream os = new FileOutputStream(out)) {
            copy(in, os);
            nativeOnFilePicked(out.getAbsolutePath());
        } catch (Exception e) {
            nativeOnFilePicked("");
        }
    }

    /** Copies an exported image into Pictures/ArtGraf so it shows up in the gallery. */
    public static boolean saveToGallery(String srcPath, String displayName, String mime) {
        ArtGrafActivity a = (ArtGrafActivity) mSingleton;
        if (a == null) return false;
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                ContentValues v = new ContentValues();
                v.put(MediaStore.Images.Media.DISPLAY_NAME, displayName);
                v.put(MediaStore.Images.Media.MIME_TYPE, mime);
                v.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/ArtGraf");
                Uri uri = a.getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
                if (uri == null) return false;
                try (InputStream in = new FileInputStream(srcPath); OutputStream os = a.getContentResolver().openOutputStream(uri)) {
                    copy(in, os);
                }
            } else {
                File dir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES), "ArtGraf");
                dir.mkdirs();
                File out = new File(dir, displayName);
                try (InputStream in = new FileInputStream(srcPath); OutputStream os = new FileOutputStream(out)) {
                    copy(in, os);
                }
                a.sendBroadcast(new Intent(Intent.ACTION_MEDIA_SCANNER_SCAN_FILE, Uri.fromFile(out)));
            }
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private String displayName(Uri uri) {
        String name = "picked";
        try (Cursor c = getContentResolver().query(uri, null, null, null, null)) {
            if (c != null && c.moveToFirst()) {
                int idx = c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (idx >= 0) name = c.getString(idx);
            }
        } catch (Exception ignored) {
        }
        return name.replace('/', '_');
    }

    private static void copy(InputStream in, OutputStream out) throws java.io.IOException {
        byte[] buf = new byte[1 << 16];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
    }
}

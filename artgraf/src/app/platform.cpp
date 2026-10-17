#include "platform.h"

#ifdef __ANDROID__
#include <jni.h>
#include <mutex>

#include <SDL.h>
#include <SDL_system.h>

namespace {
std::mutex gMutex;
bool gHavePicked = false;
std::string gPicked;
}  // namespace

extern "C" JNIEXPORT void JNICALL Java_com_artgraf_app_ArtGrafActivity_nativeOnFilePicked(JNIEnv* env, jclass, jstring path) {
    const char* s = env->GetStringUTFChars(path, nullptr);
    std::lock_guard<std::mutex> lock(gMutex);
    gPicked = s ? s : "";
    gHavePicked = true;
    if (s) env->ReleaseStringUTFChars(path, s);
}

namespace ag {

namespace {
jclass activityClass(JNIEnv* env) {
    jobject activity = static_cast<jobject>(SDL_AndroidGetActivity());
    jclass cls = env->GetObjectClass(activity);
    env->DeleteLocalRef(activity);
    return cls;
}
}  // namespace

bool platformIsMobile() { return true; }

bool platformPickFile(bool imagesOnly) {
    JNIEnv* env = static_cast<JNIEnv*>(SDL_AndroidGetJNIEnv());
    jclass cls = activityClass(env);
    jmethodID m = env->GetStaticMethodID(cls, "pickFile", "(Z)V");
    if (!m) return false;
    {
        std::lock_guard<std::mutex> lock(gMutex);
        gHavePicked = false;
    }
    env->CallStaticVoidMethod(cls, m, jboolean(imagesOnly));
    env->DeleteLocalRef(cls);
    return true;
}

bool platformPollPicked(std::string& path) {
    std::lock_guard<std::mutex> lock(gMutex);
    if (!gHavePicked) return false;
    gHavePicked = false;
    path = gPicked;
    return true;
}

bool platformSaveToGallery(const std::string& file, const std::string& name, const std::string& mime) {
    JNIEnv* env = static_cast<JNIEnv*>(SDL_AndroidGetJNIEnv());
    jclass cls = activityClass(env);
    jmethodID m = env->GetStaticMethodID(cls, "saveToGallery", "(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Z");
    if (!m) return false;
    jstring a = env->NewStringUTF(file.c_str()), b = env->NewStringUTF(name.c_str()), c = env->NewStringUTF(mime.c_str());
    jboolean ok = env->CallStaticBooleanMethod(cls, m, a, b, c);
    env->DeleteLocalRef(a);
    env->DeleteLocalRef(b);
    env->DeleteLocalRef(c);
    env->DeleteLocalRef(cls);
    return ok;
}

std::string platformDocumentsDir() {
    const char* p = SDL_AndroidGetExternalStoragePath();
    if (!p) p = SDL_AndroidGetInternalStoragePath();
    return p ? std::string(p) + "/" : std::string();
}

std::string platformCacheDir() {
    const char* p = SDL_AndroidGetInternalStoragePath();
    return p ? std::string(p) + "/" : std::string();
}

}  // namespace ag

#else

namespace ag {
bool platformIsMobile() { return false; }
bool platformPickFile(bool) { return false; }
bool platformPollPicked(std::string&) { return false; }
bool platformSaveToGallery(const std::string&, const std::string&, const std::string&) { return false; }
std::string platformDocumentsDir() { return {}; }
std::string platformCacheDir() { return {}; }
}  // namespace ag

#endif

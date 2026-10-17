#pragma once
// OpenGL on desktop, OpenGL ES 3 on Android. Only GL 1.1-level texture calls are used directly.
#ifdef __ANDROID__
#include <GLES3/gl3.h>
#else
#include <SDL_opengl.h>
#endif

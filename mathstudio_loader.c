#include <android/log.h>
#include <dlfcn.h>
#include <jni.h>
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

#define LOG_TAG "MathStudioLoader"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

typedef void (*set_target_sdk_fn)(int);
typedef int (*get_target_sdk_fn)(void);

static const char* const APP_STORAGE_FOLDER =
    "Android/data/com.PomegranateSoftware.MathStudio/files/MathStudio";

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void* reserved);

static void* resolve_libdl_symbol(const char* name) {
  void* symbol = dlsym(RTLD_DEFAULT, name);
  if (symbol) {
    return symbol;
  }

  void* libdl = dlopen("libdl.so", RTLD_NOW | RTLD_LOCAL);
  if (libdl) {
    symbol = dlsym(libdl, name);
  }

  return symbol;
}

static int get_linker_target_sdk(void) {
  get_target_sdk_fn get_target =
      (get_target_sdk_fn)resolve_libdl_symbol(
          "android_get_application_target_sdk_version");
  if (!get_target) {
    return -1;
  }

  return get_target();
}

static void set_linker_target_sdk(int sdk) {
  set_target_sdk_fn set_target =
      (set_target_sdk_fn)resolve_libdl_symbol(
          "android_set_application_target_sdk_version");
  if (!set_target) {
    set_target = (set_target_sdk_fn)resolve_libdl_symbol(
        "__loader_android_set_application_target_sdk_version");
  }

  int before = get_linker_target_sdk();

  if (set_target) {
    set_target(sdk);
    LOGI("requested linker target SDK %d (before=%d after=%d)", sdk, before,
         get_linker_target_sdk());
  } else {
    LOGE("could not resolve linker target SDK setter (before=%d)", before);
  }
}

static void* load_original_library(void) {
  Dl_info info;
  if (dladdr((const void*)&JNI_OnLoad, &info) == 0 || !info.dli_fname) {
    LOGE("dladdr failed while locating loader library");
    return NULL;
  }

  char path[PATH_MAX];
  if (strlen(info.dli_fname) >= sizeof(path)) {
    LOGE("loader path is too long");
    return NULL;
  }

  strcpy(path, info.dli_fname);
  char* dir = dirname(path);
  char original_path[PATH_MAX];
  int written = snprintf(original_path, sizeof(original_path), "%s/%s", dir,
                         "libpomegranate_orig.so");
  if (written <= 0 || (size_t)written >= sizeof(original_path)) {
    LOGE("original library path is too long");
    return NULL;
  }

  void* handle = dlopen(original_path, RTLD_NOW | RTLD_GLOBAL);
  if (!handle) {
    LOGE("failed to load original library: %s", dlerror());
  }
  return handle;
}

static int resolve_method(void* handle, JNINativeMethod* method,
                          const char* symbol) {
  method->fnPtr = dlsym(handle, symbol);
  if (!method->fnPtr) {
    LOGE("missing JNI symbol %s: %s", symbol, dlerror());
    return 0;
  }
  return 1;
}

static int assign_original_string(void* handle, const char* symbol,
                                  const char* value) {
  void* string_object = dlsym(handle, symbol);
  if (!string_object) {
    LOGE("missing string symbol %s: %s", symbol, dlerror());
    return 0;
  }

  void* assign = dlsym(handle, "_ZNSs6assignEPKc");
  if (!assign) {
    LOGE("missing std::string::assign symbol: %s", dlerror());
    return 0;
  }

  typedef void* (*string_assign_fn)(void*, const char*);
  ((string_assign_fn)assign)(string_object, value);
  return 1;
}

static void set_original_storage_path(void* handle) {
  if (!assign_original_string(handle, "_ZN11Pomegranate11WindowTitleE",
                              APP_STORAGE_FOLDER)) {
    return;
  }

  LOGI("set native window title/storage folder to %s", APP_STORAGE_FOLDER);
}

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void* reserved) {
  (void)reserved;

  JNIEnv* env = NULL;
  if ((*vm)->GetEnv(vm, (void**)&env, JNI_VERSION_1_6) != JNI_OK) {
    return JNI_ERR;
  }

  /* The original library has text relocations. Android allows those only when
     the linker's app target is below API 23, so lower it only for dlopen(). */
  set_linker_target_sdk(22);
  void* original = load_original_library();
  set_linker_target_sdk(24);
  if (!original) {
    return JNI_ERR;
  }
  set_original_storage_path(original);

  JNINativeMethod methods[] = {
      {"init", "(II)V", NULL},
      {"keyPress", "(I)V", NULL},
      {"kill", "()V", NULL},
      {"pause", "()V", NULL},
      {"pinch", "(I)V", NULL},
      {"reinit", "(II)V", NULL},
      {"resize", "(II)V", NULL},
      {"resume", "()V", NULL},
      {"sendCommand", "(I)Z", NULL},
      {"sendCommandString", "(ILjava/lang/String;)Z", NULL},
      {"setScreenProperty", "(IF)V", NULL},
      {"step", "()V", NULL},
      {"title", "()Ljava/lang/String;", NULL},
      {"touch", "(IIIII)V", NULL},
  };

  const char* symbols[] = {
      "Java_com_PomegranateSoftware_MathStudio_GameNative_init",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_keyPress",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_kill",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_pause",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_pinch",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_reinit",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_resize",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_resume",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_sendCommand",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_sendCommandString",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_setScreenProperty",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_step",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_title",
      "Java_com_PomegranateSoftware_MathStudio_GameNative_touch",
  };

  const int method_count = (int)(sizeof(methods) / sizeof(methods[0]));
  for (int i = 0; i < method_count; ++i) {
    if (!resolve_method(original, &methods[i], symbols[i])) {
      return JNI_ERR;
    }
  }

  jclass cls = (*env)->FindClass(env,
      "com/PomegranateSoftware/MathStudio/GameNative");
  if (!cls) {
    LOGE("failed to find GameNative class");
    return JNI_ERR;
  }

  if ((*env)->RegisterNatives(env, cls, methods, method_count) != JNI_OK) {
    LOGE("failed to register original GameNative methods");
    return JNI_ERR;
  }

  return JNI_VERSION_1_6;
}

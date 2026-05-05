#include <android/log.h>
#include <dlfcn.h>
#include <errno.h>
#include <jni.h>
#include <libgen.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define LOG_TAG "MathStudioExpressLoader"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

static const char* const DOCUMENT_STORAGE_ROOT = "/sdcard/Documents/MathStudio/";

typedef void (*set_storage_path_fn)(JNIEnv*, jclass, jstring);

static set_storage_path_fn original_set_storage_path;
static char internal_storage_root[PATH_MAX] = "/data/data/com.PomegranateApps.MathStudioExpress/files/MathStudio/";

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void* reserved);

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

static int has_suffix(const char* value, const char* suffix) {
  size_t value_len = strlen(value);
  size_t suffix_len = strlen(suffix);
  return value_len >= suffix_len &&
         strcmp(value + value_len - suffix_len, suffix) == 0;
}

static int is_document_file(const char* path) {
  return has_suffix(path, ".math") || has_suffix(path, ".scripts");
}

static const char* strip_resources_prefix(const char* path) {
  static const char* const prefix = "Resources/";
  size_t prefix_len = strlen(prefix);
  if (strncmp(path, prefix, prefix_len) == 0) {
    return path + prefix_len;
  }
  return path;
}

static int is_absolute_external_path(const char* path) {
  return strncmp(path, "/sdcard/", 8) == 0 ||
         strncmp(path, "/storage/", 9) == 0 ||
         strncmp(path, "/mnt/", 5) == 0;
}

static void join_path(char* out, size_t out_size, const char* root,
                      const char* relative) {
  if (!relative || !relative[0]) {
    snprintf(out, out_size, "%s", root);
    return;
  }
  if (is_absolute_external_path(relative)) {
    snprintf(out, out_size, "%s", relative);
    return;
  }

  while (*relative == '/') {
    relative++;
  }

  size_t root_len = strlen(root);
  const char* separator = root_len > 0 && root[root_len - 1] == '/' ? "" : "/";
  snprintf(out, out_size, "%s%s%s", root, separator, relative);
}

static const char* express_get_storage_path(const char* path) {
  static char storage_path[PATH_MAX];
  const char* safe_path = path ? path : "";
  const char* root = internal_storage_root;

  if (!safe_path[0] || is_document_file(safe_path)) {
    root = DOCUMENT_STORAGE_ROOT;
    safe_path = strip_resources_prefix(safe_path);
  }

  join_path(storage_path, sizeof(storage_path), root, safe_path);
  return storage_path;
}

static int patch_absolute_jump(void* target, void* replacement) {
  long page_size = sysconf(_SC_PAGESIZE);
  if (page_size <= 0) {
    LOGE("invalid page size");
    return 0;
  }

  uintptr_t address = (uintptr_t)target;
  uintptr_t page_start = address & ~((uintptr_t)page_size - 1);
  uintptr_t page_end = (address + 8 + (uintptr_t)page_size - 1) &
                       ~((uintptr_t)page_size - 1);
  size_t page_len = page_end - page_start;

  if (mprotect((void*)page_start, page_len,
               PROT_READ | PROT_WRITE | PROT_EXEC) != 0) {
    LOGE("mprotect RWX failed: %d", errno);
    return 0;
  }

  uint32_t patch[2];
  patch[0] = 0xe51ff004;  // ldr pc, [pc, #-4]
  patch[1] = (uint32_t)(uintptr_t)replacement;
  memcpy(target, patch, sizeof(patch));
  __builtin___clear_cache((char*)target, (char*)target + sizeof(patch));

  if (mprotect((void*)page_start, page_len, PROT_READ | PROT_EXEC) != 0) {
    LOGE("mprotect RX failed: %d", errno);
    return 0;
  }

  return 1;
}

static int patch_get_storage_path(void* handle) {
  void* target = dlsym(handle, "_ZN11Pomegranate14GetStoragePathEPKc");
  if (!target) {
    LOGE("missing Pomegranate::GetStoragePath: %s", dlerror());
    return 0;
  }

  if (!patch_absolute_jump(target, (void*)&express_get_storage_path)) {
    return 0;
  }

  LOGI("patched Pomegranate::GetStoragePath for split Express storage");
  return 1;
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

static void copy_internal_storage_root(const char* path) {
  if (!path || !path[0]) {
    return;
  }

  size_t len = strlen(path);
  if (len >= sizeof(internal_storage_root)) {
    len = sizeof(internal_storage_root) - 1;
  }
  memcpy(internal_storage_root, path, len);
  internal_storage_root[len] = '\0';
  if (len > 0 && internal_storage_root[len - 1] != '/' &&
      len + 1 < sizeof(internal_storage_root)) {
    internal_storage_root[len] = '/';
    internal_storage_root[len + 1] = '\0';
  }
}

static void shim_set_storage_path(JNIEnv* env, jclass cls, jstring path) {
  const char* chars = NULL;
  if (path) {
    chars = (*env)->GetStringUTFChars(env, path, NULL);
  }
  if (chars) {
    copy_internal_storage_root(chars);
    (*env)->ReleaseStringUTFChars(env, path, chars);
    LOGI("set internal storage root to %s", internal_storage_root);
  }

  if (original_set_storage_path) {
    original_set_storage_path(env, cls, path);
  }
}

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void* reserved) {
  (void)reserved;

  JNIEnv* env = NULL;
  if ((*vm)->GetEnv(vm, (void**)&env, JNI_VERSION_1_6) != JNI_OK) {
    return JNI_ERR;
  }

  void* original = load_original_library();
  if (!original) {
    return JNI_ERR;
  }
  if (!patch_get_storage_path(original)) {
    return JNI_ERR;
  }

  original_set_storage_path = (set_storage_path_fn)dlsym(
      original, "Java_com_PomegranateApps_GameNative_setStoragePath");
  if (!original_set_storage_path) {
    LOGE("missing original setStoragePath: %s", dlerror());
    return JNI_ERR;
  }

  JNINativeMethod methods[] = {
      {"getClipboardText", "()Ljava/lang/String;", NULL},
      {"isLandscape", "()Z", NULL},
      {"keyPress", "(I)V", NULL},
      {"kill", "()V", NULL},
      {"pinch", "(ID)V", NULL},
      {"prepare", "(II)V", NULL},
      {"resume", "()V", NULL},
      {"sendCommand", "(I)Z", NULL},
      {"sendCommandString", "(ILjava/lang/String;)Z", NULL},
      {"setClipboardText", "(Ljava/lang/String;)V", NULL},
      {"setScreenProperty", "(IF)V", NULL},
      {"setStoragePath", "(Ljava/lang/String;)V", (void*)&shim_set_storage_path},
      {"step", "()I", NULL},
      {"supportsLandscape", "()Z", NULL},
      {"supportsPortrait", "()Z", NULL},
      {"suspend", "()V", NULL},
      {"title", "()Ljava/lang/String;", NULL},
      {"touch", "(IIIII)V", NULL},
  };

  const char* symbols[] = {
      "Java_com_PomegranateApps_GameNative_getClipboardText",
      "Java_com_PomegranateApps_GameNative_isLandscape",
      "Java_com_PomegranateApps_GameNative_keyPress",
      "Java_com_PomegranateApps_GameNative_kill",
      "Java_com_PomegranateApps_GameNative_pinch",
      "Java_com_PomegranateApps_GameNative_prepare",
      "Java_com_PomegranateApps_GameNative_resume",
      "Java_com_PomegranateApps_GameNative_sendCommand",
      "Java_com_PomegranateApps_GameNative_sendCommandString",
      "Java_com_PomegranateApps_GameNative_setClipboardText",
      "Java_com_PomegranateApps_GameNative_setScreenProperty",
      NULL,
      "Java_com_PomegranateApps_GameNative_step",
      "Java_com_PomegranateApps_GameNative_supportsLandscape",
      "Java_com_PomegranateApps_GameNative_supportsPortrait",
      "Java_com_PomegranateApps_GameNative_suspend",
      "Java_com_PomegranateApps_GameNative_title",
      "Java_com_PomegranateApps_GameNative_touch",
  };

  const int method_count = (int)(sizeof(methods) / sizeof(methods[0]));
  for (int i = 0; i < method_count; ++i) {
    if (!symbols[i]) {
      continue;
    }
    if (!resolve_method(original, &methods[i], symbols[i])) {
      return JNI_ERR;
    }
  }

  jclass cls = (*env)->FindClass(env, "com/PomegranateApps/GameNative");
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

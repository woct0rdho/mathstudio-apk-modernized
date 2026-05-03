# MathStudio APK Modernized

MathStudio is the best Android math app I've used. It's a pity that it's unmaintained on Android since 2016. I've modernized the APK and now it should support Android >= 7 with armeabi-v7a. I've tested it on Android 13 and 14. It may show some incompatibility warnings, but it actually works.

## Files in this repo

- `MathStudio_5.3_APKPure.apk`: original 5.3 APK obtained from APKPure.
- `MathStudio_5.3_modern_signed.apk`: modernized 5.3 APK.
- `MathStudioExpress_6.0.5_APK4Fun.apk`: original 6.0.5 APK obtained from APK4Fun.
- `MathStudioExpress_6.0.5_modern_signed.apk`: modernized 6.0.5 APK.
- `mathstudio_loader.c`: loader shim.
- `patch_mathstudio_apk.py`: binary APK/manifest repack script.
- `patch_smali_modern_storage.py`: smali patch script for 5.3 Java-side storage changes.
- `patch_smali_express_modern_storage.py`: smali patch script for 6.0.5 Java-side storage changes.

## What was patched

1. Raised the app target SDK to 24.
2. For MathStudio 5.3, replaced the native library entry with a loader shim. Preserved the original native library as `lib/armeabi-v7a/libpomegranate_orig.so`. Packaged the loader shim as `lib/armeabi-v7a/libpomegranate.so`.
3. Patched native storage routing so the old native engine looks under the app-specific external files directory. Patched Java storage paths to use `getExternalFilesDir(null)` instead of broad `/sdcard/` storage.
4. Added high-aspect-ratio manifest support so Android does not letterbox the app on tall screens.
5. Re-packaged and signed the APK.

## Manifest patch

`patch_mathstudio_apk.py` edits the binary Android manifest directly. It does the following:
1. Adds or updates `android:targetSdkVersion` on `<uses-sdk>`.
2. Optionally adds `android:debuggable="true"` when `--debuggable` is passed.
3. Adds `android:resizeableActivity="true"` and `android:maxAspectRatio="3.0"` to the application/activity entries.
4. Adds `android.max_aspect` metadata with value `3.0` for vendor compatibility.
5. Updates the binary XML string pool and resource map so the inserted attributes are valid.

## Loader shim

The original MathStudio 5.3 `libpomegranate.so` is an armeabi-v7a library with text relocations. Android blocks text relocations for apps targeting API 23 or newer.

The modernized app targets API 24, which is supported as of Android 17. The loader shim temporarily lowers the linker target SDK to 22 when loading the original library. It then restores the linker target SDK to 24.

The shim also registers the original JNI methods with `GameNative`, so Java continues calling the original engine functions.

MathStudio Express 6.0.5 does not use this shim. Its inspected native library did not contain a `DT_TEXTREL` dynamic entry, and its Java code already calls native `GameNative.setStoragePath(...)`.

## Native storage patch

The native engine builds resource paths through `Pomegranate::GetStoragePath(...)`. That function prepends `/sdcard/`, uses the native window title as the folder name, and appends `/.data/` for resource files.

To make native resource reads land in app-specific external storage, the shim assigns `Pomegranate::WindowTitle` to this relative folder:
```
Android/data/com.PomegranateSoftware.MathStudio/files/MathStudio
```

The native code then resolves resource files such as:
```
/sdcard/Android/data/com.PomegranateSoftware.MathStudio/files/MathStudio/.data/verdana18.font
```

## Java storage patch

The MathStudio 5.3 Java code originally used `/sdcard/` and `GameNative.title()` to build paths. After the native title was repurposed for storage routing, those Java title calls had to be separated from user-facing names. The 5.3 smali patch does the following:
1. Adds `GameActivity.getStorageRoot()`.
2. Implements it with `getExternalFilesDir(null).getAbsolutePath() + "/"`.
3. Changes resource paths to use `getStorageRoot()`.
4. Uses literal `MathStudio` for the visible app folder/title where Java needs the real display name.

The MathStudio Express 6.0.5 Java code already has native `setStoragePath(...)`, so it does not need the native-title shim trick. The 6.0.5 smali patch does the following:
1. Adds `GameActivity.getStorageRoot()`.
2. Implements it with `getExternalFilesDir(null).getAbsolutePath()`.
3. Changes startup resource copying and `GameNative.setStoragePath(...)` to use the app-specific external files directory.
4. Changes screenshots from `/sdcard/<title>/Screenshots` to the app-specific external files directory.

## Aspect ratio patch

Before patching, there was a black area between the app UI and the Android navigation buttons. That is Android high-aspect-ratio compatibility letterboxing: the original app did not declare that it supports tall phone screens, so the system limited the app to a shorter viewport and filled the remaining area black. The patch fixes this in the manifest by declaring high-aspect support:
```xml
android:resizeableActivity="true"
android:maxAspectRatio="3.0"
<meta-data android:name="android.max_aspect" android:value="3.0" />
```

The default `3.0` ratio is intentionally higher than current tall phones, including 20:9 and similar displays. You can override it with `--max-aspect-ratio <ratio>` when running `patch_mathstudio_apk.py`.

## Build steps

The commands below assume the required Android SDK build tools, Android NDK compiler, `baksmali.jar`, `smali.jar`, and a signing keystore are available.

### MathStudio 5.3

1. Disassemble the original DEX:
   ```sh
   java -jar baksmali.jar disassemble MathStudio_5.3_APKPure.apk -o smali_modern_storage
   ```
2. Apply the smali storage patch:
   ```sh
   python patch_smali_modern_storage.py smali_modern_storage
   ```
3. Reassemble the patched DEX:
   ```sh
   java -jar smali.jar assemble smali_modern_storage -o classes_modern_storage_api.dex
   ```
4. Build the native loader shim with Android NDK clang:
   ```sh
   clang --target=armv7a-linux-androideabi24 -shared -fPIC -O2 \
     -o libpomegranate_shim_target24_storage.so \
     mathstudio_loader.c \
     -llog -ldl
   ```
5. Build an unsigned APK:
   ```sh
   python patch_mathstudio_apk.py \
     --apk MathStudio_5.3_APKPure.apk \
     --shim libpomegranate_shim_target24_storage.so \
     --classes-dex classes_modern_storage_api.dex \
     --out MathStudio_5.3_modern_unsigned.apk
   ```
6. Align the APK:
   ```sh
   zipalign -p -f 4 \
     MathStudio_5.3_modern_unsigned.apk \
     MathStudio_5.3_modern_aligned.apk
   ```
7. Sign the APK:
   ```sh
   apksigner sign \
     --ks <keystore> \
     --ks-key-alias <alias> \
     --out MathStudio_5.3_modern_signed.apk \
     MathStudio_5.3_modern_aligned.apk
   ```
8. Verify the signature:
   ```sh
   apksigner verify --verbose MathStudio_5.3_modern_signed.apk
   ```

### MathStudio Express 6.0.5

1. Disassemble the original DEX:
   ```sh
   java -jar baksmali.jar disassemble MathStudioExpress_6.0.5_APK4Fun.apk -o smali_express_modern_storage
   ```
2. Apply the smali storage patch:
   ```sh
   python patch_smali_express_modern_storage.py smali_express_modern_storage
   ```
3. Reassemble the patched DEX:
   ```sh
   java -jar smali.jar assemble smali_express_modern_storage -o classes_express_modern_storage.dex
   ```
4. Build an unsigned APK:
   ```sh
   python patch_mathstudio_apk.py \
     --apk MathStudioExpress_6.0.5_APK4Fun.apk \
     --classes-dex classes_express_modern_storage.dex \
     --out MathStudioExpress_6.0.5_modern_unsigned.apk
   ```
5. Align the APK:
   ```sh
   zipalign -p -f 4 \
     MathStudioExpress_6.0.5_modern_unsigned.apk \
     MathStudioExpress_6.0.5_modern_aligned.apk
   ```
6. Sign the APK:
   ```sh
   apksigner sign \
     --ks <keystore> \
     --ks-key-alias <alias> \
     --out MathStudioExpress_6.0.5_modern_signed.apk \
     MathStudioExpress_6.0.5_modern_aligned.apk
   ```
7. Verify the signature:
   ```sh
   apksigner verify --verbose MathStudioExpress_6.0.5_modern_signed.apk
   ```

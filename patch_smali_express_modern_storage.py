#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


GAME_ACTIVITY_STORAGE_HELPERS = r'''
.method public getStorageRoot()Ljava/lang/String;
    .registers 3

    .prologue
    const/4 v1, 0x0

    invoke-virtual {p0, v1}, Lcom/PomegranateApps/GameActivity;->getExternalFilesDir(Ljava/lang/String;)Ljava/io/File;

    move-result-object v0

    invoke-virtual {v0}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v0

    return-object v0
.end method

.method public getInternalStorageRoot()Ljava/lang/String;
    .registers 2

    .prologue
    invoke-virtual {p0}, Lcom/PomegranateApps/GameActivity;->getFilesDir()Ljava/io/File;

    move-result-object v0

    invoke-virtual {v0}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v0

    return-object v0
.end method

.method public getDocumentStorageRoot()Ljava/lang/String;
    .registers 3

    .prologue
    invoke-static {}, Landroid/os/Environment;->getExternalStorageDirectory()Ljava/io/File;

    move-result-object v0

    invoke-virtual {v0}, Ljava/io/File;->getPath()Ljava/lang/String;

    move-result-object v0

    new-instance v1, Ljava/lang/StringBuilder;

    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V

    invoke-virtual {v1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v2, "/Documents/MathStudio/"

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    return-object v0
.end method

.method public getResourceStoragePath(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    .registers 6
    .param p1, "resourcesPath"    # Ljava/lang/String;
    .param p2, "fileName"    # Ljava/lang/String;

    .prologue
    const-string v0, ".math"

    invoke-virtual {p2, v0}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z

    move-result v0

    if-nez v0, :cond_documents

    const-string v0, ".scripts"

    invoke-virtual {p2, v0}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z

    move-result v0

    if-eqz v0, :cond_internal

    :cond_documents
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    invoke-virtual {p0}, Lcom/PomegranateApps/GameActivity;->getDocumentStorageRoot()Ljava/lang/String;

    move-result-object v1

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0, p2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    return-object v0

    :cond_internal
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0, p2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    return-object v0
.end method

.method public requestStoragePermissionIfNeeded()Z
    .registers 4

    .prologue
    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I

    const/16 v1, 0x17

    if-lt v0, v1, :cond_granted

    const-string v0, "android.permission.WRITE_EXTERNAL_STORAGE"

    invoke-virtual {p0, v0}, Lcom/PomegranateApps/GameActivity;->checkSelfPermission(Ljava/lang/String;)I

    move-result v1

    if-eqz v1, :cond_granted

    const/4 v1, 0x1

    new-array v1, v1, [Ljava/lang/String;

    const/4 v2, 0x0

    aput-object v0, v1, v2

    const/4 v2, 0x1

    invoke-virtual {p0, v1, v2}, Lcom/PomegranateApps/GameActivity;->requestPermissions([Ljava/lang/String;I)V

    const/4 v0, 0x1

    return v0

    :cond_granted
    const/4 v0, 0x0

    return v0
.end method

.method public onRequestPermissionsResult(I[Ljava/lang/String;[I)V
    .registers 5
    .param p1, "requestCode"    # I
    .param p2, "permissions"    # [Ljava/lang/String;
    .param p3, "grantResults"    # [I

    .prologue
    invoke-super {p0, p1, p2, p3}, Landroid/app/Activity;->onRequestPermissionsResult(I[Ljava/lang/String;[I)V

    const/4 v0, 0x1

    if-ne p1, v0, :cond_return

    array-length v0, p3

    if-lez v0, :cond_return

    const/4 v0, 0x0

    aget v0, p3, v0

    if-nez v0, :cond_return

    invoke-virtual {p0}, Lcom/PomegranateApps/GameActivity;->recreate()V

    :cond_return
    return-void
.end method
'''


def replace_once(text: str, old: str, new: str, file_name: str) -> str:
    if old not in text:
        raise ValueError(f"pattern not found in {file_name}: {old[:80]!r}")
    return text.replace(old, new, 1)


def patch_game_activity(path: Path) -> None:
    text = path.read_text()
    if "getInternalStorageRoot()Ljava/lang/String;" not in text:
        text = text.replace(".method public static hasStorage(Z)Z",
                            GAME_ACTIVITY_STORAGE_HELPERS + "\n.method public static hasStorage(Z)Z")

    text = replace_once(
        text,
        "    invoke-static {}, Landroid/os/Environment;->getExternalStorageDirectory()Ljava/io/File;\n\n"
        "    move-result-object v17\n\n"
        "    invoke-virtual/range {v17 .. v17}, Ljava/io/File;->getPath()Ljava/lang/String;\n\n"
        "    move-result-object v14",
        "    invoke-virtual/range {p0 .. p0}, Lcom/PomegranateApps/GameActivity;->getInternalStorageRoot()Ljava/lang/String;\n\n"
        "    move-result-object v14",
        path.name)
    text = replace_once(
        text,
        "    .prologue\n"
        "    .line 175\n"
        "    invoke-virtual/range {p0 .. p0}, Lcom/PomegranateApps/GameActivity;->checkStorage()V",
        "    .prologue\n"
        "    invoke-super/range {p0 .. p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V\n\n"
        "    invoke-virtual/range {p0 .. p0}, Lcom/PomegranateApps/GameActivity;->requestStoragePermissionIfNeeded()Z\n\n"
        "    move-result v17\n\n"
        "    if-eqz v17, :cond_storage_permission_ready\n\n"
        "    return-void\n\n"
        "    :cond_storage_permission_ready\n"
        "    .line 175\n"
        "    invoke-virtual/range {p0 .. p0}, Lcom/PomegranateApps/GameActivity;->checkStorage()V",
        path.name)
    text = replace_once(
        text,
        "    :cond_c0\n"
        "    invoke-super/range {p0 .. p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V\n\n"
        "    .line 207",
        "    :cond_c0\n"
        "    nop\n\n"
        "    .line 207",
        path.name)
    text = replace_once(
        text,
        "    move-object/from16 v0, p0\n\n"
        "    invoke-virtual {v0, v14}, Lcom/PomegranateApps/GameActivity;->createPath(Ljava/lang/String;)V\n\n"
        "    .line 191\n"
        "    invoke-virtual/range {p0 .. p0}, Lcom/PomegranateApps/GameActivity;->resourceFileNames()Ljava/util/ArrayList;",
        "    move-object/from16 v0, p0\n\n"
        "    invoke-virtual {v0, v14}, Lcom/PomegranateApps/GameActivity;->createPath(Ljava/lang/String;)V\n\n"
        "    invoke-virtual/range {p0 .. p0}, Lcom/PomegranateApps/GameActivity;->getDocumentStorageRoot()Ljava/lang/String;\n\n"
        "    move-result-object v17\n\n"
        "    move-object/from16 v0, p0\n\n"
        "    move-object/from16 v1, v17\n\n"
        "    invoke-virtual {v0, v1}, Lcom/PomegranateApps/GameActivity;->createPath(Ljava/lang/String;)V\n\n"
        "    .line 191\n"
        "    invoke-virtual/range {p0 .. p0}, Lcom/PomegranateApps/GameActivity;->resourceFileNames()Ljava/util/ArrayList;",
        path.name)
    text = replace_once(
        text,
        "    new-instance v17, Ljava/lang/StringBuilder;\n\n"
        "    invoke-direct/range {v17 .. v17}, Ljava/lang/StringBuilder;-><init>()V\n\n"
        "    move-object/from16 v0, v17\n\n"
        "    invoke-virtual {v0, v14}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n\n"
        "    move-result-object v17\n\n"
        "    move-object/from16 v0, v17\n\n"
        "    invoke-virtual {v0, v6}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n\n"
        "    move-result-object v17\n\n"
        "    invoke-virtual/range {v17 .. v17}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;\n\n"
        "    move-result-object v17",
        "    move-object/from16 v0, p0\n\n"
        "    move-object v1, v14\n\n"
        "    move-object v2, v6\n\n"
        "    invoke-virtual {v0, v1, v2}, Lcom/PomegranateApps/GameActivity;->getResourceStoragePath(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;\n\n"
        "    move-result-object v17",
        path.name)
    path.write_text(text)


def patch_game_renderer(path: Path) -> None:
    text = path.read_text()
    text = replace_once(
        text,
        "    const-string v3, \"/sdcard/\"\n\n"
        "    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n\n"
        "    move-result-object v2",
        "    move-object/from16 v0, p0\n\n"
        "    iget-object v3, v0, Lcom/PomegranateApps/GameRenderer;->gameActivity:Lcom/PomegranateApps/GameActivity;\n\n"
        "    invoke-virtual {v3}, Lcom/PomegranateApps/GameActivity;->getStorageRoot()Ljava/lang/String;\n\n"
        "    move-result-object v3\n\n"
        "    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n\n"
        "    move-result-object v2\n\n"
        "    const-string v3, \"/\"\n\n"
        "    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n\n"
        "    move-result-object v2",
        path.name)
    path.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("smali_dir", type=Path)
    args = parser.parse_args()
    base = args.smali_dir / "com" / "PomegranateApps"
    patch_game_activity(base / "GameActivity.smali")
    patch_game_renderer(base / "GameRenderer.smali")


if __name__ == "__main__":
    main()

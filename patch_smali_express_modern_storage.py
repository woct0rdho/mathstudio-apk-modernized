#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


GAME_ACTIVITY_STORAGE_HELPER = r'''
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
'''


def replace_once(text: str, old: str, new: str, file_name: str) -> str:
    if old not in text:
        raise ValueError(f"pattern not found in {file_name}: {old[:80]!r}")
    return text.replace(old, new, 1)


def patch_game_activity(path: Path) -> None:
    text = path.read_text()
    if "getStorageRoot()Ljava/lang/String;" not in text:
        text = text.replace(".method public static hasStorage(Z)Z",
                            GAME_ACTIVITY_STORAGE_HELPER + "\n.method public static hasStorage(Z)Z")

    text = replace_once(
        text,
        "    invoke-static {}, Landroid/os/Environment;->getExternalStorageDirectory()Ljava/io/File;\n\n"
        "    move-result-object v17\n\n"
        "    invoke-virtual/range {v17 .. v17}, Ljava/io/File;->getPath()Ljava/lang/String;\n\n"
        "    move-result-object v14",
        "    invoke-virtual/range {p0 .. p0}, Lcom/PomegranateApps/GameActivity;->getStorageRoot()Ljava/lang/String;\n\n"
        "    move-result-object v14",
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

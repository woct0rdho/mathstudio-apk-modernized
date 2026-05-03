#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


GAME_ACTIVITY_STORAGE_HELPER = r'''
.method public getStorageRoot()Ljava/lang/String;
    .registers 4

    .prologue
    const/4 v1, 0x0

    invoke-virtual {p0, v1}, Lcom/PomegranateSoftware/MathStudio/GameActivity;->getExternalFilesDir(Ljava/lang/String;)Ljava/io/File;

    move-result-object v0

    invoke-virtual {v0}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v0

    new-instance v1, Ljava/lang/StringBuilder;

    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V

    invoke-virtual {v1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v2, "/"

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

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
        text = text.replace(".method public copyFileToStorageCard(ILjava/lang/String;)Z",
                            GAME_ACTIVITY_STORAGE_HELPER + "\n.method public copyFileToStorageCard(ILjava/lang/String;)Z")

    text = replace_once(
        text,
        "    const-string v5, \"/sdcard/\"",
        "    invoke-virtual {p0}, Lcom/PomegranateSoftware/MathStudio/GameActivity;->getStorageRoot()Ljava/lang/String;\n\n    move-result-object v5",
        path.name)
    text = replace_once(
        text,
        "    invoke-static {}, Lcom/PomegranateSoftware/MathStudio/GameNative;->title()Ljava/lang/String;\n\n    move-result-object v8",
        "    const-string v8, \"MathStudio\"",
        path.name)
    text = text.replace(
        "    invoke-static {}, Lcom/PomegranateSoftware/MathStudio/GameNative;->title()Ljava/lang/String;\n\n    move-result-object v2",
        "    const-string v2, \"MathStudio\"")
    text = text.replace(
        "    invoke-static {}, Lcom/PomegranateSoftware/MathStudio/GameNative;->title()Ljava/lang/String;\n\n    move-result-object v0",
        "    const-string v0, \"MathStudio\"")
    path.write_text(text)


def patch_mathstudio_activity(path: Path) -> None:
    text = path.read_text()
    text = replace_once(
        text,
        "    const-string v2, \"/sdcard/\"",
        "    invoke-virtual {p0}, Lcom/PomegranateSoftware/MathStudio/MathStudioActivity;->getStorageRoot()Ljava/lang/String;\n\n    move-result-object v2",
        path.name)
    text = text.replace(
        "    invoke-static {}, Lcom/PomegranateSoftware/MathStudio/GameNative;->title()Ljava/lang/String;\n\n    move-result-object v4",
        "    const-string v4, \"MathStudio\"")
    text = text.replace(
        "    invoke-static {}, Lcom/PomegranateSoftware/MathStudio/GameNative;->title()Ljava/lang/String;\n\n    move-result-object v2",
        "    const-string v2, \"MathStudio\"")
    path.write_text(text)


def patch_game_renderer(path: Path) -> None:
    text = path.read_text()
    text = replace_once(
        text,
        "    const-string v5, \"/sdcard/\"\n\n    invoke-virtual {v4, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;",
        "    move-object/from16 v0, p0\n\n    iget-object v5, v0, Lcom/PomegranateSoftware/MathStudio/GameRenderer;->gameActivity:Lcom/PomegranateSoftware/MathStudio/GameActivity;\n\n    invoke-virtual {v5}, Lcom/PomegranateSoftware/MathStudio/GameActivity;->getStorageRoot()Ljava/lang/String;\n\n    move-result-object v5\n\n    invoke-virtual {v4, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;",
        path.name)
    text = text.replace(
        "    invoke-static {}, Lcom/PomegranateSoftware/MathStudio/GameNative;->title()Ljava/lang/String;\n\n    move-result-object v5",
        "    const-string v5, \"MathStudio\"")
    path.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("smali_dir", type=Path)
    args = parser.parse_args()
    base = args.smali_dir / "com" / "PomegranateSoftware" / "MathStudio"
    patch_game_activity(base / "GameActivity.smali")
    patch_mathstudio_activity(base / "MathStudioActivity.smali")
    patch_game_renderer(base / "GameRenderer.smali")


if __name__ == "__main__":
    main()

"""Texture-folder operators: find missing textures, open folder.

Ported from legacy ``light_profiles.{FindMissingTextures, OpenTexturesFolder}``.
Uses ``core.paths.TEXTURES_DIR`` instead of a computed-relative path.
"""

from __future__ import annotations

import sys

import bpy

from ..core.paths import TEXTURES_DIR


class LLS_OT_FindMissingTextures(bpy.types.Operator):
    bl_idname = "lls.find_missing_textures"
    bl_label = "Find Missing Textures"
    bl_description = "Find missing light textures"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(len(context.scene.LLStudio.profile_list))

    def execute(self, context: bpy.types.Context) -> set[str]:
        bpy.ops.file.find_missing_files(directory=str(TEXTURES_DIR))
        # Force a viewport refresh so the materials pick up the new paths.
        context.scene.frame_current = context.scene.frame_current
        return {"FINISHED"}


class LLS_OT_OpenTexturesFolder(bpy.types.Operator):
    bl_idname = "lls.open_textures_folder"
    bl_label = "Open Textures Folder"
    bl_description = "Open textures folder"

    def execute(self, context: bpy.types.Context) -> set[str]:
        # bpy.ops.wm.path_open is the cross-platform recommended path.
        path = str(TEXTURES_DIR)
        try:
            bpy.ops.wm.path_open(filepath=path)
            return {"FINISHED"}
        except RuntimeError:
            pass
        # Fallback: spawn a platform-specific shell command.
        import subprocess  # noqa: S404 - intentional, only hard-coded args

        if sys.platform == "darwin":
            subprocess.Popen(["open", path])  # noqa: S603, S607
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", path])  # noqa: S603, S607
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", path])  # noqa: S603, S607
        return {"FINISHED"}


classes: tuple[type[bpy.types.Operator], ...] = (
    LLS_OT_FindMissingTextures,
    LLS_OT_OpenTexturesFolder,
)

# LeoMoon LightStudio

## Important Notice
Download the installable add-on ZIP from the **[Releases page](https://github.com/leomoon-studios/leomoon-lightstudio/releases)**. Do not use GitHub's **Code > Download ZIP** source archive as the Blender extension package.

LeoMoon LightStudio (formerly known as Blender Light Studio) is 100% free and open-source. You can download and use it from here without any limitations.

## Development Fund
If you think this plugin speeds up your workflow, consider funding the development of it by **[purchasing it here](https://blendermarket.com/products/leomoon-lightstudio)**. This will help to fix bugs, improve user interface and add new features.

## Introduction
[![LeoMoon LightStudio 2.5.0 Demo](https://img.youtube.com/vi/XT_m2E_qsaU/sddefault.jpg)](https://www.youtube.com/watch?v=XT_m2E_qsaU)

LeoMoon LightStudio (formerly known as Blender Light Studio) is the easiest, fastest and most advanced lighting system for Blender. LeoMoon LightStudio is packed with features and the Light Node has so many options so you can customize each light exactly the way you want.

Video below shows the options that are available per light.

[![New Light Node](https://img.youtube.com/vi/bKVe2n2tGvs/sddefault.jpg)](https://www.youtube.com/watch?v=bKVe2n2tGvs)

## Features
- Add/remove lights around objects
- Add multiple light profiles
- Easily switch between light profiles with a single click
- Enable multiple profiles at once with Multi Profile Mode
- Animate profile visibility in Multi Profile Mode
- Each light has many options to customize, including texture, color, intensity, exposure, masks, desaturation, and grid controls
- LightStudio light options can be animated
- Each light can have a different light texture
- Fastest render update while lighting
- 15 Realistic HDR light textures included
- Easy 2D manipulation of lights in the LightStudio Control Panel, with an equirectangular preview that translates to positioning of that light in 3D space
- Toggle a light by double clicking on it in the LightPanel
- Isolate a light by right clicking on it in the LightPanel
- Lights can be added to different render layers
- Export lights as EXR HDRIs
- Import/export light profiles
- Cycles support for advanced mesh lights
- EEVEE support with Basic lights

## Limitations
~~LeoMoon LightStudio uses mesh lights and currently, EEVEE does not support mesh lights in real-time. Rendering is only supported in Cycles.~~

LeoMoon LightStudio now supports EEVEE if "Basic light" is used.

## Background HDR vs Manual Lighting
Why not use the other background HDR light plugins? That's because template based light plugins are predictable and limited. For product renders, you want lots of options and control, NOT templates! However you can create your own light profiles in LeoMoon LightStudio and import/export light profiles in different projects.

## Changelog
- 3.1.0 2026-07-25
    - Adds Desaturate, Mask - Grid Columns, and Mask - Grid Rows in per-light profile IO
    - Adds default schema values for the new advanced material inputs
    - Restores material inputs by socket name first, with index fallback
    - Exposes grid rows and columns as integer sidebar controls
    - Forces grid rows and columns to integers during import/export
    - Updates modal preview UBO for the new material inputs
    - Adds grid mask rendering to the LightStudio panel preview
    - Matches preview grid parity for even, odd, and mixed row/column counts
    - Fixes modal scale precision state initialization crash
    - Adds keyable profile switching in Multi Profile Mode

- 3.0.1 2026-05-09
    - Adds persistent hidden lights in profile export/import
    - Fix: preserve hidden lights when toggling isolate from the Control Panel

- 3.0.0 2026-05-02
    - Ported to Blender 5.1+ modern extension format
    - Added "Insert Key for Active Light" button under the Animation mode toggle that keys only LightStudio channels via the LightStudio Keying Set
    - Added equirectangular representation of lights in light panel as a preview
    - Added Control Panel customization options in add-on settings
    - Fixed Control Panel coordinates to match EXR export output
    - Fixed EXR export crash when viewport rendering is on
    - Fixed Reset Control Panel crash
    - Fixed help menu icons

- 2.16.3 2026-03-26
    - Added Blender 5.1 support

- 2.16.2 2025-03-28
    - Added grid lines to LightPanel canvas

- 2.16.1 2025-03-19
    - Added Blender 4.4 support

- 2.16.0 2024-11-16
    - Improved plugin UI
    - Added light visibility in camera toggle in the light list
    - Added profile constraint to an object

- 2.15.3 2024-10-16
    - Moved Setup Background to Background section
    - Added Transparent Background to Background section
    - Moved Export Lights as EXR to Import/Export section
    - Moved show/hide lights in camera to Misc section
    - LightStudio now switches to Cycles when it is created

- 2.15.2 2024-10-07
    - Added EEVEE (EEVEE Next) support for Blender 4.2.x

- 2.15.1 2024-02-26
    - Fixed all issues with Blender 4.x
    - Added backward compatibility for Blender 3.2 and later

- 2.15.0 2023-12-20
    - Added Blender 4 support
    - Added Ctrl+F hotkey to `point to add` a light
    - Made isolating light independent of visibility toggle
    - Added support for handle rotation

- 2.14.0 2023-11-10
    - Added macOS Metal support

- 2.13.0 2023-03-09
    - Added Cycles|EEVEE switch button
    - Added EXR exporting of lights to be used in other 3D programs
    - Added camera light visibility
    - Added saving the on/off state of each light
    - Fixed copied profile not being saved
    - Fixed shadow catcher not working with advanced lights in Blender 3.x

- 2.12.0 2022-11-22
    - Fixed problem with light brush not sliding in Blender 3.3
    - Replaced deprecated bgl module with gpu
    - Added ability to use Ctrl+D to duplicate a light
    - This version will only support Blender 3.2.2 or later

- 2.11.1 2022-08-09
    - Fixed LightStudio Control Panel resizing in Blender 3.2.2

- 2.11.0 2022-03-21
    - Added compatibility with Blender 3.1
    - Fixed issue with copying scene with LLS

- 2.10.0 2021-12-28
    - Added compatibility with Blender 3.0
    - Fixed error that happens when using Light Brush feature on instanced objects
    - When copying a profile in multimode, keep the same visibility value of source profile
    - When copying a light, deselect the source light and select the newly copied light in both single profile and multi profile
    - Added a button to select the handle of the profile

- 2.9.1 2021-09-15
    - Adds Switch to Cycles button
    - Moves Profiles panel before Lights panel
    - Fixes Copy Light
    - Fixes Copy Profile

- 2.9.0 2021-08-11:
    - Added Reset Control Panel button under Misc section
    - Added Multi Profile Mode
    - Bug fixes and improvements

- 2.8.2 2021-07-17:
    - Fixed Basic light not working when switching mode
    - Minor visual changes
    - Minor bugfixes

- 2.8.1 2021-07-14:
    - Minor bugfixes

- 2.8.0 2021-07-13:
    - Fixed compatibility issue with Blender 2.93+
    - Changed the way animated lights are handled
    - Added Normal and Animation mode to make keyframe editing easier

- 2.7.0 2020-11-10:
    - Added two types of lights:
        - Advanced: Supports HDR light textures and has many masking options
        - Basic: Blender's area light with limited options to support EEVEE
    - Many bugfixes and improvements

- 2.6.2 2020-10-07:
    - Added custom hotkeys to addon preferences
    - Major improvements added to Light Brush with F hotkey (3D Edit)
    - Added G hotkey to move lights in the light panel and 3D view
    - R and S hotkeys can now rotate and scale lights in the 3D view also
    - Improved undo

- 2.6.1 2020-08-21:
    - Added "Up" and "Down" buttons to sort lights in the light list
    - Added button to copy a light in the light list
    - Selecting a light in the light list will bring that light to top in the LightPanel
    - Lights in copied profiles do not have shared materials any more
    - Constrained clickable area of the control panel by 3D viewport properties area

- 2.6.0 2020-07-31:
    - Replaced Add Light and Delete Light buttons with a light list
    - Lights can be renamed in the light list
    - Lights can be toggled in the light list
    - Lights can be isolated in the light list
    - Light selection is synchronized with the LightPanel

- 2.5.2 2020-07-10:
    - Fixed light going outside of LightPanel
    - Added resizing to LighPanel
    - Minor bugfixes

- 2.5.1 2020-05-08:
    - Fixed Copy Profile function
    - Fixed Copy Profile to Scene function
    - Fixed LightStudio world node from being created again if it exists
    - Added Open Textures Folder button

- 2.5.0 2020-03-23:
    - Fixed LightStudio error when opening Bledner 2.8x
    - Fixed LightStudio error when deleting studio
    - Fixed strange behavior when clicking LightStudio Control Panel multiple times
    - Fixed the ordering of LightStudio side panel
    - Improved the light node
    - Added all the light effect previews to the LightStudio Control Panel
    - Added light preview options for each light to the LightStudio Control Panel
    - Added LightStudio Keying Set to animate lights
    - Added Background Setup button to quickly setup the background optimized for lighting
    - Added missing/changed descriptions for a few buttons
    - Added a darker green border when lights are not selected
    - Moved rotate, move, and scale text from top to bottom where the info is usually displayed
    - Moved hotkeys help text to Hotkeys section in the side panel

- 2.4.1 beta 2019-01-19:
    - Many bugfixes
    - LightStudio Control Panel is now using OpenGL

- 2.4.0 beta:
    - Ported to Blender 2.8x
    - Added the new LightStudio Control Panel

## Usage

> **Blender 5.1+ (extension format):** Always install from the [Releases page](https://github.com/leomoon-studios/leomoon-textcounter/releases). Do **not** use the green "Code → Download ZIP" button. That downloads the source, not the installable extension.

1. Download `leomoon-lightstudio-X.Y.Z_blender-A.B.C.zip` from the Releases page.
2. In Blender, open `Edit → Preferences → Get Extensions`.
3. Click the **▼ dropdown arrow** in the **top-right corner** of the panel (next to the **Repositories** selector) and choose **Install from Disk…**.
4. Select the downloaded `.zip`. The extension is enabled automatically and appears under the **Installed** section.
5. Open the N panel to see the **LightStudio** tab.

## Compatibility

Tested with Blender 5.1.1

## Development

```bash
make venv     # create .venv with ruff + pytest
make check    # ruff lint + pytest
make build    # build dist/leomoon-lightstudio-<ver>_blender-<min>.zip
make install  # build and install into the Blender user profile
make tag      # create an annotated git tag from the manifest version
```

Override the Blender binary if it isn't on `PATH`:

```bash
make build BLENDER=/path/to/blender
```

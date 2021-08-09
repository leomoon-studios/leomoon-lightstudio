# LeoMoon LightStudio
## Important Notice
LeoMoon LightStudio (formerly known as Blender Light Studio) is 100% free and open-source. You can download and use it from here without any limitations.

## Development Fund
If you think this plugin speeds up your workflow, consider funding the development of it by **[purchasing it here](https://blendermarket.com/products/leomoon-lightstudio)**. This will help to fix bugs, improve user interface and add new features.

## Introduction
[![LeoMoon LightStudio 2.5.0 Demo](https://img.youtube.com/vi/XT_m2E_qsaU/sddefault.jpg)](https://www.youtube.com/watch?v=XT_m2E_qsaU)

LeoMoon LightStudio (formerly known as Blender Light Studio) is the easiest, fastest and most advanced lighting system for Blender 2.8x. LeoMoon LightStudio is packed with features and the new Light Node has so many options so you can customize each light exactly the way you want.

Video below shows the options that are available per light.

[![New Light Node](https://img.youtube.com/vi/bKVe2n2tGvs/sddefault.jpg)](https://www.youtube.com/watch?v=bKVe2n2tGvs)

## Features
* Add/Remove lights around objects
* Add multiple light profiles
* Easily switch between light profiles with a single click
* Each light has many options to customize
* All options per light can be animated
* Each light can have a different light texture
* Fastest render update while lighting
* 15 Realistic HDR light textures included
* Easy 2D manipulation of lights in the LightStudio Control Panel which translates to positioning of that light in 3D space
* Toggle a light by double clicking on it in the LightPanel
* Isolate a light by right clicking on it in the LightPanel
* Lights can be added to different renders layers
* Import/Export light profiles

## Limitations
~~LeoMoon LightStudio uses mesh lights and currently, EEVEE does not support mesh lights in real-time. Rendering is only supported in Cycles.~~

LeoMoon LightStudio now supports EEVEE if "Basic light" is used.


## Background HDR vs Manual Lighting
Why not use the other background HDR light plugins? That's because template based light plugins are predictable and limited. For product renders, you want lots of options and control, NOT templates! However you can create your own light profiles in LeoMoon LightStudio and import/export light profiles in different projects.

## Changelog
### 2.8.2 2021-07-17:
* Fixes Basic light not working when switching mode
* Minor visual changes
* Minor bugfixes

### 2.8.1 2021-07-14:
* Minor bugfixes

### 2.8.0 2021-07-13:
* Fixed compatibility issue with Blender 2.93+
* Changed the way animated lights are handled
* Added Normal and Animation mode to make keyframe editing easier

### 2.7.0 2020-11-10:
* Added two types of lights:
    * Advanced: Supports HDR light textures and has many masking options
    * Basic: Blender's area light with limited options to support EEVEE
* Many bugfixes and improvements

### 2.6.2 2020-10-07:
* Added custom hotkeys to addon preferences
* Major improvements added to Light Brush with F hotkey (3D Edit)
* Added G hotkey to move lights in the light panel and 3D view
* R and S hotkeys can now rotate and scale lights in the 3D view also
* Improved undo

### 2.6.1 2020-08-21:
* Added "Up" and "Down" buttons to sort lights in the light list
* Added button to copy a light in the light list
* Selecting a light in the light list will bring that light to top in the LightPanel
* Lights in copied profiles do not have shared materials any more
* Constrained clickable area of the control panel by 3D viewport properties area

### 2.6.0 2020-07-31:
* Replaced Add Light and Delete Light buttons with a light list
* Lights can be renamed in the light list
* Lights can be toggled in the light list
* Lights can be isolated in the light list
* Light selection is synchronized with the LightPanel

### 2.5.2 2020-07-10:
* Fixed light going outside of LightPanel
* Added resizing to LighPanel
* Minor bugfixes

### 2.5.1 2020-05-08:
* Fixed Copy Profile function
* Fixed Copy Profile to Scene function
* Fixed LightStudio world node from being created again if it exists
* Added Open Textures Folder button

### 2.5.0 2020-03-23:
* Fixed LightStudio error when opening Bledner 2.8x
* Fixed LightStudio error when deleting studio
* Fixed strange behavior when clicking LightStudio Control Panel multiple times
* Fixed the ordering of LightStudio side panel
* Improved the light node
* Added all the light effect previews to the LightStudio Control Panel
* Added light preview options for each light to the LightStudio Control Panel
* Added LightStudio Keying Set to animate lights
* Added Background Setup button to quickly setup the background optimized for lighting
* Added missing/changed descriptions for a few buttons
* Added a darker green border when lights are not selected
* Moved rotate, move, and scale text from top to bottom where the info is usually displayed
* Moved hotkeys help text to Hotkeys section in the side panel

### 2.4.1 beta 2019-01-19:
* Many bugfixes
* LightStudio Control Panel is now using OpenGL

### 2.4.0 beta:
* Ported to Blender 2.8x
* Added the new LightStudio Control Panel

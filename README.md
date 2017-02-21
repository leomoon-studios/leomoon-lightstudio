# Light Studio plugin for Blender
## Introduction
Introducing Light Studio plugin for Blender. Based on a prototype by Maciek Ptaszynski and inspired by HDR Light Studio 5 lighting system.

[![Light Studio plugin for Blender](http://img.youtube.com/vi/I6KVYMLFR98/0.jpg)](https://www.youtube.com/watch?v=I6KVYMLFR98)

## Features
  - Add/Remove lights around objects (0,0,0)
  - Add unlimited number of lights
  - Each light has options like intensity, color, scale, distance, etc.
  - Easy 2D manipulation of light which translates to 3D positioning of light
  - Realistic HDR light textures included
  - Each light can have different light texture
  - Toggle lights
  - Isolate light
  - Lights are selectable to use render layers
  - 3D Edit operator - interactive light placement and adjustment:
	- Click on object to reposition light in one of two modes: reflection or normal [N].
	- [S] Scale light mesh
	- [G] Grab (meant to be used in rendered preview)
	- [R] Rotate
  - Import/Export of light profiles

## Funded by
  - LeoMoon Studios

## Donors
  - Damir Simovski
  - Krzysztof Czerwiński x2

## Programmers
  - Marcin Zielinski

## Prototype and Initial Scene by
  - Maciek Ptaszynski

## Donations
The speed of future development of this plugin depends on community donations. If you use this plugin, please consider donating. Any amount will help and 100% of donations will go towards development of this plugin. You can donate using "[THIS LINK](https://www.paypal.me/aminpersia)".

## Changelog
  - 2.3.5:
    - Bugfix
  - 2.3.4:
    - Bugfix for left-click selection
  - 2.3.3:
    - Bugfix (light scale and rotation not exporting, profiles not copying correctly)
    - Button to easily fix broken texture paths
  - 2.3.2:
    - Fix for left-click selection
  - 2.3.1:
    - Import/Export profiles
  - 2.3.0:
    - 3D Edit (first iteration of Light Brush)
    - Bugfixes
  - 2.2.1:
    - Added Blender 2.78 support
  - 2.1:
    - Added the ability to delete lights like other objects
    - Added more HDR lights
    - Added light previews
    - All HDR lights now have transparency
    - GUI changes
    - Bug fixes
  - 2.0.1:
    - Added Light Profiles feature
	- Added light preview for each light
  - 1.2.3:
    - Solved Linux problems
  - 1.2.2:
    - Linux paths bugfix
    - Control plane highlights when new light added
  - 1.2.1:
    - Minor bugfix
  - 1.2.0:
    - Protection from accidental deletion
    - Light objects made selectable
    - Control plane lights up when corresponding light object is selected, and vice versa
  - 1.1.1:
    - Added Light visibility toggles
    - Added Light Distance option
  - 1.1.0: 
    - Automatically switch to cycles after clicking "Prepare Light Studio"
  - 1.0.1:
    - Some fixes
  - 1.0.0:
    - Beta release

## How to install
  - 01: Download "[Blender Light Studio](https://leomoon.com/projects/plugins/blender-light-studio/)"
  - 02: Open Blender and go to File -> User Preferences... -> Addons
  - 03: Click on "Install from File..." and select "blender-light-studio.zip"
  - 04: After installation, the new plugin should show up and you can enable it
    - If it doesn't, search for "studio" and enable the plugin
  - 06: Close "User Preferences..."
  - 07: Go to the new tab called "Light Studio"
  - 08: Click on "Create Light Studio"
  - 09: Click on "Prepare Layout"
  - 10: Start adding lights by clicking "Add Light" and moving them around using the new split viewport
  - 11: Use the options for the selected light and light your scene
  - 12: Happy Blending!

## Future Ideas
  - Copy profile to scene (internal) operator
  - Add ability to export (render) the light setup as environment texture (Equirectangular Panoramic EXR)

## Compatibility
Tested with Blender 2.78a

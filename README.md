# Light Studio plugin for Blender
## Introduction
Introducing Light Studio plugin for Blender. Based on a prototype by Maciek Ptaszynski and inspired by HDR Light Studio 5 lighting system.

[![Light Studio plugin for Blender](http://img.youtube.com/vi/NWPeuJ6I5kc/0.jpg)](https://www.youtube.com/watch?v=NWPeuJ6I5kc)

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

## Donations
Future development of this project depends on community donations. All proceeds will go towards the development. You can donate using "[THIS LINK](https://www.paypal.me/leomoon)" and make sure to include which project you want to support.

## Funded by
  - LeoMoon Studios

## Donors
  - Damir Simovski
  - Krzysztof Czerwiński x2
  - Paul Kotelevets
  - Jacinto Carbajosa Fermoso x2
  - Tiago Santos

## Programmers
  - Marcin Zielinski

## Prototype and Initial Scene by
  - Maciek Ptaszynski

## Changelog
  - 2.3.9:
    - Bugfix
  - 2.3.8:
    - State of Selection Override is now stored between sessions
  - 2.3.6:
    - Added empty for each profile for easy movement
    - Added copy profile to scene
    - Added auto refresh light textures
    - Light distance is animatable now
    - Fixed left click (partially)
    - Fixed blend autopacking
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
  - 01: Download "[Blender Light Studio](https://leomoon.com/downloads/plugins/blender-light-studio/)"
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

## Known Issues
  - In case of problems with left click selection, manipulators or overlapping selection please disable Override Selection checkbox under Misc. panel
  
## Future Ideas
  - Copy profile to scene (internal) operator
  - Add ability to export (render) the light setup as environment texture (Equirectangular Panoramic EXR)

## Compatibility
Tested with Blender 2.78a

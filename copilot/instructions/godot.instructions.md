---
applyTo: "**/*.gd,**/*.tscn,**/*.tres,**/project.godot"
description: Godot install locations and engine version (conditional).
---

# Godot Rule (conditional)

Applies ONLY when working with Godot. Ignore otherwise.

Godot installs are managed by a flatpak called 'Godots'.

- GODOT_ROOT -> ~/.var/app/io.github.MakovWait.Godots/data/godot/app_userdata/Godots/versions
- Project engine = Godot 4.7 (spine-godot GDExtension .so is built for 4.7 and hard-refuses 4.6).
- Godot 4.7 = GODOT_ROOT/Godot_v4_7-stable_linux_x86_64/Godot_v4.7-stable_linux.x86_64

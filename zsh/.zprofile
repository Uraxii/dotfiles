# Let KDE Plasma provide its own Qt platform theme integration.
# Forcing qt6ct under Plasma 6 makes Qt apps read ~/.config/qt6ct
# palettes instead of the color scheme selected in Plasma System Settings.
if [ "${XDG_CURRENT_DESKTOP:-}" != "KDE" ] && [ "${XDG_SESSION_DESKTOP:-}" != "KDE" ] && [ "${DESKTOP_SESSION:-}" != "plasma" ]; then
  export QT_QPA_PLATFORMTHEME=qt6ct
fi

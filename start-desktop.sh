#!/usr/bin/env bash
set -e

echo "[*] Installing packages..."

# ==== Update =======================================================
sudo apt-get update -y
sudo apt-get upgrade -y

# ==== Install packages (NO XPRA) ==================================
sudo apt-get install -y \
  xfce4 xfce4-goodies \
  tightvncserver novnc websockify \
  dbus-x11 x11-xserver-utils \
  xfce4-terminal xfce4-panel \
  pulseaudio \
  ibus ibus-mozc \
  language-pack-ja language-pack-gnome-ja \
  fonts-ipafont fonts-ipafont-gothic fonts-ipafont-mincho \
  wget tar xz-utils bzip2

# ==== Locale =======================================================
sudo locale-gen ja_JP.UTF-8
sudo update-locale LANG=ja_JP.UTF-8

export LANG=ja_JP.UTF-8
export LC_ALL=ja_JP.UTF-8
export LANGUAGE=ja_JP:ja

# ==== Input Method (IBus) ==========================================
export GTK_IM_MODULE=ibus
export QT_IM_MODULE=ibus
export XMODIFIERS=@im=ibus

mkdir -p ~/.config/autostart
cat > ~/.config/autostart/ibus.desktop <<'EOF'
[Desktop Entry]
Type=Application
Exec=ibus-daemon -drx
X-GNOME-Autostart-enabled=true
Name=IBus
EOF

# ==== VNC Setup ====================================================
VNC_DIR="$HOME/.vnc"
mkdir -p "$VNC_DIR"

# VNC password (noVNC用)
echo "vncpass" | vncpasswd -f > "$VNC_DIR/passwd" || true
chmod 600 "$VNC_DIR/passwd"

# XFCE startup
cat > "$VNC_DIR/xstartup" <<'EOF'
#!/bin/bash
export LANG=ja_JP.UTF-8
export LC_ALL=ja_JP.UTF-8
export LANGUAGE=ja_JP:ja

export GTK_IM_MODULE=ibus
export QT_IM_MODULE=ibus
export XMODIFIERS=@im=ibus

xrdb $HOME/.Xresources
exec dbus-launch --exit-with-session startxfce4
EOF
chmod +x "$VNC_DIR/xstartup"

# ==== Cleanup old sessions ========================================
vncserver -kill :1 2>/dev/null || true
pkill Xvfb 2>/dev/null || true

# ==== Start VNC ====================================================
echo "[*] Starting VNC (:1)..."
vncserver :1 -geometry 1366x768 -depth 16

# ==== Start noVNC ==================================================
echo "[*] Starting noVNC (6080)..."
nohup websockify --web=/usr/share/novnc/ \
  6080 localhost:5901 \
  > /tmp/novnc.log 2>&1 &

# ==== Audio (system only, no forwarding) ==========================
pulseaudio --kill 2>/dev/null || true
pulseaudio --start --exit-idle-time=-1

# ==== Done =========================================================
echo "=============================================================="
echo " ✔ noVNC  : http://localhost:6080/"
echo " ✔ Desktop: XFCE4 (Japanese / IBus / Mozc)"
echo " ✔ Note   : Audio forwarding disabled (browser limitation)"
echo "=============================================================="

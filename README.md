# Raspberry Pi Playwright Login Automation

A **Raspberry Pi / Debian / Ubuntu / Armbian** automation workflow that:

* uses **Python Playwright**
* launches **system Chromium** (and **installs Chromium if missing**)
* logs in → waits → redirects → takes screenshot
* supports **kiosk** or **maximized**

> **Important Pi note:** Playwright works reliably on **64-bit OS (arm64)**. If your Pi is running **32-bit (armhf)**, Playwright is likely to fail. Use Raspberry Pi OS **64-bit** / Debian arm64 / Ubuntu arm64.

---

## 1) Folder layout

Put these two files in the same folder (e.g. `~/pw_login_pi/`):

* `run_pi_playwright_login.sh` (installer + runner)
* `login_and_redirect.py` (Playwright automation)

---

## 2) `run_pi_playwright_login.sh` (setup + run)

The bash script handles:
- Installing Python, pip, venv
- Installing Chromium if not present
- Creating a virtual environment
- Installing Playwright and dependencies
- Running the Python automation script

Make it executable:

```bash
chmod +x run_pi_playwright_login.sh
```

---

## 3) `login_and_redirect.py` (Python Playwright logic)

The Python script:
- Accepts credentials via environment variables or prompts
- Opens the login page
- Fills in credentials and submits
- Waits for login to complete
- Redirects to the target page
- Takes a screenshot
- Optionally keeps the browser open

---

## 4) Run it

### Option A (recommended): pass credentials via environment (so you don't type every boot)

```bash
export LOGIN_USER="your_username"
export LOGIN_PASS="your_password"
./run_pi_playwright_login.sh
```

### Option B: no env → it will prompt you

```bash
./run_pi_playwright_login.sh
```

### Custom settings example

```bash
URL="https://www.hyxicloud.com" \
REDIRECT_URL="https://www.hyxicloud.com/#/dataWall" \
USERNAME_PLACEHOLDER="Login Account" \
PASSWORD_SELECTOR="input[name='password']" \
LOGIN_BUTTON_TEXT="Login" \
WAIT_AFTER_LOGIN_SECONDS=5 \
FULLSCREEN_MODE=kiosk \
./run_pi_playwright_login.sh
```

---

## 5) Auto-start on boot (GUI kiosk)

To turn your Raspberry Pi into a **kiosk** that automatically logs in and displays the dashboard on boot:

### Method A: Using `.xinitrc` (Lightweight, no desktop manager)

1. **Install minimal X server:**

```bash
sudo apt-get install -y xorg xserver-xorg xinit
```

2. **Configure auto-login** (edit `/etc/systemd/system/getty@tty1.service.d/autologin.conf`):

```bash
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d/
sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf > /dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin pi --noclear %I \$TERM
EOF
```

3. **Create `~/.bash_profile`** to start X on login:

```bash
cat >> ~/.bash_profile <<'EOF'
if [[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]]; then
    startx -- -nocursor
fi
EOF
```

4. **Create `~/.xinitrc`** to launch the kiosk:

```bash
cat > ~/.xinitrc <<'EOF'
#!/bin/sh

# Disable screen blanking
xset s off
xset -dpms
xset s noblank

# Hide mouse cursor after 5 seconds of inactivity (optional)
# Requires: sudo apt-get install -y unclutter
unclutter -idle 5 &

# Set credentials (IMPORTANT: secure this file!)
export LOGIN_USER="your_username"
export LOGIN_PASS="your_password"

# Navigate to the script directory
cd ~/pw_login_pi

# Run the automation
./run_pi_playwright_login.sh

# Keep X running (if browser closes, this prevents X from exiting)
exec tail -f /dev/null
EOF

chmod +x ~/.xinitrc
```

5. **Reboot:**

```bash
sudo reboot
```

On boot, the Pi will:
- Auto-login as `pi` user
- Start X server
- Launch Chromium in kiosk mode
- Login and navigate to the dashboard

---

### Method B: Using systemd service (Works with any desktop environment)

This method creates a systemd service that runs the automation after graphical login.

1. **Create a startup script with credentials:**

```bash
mkdir -p ~/pw_login_pi
cat > ~/pw_login_pi/kiosk_startup.sh <<'EOF'
#!/bin/bash

# Wait for X server to be ready
while ! xset q &>/dev/null; do
    sleep 1
done

# Disable screen blanking
xset s off
xset -dpms
xset s noblank

# Set credentials
export LOGIN_USER="your_username"
export LOGIN_PASS="your_password"

# Environment variables for the automation
export DISPLAY=:0
export URL="https://www.hyxicloud.com"
export REDIRECT_URL="https://www.hyxicloud.com/#/dataWall"
export FULLSCREEN_MODE="kiosk"
export HEADLESS="0"

# Navigate to script directory
cd ~/pw_login_pi

# Run the automation
./run_pi_playwright_login.sh
EOF

chmod +x ~/pw_login_pi/kiosk_startup.sh
```

2. **Create systemd user service:**

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/kiosk-dashboard.service <<'EOF'
[Unit]
Description=Kiosk Dashboard Auto-login
After=graphical-session.target

[Service]
Type=simple
ExecStart=/home/pi/pw_login_pi/kiosk_startup.sh
Restart=on-failure
RestartSec=10
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
EOF
```

3. **Enable and start the service:**

```bash
systemctl --user daemon-reload
systemctl --user enable kiosk-dashboard.service
systemctl --user start kiosk-dashboard.service
```

4. **Enable lingering** (keeps user services running):

```bash
sudo loginctl enable-linger $USER
```

5. **Reboot to test:**

```bash
sudo reboot
```

---

### Method C: Using LXDE/Desktop autostart (For Raspberry Pi OS with Desktop)

1. **Create autostart entry:**

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/kiosk-dashboard.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Kiosk Dashboard
Exec=/home/pi/pw_login_pi/kiosk_startup.sh
X-GNOME-Autostart-enabled=true
EOF
```

2. **Create the startup script** (same as Method B, step 1)

3. **Disable screen blanking** in Raspberry Pi Configuration:
   - Menu → Preferences → Raspberry Pi Configuration → Display → Screen Blanking: Disable

4. **Configure auto-login:**
   - Menu → Preferences → Raspberry Pi Configuration → System → Auto Login: Enable

5. **Reboot:**

```bash
sudo reboot
```

---

## 6) Security considerations

⚠️ **Important:** The scripts above store credentials in plain text. For production:

1. **Use encrypted credentials:**

```bash
# Install keyring
pip install keyring

# Store credentials once
python3 -c "import keyring; keyring.set_password('hyxicloud', 'username', 'your_user')"
python3 -c "import keyring; keyring.set_password('hyxicloud', 'password', 'your_pass')"
```

2. **Modify `login_and_redirect.py`** to retrieve from keyring:

```python
import keyring

# Replace the credential section with:
user = keyring.get_password('hyxicloud', 'username') or input("Username: ").strip()
pw = keyring.get_password('hyxicloud', 'password') or getpass("Password: ")
```

3. **Restrict file permissions:**

```bash
chmod 600 ~/pw_login_pi/kiosk_startup.sh
chmod 600 ~/.xinitrc
```

4. **Use a dedicated kiosk user** (not the default `pi` user)

5. **Enable unattended-upgrades** for security updates:

```bash
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

---

## 7) Troubleshooting

### Chromium doesn't start or crashes

- Ensure you're on **64-bit OS**: `uname -m` should show `aarch64` (not `armv7l`)
- Check GPU memory: `sudo raspi-config` → Performance → GPU Memory → Set to at least 128MB
- Try disabling GPU acceleration: Add `--disable-gpu` to `launch_args` in `login_and_redirect.py`

### Browser stays blank or login fails

- Increase `WAIT_AFTER_LOGIN_SECONDS` (default is 5, try 10-15)
- Check selectors are correct: inspect the login page and verify `USERNAME_PLACEHOLDER`, `PASSWORD_SELECTOR`, etc.
- Run in headed mode first to see what's happening: `HEADLESS=0 ./run_pi_playwright_login.sh`

### Screen goes blank after a few minutes

```bash
# Add to startup script or .xinitrc:
xset s off
xset -dpms
xset s noblank
```

### Can't access the Pi anymore (stuck in kiosk)

- Press `Ctrl+Alt+F2` to switch to another TTY
- Login there and disable the autostart service
- Or: Boot with a keyboard attached and press `Shift` during boot → Raspberry Pi config → Disable auto-login

### Logs for debugging

Check the logs at `~/pw_login_pi/pw_py_login/logs/` for detailed execution logs.

---

## 8) Monitoring and recovery

### Add watchdog to restart on failure

Install and configure a watchdog to auto-reboot if the system hangs:

```bash
sudo apt-get install -y watchdog
sudo systemctl enable watchdog
sudo systemctl start watchdog
```

### Browser crash recovery

Add to your startup script:

```bash
# In kiosk_startup.sh, wrap the run command:
while true; do
    ./run_pi_playwright_login.sh
    echo "Browser closed, restarting in 5 seconds..."
    sleep 5
done
```

---

## 9) Customization options

All configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `URL` | `https://www.hyxicloud.com` | Initial login page |
| `REDIRECT_URL` | `https://www.hyxicloud.com/#/dataWall` | Dashboard page after login |
| `USERNAME_PLACEHOLDER` | `Login Account` | Placeholder text for username field |
| `PASSWORD_SELECTOR` | `input[name='password']` | CSS selector for password field |
| `LOGIN_BUTTON_TEXT` | `Login` | Text on the login button |
| `WAIT_AFTER_LOGIN_SECONDS` | `5` | Seconds to wait after clicking login |
| `FULLSCREEN_MODE` | `kiosk` | `kiosk` or `maximized` |
| `HEADLESS` | `0` | `1` for headless, `0` for headed |
| `CHROMIUM_PATH` | (auto-detected) | Full path to Chromium executable |
| `WORKDIR` | `$PWD/pw_py_login` | Working directory for logs/output |

---

## 10) Remote management

### VNC access (to see the kiosk remotely)

```bash
sudo apt-get install -y realvnc-vnc-server
sudo systemctl enable vncserver-x11-serviced.service
sudo systemctl start vncserver-x11-serviced.service
```

Configure VNC password: `sudo raspi-config` → Interface Options → VNC → Enable

### SSH access (always recommended to keep enabled)

```bash
sudo systemctl enable ssh
sudo systemctl start ssh
```

Now you can SSH in and manage the kiosk remotely or use VNC to see the display.

---

## Summary

You now have a complete Raspberry Pi kiosk solution that:

✅ Auto-installs dependencies  
✅ Launches Chromium in kiosk mode  
✅ Automatically logs in  
✅ Navigates to your dashboard  
✅ Can auto-start on boot  
✅ Includes security and recovery options  

Perfect for digital signage, monitoring dashboards, or any kiosk application!
# easymoney-dashboard

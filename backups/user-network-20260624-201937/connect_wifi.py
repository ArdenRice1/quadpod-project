#!/usr/bin/env python3
import sys
import time
import subprocess

def main():
    if len(sys.argv) < 2: 
        sys.exit(1)
        
    ssid = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Wait for the Flask HTTP redirect to reach the user's phone
    time.sleep(3) 
    
    # 1. Take down hotspot
    subprocess.run(["sudo", "nmcli", "connection", "down", "quadpod-hotspot"], check=False)
    time.sleep(4) # Radio cooldown to prevent zombie states
    
    try:
        # 2. Configure the new Wi-Fi connection
        subprocess.run(["sudo", "nmcli", "connection", "delete", ssid], check=False)
        subprocess.run(["sudo", "nmcli", "connection", "add", "type", "wifi", "ifname", "wlan0", "con-name", ssid, "ssid", ssid], check=True)
        
        if password:
            subprocess.run(["sudo", "nmcli", "connection", "modify", ssid, "wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password], check=True)
        
        # 3. Connect
        subprocess.run(["sudo", "nmcli", "connection", "up", ssid], check=True)
        
        # 4. Lock Persistence (Set priority & create the 'Do Not Disturb' flag)
        subprocess.run(["sudo", "nmcli", "connection", "modify", ssid, "connection.autoconnect-priority", "10"], check=False)
        subprocess.run(["sudo", "touch", "/opt/quadpod/.manual_wifi_mode"], check=True)
        
        # 5. Broadcast the new IP to the network
        subprocess.run(["sudo", "systemctl", "restart", "avahi-daemon"], check=False)
        
    except subprocess.CalledProcessError:
        # FALLBACK: Clear the flag and revert to hotspot so the device isn't stranded
        subprocess.run(["sudo", "rm", "-f", "/opt/quadpod/.manual_wifi_mode"], check=False)
        subprocess.run(["sudo", "nmcli", "connection", "up", "quadpod-hotspot"], check=False)

if __name__ == "__main__":
    main()
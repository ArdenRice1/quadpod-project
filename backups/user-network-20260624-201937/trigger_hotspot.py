    #!/usr/bin/env python3
import subprocess

# 1. Unlock the system
subprocess.run(["sudo", "rm", "-f", "/opt/quadpod/.manual_wifi_mode"], check=False)

# 2. Trigger your existing hotspot setup script
subprocess.run(['sudo', '/opt/quadpod/scripts/setup-hotspot.sh'], check=True)
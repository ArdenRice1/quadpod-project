#  CHANGELOG.md

All notable changes to the QuadPod project will be documented here.

---

## [v1.0.0] - Initial Working Release

###  Features
- Full Flask-based test workflow:
  - `/` → test info form
  - `/manual` → actuator control (UI only)
  - `/pretest` → preload simulation with conditional logic
  - `/test` → simulated force data and CSV logging
  - `/result` → test summary with CSV download
- Throwaway test logging toggle
- Bootstrap 5 UI with session-based routing
- Max force tracking and dynamic button feedback

# Neutrinos Electrónicos WRO 2026 - Terreneitor

## Table of Contents

- [Project Overview](#project-overview)
- [The Robot: Terreneitor](#the-robot-terreneitor)
- [System Architecture](#system-architecture)
- [Hardware Specifications](#hardware-specifications)
- [Software Architecture](#software-architecture)
  - [Programming Languages](#programming-languages)
  - [Python Libraries](#python-libraries)
  - [Directory Structure](#directory-structure)
- [Navigation Algorithm](#navigation-algorithm)
- [Serial Communication Protocol](#serial-communication-protocol)
- [Installation and Setup](#installation-and-setup)
- [Usage Instructions](#usage-instructions)
- [Component List](#component-list)
- [License](#license)

---

## Project Overview

**Terreneitor** is an autonomous vehicle designed for the World Robot Olympiad (WRO) 2026 Future Engineers competition. The robot implements a hybrid computing architecture combining a **Raspberry Pi 4** as the high-level perception and decision unit and an **Arduino UNO** as the real-time hardware controller.

**Current Implementation:**
- **Hybrid Architecture:** Raspberry Pi 4 for navigation logic + Arduino UNO for motor/servo control
- **Ultrasonic-Based Navigation:** HC-SR04 sensor for wall detection and corner counting
- **Simple Direction Commands:** Single-character commands (C, D, I) for steering servo control
- **Physical Start Button:** GPIO 17 button for WRO Rule 9.11 compliance
- **Systemd Auto-Start:** Automatic service execution on power-up

---

## The Robot: Terreneitor

The robot is named after the "Terreneitor" toy car that every team member owned during childhood, a shared memory that inspired the vehicle's identity.

---

## System Architecture

The robot employs a dual-processor architecture:

```
+-------------------------------------------------------------+
|                      RASPBERRY PI 4                         |
|  - Ultrasonic Distance Reading (HC-SR04 via RPi.GPIO)       |
|  - Corner Detection & Lap Counter                          |
|  - Simple Direction Commands (C/D/I)                       |
|  - Physical Start Button Monitoring (GPIO 17)              |
+------------------------------+------------------------------+
                               | USB Serial (115200 baud)
                               | Commands: C, D, I, V:vel;A:ang
                               | Telemetry: T:Z:z;A:a;U:u;
+------------------------------v------------------------------+
|                       ARDUINO UNO                           |
|  - Simple Command Parser (C/D/I + V:vel;A:ang)             |
|  - BTS7960 H-Bridge DC Motor PWM Drive                      |
|  - SG90 Steering Servo Control (0° - 180°)                  |
|  - HC-SR04 Rear Ultrasonic Distance Reader                  |
+-------------------------------------------------------------+
```

---

## Hardware Specifications

### Main Processing Units
- **SBC:** Raspberry Pi 4 Model B (4GB RAM)
- **MCU:** Arduino UNO R3

### Power Architecture
- Independent high-capacity battery pack for traction motors
- Dedicated power supply for Raspberry Pi 4 and Arduino
- Voltage regulator: XL4015 step-down buck converter
- 5V active cooling fan for Raspberry Pi 4
- Physical start button (GPIO 17 / Pin 11)

### Sensors
- **Front Distance:** HC-SR04 ultrasonic sensor (GPIO 23 Trigger, GPIO 24 Echo)
- **Rear Distance:** HC-SR04 ultrasonic sensor (connected to Arduino)
- **Ultrasonic Servo:** SG90 micro servo for panning (GPIO 18)

### Actuators
- **Motor Driver:** BTS7960 43A High-Power H-Bridge
- **Traction Motor:** High-torque DC motor
- **Steering Servo:** SG90 micro servo (0° - 180° range)
- **Ultrasonic Panning Servo:** SG90 micro servo (0° - 180° range)

---

## Software Architecture

### Programming Languages
- **Python 3:** Raspberry Pi high-level logic and navigation
- **C++:** Arduino firmware for real-time motor drive and sensor polling

### Python Libraries
- `pyserial`: Serial communication between Pi and Arduino
- `RPi.GPIO`: Direct GPIO control for ultrasonic sensor and button
- `gpiozero`: Servo control for ultrasonic panning

### Directory Structure

```
WRO2026-neutrinos-electronicos/
├── README.md                         # Main project documentation
├── LICENSE                           # Project license
├── .gitignore                        # Git exclusion rules
│
├── code/                             # Source code directory
│   ├── firmware_terreneitor/         # Arduino C++ Firmware
│   │   └── firmware_terreneitor.ino  # Motor, servo, and serial comms
│   │
│   ├── safety_sys/                   # Emergency Navigation System
│   │   ├── main.py                   # Main navigation with ultrasonic
│   │   ├── requirements.txt          # Python package dependencies
│   │   ├── scripts/                  # Execution scripts
│   │   │   └── start_robot.sh        # Service wrapper script
│   │   └── services/                 # Systemd service files
│   │       └── wro-robot.service     # Auto-start service
│   │
│   └── test_servo_pin12/             # Servo testing sketches
│       └── test_servo_pin12.ino      # Servo diagnostic test
│
├── elec/                             # Electrical schematics
├── mech/                             # 3D models and CAD files
└── photos/                           # Team and vehicle photos
```

---

## Navigation Algorithm

The navigation system in `code/safety_sys/main.py` implements a reactive corner-detection algorithm:

### Corner Detection
- **Frontal Wall Detection:** When ultrasonic distance ≤ 75 cm, a corner is detected
- **Cooldown:** 1.4 second minimum between corner detections to prevent double-counting
- **Lap Counter:** 4 corners = 1 lap, 12 corners = 3 laps (race completion)

### Steering Logic
- **Straight Cruise:** Speed 65, Servo centered (90°)
- **Corner Turn:** Speed 45, Servo turns left (110°) or right (70°) based on autodetected direction
- **Turn Duration:** Minimum 0.5s, maximum 1.6s
- **Track Clear:** When distance ≥ 110 cm, return to straight cruise

### Physical Start Button (WRO Rule 9.11)
- **GPIO 17:** Physical button for race start/stop
- **Toggle Logic:** Button press toggles between running and stopped states
- **Standby Mode:** System waits in standby until button is pressed

---

## Serial Communication Protocol

### Raspberry Pi → Arduino Commands

**Simple Direction Commands (New):**
- `C\n` → Center steering servo (90°)
- `D\n` → Turn right (0°)
- `I\n` → Turn left (180°)

**Traditional Velocity Commands (Backward Compatible):**
- `V:65;A:90\n` → Speed 65, Angle 90°
- `V:45;A:110\n` → Speed 45, Angle 110°

### Arduino → Raspberry Pi Telemetry

Format: `T:Z:<z>;A:<a>;U:<u>;`
- `Z`: Encoder speed (currently unused)
- `A`: Current servo angle
- `U`: Rear ultrasonic distance (cm)

---

## Installation and Setup

### Raspberry Pi Setup

1. **Clone repository (initial setup only):**
   ```bash
   cd /home/pi
   git clone https://github.com/flvr-soda/WRO2026-neutrinos-electronicos.git
   cd WRO2026-neutrinos-electronicos
   ```

2. **Create Python virtual environment & install dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r code/safety_sys/requirements.txt
   ```

3. **Install Arduino Firmware:**
   ```bash
   cd code/firmware_terreneitor
   arduino-cli compile --fqbn arduino:avr:uno firmware_terreneitor.ino
   arduino-cli upload -p /dev/ttyUSB0 --fqbn arduino:avr:uno firmware_terreneitor.ino
   ```

4. **Setup systemd service:**
   ```bash
   sudo cp code/services/wro-robot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable wro-robot.service
   chmod +x code/scripts/start_robot.sh
   ```

### Deploying Updates (SCP Method)

To deploy updated files from your development machine to the Raspberry Pi:

```bash
# Copy main.py
scp code/safety_sys/main.py pi@terreneitor.local:/home/pi/WRO2026-neutrinos-electronicos/code/safety_sys/

# Copy firmware
scp code/firmware_terreneitor/firmware_terreneitor.ino pi@terreneitor.local:/home/pi/WRO2026-neutrinos-electronicos/code/firmware_terreneitor/

# Then on Raspberry Pi, recompile and upload firmware:
cd ~/WRO2026-neutrinos-electronicos/code/firmware_terreneitor
arduino-cli compile --fqbn arduino:avr:uno firmware_terreneitor.ino
arduino-cli upload -p /dev/ttyUSB0 --fqbn arduino:avr:uno firmware_terreneitor.ino

# Restart service
sudo systemctl restart wro-robot.service
```

---

## Usage Instructions

### Manual Execution

```bash
cd /home/pi/WRO2026-neutrinos-electronicos
source venv/bin/activate
python3 code/safety_sys/main.py
```

### Systemd Auto-Start Service

```bash
# Start service
sudo systemctl start wro-robot.service

# View logs
sudo journalctl -u wro-robot.service -f

# Stop service
sudo systemctl stop wro-robot.service
```

---

## Component List

| Category | Component | Model / Specs | Purpose |
|:---|:---|:---|:---|
| **Processing** | Single Board Computer | Raspberry Pi 4 Model B (4GB) | Navigation Logic, Decision Making |
| **Processing** | Microcontroller | Arduino UNO R3 | Motor Control, Servo Control, Telemetry |
| **Distance** | Ultrasonic Sensor | HC-SR04 (Front) | Corner Detection, Wall Ranging |
| **Distance** | Ultrasonic Sensor | HC-SR04 (Rear) | Rear Obstacle Measurement |
| **Actuator** | Motor Driver | BTS7960 43A H-Bridge | DC Traction Motor Drive |
| **Actuator** | Steering Servo | SG90 Micro Servo (0° - 180°) | Front Wheel Steering |
| **Actuator** | Panning Servo | SG90 Micro Servo (0° - 180°) | Ultrasonic Panning |
| **Regulation** | Buck Converter | XL4015 Step-Down Module | High-Current Clean Voltage Stabilization |

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

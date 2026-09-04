# Neutrinos Electrónicos WRO 2026 - Terreneitor

## Table of Contents

- [Project Overview](#project-overview)
- [Team Introduction](#team-introduction)
- [The Robot: Terreneitor](#the-robot-terreneitor)
- [System Architecture](#system-architecture)
- [Hardware Specifications](#hardware-specifications)
- [Software Architecture](#software-architecture)
  - [Programming Languages](#programming-languages)
  - [Python Libraries](#python-libraries)
  - [Diagrams](#diagrams)
  - [Flowcharts](#flowcharts)
  - [Directory Structure](#directory-structure)
- [Algorithmic Logic](#algorithmic-logic)
  - [Finite State Machine (FSM)](#finite-state-machine-fsm)
  - [Computer Vision Processing](#computer-vision-processing)
  - [LiDAR-Based Parking](#lidar-based-parking)
  - [Serial Communication Protocol](#serial-communication-protocol)
- [Module Descriptions](#module-descriptions)
- [Emergency Navigation System](#emergency-navigation-system)
- [Installation and Setup](#installation-and-setup)
- [Configuration](#configuration)
- [Usage Instructions](#usage-instructions)
- [Component List](#component-list)
- [Robot Images](#robot-images)
- [Practice Videos](#practice-videos)
- [WRO 2026 Compliance](#wro-2026-compliance)
- [Development Milestones](#development-milestones)

## Project Overview

Terreneitor is an autonomous robot designed for the World Robot Olympiad (WRO) 2026 competition. The robot implements a hybrid architecture combining a Raspberry Pi 4 as the high-level processing unit and an Arduino UNO as the real-time hardware controller. This design ensures both sophisticated decision-making capabilities and precise motor control with minimal latency.

**Key Design Principles:**
- **Hybrid Centralized Architecture:** Single Raspberry Pi 4 as master node with Arduino UNO as dedicated hardware controller to avoid critical latency issues
- **Isolated Control Loop:** PID-based motor control with encoder feedback running entirely on Arduino for immediate, smooth velocity control without network delays
- **Configuration-Driven Logic:** All competition logic decoupled from source code via centralized config.yaml for rapid pit modifications without recompilation
- **Modular Software Design:** Event-based Finite State Machine (FSM) on Raspberry Pi enabling independent development, testing, and debugging of each race phase

## Installation and Setup

### Raspberry Pi Setup

1. **Clone the repository:**
   ```bash
   cd /home/pi
   git clone <repository-url>
   cd WRO2026-neutrinos-electronicos/code/raspberry_pi
   ```

2. **Create virtual environment and install dependencies:**
   ```bash
   python3 -m venv env
   source env/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure hardware settings:**
   - Edit `config.yaml` to set calibration parameters
   - Adjust HSV color ranges for your lighting conditions
   - Set motor speeds and servo angles

4. **Install Arduino firmware:**
   - Open `code/arduino/firmware_terreneitor/firmware_terreneitor.ino` in Arduino IDE
   - Upload to Arduino UNO

### Systemd Auto-Start Setup

For competition use where SSH access is not available, install the systemd service:

**Main System:**
```bash
cd /home/pi/WRO2026-neutrinos-electronicos/code/raspberry_pi
chmod +x start_robot.sh
sudo cp wro-robot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wro-robot.service
sudo systemctl start wro-robot.service
```

**Emergency System:**
```bash
cd /home/pi/WRO2026-neutrinos-electronicos/code/EMERGENCIA
chmod +x start_emergency.sh
sudo cp wro-emergency.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wro-emergency.service
sudo systemctl start wro-emergency.service
```

See `code/raspberry_pi/INSTALL_SERVICE.md` for detailed instructions.

## Configuration

### Main System Configuration (`code/raspberry_pi/config.yaml`)

Key configuration sections:
- `velocidades`: Motor speed settings
- `angulos_servo`: Servo angle calibration
- `hsv_rojo/hsv_verde/hsv_magenta`: Color detection ranges
- `competicion`: Competition rules and parameters
- `lidar`: LiDAR scanning parameters
- `vehiculo`: Vehicle dimensions for maneuvering

### Emergency System Configuration (`code/EMERGENCIA/config.yaml`)

Simplified configuration for emergency navigation:
- `navegacion`: Speed and timing parameters
- `vision`: Black wall detection thresholds
- No serial port configuration (auto-detected)

## Usage Instructions

### Manual Execution (Development)

**Main System:**
```bash
cd /home/pi/WRO2026-neutrinos-electronicos/code/raspberry_pi
source env/bin/activate
python3 main.py
```

**Emergency System:**
```bash
cd /home/pi/WRO2026-neutrinos-electronicos/code/EMERGENCIA
source ../env/bin/activate
python3 main.py
```

### Using Startup Scripts

**Main System:**
```bash
cd /home/pi/WRO2026-neutrinos-electronicos/code/raspberry_pi
./start_robot.sh
```

**Emergency System:**
```bash
cd /home/pi/WRO2026-neutrinos-electronicos/code/EMERGENCIA
./start.sh
```

### Hardware Testing

Test scripts are available in `code/raspberry_pi/tests/`:
- `test_camara.py`: Camera testing with headless mode
- `test_lidar.py`: LiDAR and servo testing
- `test_ultrasonico.py`: Ultrasonic sensor testing
- `test_completo.py`: Integrated sensor testing

### Systemd Service Management

**Check service status:**
```bash
sudo systemctl status wro-robot.service
# or
sudo systemctl status wro-emergency.service
```

**View logs:**
```bash
sudo journalctl -u wro-robot.service -f
# or
sudo journalctl -u wro-emergency.service -f
```

**Stop service:**
```bash
sudo systemctl stop wro-robot.service
# or
sudo systemctl stop wro-emergency.service
```

**Switch between services:**
```bash
sudo systemctl stop wro-robot.service
sudo systemctl disable wro-robot.service
sudo systemctl enable wro-emergency.service
sudo systemctl start wro-emergency.service
```

## Project Overview

Terreneitor is an autonomous robot designed for the World Robot Olympiad (WRO) 2026 competition. The robot implements a hybrid architecture combining a Raspberry Pi 4 as the high-level processing unit and an Arduino UNO as the real-time hardware controller. This design ensures both sophisticated decision-making capabilities and precise motor control with minimal latency.

**Key Design Principles:**
- **Hybrid Centralized Architecture:** Single Raspberry Pi 4 as master node with Arduino UNO as dedicated hardware controller to avoid critical latency issues
- **Isolated Control Loop:** PID-based motor control with encoder feedback running entirely on Arduino for immediate, smooth velocity control without network delays
- **Configuration-Driven Logic:** All competition logic decoupled from source code via centralized config.yaml for rapid pit modifications without recompilation
- **Modular Software Design:** Event-based Finite State Machine (FSM) on Raspberry Pi enabling independent development, testing, and debugging of each race phase

## Team Introduction

<img src="photos/team/team-intro.jpeg" alt="Team Photo" width="500" align="center">

| Name | Role |
|------|------|
| Ismael Armada | Software |
| Sebastián Vera | Mechanics |
| Andrés Lugo | Electronics |
| Milagro Rojas | Coach |

**Ismael Armada:** I am 20 years old, in my 4th semester of my Computer Science major. I learned about WRO thanks to a mutual friend I share with our team's coach. With this competition, I simply aim to challenge myself as a programmer by diving headfirst, for the very first time, into the development of a robotics project.

**Sebastián Vera:** I am 18 years old and a Mechanical Engineering student, currently in my 3rd semester. I discovered WRO through my high school, as we were able to represent it during our senior year. I loved that experience, and it introduced me to this amazing world of robotics—how fun and challenging it really is! I hope to have the opportunity to represent both my team and my country in such an incredible competition.

**Andrés Lugo:** I am 19 years old and an Electrical Engineering student, currently taking 2nd-semester courses in Mechanical Engineering. I got to know WRO by competing alongside Sebastián for the first time in our senior year of high school. I didn't have much knowledge back then, but it was my gateway into this world.

## The Robot: Terreneitor

Every project needs an identity, and ours was born out of a shared memory. During one of our first team meetings, a conversation about remote-controlled cars revealed that every single member of our team had owned a "Terreneitor" toy car growing up. That shared memory made us want to name our robot 'Terreneitor'.

## System Architecture

The system employs a dual-processor architecture optimized for both high-level decision making and real-time hardware control:

**Raspberry Pi 4 (High-Level Processing):**
- Processes camera input using OpenCV for color detection
- Manages LiDAR sensor data for parking maneuvers
- Implements Finite State Machine for race phase management
- Executes navigation strategies and obstacle avoidance algorithms
- Handles competition rule compliance (time limits, lap counting, signal violation detection)

**Arduino UNO (Real-Time Control):**
- Receives velocity and steering commands via serial communication
- Implements PID control loop for motor speed regulation
- Reads encoder data for velocity feedback and distance measurement
- Controls motor driver (BTS7960 H-bridge) and steering servo (MG996R)
- Sends telemetry data back to Raspberry Pi

**Communication Protocol:**
- Serial USB connection at 115200 baud
- Auto-detects first available port (/dev/ttyUSB* or /dev/ttyACM*)
- Command format: `V:[velocity];A:[angle]\n`
- Telemetry format: `T:Z:[gyro_z];A:[angle];U:[ultrasonic_dist]\n`
- Asynchronous command queue with dedicated worker thread for non-blocking operation

## Hardware Specifications

### Main Components
- **SBC:** Raspberry Pi 4 Model B - 4GB RAM
- **MCU:** Arduino UNO

### Power Architecture
- Motor battery pack
- Separate batteries for Arduino and Raspberry Pi
- Voltage stabilizer: XL4015 model
- Battery charger
- Battery mounting structure
- Two switches: main power and start button
- 5V cooling fan for Raspberry Pi 4

### Sensors
- **Camera:** OV5647 with 120° field of view
- **Distance Sensors:** HC-SR04 ultrasonic sensors
- **Orientation Sensor:** MPU6050 6-DOF IMU
- **LiDAR:** TF-Luna mounted on SG90 servo
- **Speed Sensor:** 100-line quadrature encoder (phase-shifted)
  - Generates quadrature signals for velocity measurement and direction detection

### Actuators
- **Motor Driver:** BTS7960 H-bridge
- **Traction Motor:** DC motor
- **Steering Servo:** MG996R 180° servo motor

### Other Components
- Cables and USB cables
- Soldering materials
- 3D printed parts

## Software Architecture

### Programming Languages
- **Python:** Raspberry Pi high-level processing
- **C++:** Arduino real-time control

### Python Libraries
- **PyYAML:** Configuration file parsing
- **OpenCV:** Computer vision processing
- **PySerial:** Serial communication with Arduino
- **GPIOZero:** GPIO pin control for buttons and servos
- **NumPy:** Numerical operations for vision processing

### Diagrams

*System architecture and electrical diagrams will be added here.*

- **Block Diagram:** Overall system architecture showing Raspberry Pi, Arduino, and peripheral connections
- **Electrical Schematics:** Power distribution, sensor wiring, and motor driver circuits
- **Mechanical Drawings:** Chassis design, component placement, and assembly views

*Diagrams are stored in the `elec/` and `mech/` directories.*

### Flowcharts

*Process flowcharts will be added here.*

- **Main Control Loop:** Raspberry Pi main execution flow
- **FSM State Transitions:** Finite State Machine state diagram
- **Parking Algorithm:** LiDAR-based parking maneuver flow
- **Obstacle Avoidance:** Vision-based evasion logic
- **Emergency Navigation:** Fallback system flow

*Flowcharts will be added as development progresses.*

### Directory Structure

```
WRO2026-neutrinos-electronicos/
│
├── README.md                         # Main project documentation
├── .gitignore                        # Binary/temporary file exclusions
│
├── code/                             # Source code directory
│   ├── arduino/                      # C++ source code (Arduino IDE)
│   │   └── firmware_terreneitor/
│   │       ├── firmware_terreneitor.ino   # Main loop (Setup and Loop)
│   │       ├── config.h                   # Static pin assignments and interrupts
│   │       ├── motores.cpp               # H-bridge control, MG996R servo, PID speed control
│   │       ├── sensores.cpp              # Encoder, HC-SR04, MPU6050 routines
│   │       ├── comunicacion.cpp          # Serial messaging protocol parsers
│   │       ├── pid.cpp                   # PID controller with anti-windup
│   │       └── pid.h                     # PID structure and function declarations
│   │
│   ├── raspberry_pi/                  # Python source code (Main Processing)
│   │   ├── requirements.txt              # Required libraries (opencv-python, pyyaml, pyserial, gpiozero)
│   │   ├── main.py                      # Startup script and system orchestration
│   │   ├── config.yaml                  # Calibration parameters and competition variables
│   │   ├── start_robot.sh               # Systemd service wrapper for auto-start
│   │   ├── wro-robot.service            # Systemd service file for main system
│   │   ├── INSTALL_SERVICE.md            # Systemd service installation instructions
│   │   ├── src/                         # Control modules and libraries
│   │   │   ├── __init__.py
│   │   │   ├── config_loader.py         # YAML file validator and reader
│   │   │   ├── comms_arduino.py         # Serial communication interface (auto-detects port)
│   │   │   ├── vision.py                # HSV segmentation algorithms (120° Camera)
│   │   │   └── lidar.py                 # SG90 servo control and TF-Luna readings
│   │   │
│   │   ├── estados/                     # Independent FSM state classes
│   │   │   ├── __init__.py
│   │   │   ├── fsm.py                   # Native transition controller
│   │   │   ├── estado_inicio.py         # Initialization and condition checking routine
│   │   │   ├── estado_navegacion.py     # Obstacle avoidance algorithm (Red/Green)
│   │   │   ├── estado_estacionar.py     # Automatic parallel parking maneuver
│   │   │   └── estado_fin.py            # Safe vehicle shutdown at round end
│   │   │
│   │   ├── estrategias/                 # Interchangeable strategies for surprise rules
│   │   │   ├── __init__.py
│   │   │   ├── estrategia_base.py       # Abstract base class for strategies
│   │   │   └── estrategia_normal.py     # Normal navigation strategy
│   │   │
│   │   └── tests/                       # Test scripts for hardware validation
│   │       ├── test_camara.py            # Camera testing with headless mode
│   │       ├── test_lidar.py            # LiDAR and servo testing
│   │       ├── test_ultrasonico.py      # Ultrasonic sensor testing
│   │       └── test_completo.py         # Integrated sensor testing
│   │
│   └── EMERGENCIA/                     # Emergency navigation system (fallback)
│       ├── main.py                      # Emergency navigation program
│       ├── config.yaml                  # Emergency system configuration
│       ├── start.sh                     # Startup script for emergency system
│       ├── start_emergency.sh           # Systemd service wrapper
│       ├── wro-emergency.service        # Systemd service file for emergency system
│       └── README.md                    # Emergency system documentation
│
├── auxiliar/                          # Auxiliary files and documentation
├── elec/                             # Electrical schematics and diagrams
├── mech/                             # Mechanical designs and 3D models
├── photos/                           # Project photos
└── videos/                           # Project videos
```

## Algorithmic Logic

### Finite State Machine (FSM)

The robot's behavior is controlled by an event-based Finite State Machine implemented in Python on the Raspberry Pi. The FSM manages the complete race cycle through distinct states:

**State: INICIO (Start)**
- Waits for physical start button press via GPIO
- Initializes all hardware interfaces (camera, LiDAR, Arduino communication)
- Loads competition configuration from config.yaml
- Falls back to keyboard input if GPIO unavailable (degraded mode)
- Transitions to NAVEGACION upon button press

**State: NAVEGACION (Navigation)**
- Main navigation state for both Obstacle and Open challenges
- Implements lap counting using encoder telemetry
- Enforces 3-minute time limit
- Detects finish section for Open Challenge
- Detects signal violations for Obstacle Challenge
- Returns to start section after 3 laps in Open Challenge
- Uses asynchronous vision processing for obstacle detection
- Transitions to ESTACIONAR (Obstacle) or FIN (Open) based on challenge type

**State: ESTACIONAR (Parking)**
- Executes automatic parallel parking maneuver using LiDAR
- Multi-phase parking algorithm:
  1. **Scan Phase:** Sweeps LiDAR servo to detect parking gap
  2. **Approach Phase:** Moves forward and aligns with detected gap
  3. **Reverse Phase:** Executes reverse maneuver into parking space
  4. **Straighten Phase:** Adjusts final position within parking space
- Uses TF-Luna distance sensor for gap detection
- Transitions to FIN upon completion

**State: FIN (Finish)**
- Stops all motors immediately
- Centers steering servo
- Signals FSM exit
- Ensures safe shutdown of all hardware

**Anti-Windup Protection:**
- Clamps integral term when output saturates
- Prevents integral windup during prolonged error conditions
- Ensures stable control during startup and direction changes

**Encoder-Based Velocity Feedback:**
- 100-line quadrature encoder provides 400 pulses per revolution
- Interrupt-driven reading ensures accurate velocity measurement
- Velocity calculated in cm/s based on wheel circumference
- Distance accumulated for lap counting

**Control Loop Frequency:**
- PID computation at 50 Hz (every 20ms)
- Telemetry transmission at 10 Hz (every 100ms)
- Watchdog timeout stops motors if no commands received within 500ms

### Computer Vision Processing

The vision system uses OpenCV for real-time color detection and obstacle avoidance:

**HSV Color Space Segmentation:**
- Converts RGB camera frames to HSV color space
- Defines color ranges for Red, Green, and Magenta (parking zone)
- Red uses dual-range detection (0-10° and 170-180° in hue)
- Green: 40-80° hue range
- Magenta: 140-170° hue range

**Noise Filtering:**
- Morphological opening operation with 5x5 kernel
- Removes small noise and fills small holes
- Ensures robust detection under varying lighting conditions

**Contour Analysis:**
- Finds contours in masked color regions
- Selects largest contour by area
- Calculates centroid using image moments
- Filters detections by minimum area threshold (configurable)

**Asynchronous Processing:**
- Vision processing runs in background thread
- Main loop retrieves latest detection without blocking
- Enables ~20 Hz control loop while vision processes at ~10 Hz
- Prevents camera read delays from affecting motor control

**Proportional Steering:**
- Calculates steering angle based on obstacle centroid position
- Obstacles closer to frame center require sharper turns
- Formula: `angle = straight + factor * (evasion_angle - straight)`
- Factor ranges from 0 (edge) to 1 (center) for smooth steering

### LiDAR-Based Parking

The parking system uses the TF-Luna LiDAR sensor mounted on a servo for gap detection and maneuver execution:

**Servo Scanning:**
- SG90 servo sweeps LiDAR from 45° to 135°
- Step size configurable (default 15°)
- Sleep time reduced to 80ms for performance optimization
- Returns list of (angle, distance) tuples

**Gap Detection Algorithm:**
- Searches for 3 consecutive readings above threshold (80cm)
- Indicates open space suitable for parking
- Logs detected gap angle for alignment

**Parking Maneuver Phases:**

1. **Scan Phase:**
   - Stops robot for stable scanning
   - Sweeps LiDAR across angle range
   - Identifies parking gap location
   - Retries up to 5 times if no gap found

2. **Approach Phase:**
   - Moves forward slowly for 1.5 seconds
   - Turns steering to align with gap
   - Stops momentarily before reverse

3. **Reverse Phase:**
   - Turns wheels at angle for reverse entry
   - Reverses for 1.2 seconds
   - Straightens wheels and continues reverse
   - Turns opposite direction to straighten
   - Checks distance to wall with LiDAR
   - Adjusts position if too close

4. **Straighten Phase:**
   - Moves forward slightly to center
   - Stops completely
   - Marks parking as complete

**Error Handling:**
- All LiDAR operations wrapped in try-except blocks
- Returns -1.0 on read errors for graceful degradation
- Logs errors for diagnostic purposes

### Serial Communication Protocol

The communication between Raspberry Pi and Arduino uses a custom serial protocol:

**Command Format (Pi → Arduino):**
```
V:[velocity];A:[angle]\n
```
- Velocity: 0-100 (percentage of max speed)
- Angle: 40-140 (servo angle, 90 = straight)
- Example: `V:60;A:90\n` (60% speed, straight)

**Telemetry Format (Arduino → Pi):**
```
T:Z:[gyro_z];A:[angle];U:[ultrasonic_dist]\n
```
- Z: Gyroscope Z-axis angle in degrees (accumulated rotation)
- A: Current servo angle (40-140)
- U: Rear ultrasonic distance in cm
- Example: `T:Z:45;A:90;U:25\n`

**Asynchronous Command Queue:**
- Commands placed in queue (max 10 items)
- Dedicated worker thread processes queue
- Non-blocking send from main loop
- Discards oldest command if queue full (acceptable for real-time control)
- Timeout of 50ms on queue get to prevent blocking

**Telemetry Validation:**
- Range validation on all received values
- Rejects values outside expected ranges
- Prevents corrupted data from affecting control
- Logs validation failures for debugging

**Reconnection Logic:**
- Automatic reconnection attempt on serial errors
- Separate thread for reconnection to avoid blocking
- 2-second backoff between attempts
- Graceful degradation if reconnection fails

## Module Descriptions

### Arduino Firmware Modules

**firmware_terreneitor.ino**
- Main entry point for Arduino firmware
- Initializes serial communication at 115200 baud
- Sets up encoder interrupts
- Initializes motor driver and servo
- Main loop processes serial commands and runs PID control
- Sends telemetry every 100ms
- Implements watchdog timeout (500ms) for safety

**config.h**
- Defines pin assignments for all hardware
- Declares global variables shared across modules
- Defines physical constants (wheel circumference, etc.)
- Specifies PID parameters (Kp, Ki, Kd)
- Defines function prototypes for all modules

**motores.cpp**
- Controls BTS7960 H-bridge motor driver
- Controls MG996R steering servo
- Implements PID control loop
- Applies velocity and angle commands
- Constrains angles to safe range (40-140)
- Currently supports forward motion only

**sensores.cpp**
- Handles encoder interrupt service routines
- Counts encoder ticks for velocity calculation
- Calculates speed in cm/s based on wheel circumference
- Accumulates total distance traveled
- Uses atomic operations for safe interrupt reading

**comunicacion.cpp**
- Initializes serial communication
- Reads incoming commands line-by-line
- Parses command format: `V:[vel];A:[ang]\n`
- Updates velocity and angle setpoints
- Validates command format
- Discards invalid commands

**pid.cpp**
- Implements PID controller structure
- Provides initialization function
- Computes PID output from error
- Implements anti-windup clamping
- Provides reset function for integral/derivative

**pid.h**
- Declares PID structure with Kp, Ki, Kd, integral, derivative
- Declares function prototypes
- Defines constants for anti-windup

### Raspberry Pi Software Modules

**main.py**
- Entry point for Raspberry Pi software
- Loads configuration from config.yaml
- Initializes hardware interfaces (Arduino, vision, LiDAR)
- Loads navigation strategy (for surprise rules)
- Sets up FSM with all states
- Runs FSM main loop
- Handles graceful shutdown and resource cleanup

**config_loader.py**
- Reads and parses YAML configuration file
- Validates configuration ranges (speeds, angles)
- Provides accessor methods for config sections
- Returns default values if config missing
- Validates competition parameters

**comms_arduino.py**
- Manages serial connection with Arduino
- Implements asynchronous command queue
- Dedicated worker thread for command sending
- Non-blocking command sending from main loop
- Reads and parses telemetry with validation
- Implements automatic reconnection on errors
- Provides safe shutdown method

**vision.py**
- Processes camera frames for color detection
- Implements HSV color segmentation
- Filters noise with morphological operations
- Calculates contours and centroids
- Implements asynchronous processing with background thread
- Provides latest detection without blocking
- Supports Red, Green, and Magenta detection

**lidar.py**
- Interfaces with TF-Luna LiDAR sensor
- Controls SG90 servo for scanning
- Parses 9-byte TF-Luna data frames
- Validates signal strength for reliable readings
- Implements environment scanning with servo sweep
- Optimized scan time (80ms per step)
- Provides distance reading in centimeters

**fsm.py**
- Base class for FSM states
- FSM manager class for state transitions
- Handles state registration
- Runs FSM main loop
- Manages state enter/execute/exit lifecycle
- Supports graceful FSM exit

**estado_inicio.py**
- Waits for physical start button press
- Uses gpiozero.Button for GPIO control
- Falls back to keyboard input if GPIO unavailable
- Initializes all hardware on entry
- Releases button resources on exit

**estado_navegacion.py**
- Main navigation state for both challenges
- Implements lap counting with encoder
- Enforces 3-minute time limit
- Detects finish section for Open Challenge
- Detects signal violations for Obstacle Challenge
- Returns to start section after 3 laps
- Uses asynchronous vision processing
- Implements proportional steering for obstacle avoidance
- Handles both Obstacle and Open challenge logic

**estado_estacionar.py**
- Executes automatic parallel parking
- Multi-phase parking algorithm
- Uses LiDAR for gap detection
- Implements scan, approach, reverse, and straighten phases
- Comprehensive error handling for all hardware operations
- Transitions to FIN upon completion

**estado_fin.py**
- Stops all motors immediately
- Centers steering servo
- Signals FSM exit
- Ensures safe shutdown

**estrategia_base.py**
- Abstract base class for navigation strategies
- Defines interface for strategy implementation
- Enables strategy injection for surprise rules
- Requires decidir_accion() and get_nombre() methods

**estrategia_normal.py**
- Concrete implementation of normal navigation strategy
- Implements obstacle avoidance logic
- Red: evade to left (angle 130)
- Green: evade to right (angle 50)
- Magenta: straight line (parking zone)
- Proportional steering based on obstacle position

## Component List

### Electronic Components
- **Raspberry Pi 4 Model B** - 4GB RAM
- **Arduino UNO** - Microcontroller
- **BTS7960 H-Bridge Motor Driver** - Motor control
- **XL4015 Voltage Regulator** - Power stabilization
- **MPU6050 6-DOF IMU** - Gyroscope and accelerometer
- **HC-SR04 Ultrasonic Sensor** - Distance measurement
- **TF-Luna LiDAR Sensor** - Distance measurement for parking
- **OV5647 Camera Module** - Computer vision input
- **100-line Quadrature Encoder** - Velocity feedback
- **MG996R Servo Motor** - Steering control
- **DC Motor** - Traction
- **SG90 Servo** - LiDAR scanning

### Mechanical Components
- **Chassis** - 3D printed frame
- **Wheels** - Custom design
- **Battery Mount** - Power system housing
- **Switches** - Main power and start button
- **Cooling Fan** - 5V fan for Raspberry Pi
- **Cables and Connectors** - Wiring harness

### Power System
- **Motor Battery Pack** - High-capacity batteries
- **Separate Batteries** - For Arduino and Raspberry Pi
- **Battery Charger** - Charging system

*Detailed component specifications and part numbers will be added as the BOM is finalized.*

## Robot Images

*Robot images will be organized in the `photos/` directory with the following structure:*

```
photos/
├── top/          # Top view of the robot
├── front/        # Front view
├── left/         # Left side view
├── right/        # Right side view
├── back/         # Rear view
├── bottom/       # Bottom view (chassis)
└── team/         # Team photos
```

*Images will be added as the robot assembly progresses.*

## Practice Videos

*Practice run videos will be stored in the `videos/` directory.*

- **Test Runs:** Early development testing
- **Navigation Tests:** Obstacle avoidance validation
- **Parking Tests:** LiDAR parking maneuver validation
- **Competition Runs:** Full competition simulations

*Videos will be added as testing progresses.*

## WRO 2026 Compliance

The robot is designed to comply with WRO 2026 regulations for the Regular Category - Senior age group. Key compliance features:

- **Autonomous Operation:** No human intervention during the run
- **Time Limit:** 3-minute maximum run time enforced by software
- **Lap Counting:** Encoder-based lap counting for Open Challenge
- **Signal Detection:** Vision-based signal violation detection for Obstacle Challenge
- **Parking Maneuver:** Automatic parallel parking using LiDAR for Obstacle Challenge
- **Start Button:** Physical GPIO button for competition start (Rule 9.11)
- **Return to Start:** Automatic return to start section after 3 laps (Open Challenge)

## Development Milestones

1. **Electrical and Chassis Phase (Andrés and Sebastián):** Assembly of battery structure with XL4015 regulator to ensure clean and independent power supply for Raspberry Pi and Arduino. Wiring of BTS7960 H-bridge and main motor mounting.
2. **Traction Control Loop (Ismael):** Arduino programming of DC motor speed control in closed loop using encoder interrupts. The goal of this milestone is to achieve constant robot speed in cm/s regardless of battery charge state.
3. **Vision and Link Prototyping (Ismael):** Development of vision.py script on Raspberry Pi using static images of color blocks (red/green) to define optimal HSV ranges. In parallel, establish basic serial communication to send simple text frames like V:50;A:90 (Velocity: 50%, Angle: 90°) to Arduino.

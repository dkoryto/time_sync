# Application Features
This application offers the following features:

## 1. Clocks showing current time:
- Local time clock updated every second
  
- UTC time clock updated every second
  
- Black clock font for good readability

## 2. System time synchronization:

- Default NTP server: tempus1.gum.gov.pl (Polish official time server)

- Automatic synchronization via Windows Time service (on Windows only)

- Test mode to simulate synchronization process

## 3. Cross-platform compatibility:

- Full functionality on Windows

- Test mode (without synchronization) on macOS

## 4. Additional information:

- Link to GitHub repository in the lower right corner

- Author information (Dariusz Koryto, dariusz@koryto.eu) available by clicking

- MIT license information

# Compiling your application
To compile your application into an executable file, follow these steps:

For Windows:

pip install pyinstaller

pyinstaller --onefile --windowed --name ClockSync --manifest admin_manifest.xml timesync.py


For macOS:
pip install pyinstaller

pyinstaller --onefile --windowed --name ClockSync timesync.py

The finished application will be available in the dist folder.


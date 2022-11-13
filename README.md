# pyportal_station

#### CircuitPython based project for Adafruit PyPortal to use MQTT and show weather

This repo is a snapshot of all libraries, icons, and python scripts
needed to have time and weather info on a PyPortal

![PyPortal weather station](https://live.staticflickr.com/65535/52496248772_7e26e1e3ad_k.jpg)

For more info on what this is doing, look at these 2 learning guides from
Adafruit:

- [PyPortal MQTT Sensor Node](https://learn.adafruit.com/pyportal-mqtt-sensor-node-control-pad-home-assistant)
- [PyPortal Weather Station](https://learn.adafruit.com/pyportal-weather-station)

For a quick start on PyPortal, look at these awesome pages:

- [PyPortal CircuitPy Tutorial (AdaBox 011)](https://www.devdungeon.com/content/pyportal-circuitpy-tutorial-adabox-011#toc-19)
- [Primary Guide: Adafruit PyPortal](https://learn.adafruit.com/adafruit-pyportal)

Lastly, check these links for a good reference on Circuit Python

- [Adafruit CircuitPython PyPortal](https://github.com/adafruit/Adafruit_CircuitPython_PyPortal)
- [CircuitPython Libraries](https://learn.adafruit.com/circuitpython-essentials/circuitpython-libraries)

### Removing _all_ files from CIRCUITPY drive

```
# NOTE: Do not do this before backing up all files!!!
>>> import storage ; storage.erase_filesystem()
```

### Copying files from cloned repo to CIRCUITPY drive
```
# First, get to the REPL prompt so the board will not auto-restart as
# you copy files into it

# Assuming that PyPortal is mounted under /Volumes/CIRCUITPY
$  cd ${THIS_REPO_DIR}
$  [ -d /Volumes/CIRCUITPY/ ] && \
   rm -rf /Volumes/CIRCUITPY/* && \
   (tar czf - *) | ( cd /Volumes/CIRCUITPY ; tar xzvf - ) && \
   echo ok || echo not_okay
```

Example MQTT commands

```bash
PREFIX='/pyportal'
MQTT=192.168.10.10

# Subscribing to status messages

mosquitto_sub -F '@Y-@m-@dT@H:@M:@S@z : %q : %t : %p' -h $MQTT  -t "${PREFIX}/#"

# Request general info
mosquitto_pub -h $MQTT -t "${PREFIX}/ping" -r -n

# Set screen brightness
mosquitto_pub -h $MQTT -t "${PREFIX}/brightness" -m on
mosquitto_pub -h $MQTT -t "${PREFIX}/brightness" -m 0.1
mosquitto_pub -h $MQTT -t "${PREFIX}/brightness" -m off

# Neopixel control
mosquitto_pub -h $MQTT -t "${PREFIX}/neopixel" -m 0        ; # off
mosquitto_pub -h $MQTT -t "${PREFIX}/neopixel" -m 0xff     ; # blue
mosquitto_pub -h $MQTT -t "${PREFIX}/neopixel" -m 0xff00   ; # green
mosquitto_pub -h $MQTT -t "${PREFIX}/neopixel" -m 0xff0000 ; # red

# On board led blink
mosquitto_pub -h $MQTT -t "${PREFIX}/blinkrate" -m on   ; # on
mosquitto_pub -h $MQTT -t "${PREFIX}/blinkrate" -m 0    ; # off
mosquitto_pub -h $MQTT -t "${PREFIX}/blinkrate" -m 0.1  ; # 100ms
```

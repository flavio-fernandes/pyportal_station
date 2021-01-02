# pyportal_station

#### CircuitPython based project for Adafruit PyPortal to use MQTT and show weather

This repo is a snapshot of all libraries, icons, and python scripts
needed to have time and weather info on a PyPortal

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


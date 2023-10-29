# pyportal_station

#### CircuitPython based project for Adafruit PyPortal to use MQTT and show weather

This repo provides icons and python files needed to display time and weather on a PyPortal.
Circuit Python libraries can be installed via circup, as shown below.

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
$  [ -e ./code.py ] && \
   [ -d /Volumes/CIRCUITPY/ ] && \
   rm -rf /Volumes/CIRCUITPY/* && \
   (tar czf - *) | ( cd /Volumes/CIRCUITPY ; tar xzvf - ) && \
   echo ok || echo not_okay
```

### Libraries

Use [circup](https://learn.adafruit.com/keep-your-circuitpython-libraries-on-devices-up-to-date-with-circup)
to install these libraries:

```text
$ python3 -m venv .env && source ./.env/bin/activate && \
  pip install --upgrade pip

$ pip3 install circup

$ for LIB in \
    adafruit_adt7410 \
    adafruit_bitmap_font \
    adafruit_esp32spi \
    adafruit_logging \
    adafruit_pyportal \
    neopixel \
    ; do circup install $LIB ; done
```

**Note:** `adafruit_minimqtt` from latest library is not working, so we will be using an older revision, located
under the lib directory in this repo. To be fixed...

```text
    466.125: DEBUG - SUBSCRIBING to topic /pyportalkitchen/brightness with QoS 0
    466.168: DEBUG - Receiving PUBLISH
    Topic: /sensor/temperature_house
    Msg: bytearray(b'69')
    466.180: INFO - MMQT error: invalid message received as response to SUBSCRIBE: 0x31
    466.203: DEBUG - Reconnect timeout computed to 4.00
    466.205: DEBUG - adding jitter 0.91 to 4.00 seconds
    466.208: DEBUG - Attempting to connect to MQTT broker (attempt #2)
    466.209: DEBUG - Attempting to establish MQTT connection...
    466.211: DEBUG - Sleeping for 4.91 seconds due to connect back-off
    Traceback (most recent call last):
      File "code.py", line 301, in <module>
      File "/lib/adafruit_minimqtt/adafruit_minimqtt.py", line 502, in connect
      File "/lib/adafruit_minimqtt/adafruit_minimqtt.py", line 560, in _connect
```
    
This is what it should look like:
```text
$ ls /Volumes/CIRCUITPY/
LICENSE         boot_out.txt    fonts           init_background.bmp openweather_graphics.py secrets.py.sample
README.md       code.py         icons           lib

$ ls /Volumes/CIRCUITPY/lib
adafruit_adt7410.mpy        adafruit_portalbase
adafruit_bitmap_font        adafruit_pyportal
adafruit_esp32spi       adafruit_register
adafruit_io         adafruit_touchscreen.mpy
adafruit_logging.mpy        neopixel.mpy
adafruit_minimqtt

$ circup freeze | sort
Found device at /Volumes/CIRCUITPY, running CircuitPython 8.2.7.
```

### secrets.py

Make sure to create a file called secrets.py to include info on the wifi as well as the MQTT
broker you will connect to. Use [**secrets.py.sample**](https://github.com/flavio-fernandes/pyportal_station/blob/main/secrets.py.sample)
as reference.

At this point, all needed files should be in place, and all that
is needed is to let code.py run. From the Circuit Python serial console:

```text
>>  <CTRL-D>
soft reboot
...
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

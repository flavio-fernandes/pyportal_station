# NOTE: Make sure you've created your secrets.py file before running this example
# https://learn.adafruit.com/adafruit-pyportal/internet-connect#whats-a-secrets-file-17-2
#
# This file mostly implements the 2 following sample code from
# https://github.com/adafruit/Adafruit_Learning_System_Guides
#  - https://learn.adafruit.com/pyportal-mqtt-sensor-node-control-pad-home-assistant
#  - https://learn.adafruit.com/pyportal-weather-station
#

import gc
import json
import sys
import time
from collections import namedtuple

import adafruit_adt7410
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import board
import busio
import digitalio
from adafruit_esp32spi import adafruit_esp32spi_wifimanager
from adafruit_pyportal import PyPortal
from analogio import AnalogIn

cwd = ("/" + __file__).rsplit('/', 1)[0]  # the current working directory (where this file is)
sys.path.append(cwd)
import openweather_graphics  # pylint: disable=wrong-import-position

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# ------------- Pyportal init ------------- #

# Set up where we'll be fetching data from
DATA_SOURCE = "http://api.openweathermap.org/data/2.5/weather?id=" + secrets[
    'openweather_location_id'] + "&units=imperial&appid=" + secrets[
    'openweather_token']
DATA_LOCATION = []

# Initialize the pyportal object and let us know what data to fetch and where
# to display it
pyportal = PyPortal(url=DATA_SOURCE,
                    json_path=DATA_LOCATION,
                    status_neopixel=board.NEOPIXEL,
                    default_bg=0x000000)

# ------------- WiFi ------------- #

wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(pyportal._esp, secrets, None)

# ------- Sensor Setup ------- #

# init. the temperature sensor (ADT7410)
i2c_bus = busio.I2C(board.SCL, board.SDA)
adt = adafruit_adt7410.ADT7410(i2c_bus, address=0x48)
adt.high_resolution = True

# init. the light sensor
adc = AnalogIn(board.LIGHT)

# ------- Led  ------- #

board_led = digitalio.DigitalInOut(board.L)  # Or board.D13
board_led.switch_to_output()

# ------- Stats  ------- #

counters = {}
def _inc_counter(name):
    global counters
    curr_value = counters.get(name, 0)
    counters[name] = curr_value + 1

# ------------- MQTT Topic Setup ------------- #

def _parse_ping(_topic, message):
    global tss
    tss['send_status'] = None  # clear to force send status now
    _inc_counter('ping')


def _parse_brightness(topic, message):
    print("_parse_brightness: {0} {1} {2}".format(
        len(message), topic, message))
    set_backlight(message)
    _inc_counter('bright')


def _parse_openweather_message(topic, message):
    global tss, gfx
    print("_parse_openweather_message: {0} {1} {2}".format(
        len(message), topic, message))
    try:
        gfx.display_weather(message)
        tss['weather'] = time.monotonic()  # reset so no new update is needed
        _inc_counter('weather_cache')
    except Exception as e:
        print(f"Error in _parse_openweather_message -", e)


mqtt_topic = secrets.get("topic_prefix") or "/pyportal"
mqtt_pub_temperature = f"{mqtt_topic}/temperature"
mqtt_pub_light = f"{mqtt_topic}/light"
mqtt_pub_status = f"{mqtt_topic}/status"

mqtt_subs = {
    f"{mqtt_topic}/ping": _parse_ping,
    f"{mqtt_topic}/brightness": _parse_brightness,
    "/openweather/raw": _parse_openweather_message,
}


# ------------- MQTT Functions ------------- #

# Define callback methods which are called when events occur
# pylint: disable=unused-argument, redefined-outer-name
def connect(client, userdata, flags, rc):
    # This function will be called when the client is connected
    # successfully to the broker.
    print("Connected to MQTT Broker!", end=" ")
    print(f"mqtt_msg: {client.mqtt_msg}", end=" ")
    print(f"Flags: {flags} RC: {rc}")
    for mqtt_sub in mqtt_subs:
        print("Subscribing to %s" % mqtt_sub)
        client.subscribe(mqtt_sub)


def disconnected(client, userdata, rc):
    # This method is called when the client is disconnected
    print("Disconnected from MQTT Broker!")


def subscribe(client, userdata, topic, granted_qos):
    # This method is called when the client subscribes to a new feed.
    print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))


def publish(client, userdata, topic, pid):
    # This method is called when the client publishes data to a feed.
    print("Published to {0} with PID {1}".format(topic, pid))


def message(client, topic, message):
    """Method called when a client's subscribed feed has a new
    value.
    :param str topic: The topic of the feed with a new value.
    :param str message: The new value
    """
    # print("New message on topic {0}: {1}".format(topic, message))
    if topic in mqtt_subs:
        mqtt_subs[topic](topic, message)


# ------------- Network Connection ------------- #

# Connect to WiFi
print("Connecting to WiFi...")
wifi.connect()
print("Connected to WiFi!")

# Initialize MQTT interface with the esp interface
MQTT.set_socket(socket, pyportal._esp)

# Set up a MiniMQTT Client
client = MQTT.MQTT(
    broker=secrets["broker"],
    port=1883,
    username=secrets["broker_user"],
    password=secrets["broker_pass"],
)
client.attach_logger()
client.set_logger_level("DEBUG")

# Connect callback handlers to client
client.on_connect = connect
client.on_disconnect = disconnected
client.on_subscribe = subscribe
client.on_publish = publish
client.on_message = message

print("Attempting to connect to %s" % client.broker)
client.connect()

# ------------- Screen elements ------------- #

# Backlight function
def set_backlight(val):
    """Adjust the TFT backlight.
    :param val: The backlight brightness. Use a value between ``0`` and ``1``, where ``0`` is
                off, and ``1`` is 100% brightness. Can also be 'on' or 'off'
    """
    if isinstance(val, str):
        val = {"on": 1.0, "off": 0}.get(val.lower(), val)
    try:
        val = float(val)
    except (ValueError, TypeError):
        return
    val = max(0, min(1.0, val))
    board.DISPLAY.auto_brightness = False
    board.DISPLAY.brightness = val


gfx = openweather_graphics.OpenWeather_Graphics(pyportal.splash, am_pm=True, celsius=False)
set_backlight("on")

# ------------- Iteration routines ------------- #

def interval_weather():
    value = pyportal.fetch()
    print("interval_weather response is", value)
    gfx.display_weather(value)
    _inc_counter('weather_get')


def interval_send_status():
    global counters

    value = {"lux": adc.value,
             "up_mins": int(time.monotonic() - t0) // 60,
             "bright": board.DISPLAY.brightness,
             "ip": wifi.ip_address(),
             "counters": str(counters),
             "mem_free": gc.mem_free(),}
    client.publish(mqtt_pub_temperature, (adt.temperature * 9 / 5) + 32)  # Celsius to Fahrenheit
    client.publish(mqtt_pub_light, value["lux"] // 64)  # map 65535 to 1024 (16 to 10 bits)
    client.publish(mqtt_pub_status, json.dumps(value))
    print(f"send_status: {mqtt_pub_status}: {value}")


def interval_led_blink():
    board_led.value = not board_led.value


TS = namedtuple("TS", "interval fun")
TS_INTERVALS = {
    'localtime': TS(3601, pyportal.get_local_time),
    'weather': TS(11 * 60, interval_weather),
    'update_time': TS(30, gfx.update_time),
    'send_status': TS(10 * 60, interval_send_status),
    'led_blink': TS(15, interval_led_blink),
}

# ------------- Main loop ------------- #

tss = {interval: None for interval in TS_INTERVALS}
t0 = time.monotonic()
now = t0
while True:
    # Poll the message queue
    try:
        client.loop()
    except RuntimeError as e:
        print(f"Failed mqtt client loop: {e}")
        _inc_counter('mqtt_loop_fail')
        time.sleep(3)

    now = time.monotonic()
    for ts_interval in TS_INTERVALS:
        if not tss[ts_interval] or now > tss[ts_interval] + TS_INTERVALS[ts_interval].interval:
            try:
                if TS_INTERVALS[ts_interval].interval >= 60:
                    lt = time.localtime()
                    print(f"{lt.tm_hour}:{lt.tm_min}:{lt.tm_sec} Interval {ts_interval} triggered")
                else:
                    print(".", end="")
                TS_INTERVALS[ts_interval].fun()
                tss[ts_interval] = time.monotonic()
            except (ValueError, RuntimeError) as e:
                print(f"Error in {ts_interval}, retrying in 10s -", e)
                tss[ts_interval] = (now - TS_INTERVALS[ts_interval].interval) + 10

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


from microcontroller import watchdog as wd
from watchdog import WatchDogMode
import adafruit_adt7410
import adafruit_logging as logging
import board
import busio
import digitalio
import microcontroller
import neopixel
import rtc
import supervisor
from analogio import AnalogIn

import adafruit_esp32spi.adafruit_esp32spi_socket as socket
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_pyportal import PyPortal

supervisor.runtime.autoreload = False

cwd = ("/" + __file__).rsplit("/", 1)[
    0
]  # the current working directory (where this file is)
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
DATA_SOURCE = (
    "http://api.openweathermap.org/data/2.5/weather?id="
    + secrets["openweather_location_id"]
    + "&units=imperial&appid="
    + secrets["openweather_token"]
)
DATA_LOCATION = []

# Watch out for the WatchDogMode!
ENABLE_DOG = True
dog_is_enabled = False

# Initialize the pyportal object and let us know what data to fetch and where
# to display it
pyportal = PyPortal(
    url=DATA_SOURCE, json_path=DATA_LOCATION, status_neopixel=None, default_bg=0x000000
)

gfx = openweather_graphics.OpenWeather_Graphics(
    pyportal.splash, am_pm=True, celsius=False
)

# ------- Sensor Setup ------- #

# init. the temperature sensor (ADT7410)
i2c_bus = busio.I2C(board.SCL, board.SDA)
adt = adafruit_adt7410.ADT7410(i2c_bus, address=0x48)
adt.high_resolution = True

# init. the light sensor
adc = AnalogIn(board.LIGHT)

# ------- Leds  ------- #

# ref: https://www.devdungeon.com/content/pyportal-circuitpy-tutorial-adabox-011#toc-27
pixels = neopixel.NeoPixel(board.NEOPIXEL, 1, auto_write=True)
pixels[0] = (0, 0, 0)

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
    tss["send_status"] = None  # clear to force send status now
    _inc_counter("ping")


def _parse_brightness(topic, message):
    print("_parse_brightness: {0} {1} {2}".format(len(message), topic, message))
    set_backlight(message)
    _inc_counter("brightness")


def _parse_neopixel(_topic, message):
    global pixels
    try:
        value = int(message)
    except ValueError as e:
        print(f"bad neo value: {e}")
        return
    pixels[0] = ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)
    _inc_counter("neo")


LED_BLINK = "led_blink"
LED_BLINK_DEFAULT = 60


def _parse_blinkrate(_topic, message):
    global tss, TS_INTERVALS, board_led

    message = message.lower()
    value_map = {"off": 0, "no": 0, "on": None, "yes": None, "": LED_BLINK_DEFAULT}
    try:
        if message.startswith("-") or message in value_map:
            value = value_map.get(message)
        else:
            value = float(message)
    except ValueError as e:
        print(f"bad blink value given {message}: {e}")
        return

    if value:
        TS_INTERVALS[LED_BLINK] = TS(value, interval_led_blink)
        tss[LED_BLINK] = None
    else:
        # Stop blinking. Turn off if value is 0. Turn on if value is None.
        try:
            del TS_INTERVALS[LED_BLINK]
            del tss[LED_BLINK]
        except KeyError:
            pass
        board_led.value = value is None
    _inc_counter("blink")


def _parse_openweather_message(topic, message):
    global tss, gfx
    print(
        "_parse_openweather_message: {0} {1} {2}".format(len(message), topic, message)
    )
    try:
        gfx.display_weather(message)
        tss["weather"] = time.monotonic()  # reset so no new update is needed
        _inc_counter("weather_mqtt")
    except Exception as e:
        print(f"Error in _parse_openweather_message -", e)


def _parse_localtime_message(topic, message):
    # /aio/local_time : 2021-01-15 23:07:36.339 015 5 -0500 EST
    try:
        print(f"Local time mqtt: {message}")
        times = message.split(" ")
        the_date = times[0]
        the_time = times[1]
        year_day = int(times[2])
        week_day = int(times[3])
        is_dst = None  # no way to know yet
        year, month, mday = [int(x) for x in the_date.split("-")]
        the_time = the_time.split(".")[0]
        hours, minutes, seconds = [int(x) for x in the_time.split(":")]
        now = time.struct_time(
            (year, month, mday, hours, minutes, seconds, week_day, year_day, is_dst)
        )
        rtc.RTC().datetime = now
        tss["localtime"] = time.monotonic()  # reset so no new update is needed
        _inc_counter("local_time_mqtt")
    except Exception as e:
        print(f"Error in _parse_localtime_message -", e)
        _inc_counter("local_time_mqtt_failed")


def _parse_temperature_house(topic, message):
    gfx.display_inside_temp(int(message))
    _inc_counter("inside_temp")


mqtt_topic = secrets.get("topic_prefix") or "/pyportal"
mqtt_pub_temperature = f"{mqtt_topic}/temperature"
mqtt_pub_light = f"{mqtt_topic}/light"
mqtt_pub_status = f"{mqtt_topic}/status"

mqtt_subs = {
    f"{mqtt_topic}/ping": _parse_ping,
    f"{mqtt_topic}/brightness": _parse_brightness,
    f"{mqtt_topic}/neopixel": _parse_neopixel,
    f"{mqtt_topic}/blinkrate": _parse_blinkrate,
    "/openweather/raw": _parse_openweather_message,
    "/aio/local_time": _parse_localtime_message,
    "/sensor/temperature_house": _parse_temperature_house,
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
        print(f"Subscribing to {mqtt_sub}")
        client.subscribe(mqtt_sub)
    _inc_counter("connect")


def disconnected(_client, _userdata, rc):
    # This method is called when the client is disconnected
    print(f"Disconnected from MQTT Broker! RC: {rc}")
    _inc_counter("disconnected")


def subscribe(_client, _userdata, topic, granted_qos):
    # This method is called when the client subscribes to a new feed.
    print(f"Subscribed to {topic} with QOS level {granted_qos}")
    _inc_counter("subscribe")


def publish(_client, userdata, topic, pid):
    # This method is called when the client publishes data to a feed.
    print(f"Published to {topic} with PID {pid}")
    _inc_counter("publish")


def message(_client, topic, message):
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
pyportal.network.connect()
print("Connected to WiFi!")

# Initialize MQTT interface with the esp interface
MQTT.set_socket(socket, pyportal.network._wifi.esp)

# Set up a MiniMQTT Client
# https://github.com/adafruit/Adafruit_CircuitPython_MiniMQTT/issues/129
broker_user = secrets["broker_user"] if secrets["broker_user"] else None
broker_pass = secrets["broker_pass"] if secrets["broker_pass"] else None

client = MQTT.MQTT(
    broker=secrets["broker"],
    port=1883,
    username=broker_user,
    password=broker_pass,
)
try:
    client.enable_logger(logging, logging.DEBUG)
except:
    client.attach_logger()
    client.set_logger_level("DEBUG")

# Connect callback handlers to client
client.on_connect = connect
client.on_disconnect = disconnected
client.on_subscribe = subscribe
client.on_publish = publish
client.on_message = message

print(f"Attempting to MQTT connect to {client.broker}")
try:
    client.connect()
except Exception as e:
    print(f"FATAL! Unable to MQTT connect to {client.broker}: {e}")
    time.sleep(120)
    # bye bye cruel world
    microcontroller.reset()

# ------------- Screen elements ------------- #

# Backlight function
def set_backlight(val):
    """Adjust the TFT backlight.
    :param val: The backlight brightness. Use a value between ``0`` and ``1``, where ``0`` is
                off, and ``1`` is 100% brightness. Can also be 'on' or 'off'
    """
    if isinstance(val, str):
        val = {
            "on": 1,
            "off": 0,
            "mid": 0.5,
            "min": 0.01,
            "max": 1,
            "yes": 1,
            "no": 0,
            "y": 1,
            "n": 0,
        }.get(val.lower(), val)
    try:
        val = float(val)
    except (ValueError, TypeError):
        return
    val = max(0, min(1.0, val))
    # https://github.com/adafruit/circuitpython/pull/1815
    # board.DISPLAY.auto_brightness = False
    board.DISPLAY.brightness = val


set_backlight("on")


# ------------- Iteration routines ------------- #


def interval_localtime():
    # pyportal.get_local_time()
    _inc_counter("local_time_fetch")


def interval_weather():
    # value = pyportal.fetch()
    # print("interval_weather response is", value)
    # gfx.display_weather(value)
    _inc_counter("weather_fetch")


def interval_send_status():
    global counters

    value = {
        "lux": adc.value,
        "uptime_mins": int(time.monotonic() - t0) // 60,
        "brightness": board.DISPLAY.brightness,
        "ip": pyportal.network.ip_address,
        "counters": str(counters),
        "mem_free": gc.mem_free(),
    }
    client.publish(
        mqtt_pub_temperature, (adt.temperature * 9 / 5) + 32
    )  # Celsius to Fahrenheit
    client.publish(
        mqtt_pub_light, value["lux"] // 64
    )  # map 65535 to 1024 (16 to 10 bits)
    client.publish(mqtt_pub_status, json.dumps(value))
    print(f"send_status: {mqtt_pub_status}: {value}")


def interval_led_blink():
    board_led.value = not board_led.value


TS = namedtuple("TS", "interval fun")
TS_INTERVALS = {
    "localtime": TS(3620, interval_localtime),
    "weather": TS(11 * 60, interval_weather),
    "update_time": TS(16, gfx.update_time),
    "send_status": TS(10 * 60, interval_send_status),
    LED_BLINK: TS(LED_BLINK_DEFAULT, interval_led_blink),  # may be overridden via mqtt
}


def _try_reconnect(e):
    print(f"Failed mqtt loop: {e}")
    _inc_counter("fail_loop")
    feed_dog()
    time.sleep(3)

    disc_ok = False
    try:
        feed_dog()
        client.disconnect()
        disc_ok = True
    except Exception as e:
        print(f"Failed mqtt disconnect: {e}")

    try:
        if not disc_ok:
            _inc_counter("esp_reset")
            feed_dog()
            pyportal.network._wifi.esp.reset()
            print("Reconnecting to WiFi...")
            feed_dog()
            pyportal.network.connect()
            print("Reset esp and Wifi connected")
    except Exception as e:
        print(f"FATAL! Failed esp reset: {e}")

    try:
        feed_dog()
        client.connect()
        print("Reconnected to mqtt broker")
    except Exception as e:
        # bye bye cruel world
        print(f"FATAL! Failed reconnect: {e}")
        microcontroller.reset()


def run_once():
    global dog_is_enabled

    if ENABLE_DOG:
        print("--------------------------------------------------------")
        print("IMPORTANT: watch dog is enabled! To disable it, do:")
        print("from microcontroller import watchdog as wd ; wd.deinit()")
        print("--------------------------------------------------------")
        wd.timeout = 15  # timeout in seconds
        wd.mode = WatchDogMode.RESET
        dog_is_enabled = True
    else:
        print("NOTE: watch dog is disabled")
        no_dog()


def no_dog():
    global dog_is_enabled

    try:
        wd.deinit()
        dog_is_enabled = False
    except Exception as e:
        print(f"could not disable watchdog: {e}")
    return not dog_is_enabled


def feed_dog():
    if dog_is_enabled:
        wd.feed()


run_once()

# ------------- Main loop ------------- #

tss = {interval: None for interval in TS_INTERVALS}
t0 = time.monotonic()
now = t0
loop_failures = 0
while True:
    feed_dog()

    try:
        if not client.loop(timeout=0.5):
            ## if not client.loop():
            # Take a little break if nothing really happened
            time.sleep(0.123)
        loop_failures = 0
    except Exception as e:
        loop_failures += 1
        if loop_failures > 2:
            _try_reconnect(e)
            loop_failures = 0

    now = time.monotonic()
    for ts_interval in TS_INTERVALS:
        if (
            not tss[ts_interval]
            or now > tss[ts_interval] + TS_INTERVALS[ts_interval].interval
        ):
            try:
                if TS_INTERVALS[ts_interval].interval >= 60:
                    lt = time.localtime()
                    print(
                        f"{lt.tm_hour}:{lt.tm_min}:{lt.tm_sec} Interval {ts_interval} triggered"
                    )
                else:
                    print(".", end="")
                TS_INTERVALS[ts_interval].fun()
            except (ValueError, RuntimeError) as e:
                print(f"Error in {ts_interval}, retrying in 10s: {e}")
                tss[ts_interval] = (now - TS_INTERVALS[ts_interval].interval) + 10
                _inc_counter("fail_runtime")
                continue
            except Exception as e:
                print(f"Failed {ts_interval}: {e}")
                _inc_counter("fail_other")
            tss[ts_interval] = time.monotonic()

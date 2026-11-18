# coding=utf-8
from __future__ import absolute_import
import octoprint.plugin
from octoprint.events import Events
import RPi.GPIO as GPIO
from time import sleep
from datetime import datetime
import flask
import json
from octoprint_smart_filament_sensor.filament_motion_sensor_timeout_detection import FilamentMotionSensorTimeoutDetection
from octoprint_smart_filament_sensor.data import SmartFilamentSensorDetectionData

class SmartFilamentSensor(octoprint.plugin.StartupPlugin,
                         octoprint.plugin.EventHandlerPlugin,
                         octoprint.plugin.TemplatePlugin,
                         octoprint.plugin.SettingsPlugin,
                         octoprint.plugin.AssetPlugin,
                         octoprint.plugin.SimpleApiPlugin):

    def initialize(self):
        self._logger.info("Running RPi.GPIO version '{0}'".format(getattr(GPIO, 'VERSION', 'unknown')))
        try:
            GPIO.setwarnings(False)
        except Exception:
            pass

        self.print_started = False
        self.last_movement_time = datetime.now()
        self.lastE = -1
        self.currentE = -1
        self.START_DISTANCE_OFFSET = 7
        self.send_code = False
        self.motion_sensor_thread = None
        self._data = SmartFilamentSensorDetectionData(self.motion_sensor_detection_distance, True, self.updateToUi)

    def is_api_protected(self):
        return True

# Properties
    @property
    def motion_sensor_pin(self):
        try:
            return int(self._settings.get(["motion_sensor_pin"]))
        except (TypeError, ValueError):
            return -1

    @property
    def motion_sensor_pause_print(self):
        return self._settings.get_boolean(["motion_sensor_pause_print"])

    @property
    def detection_method(self):
        try:
            return int(self._settings.get(["detection_method"]))
        except (TypeError, ValueError):
            return 0

    @property
    def motion_sensor_enabled(self):
        return self._settings.get_boolean(["motion_sensor_enabled"])

    @property
    def pause_command(self):
        cmd = self._settings.get(["pause_command"])
        return cmd if cmd else "M600"

# Distance detection
    @property
    def motion_sensor_detection_distance(self):
        try:
            return int(self._settings.get(["motion_sensor_detection_distance"]))
        except (TypeError, ValueError):
            return 15

# Timeout detection
    @property
    def motion_sensor_max_not_moving(self):
        try:
            return int(self._settings.get(["motion_sensor_max_not_moving"]))
        except (TypeError, ValueError):
            return 45

# General Properties
    @property
    def mode(self):
        try:
            return int(self._settings.get(["mode"]))
        except (TypeError, ValueError):
            return 0

# Initialization methods
    def _setup_sensor(self):
        if self.motion_sensor_pin < 0:
            self._logger.info("Motion sensor pin is not configured (%s)", self.motion_sensor_pin)
            return

        try:
            if self.mode == 0:
                self._logger.info("Using Board Mode")
                GPIO.setmode(GPIO.BOARD)
            else:
                self._logger.info("Using BCM Mode")
                GPIO.setmode(GPIO.BCM)

            GPIO.setup(self.motion_sensor_pin, GPIO.IN)
        except Exception as e:
            self._logger.error("Failed to setup GPIO mode/pin: %s", e)
            return

        # Always remove any previous event before re-registering
        try:
            GPIO.remove_event_detect(self.motion_sensor_pin)
        except Exception:
            pass

        # Stop any active threads before reconfiguring
        self.motion_sensor_stop_thread()

        # Add distance detection listener if enabled
        if self.detection_method == 1 and self.motion_sensor_enabled:
            try:
                GPIO.add_event_detect(self.motion_sensor_pin, GPIO.BOTH, callback=self.reset_distance)
                self._logger.info("Registered hardware edge detection for distance mode on pin %s", self.motion_sensor_pin)
            except Exception as e:
                self._logger.warning("Hardware edge detection failed for distance mode (%s). Starting polling thread.", e)
                self.motion_sensor_thread = FilamentMotionSensorTimeoutDetection(
                    1,
                    "DistancePollingThread",
                    self.motion_sensor_pin,
                    3600,
                    self._logger,
                    self._data,
                    pTimeoutCallback=None,
                    pMotionCallback=self.reset_distance
                )
                self.motion_sensor_thread.start()

        if not self.motion_sensor_enabled:
            self._logger.info("Motion sensor is deactivated in settings")

        self._data.filament_moving = False
        self.load_smart_filament_sensor_data()

    def load_smart_filament_sensor_data(self):
        self._data.remaining_distance = self.motion_sensor_detection_distance

    def on_after_startup(self):
        self._logger.info("Smart Filament Sensor started")
        self._setup_sensor()

    def get_settings_defaults(self):
        return dict(
            mode=0,                              # 0 = Board Mode, 1 = BCM Mode
            motion_sensor_enabled=True,          # Sensor detection enabled
            motion_sensor_pin=-1,                # Default: no pin configured
            detection_method=0,                  # 0 = timeout detection, 1 = distance detection
            motion_sensor_detection_distance=15, # Recommended detection distance
            motion_sensor_max_not_moving=45,     # Maximum seconds without movement
            pause_command="M600"
        )

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._setup_sensor()

    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=True)]

    def get_assets(self):
        return dict(js=["js/smartfilamentsensor_sidebar.js", "js/smartfilamentsensor_settings.js"])

# Sensor methods
    def stop_connection_test(self):
        if self.motion_sensor_thread is not None and self.motion_sensor_thread.name == "ConnectionTest":
            self.motion_sensor_stop_thread()
            self._logger.info("Connection test stopped")
        else:
            self._logger.info("Connection test was not running")

        self._data.connection_test_running = False
        self._data.filament_moving = False

        # If distance detection is configured and enabled, restore it
        if self.detection_method == 1 and self.motion_sensor_enabled and self.motion_sensor_pin >= 0:
            self._setup_sensor()

    def start_connection_test(self):
        CONNECTION_TEST_TIME = 2

        if self.motion_sensor_pin < 0:
            self._logger.warning("Cannot start connection test: Motion sensor pin is not set")
            return

        # Ensure any running test or timeout thread is stopped
        self.motion_sensor_stop_thread()

        try:
            if self.mode == 0:
                GPIO.setmode(GPIO.BOARD)
            else:
                GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.motion_sensor_pin, GPIO.IN)
        except Exception as e:
            self._logger.error("GPIO setup failed for connection test: %s", e)
            return

        self._data.last_motion_detected = datetime.now().timestamp()
        self._data.filament_moving = False
        self._data.connection_test_running = True

        try:
            self.motion_sensor_thread = FilamentMotionSensorTimeoutDetection(
                1,
                "ConnectionTest",
                self.motion_sensor_pin,
                CONNECTION_TEST_TIME,
                self._logger,
                self._data,
                pTimeoutCallback=lambda: self.connectionTestCallback(False),
                pMotionCallback=lambda: self.connectionTestCallback(True)
            )
            self.motion_sensor_thread.start()
            self._logger.info("Connection test started on pin %d", self.motion_sensor_pin)
        except Exception as e:
            self._logger.error("Failed to start connection test thread: %s", e)
            self._data.connection_test_running = False

    def motion_sensor_start(self):
        self._logger.info("Starting motion sensor (enabled: %s, mode: %s, pin: %s)",
                          self.motion_sensor_enabled, "Board" if self.mode == 0 else "BCM", self.motion_sensor_pin)

        if not self.motion_sensor_enabled or self.motion_sensor_pin < 0:
            return

        # Distance detection
        if self.detection_method == 1:
            self._logger.info("Motion sensor active: Distance detection (%s mm)", self.motion_sensor_detection_distance)
            self._setup_sensor()

        # Timeout detection
        elif self.detection_method == 0:
            if self.motion_sensor_thread is None:
                self._logger.info("Motion sensor active: Timeout detection (%s s)", self.motion_sensor_max_not_moving)
                self.motion_sensor_thread = FilamentMotionSensorTimeoutDetection(
                    1,
                    "MotionSensorTimeoutDetectionThread",
                    self.motion_sensor_pin,
                    self.motion_sensor_max_not_moving,
                    self._logger,
                    self._data,
                    pTimeoutCallback=self.printer_change_filament,
                    pMotionCallback=None
                )
                self.motion_sensor_thread.start()

        self.send_code = False
        self._data.filament_moving = True

    def motion_sensor_stop_thread(self):
        if self.motion_sensor_thread is not None:
            self.motion_sensor_thread.keepRunning = False
            self.motion_sensor_thread = None
            self._logger.info("Motion sensor thread stopped")

# Sensor callbacks
    def printer_change_filament(self, *args, **kwargs):
        if not self._printer.is_printing():
            self._logger.debug("Printer is not printing; ignoring filament pause request.")
            return

        if not self.send_code:
            self._logger.error("Motion sensor detected no movement")
            self._logger.info("Pause command: " + self.pause_command)
            self._printer.commands(self.pause_command)
            self.send_code = True
            self._data.filament_moving = False
            self.lastE = -1

    def reset_distance(self, pPin=None):
        self._logger.debug("Motion sensor detected movement")
        self.send_code = False
        self.last_movement_time = datetime.now()
        self._data.last_motion_detected = datetime.now().timestamp()
        if self._data.remaining_distance < self.motion_sensor_detection_distance:
            self._data.remaining_distance = self.motion_sensor_detection_distance
            self._data.filament_moving = True

    def init_distance_detection(self):
        self.lastE = float(-1)
        self.currentE = float(0)
        self.last_movement_time = datetime.now()
        self.reset_remainin_distance()

    def reset_remainin_distance(self):
        self.last_movement_time = datetime.now()
        self._data.remaining_distance = (float(self.motion_sensor_detection_distance) + self.START_DISTANCE_OFFSET)

    def calc_distance(self, pE):
        if self.detection_method != 1 or not self.motion_sensor_enabled:
            return

        if self._data.remaining_distance > 0:
            if self._data.absolut_extrusion:
                if self.lastE < 0:
                    self._logger.info("First extrusion move: setting lastE to %s", pE)
                    self.lastE = pE
                    self.currentE = pE
                    deltaDistance = 0.0
                else:
                    self.lastE = self.currentE
                    self.currentE = pE
                    deltaDistance = self.currentE - self.lastE
            else:
                deltaDistance = float(pE)

            if deltaDistance <= 0:
                return

            if deltaDistance > self.motion_sensor_detection_distance:
                deltaDistance = deltaDistance % self.motion_sensor_detection_distance

            self._data.remaining_distance = max(0.0, self._data.remaining_distance - deltaDistance)
            self._logger.debug("Remaining: %s - Extruded: %s", self._data.remaining_distance, deltaDistance)
        else:
            if self.last_movement_time is None or (datetime.now() - self.last_movement_time).total_seconds() > 10:
                self.printer_change_filament()
            else:
                self._logger.debug("Ignored pause command due to 10 second rule")

    def updateToUi(self):
        try:
            self._plugin_manager.send_plugin_message(self._identifier, self._data.toJSON())
        except Exception as e:
            self._logger.error("Failed to send plugin message to UI: %s", e)

    def connectionTestCallback(self, pMoving=False):
        self._data.filament_moving = pMoving

    def print_paused(self, pEvent=""):
        self.print_started = False
        self._logger.info("%s: Pausing filament sensors." % (pEvent))
        if self.motion_sensor_enabled and self.detection_method == 0:
            self.motion_sensor_stop_thread()

# Events
    def on_event(self, event, payload):
        if event is Events.PRINT_STARTED:
            self.stop_connection_test()
            self.print_started = True
            if self.detection_method == 1:
                self.init_distance_detection()

        elif event is Events.PRINT_RESUMED:
            self.print_started = True
            if self.detection_method == 1:
                self.reset_remainin_distance()
            self.motion_sensor_start()

        elif event is Events.Z_CHANGE:
            if self.print_started:
                self.motion_sensor_start()
                self.print_started = False

        elif event in (
            Events.PRINT_DONE,
            Events.PRINT_FAILED,
            Events.PRINT_CANCELLED,
            Events.ERROR
        ):
            self._logger.info("%s: Disabling filament sensors." % (event))
            self.print_started = False
            if self.motion_sensor_enabled and self.detection_method == 0:
                self.motion_sensor_stop_thread()

        elif event is Events.PRINT_PAUSED:
            self.print_paused(event)

        elif event is Events.USER_LOGGED_IN:
            self.updateToUi()

# API commands
    def get_api_commands(self):
        return dict(
            startConnectionTest=[],
            stopConnectionTest=[]
        )

    def on_api_command(self, command, data):
        self._logger.info("API: " + command)
        try:
            if command == "startConnectionTest":
                self.start_connection_test()
                return flask.make_response("Started connection test", 204)
            elif command == "stopConnectionTest":
                self.stop_connection_test()
                return flask.make_response("Stopped connection test", 204)
            else:
                return flask.make_response("Not found", 404)
        except Exception as e:
            self._logger.error("Exception in on_api_command(%s): %s", command, e)
            return flask.make_response(f"Internal error: {e}", 500)

# Plugin update methods
    def update_hook(self):
        return dict(
            smartfilamentsensor=dict(
                displayName="Smart Filament Sensor",
                displayVersion=self._plugin_version,
                type="github_release",
                user="Royrdan",
                repo="Octoprint-Smart-Filament-Sensor",
                current=self._plugin_version,
                stable_branch=dict(
                    name="Stable",
                    branch="master",
                    comittish=["master"]
                ),
                prerelease_branches=[
                    dict(
                        name="Release Candidate",
                        branch="PreRelease",
                        comittish=["PreRelease"],
                    )
                ],
                pip="https://github.com/Royrdan/Octoprint-Smart-Filament-Sensor/archive/{target_version}.zip"
            )
        )

    def distance_detection(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
        if self.detection_method == 1 and self.motion_sensor_enabled:
            if gcode in ("G0", "G1", "G2", "G3"):
                commands = cmd.split(" ")
                for command in commands:
                    if command.startswith("E"):
                        try:
                            extruder = float(command[1:])
                            self.calc_distance(extruder)
                        except (ValueError, TypeError):
                            pass

            elif gcode == "G92":
                self.init_distance_detection()
                self._logger.debug("Found G92 command in '%s' : Reset Extruders", cmd)

            elif gcode == "M82":
                self._data.absolut_extrusion = True
                self._logger.info("Found M82 command in '%s' : Absolut extrusion", cmd)
                self.lastE = 0

            elif gcode == "M83":
                self._data.absolut_extrusion = False
                self._logger.info("Found M83 command in '%s' : Relative extrusion", cmd)
                self.lastE = 0

        return cmd


__plugin_name__ = "Smart Filament Sensor"
__plugin_version__ = "1.2"
__plugin_pythoncompat__ = ">=2.7,<4"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = SmartFilamentSensor()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.update_hook,
        "octoprint.comm.protocol.gcode.sent": __plugin_implementation__.distance_detection
    }

def __plugin_check__():
    try:
        import RPi.GPIO
    except ImportError:
        return False

    return True

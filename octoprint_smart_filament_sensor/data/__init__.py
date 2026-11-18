import json

class SmartFilamentSensorDetectionData(object):
    @property
    def remaining_distance(self):
        return self._remaining_distance

    @remaining_distance.setter
    def remaining_distance(self, value):
        self._remaining_distance = value
        if self.callbackUpdateUI:
            self.callbackUpdateUI()

    @property
    def print_started(self):
        return self._print_started

    @print_started.setter
    def print_started(self, value):
        self._print_started = value

    @property
    def lastE(self):
        return self._lastE

    @lastE.setter
    def lastE(self, value):
        self._lastE = value

    @property
    def currentE(self):
        return self._currentE

    @currentE.setter
    def currentE(self, value):
        self._currentE = value

    @property
    def absolut_extrusion(self):
        return self._absolut_extrusion

    @absolut_extrusion.setter
    def absolut_extrusion(self, value):
        self._absolut_extrusion = value

    @property
    def last_motion_detected(self):
        return self._last_motion_detected

    @last_motion_detected.setter
    def last_motion_detected(self, value):
        self._last_motion_detected = value
        if self.callbackUpdateUI:
            self.callbackUpdateUI()

    @property
    def filament_moving(self):
        return self._filament_moving

    @filament_moving.setter
    def filament_moving(self, value):
        self._filament_moving = value
        if self.callbackUpdateUI:
            self.callbackUpdateUI()

    @property
    def connection_test_running(self):
        return self._connection_test_running

    @connection_test_running.setter
    def connection_test_running(self, value):
        self._connection_test_running = value
        if self.callbackUpdateUI:
            self.callbackUpdateUI()

    def __init__(self, pRemainingDistance, pAbsolutExtrusion, pCallback=None):
        self._remaining_distance = pRemainingDistance
        self._absolut_extrusion = pAbsolutExtrusion
        self.START_DISTANCE_OFFSET = 7
        self.callbackUpdateUI = pCallback

        # Default values
        self._print_started = False
        self._lastE = -1
        self._currentE = -1
        self._last_motion_detected = 0
        self._filament_moving = False
        self._connection_test_running = False

    def toJSON(self):
        data = {
            "_remaining_distance": self._remaining_distance,
            "_absolut_extrusion": self._absolut_extrusion,
            "_print_started": self._print_started,
            "_lastE": self._lastE,
            "_currentE": self._currentE,
            "_last_motion_detected": self._last_motion_detected,
            "_filament_moving": self._filament_moving,
            "_connection_test_running": self._connection_test_running,
        }
        return json.dumps(data, indent=4)

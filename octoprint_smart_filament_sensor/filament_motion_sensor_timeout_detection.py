import RPi.GPIO as GPIO
import threading
import time

class FilamentMotionSensorTimeoutDetection(threading.Thread):
    def __init__(self, threadID, threadName, pUsedPin, pMaxNotMovingTime, pLogger, pData, pTimeoutCallback=None, pMotionCallback=None, pCallback=None):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = threadName
        self.timeout_callback = pTimeoutCallback if pTimeoutCallback is not None else pCallback
        self.motion_callback = pMotionCallback
        self._logger = pLogger
        self._data = pData

        self.used_pin = pUsedPin
        self.max_not_moving_time = pMaxNotMovingTime
        self._data.last_motion_detected = time.time()
        self.keepRunning = True
        self.use_polling = False
        self.last_pin_state = None

        # Remove event, if already an event was set
        try:
            GPIO.remove_event_detect(self.used_pin)
        except Exception:
            pass

        try:
            GPIO.add_event_detect(self.used_pin, GPIO.BOTH, callback=self.motion)
            self._logger.info("Using hardware edge detection for %s on pin %s", self.name, self.used_pin)
        except Exception as e:
            self._logger.warning("Hardware edge detection failed on pin %s (%s). Falling back to software polling.", self.used_pin, e)
            self.use_polling = True
            try:
                self.last_pin_state = GPIO.input(self.used_pin)
            except Exception as e2:
                self._logger.error("Failed to read initial GPIO state on pin %s: %s", self.used_pin, e2)

    def run(self):
        last_check_time = time.time()
        while self.keepRunning:
            now = time.time()

            # Software polling fallback if edge detection failed
            if self.use_polling:
                try:
                    current_state = GPIO.input(self.used_pin)
                    if self.last_pin_state is not None and current_state != self.last_pin_state:
                        self.last_pin_state = current_state
                        self.motion(self.used_pin)
                    else:
                        self.last_pin_state = current_state
                except Exception as e:
                    self._logger.debug("Error during GPIO poll: %s", e)

            # Check timeout interval (~250ms)
            if (now - last_check_time) >= 0.25:
                last_check_time = now
                timespan = now - self._data.last_motion_detected
                if timespan > self.max_not_moving_time:
                    if self.timeout_callback is not None:
                        try:
                            self.timeout_callback()
                        except Exception as e:
                            self._logger.error("Error in timeout callback: %s", e)

            # Poll every 20ms if polling mode, otherwise sleep 250ms
            time.sleep(0.02 if self.use_polling else 0.25)

        try:
            GPIO.remove_event_detect(self.used_pin)
        except Exception:
            pass

    def motion(self, pPin=None):
        self._data.last_motion_detected = time.time()
        if self.motion_callback is not None:
            try:
                self.motion_callback()
            except Exception as e:
                self._logger.error("Error in motion callback: %s", e)
        self._logger.debug("Motion detected at %s", self._data.last_motion_detected)

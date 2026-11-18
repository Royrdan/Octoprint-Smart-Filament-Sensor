$(function(){
    function SmartFilamentSensorSidebarViewModel(parameters){
        var self = this;

        self.settingsViewModel = parameters[0];

        self.isSensorEnabled = ko.observable(undefined);
        self.remainingDistance = ko.observable(undefined);
        self.lastMotionDetected = ko.observable(undefined);
        self.isFilamentMoving = ko.observable("No");
        self.isConnectionTestRunning = ko.observable("Stopped");

        // Returns the value in Yes/No if the Sensor is enabled 
        self.getSensorEnabledString = function(){
            try {
                var sensorEnabled = self.settingsViewModel.settings.plugins.smartfilamentsensor.motion_sensor_enabled();
                return sensorEnabled ? "Yes" : "No";
            } catch (e) {
                return "Unknown";
            }
        };

        // Returns the value of detection_method as string
        self.getDetectionMethodString = function(){
            try {
                var detectionMethod = self.settingsViewModel.settings.plugins.smartfilamentsensor.detection_method();
                if(detectionMethod == 0){
                    return "Timeout Detection";
                } else if(detectionMethod == 1){
                    return "Distance Detection";
                }
            } catch (e) {
                return "Unknown";
            }
        };

        self.getDetectionMethodBoolean = ko.pureComputed(function(){
            try {
                var detectionMethod = self.settingsViewModel.settings.plugins.smartfilamentsensor.detection_method();
                return (detectionMethod == 1);
            } catch (e) {
                return false;
            }
        });

        self.onDataUpdaterPluginMessage = function(plugin, data){
            if(plugin !== "smartfilamentsensor"){
                return;
            }
            
            var message = (typeof data === "string") ? JSON.parse(data) : data;
            if (message["_remaining_distance"] !== undefined) {
                self.remainingDistance(Math.round(message["_remaining_distance"]));
            }
            if (message["_last_motion_detected"]) {
                var dt = new Date(message["_last_motion_detected"] * 1000);
                self.lastMotionDetected(dt.toLocaleTimeString());
            }

            if(message["_filament_moving"] === true){
                self.isFilamentMoving("Yes");
            } else {
                self.isFilamentMoving("No");
            }

            if(message["_connection_test_running"] === true){
                self.isConnectionTestRunning("Running");
            } else {
                self.isConnectionTestRunning("Stopped");
            }
        };

        self.startConnectionTest = function(){
            $.ajax({
                url: API_BASEURL + "plugin/smartfilamentsensor",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({ "command": "startConnectionTest" }),
                contentType: "application/json",
                success: self.RestSuccess
            });
        };

        self.stopConnectionTest = function(){
            $.ajax({
                url: API_BASEURL + "plugin/smartfilamentsensor",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({ "command": "stopConnectionTest" }),
                contentType: "application/json",
                success: self.RestSuccess
            });
        };

        self.RestSuccess = function(response){
            return;
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: SmartFilamentSensorSidebarViewModel,
        name: "smartFilamentSensorSidebarViewModel",
        dependencies: ["settingsViewModel"],
        elements: ["#sidebar_plugin_smartfilamentsensor"]
    });
});

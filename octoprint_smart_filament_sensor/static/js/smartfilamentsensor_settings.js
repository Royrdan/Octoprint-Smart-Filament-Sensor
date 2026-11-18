$(function(){
    function SmartFilamentSensorSettingsViewModel(parameters){
        var self = this;

        self.settingsViewModel = parameters[0];
        self.printerStateViewModel = parameters[1];
        self.connectionTestDialog = undefined;

        self.remainingDistance = ko.observable(undefined);
        self.lastMotionDetected = ko.observable(undefined);
        self.isFilamentMoving = ko.observable("Filament is not moving");
        self.isConnectionTestRunning = ko.observable(false);

        self.onStartup = function() {
            self.connectionTestDialog = $("#settings_plugin_smartfilamentsensor_connectiontest");
        };
        
        self.showConnectionTest = function() {
            if (self.connectionTestDialog) {
                self.connectionTestDialog.modal({
                    show: true
                });
            }
        };

        self.onDataUpdaterPluginMessage = function(plugin, data){
            if(plugin !== "smartfilamentsensor"){
                return;
            }
            
            var message = (typeof data === "string") ? JSON.parse(data) : data;
            if(message["_remaining_distance"] !== undefined) {
                self.remainingDistance(message["_remaining_distance"]);
            }
            if(message["_last_motion_detected"] !== undefined) {
                self.lastMotionDetected(message["_last_motion_detected"]);
            }
            if(message["_connection_test_running"] !== undefined) {
                self.isConnectionTestRunning(message["_connection_test_running"]);
            }

            if(message["_filament_moving"] === true){
                self.isFilamentMoving("Movement detected");
            }
            else{
                self.isFilamentMoving("Filament is not moving");
            }
        };

        self.enableConnectionTest = ko.pureComputed(function() {
            return !self.printerStateViewModel.isBusy();
        });

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
        construct: SmartFilamentSensorSettingsViewModel,
        name: "smartFilamentSensorSettingsViewModel",
        dependencies: ["settingsViewModel", "printerStateViewModel"],
        elements: ["#settings_plugin_smartfilamentsensor", "#settings_plugin_smartfilamentsensor_connectiontest"]
    });
});

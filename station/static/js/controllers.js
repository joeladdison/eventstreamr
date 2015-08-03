'use strict';

/* Controllers */

var myCtrls = angular.module('myApp.controllers', []);

myCtrls.controller('status-list', ['$scope', '$http', '$timeout',
    function($scope, $http, $timeout) {
        $scope.getData = function() {
        $http.get('/status').success(function(data) {
            for ( var station in data ) {
                var station_details = data[station];
                station_details.icon = 'ok';
                station_details.colour = 'green';
                var not_ok = 0;
                for ( var proc in station_details.status ) {
                    //alert( "station: " + station + " -> proc: " + proc );
                    var proc_details = station_details.status[proc];
                    if ( proc_details.status == 'started' ) {
                        proc_details.icon = 'ok';
                        proc_details.colour = 'green';
                    }
                    else {
                        not_ok++;
                        proc_details.icon = 'remove';
                        proc_details.colour = 'red';
                    }
                    proc_details.short_id = proc;
                    if ( proc_details.type == 'file' ) {
                        proc_details.short_id = proc.substring(proc.lastIndexOf("/")+1, proc.length);
                    }
                    if ( proc_details.type == 'internal' ) {
                        proc_details.label = proc;
                        proc_details.tooltip = "<em>internal process</em><br/>state: " + proc_details.status;
                    }
                    else {
                        proc_details.label = proc_details.type;
                        proc_details.tooltip = "state: " + proc_details.status + "<br/>id: " + proc_details.short_id;
                    }
                }
                if ( not_ok > 0 ) {
                    station_details.icon = 'remove';
                    station_details.colour = 'red';
                }
            }
            $scope.status_list = data;
        });
        };

        var refreshTimeout = null;
        $scope.refreshData = function() {
            console.log( "refreshing data" );
            $scope.getData();
            refreshTimeout = $timeout( $scope.refreshData, 1000 );
        };

        $scope.resetProc = function(proc_id) {
            var data = '{ "id": "' + proc_id + '" }';
            $http.post('/command/restart', data);
        };

        $scope.$on('$locationChangeStart', function(){
            if (refreshTimeout !== null)
                $timeout.cancel(refreshTimeout);
        });

        $scope.refreshData();
    }]);

myCtrls.controller('encoding', function($scope, $http) {
    $scope.schedule = {
        rooms: {},
        room: '',
        talks: {},
        talkId: null,
        talk: null,
        talkStatus: null,
        queue: [],
        inProgress: {
            active: [],
            reserved: []
        },
        outputStatus: [],
        alerts: []
    };

    $scope.formats = [];

    $scope.$watch('schedule.room', function() {
        $scope.loadTalks();
    }, true);

    $scope.$watch('schedule.talkId', function() {
        if ($scope.schedule.talkId !== null) {
            var talk = angular.copy($scope.schedule.talks[$scope.schedule.talkId]);
            // Add selected flag to files for checkboxes
            var fileList = talk.playlist;
            for (var i = 0; i < fileList.length; ++i) {
                fileList[i].selected = false;
            }
            talk.credits = '';
            talk.startTime = '';
            talk.endTime = '';

            $scope.schedule.talk = talk;
            $scope.schedule.talkStatus = null;
        }
    }, true);

    $scope.loadTalks = function() {
        var url = '/encoding/schedule/' + $scope.schedule.room;
        $http.get(url).success(function(data) {
            if ('error' in data) {
                // Handle error
            } else {
                $scope.schedule.talks = data.talks;
            }
        });
    };

    $scope.loadRooms = function() {
        var url = '/encoding/rooms';
        $http.get(url).success(function(data) {
            if ('error' in data) {
                // Handle error
            } else {
                $scope.schedule.rooms = data.rooms;
            }
        });
    };

    $scope.loadFormats = function() {
        var url = '/encoding/formats';
        $http.get(url).success(function(data) {
            if ('error' in data) {
                // Handle error
            } else {
                $scope.formats = data.formats;
            }
        });
    };

    $scope.loadQueue = function() {
        var url = '/encoding/jobs';
        $http.get(url).success(function(data) {
            if ('error' in data) {
                // Handle error
                $scope.schedule.alerts = [{
                    type: 'error',
                    msg: data.error
                }];
            } else {
                $scope.schedule.queue = data.queue;
            }
        });
    };

    $scope.loadInProgress = function() {
        var url = '/encoding/in-progress';
        $http.get(url).success(function(data) {
            if ('error' in data) {
                // Handle error
                $scope.schedule.alerts = [{
                    type: 'error',
                    msg: data.error
                }];
            } else {
                $scope.schedule.inProgress = data.status;
            }
        });
    };

    $scope.loadOutputStatus = function() {
        $scope.loadFormats();

        var url = '/encoding/output-status';
        $http.get(url).success(function(data) {
            if ('error' in data) {
                // Handle error
                $scope.schedule.alerts = [{
                    type: 'error',
                    msg: data.error
                }];
            } else {
                $scope.schedule.outputStatus = data.status;
            }
        });
    };

    $scope.encode = function() {
        var url = '/encoding/submit';

        // Build list of files
        var files = [];
        for (var i = 0; i < $scope.schedule.talk.playlist.length; ++i) {
            var file = $scope.schedule.talk.playlist[i];
            if (file.selected === true) {
                var cleanFile = {
                    filename: file.filename,
                    filepath: file.filepath
                };
                files.push(cleanFile);
            }
        }

        var talkData = $scope.schedule.talk;

        var inTime = '';
        if (talkData.startTime !== '') {
            inTime = "00:" + talkData.startTime + ".00";
        }

        var outTime = '';
        if (talkData.endTime !== '') {
            outTime = "00:" + talkData.endTime + ".00";
        }

        var talk = {
            schedule_id: talkData.schedule_id,
            title: talkData.title,
            presenters: talkData.presenters,
            file_list: files,
            in_time: inTime,
            out_time: outTime,
            credits: talkData.credits
        };

        $http.post(url, talk).success(function(data) {
            $scope.schedule.talkStatus = data.result;
        });
    };

    $scope.resubmitEncode = function(id, formats) {
        if (formats === undefined || formats === null) {
            // Use default formats
            formats = $scope.formats;
        }

        var url = '/encoding/resubmit/' + id;
        var postData = {
            formats: formats
        };

        $http.post(url, postData).success(function(data) {
            if ('alerts' in data) {
                $scope.schedule.alerts = data.alerts;
            }
        });

        $scope.loadQueue();
        $scope.loadInProgress();
        $scope.loadOutputStatus();
    };

    // Initialise
    $scope.loadRooms();
    $scope.loadFormats();
    $scope.loadQueue();
    $scope.loadInProgress();
    $scope.loadOutputStatus();
});

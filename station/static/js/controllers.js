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
        room: 'Kennedy',
        talks: {},
        talkId: null,
        talk: null,
        talkStatus: null,
    };

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
            talk.startTime = '00:00';
            talk.endTime = '00:00';

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
        var talk = {
            schedule_id: talkData.schedule_id,
            title: talkData.title,
            presenters: talkData.presenters,
            file_list: files,
            in_time: "00:" + talkData.startTime + ".00",
            out_time: "00:" + talkData.endTime + ".00",
            credits: talkData.credits
        };

        $http.post(url, talk).success(function(data) {
            $scope.schedule.talkStatus = data.result;
        });
    };

    // Initialise
    $scope.loadRooms();
});

'use strict';

/* Controllers */

var myCtrls = angular.module('myApp.controllers', []);

myCtrls.controller('status-list', ['$scope', '$http', '$timeout',
    function($scope, $http, $timeout) {
        var api_url = 'http://localhost:3000';
        $scope.getData = function() {
        $http.get( api_url + '/status' ).success(function(data) {
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

        $scope.refreshData = function() {
            console.log( "refreshing data" );
            $scope.getData();
            $timeout( $scope.refreshData, 1000 );
        };

        $scope.resetProc = function( proc_id ) {
            var data = '{ "id": "' + proc_id + '" }';
            $http.post( api_url + '/command/restart', data );
        };

        $scope.refreshData();
    }]);

myCtrls.controller('encoding', function($scope, $http) {
    var apiUrl = 'http://localhost:3000';

    $scope.schedule = {
        rooms: {},
        room: 'Kennedy',
        talks: {},
        talkId: null,
        talk: null
    };

    $scope.$watch('schedule.room', function() {
        $scope.loadTalks();
    }, true);

    $scope.$watch('schedule.talkId', function() {
        if ($scope.schedule.talkId !== null) {
            $scope.schedule.talk = angular.copy($scope.schedule.talks[$scope.schedule.talkId]);
            $scope.loadRooms();
        }
    }, true);

    $scope.loadTalks = function() {
        var url = apiUrl + '/encoding/schedule/' + $scope.schedule.room;
        $http.get(url).success(function(data) {
            if ('error' in data) {
                // Handle error
            } else {
                $scope.schedule.talks = data.talks;
            }
        });
    };

    $scope.loadRooms = function() {
        var url = apiUrl + '/encoding/rooms';
        $http.get(url).success(function(data) {
            if ('error' in data) {
                // Handle error
            } else {
                $scope.schedule.rooms = data.rooms;
            }
        });
    };

    // Initialise
    $scope.loadRooms();
});

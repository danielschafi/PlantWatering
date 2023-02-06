#!/usr/bin/env python3
# !/usr/bin/python
# -*- coding:utf-8 -*-

import datetime
from datetime import date
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, html, dcc, Output, ctx
from dash.dependencies import Input, Output, State
import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, dcc, html
import time
import serial
import datetime as dt
import numpy as np
from enum import Enum
import sys
import traceback
import RPi.GPIO as GPIO
from observable import Observable
import csv

WATERING_THRESHOLD = 40  # Threshold for pump activation
RELAY_CHANNELS = [26, 20]  # ,21 Nr 3 unused
WAITING_TIME = [180, 180]
WATERING_TIME = [2, 2]  #
CHANGE_THRESHOLD_PRECENTAGE = 6
current = [1, 1]
WORKING_HOURS = [9, 17]  # start,end


def main():
    # Setup
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    for rl in RELAY_CHANNELS:
        GPIO.setup(rl, GPIO.OUT)

    print("Setup The Relay Modules is [success]")

    ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
    ser.reset_input_buffer()

    print("Setup Serial Connection is [success]")

    wc = WateringControl(pumps=RELAY_CHANNELS,
                         requiresWaterThreshold=WATERING_THRESHOLD,
                         waitingTime=WAITING_TIME,
                         wateringTime=WATERING_TIME,
                         waterDetectionThreshold=CHANGE_THRESHOLD_PRECENTAGE)

    # runDashboard(wc)

    while True:
        if ser.in_waiting > 0:
            try:
                data = ser.readline().decode('utf-8').rstrip().split(',')
                allNum = True
                for j in data:
                    if not j.isnumeric():
                        allNum = False

                if allNum and len(data) == 4:
                    current = [data[0], data[2]]
                    avg = [data[1], data[3]]
                    wc.waterRequired(current, avg)
                    wc.switchPumps()

            except Exception as e:
                print(traceback.format_exc())


class WateringState(Enum):
    IDLE = 0
    INIT = 1
    PRE_WATERING_START = 2
    PRE_WATERING_END = 3

    WATERING_START = 4
    WATERING_END = 5

    FINISHED_START = 6
    FINISHED_END = 7

    WAITING_START = 8
    WAITING_END = 9

    ABORTED_START = 10
    ABORTED_END = 11

    RESET = 12


class WateringControl:
    moist = [0, 0]

    def __init__(self, pumps, requiresWaterThreshold=40, waitingTime=[180, 180], wateringTime=[2, 2],
                 waterDetectionThreshold=10, maxTimeToReachSensor=[15, 15]):
        self.requiresWaterThreshold = requiresWaterThreshold
        self.pumpStates = []  # Pumps on/off
        self.wateringState = []
        self.startPumpingTime = []  # time (int)
        self.startPumpingMoisture = []
        self.maxTimeToReachSensor = maxTimeToReachSensor  # duration (int)
        self.startWateringTime = []  # time (int)
        self.wateringTime = wateringTime  # duration (int)
        self.startWaitingTime = []
        self.waitingTime = waitingTime  # int duration
        self.pumps = pumps  # relays of the pumps
        self.waterDetectionThreshold = waterDetectionThreshold  # int 0-100
        self.lastWatering = []  # time (int)
        self.moisture = []  # int 0-100
        self.avgMoisture = []
        self.pumpBlocked = []  # bool if pump seems to be not functioning as it should
        self.logEntry = []
        self.logTimer = 0

        # For Each pump
        for i in range(len(pumps)):
            self.lastWatering.append(0)  # int(dt.datetime.utcnow().timestamp())
            self.startPumpingTime.append(0)
            self.pumpBlocked.append(False)
            self.moisture.append(0)
            self.avgMoisture.append(0)
            self.startPumpingMoisture.append(0)
            self.wateringState.append(WateringState.IDLE)
            self.startWateringTime.append(0)
            self.startWaitingTime.append(0)
            self.logEntry.append([])
            self.pumpOff(i)
        self.pumpBlocked = [False, False]

        # logColumns = ["timestamp", "pump", "currentMoisture","averageMoisture" ,"pumpStates", "pumpBlocked","wateringState"]

    def switchPumps(self, chatty=False):
        try:
            if len(self.pumpStates) > 0:
                for i, requiresWater in enumerate(self.pumpStates):
                    self.logEntry[i] = timestamp(), i, self.moisture[i], self.avgMoisture[i], i, self.pumpStates[i], \
                                       self.pumpBlocked[i], self.wateringState[i]

                    # State Machine
                    if self.wateringState[i] == WateringState.IDLE:
                        tsBeginn = datetime.datetime.today().replace(hour=WORKING_HOURS[0], minute=0).timestamp()
                        tsEnd = datetime.datetime.today().replace(hour=WORKING_HOURS[1], minute=0).timestamp()
                        if tsBeginn < timestamp() < tsEnd:
                            if requiresWater and self.pumpBlocked[i] != True:
                                self.wateringState[i] = WateringState.INIT

                    elif self.wateringState[i] == WateringState.INIT:
                        self.startPumpingMoisture[i] = max(self.avgMoisture[i], self.moisture[
                            i])  # Nach oben meist recht konsistent, aber vereinelt abbrueche nach unten
                        self.wateringState[i] = WateringState.PRE_WATERING_START

                    elif self.wateringState[i] == WateringState.PRE_WATERING_START:
                        self.startPumpingTime[i] = timestamp()
                        self.pumpOn(i)
                        self.wateringState[i] = WateringState.PRE_WATERING_END

                    elif self.wateringState[i] == WateringState.PRE_WATERING_END:
                        if (timestamp() - self.startPumpingTime[i]) < self.maxTimeToReachSensor[i]:
                            if self.moistureChanged(i):  # Water reached Sensor
                                self.wateringState[i] = WateringState.WATERING_START
                        else:
                            self.wateringState[i] = WateringState.ABORTED_START

                    elif self.wateringState[i] == WateringState.WATERING_START:
                        self.startWateringTime[i] = timestamp()
                        self.wateringState[i] = WateringState.WATERING_END

                    elif self.wateringState[i] == WateringState.WATERING_END:
                        if (timestamp() - self.startWateringTime[i]) > self.wateringTime[i]:
                            self.pumpOff(i)
                            self.wateringState[i] = WateringState.FINISHED_START

                    elif self.wateringState[i] == WateringState.FINISHED_START:
                        self.wateringState[i] = WateringState.FINISHED_END

                    elif self.wateringState[i] == WateringState.FINISHED_END:
                        self.wateringState[i] = WateringState.WAITING_START

                    elif self.wateringState[i] == WateringState.WAITING_START:
                        self.startWaitingTime[i] = timestamp()
                        self.wateringState[i] = WateringState.WAITING_END

                    elif self.wateringState[i] == WateringState.WAITING_END:
                        if (timestamp() - self.startWaitingTime[i]) > self.waitingTime[i]:
                            self.wateringState[i] = WateringState.RESET

                    elif self.wateringState[i] == WateringState.ABORTED_START:
                        self.pumpOff(i)
                        self.pumpBlocked[i] = True
                        self.startPumpingTime[i] = 0
                        self.startWateringTime[i] = 0
                        self.wateringState[i] = WateringState.ABORTED_END


                    elif self.wateringState[i] == WateringState.ABORTED_END:
                        self.wateringState[i] = WateringState.RESET

                    elif self.wateringState[i] == WateringState.RESET:
                        self.wateringState[i] = WateringState.IDLE

                self.logTimer = (self.logTimer + 1) % 50
                if self.logTimer == 0:
                    self.logData()
                time.sleep(0.1)

            else:
                print("No sensors / states available")

        except Exception as e:
            GPIO.cleanup()
            # print("GPIO Cleanup, Errormessage: ", e)
            print(traceback.format_exc())

    # Create logfile for each day
    def logData(self):
        filename = "/home/daniel/Desktop/Plants/log/datalog_" + str(date.today()) + ".csv"
        with open(filename, 'a') as f:
            w = csv.writer(f)
            for entry in self.logEntry:
                w.writerow(entry)
                entry = []

    def waterRequired(self, moisture, avgMoisture):
        self.pumpStates = []
        self.moisture = []
        self.avgMoisture = []
        WateringControl.moist = []

        for sensor in range(len(moisture)):
            self.moisture.append(int(moisture[sensor]))
            WateringControl.moist.append(moisture[sensor])
            self.avgMoisture.append(int(avgMoisture[sensor]))

            if self.requiresWaterThreshold < self.avgMoisture[sensor]:
                self.pumpStates.append(False)
            else:
                self.pumpStates.append(True)  # Needs water

        return self.pumpStates

    def moistureChanged(self, i):
        if self.moisture[i] > (self.startPumpingMoisture[i] + self.waterDetectionThreshold):
            return True
        else:
            return False

    def pumpOn(self, i):
        GPIO.output(self.pumps[i], GPIO.LOW)

    def pumpOff(self, i):
        GPIO.output(self.pumps[i], GPIO.HIGH)

    def getMoist(cls):
        return cls.moist


def timestamp():
    return float(dt.datetime.utcnow().timestamp())


# ----------------------------- Dashboard --------------------------------------

def runDashboard(wc):
    app = dash.Dash(external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)

    moisture = dbc.Container([
        html.H1("Moisture", style={"text-align": "center"}),
        dbc.Card([
            html.Div(id="s1Display"),
            dcc.Interval(
                id='ivS1',
                interval=1000,  # in milliseconds
                n_intervals=0
            )
        ]),
        dbc.Card([
            html.Div(id="s2Display"),
            dcc.Interval(
                id='ivS2',
                interval=1000,  # in milliseconds
                n_intervals=0
            )
        ])
    ])

    controls = dbc.Container([
        html.H1("Controls", style={"text-align": "center"}),
        html.Div([
            dbc.Button("Pump 1 On", id="btnOnP1", color="primary", size="lg"),
            dbc.Button("Pump 1 Off", id="btnOffP1", color="secondary", size="lg"),
            dbc.Button("Pump 2 On", id="btnOnP2", color="primary", size="lg"),
            dbc.Button("Pump 2 Off", id="btnOffP2", color="secondary", size="lg"),
            html.Span(id="spState", style={"verticalAlign": "middle"}),

        ], className="d-grid gap-5 col-4 mx-auto")

    ], style={"height": "100vh"})

    content = html.Div([
        html.H1("Dashboard", style={"text-align": "center"}),
        dbc.Row(moisture),
        dbc.Row(controls)

    ], style={"padding": "2rem 1rem"})

    app.layout = dbc.Container([
        dbc.Row([
            content
        ], className="h-100")

    ], fluid=True, style={"height": "100vh"})

    @app.callback(
        Output("spState", "children"),
        [Input("btnOnP1", "n_clicks"),
         Input("btnOffP1", "n_clicks"),
         Input("btnOnP2", "n_clicks"),
         Input("btnOffP2", "n_clicks")]
    )
    def pOn1(n1, n2, n3, n4):

        if "btnOnP1" == ctx.triggered_id:
            wc.pumpOn(0)
            return " "
        elif "btnOnP2" == ctx.triggered_id:
            wc.pumpOn(1)
            return " "
        elif "btnOffP1" == ctx.triggered_id:
            wc.pumpOff(0)
            return " "
        elif "btnOffP2" == ctx.triggered_id:
            wc.pumpOff(1)
            return " "

    @app.callback(Output('s1Display', 'children'),
                  Input('ivS1', 'n_intervals'))
    def update_s1(n):
        val = "67"
        style = {'padding': '5px', 'fontSize': '16px'}
        return html.H1("Sensor 1 Moisture: ", val)

    @app.callback(Output('s2Display', 'children'),
                  Input('ivS2', 'n_intervals'))
    def update_s2(n):
        val = "23"
        style = {'padding': '5px', 'fontSize': '16px'}
        return html.H1("Sensor 2 Moisture: ", val)

    app.run(debug=True)


if __name__ == "__main__":
    main()



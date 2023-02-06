# PlantWatering
In this repository you will find all the necessary code to set up your own automated plant watering system.

## ard.ini 
Contains the Code for your Arduino. You just need to download it and run it on the arduino, connect the Raspberry-PI and over the Serial Interace (with a cable)
If you plan to use it for more than two plants, you need to add the input of the additional sensors everywhere the othere two are. Don't forgett to add it to the serial send
in the same Format as the existing ones.


## PlantWatering.py
Contains the python code for your Raspberry PI
Download it, make that it executes on startup.
To modify the watering durations / moisture level / blocked times etc. you have to modify the Values at the top of the Programm.
if you want to use more Plants, you need to add the corresponding pin for the relay and add the desired values to the parameter arrays.

Generally, if you modify it, every array that has two elements, need to have as many elements als you have pumps.
(Besides the start and end times for blocking the Pumps)
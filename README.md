# smartplug2mqtt
Tuya smatplug (with power monitoring) to mqtt

Newer Tuya firmware does not work with tyua-convert OTA.
Some Smart Plugs are too difficulty to open and flash tasmota via serial.

This is a simple app to interface smart plugs to local mqtt.
I used the excellent https://github.com/TradeFace/tuyaface to read the data from the smart plug.

**How to get the IP, devId, localKey for your smart plug**
No need to root your phone - use NOX
1) Register the plug as ususal on you smart phone.

2) Install NOX Android Emulator (Could use LDPlayer or BlueStacks)
Download an old version of SmartLife 3.4.1 (or earlier) from apkmirror or other APK repo
https://www.apkmirror.com/uploads/page/2/?q=smart-life-smart-living
Newer versions store the keys elsewhere.
Install SmartLife 3.4.1 to NOX (just drag downlaoaded APK onto to the NOX window)
Login to SmartLife 3.4.1 on NOX, this will save the keys locally.
Use an Android file bowser to access 
NOX:/data/data/com.tuya.smartlife/shared_prefs/preferences_global_key_<some chars and numbers>.xml
Search for devID and localKey in the XML
You may need to enable root on the NOX gui.

**plug11-sample.json**
Update the IP, devId, localKey to the json file

**plug.py**
Update the mqtt credentials in plug.py
Run plug.py plug11-sample.json

This will pull the Power(W), Current(A), Voltage(V) from the plug and push the data to mqtt to emulate tasmota native.

The app keeps track of Today(kWh),Yesterday(kWh) and Total(kWh) and includes that in the mqtt payload.
Not ideal, but good enuf until tasmota-convert OTA starts working again.

# A simple program to print the devices' MAC address
import network

########################################
# OBJECTS
wlan = network.WLAN(network.STA_IF)    # The WLAN object for a station. Use AP_IS for an access point

########################################
# PROGRAM
print("ESP32 WLAN (Wifi) MAC address program")

wlan.active(True)                      # Activate the WLAN

if wlan.active():                      # Check if the WLAN is active

    mac_address = wlan.config("mac")   # Returns the MAC address in six bytes
    
    print("The MAC address is: ", end = "")
    for i in range(5):
        print("%02X:" % mac_address[i], end = "")
    print("%02X" % mac_address[5])     # Print the last byte without the trailing colon

else:
     print("WLAN is not active")


# Smart Home ESP-NOW handling functions module
# https://docs.micropython.org/en/latest/library/espnow.html
# https://www.donskytech.com/exploring-esp-now-in-micropython-a-learners-guide/

import network
import espnow

########################################
# OBJECTS
sta = network.WLAN(network.STA_IF)     # Or network.AP_IF
sta.active(True)                       # WLAN interface must be active to send()/recv()

en = espnow.ESPNow()                   # ESP-NOW object
en.active(True)                        # Make ESP-NOW active

########################################
# CONSTANTS
MAC_ADDR_BROADCAST = const(b'\xFF\xFF\xFF\xFF\xFF\xFF') # ESP-NOW broadcast MAC address

########################################
# FUNCTIONS
# Add MAC address to the list of receivers
def esp_now_add_mac_address(mac_addr):
    en.add_peer(mac_addr)

# Delete a MAC address from the list of receivers
def esp_now_delete_mac_address(mac_addr):
    en.del_peer(mac_addr)

# Send a message to the receiver with the MAC address
def esp_now_send_message(mac_addr, string):
    try:
        en.send(mac_addr, string, False)
    except ValueError as e:
        print("Error sending the message: " + str(e))    
# Checks if there is a message and if so returns it. Can echo the received message    
def esp_now_receive_message(echo = False):
    try:    
        tx, msg = en.recv(10)              # Check if there is something to receive, 10 ms timeout. Default is 300 s!
        
        if msg:                            # msg == None if timeout in recv()
            if echo == True:
                print(host, msg)
            return tx, msg
        else:
            return None, None
    
    except ValueError as e:
        print("Error receiving: " + str(e))
        return None, None
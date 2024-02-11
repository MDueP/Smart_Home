#######################################
# IMPORTS for all
from machine import ADC, Pin, PWM

import network

########################################
# OBJECTS
adc_lmt84 = ADC(Pin(35))             
adc_lmt84.atten(ADC.ATTN_2_5DB)        # 100 mV to 1,25 V, i.e. from about -40 °C and up to the maximum temperature for the LMT84
# LMT84 datasheet
# V = (-5.50 mV/°C) T + 1035 mV
# T = (V - 1035 mV) / (-5.5 mV/°C)
alpha = 0                              # Temperature coefficients
beta = 0                               # temp = alpha * ADC_value + beta
########################################
# FUNCTIONS

# Returns the MAC address A simple function returning the devices' MAC address in a 
def get_mac_address():
    
    wlan = network.WLAN(network.STA_IF)# The WLAN object for a station. Use AP_IS for an access point
    wlan.active(True)                  # Activate the WLAN

    if wlan.active():                  # Check if the WLAN is active
        mac_address =  wlan.config("mac")  # Returns the MAC address in six bytes
        mac_string = ("%02X:%02X:%02X:%02X:%02X:%02X") % (mac_address[0], mac_address[1], mac_address[2], mac_address[3], mac_address[4], mac_address[5])
    else:
        mac_string = "MAC address not found!"
        
    return mac_string

# Returns the onboard LMT84 temperature averaged over 64 measurements
def get_temperature():
    adc_val = 0
    for i in range (64):
        adc_val += adc_lmt84.read()
    adc_val = adc_val >> 6
    
    temp = alpha * adc_val + beta

    return temp

# Returns the onboard LMT84 ADC value averaged over 256 measurements
def get_temp_adc():
    adc_val = 0
    for i in range (256):
        adc_val += adc_lmt84.read()
    adc_val = adc_val >> 8
    
    return adc_val

# Set calibration values and calculate alpha and beta
def set_temp_calibration(temp1, adc1, temp2, adc2):
    global alpha
    global beta
    
    alpha = (temp2 - temp1) / (adc2 - adc1)
    beta = temp2 - alpha * adc2        # or beta = temp1 - alpha * adc1
    
    print("LMT84: alpha: %f, beta: %f" % (alpha, beta))

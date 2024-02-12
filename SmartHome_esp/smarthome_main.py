# Smart Home program. Reads local devices and external sensors and controls external devices
# Hardware platform is an Educaboard
# MicroPython and ESP32 https://docs.micropython.org/en/latest/esp32/quickref.html
#
import sys, uselect                    # Needed for USB port use
from machine import ADC, I2C, Pin, PWM, SPI, UART
import time
from time import sleep

########################################
# OWN MODULES
# Generic libraries not specific to this program
from eeprom_24xx64 import EEPROM_24xx64
from portExp_MCP23S08 import PortExp_MCP23S08
from gps_simple import GPS_SIMPLE

# Modules specific to this program 
import smarthome_espnow as en
import smarthome_lcd as lcd
import smarthome_misc as misc

########################################
# CONFIGURATION
splash_strings = [                     # Welcome splash screen text, 20 charcters wide three lines
        "KEA IT Teknolog 2024",
        "Indlejrede Systemer ",
        "Smart Home Dashboard",
        "                    "]        # The fourth line will be replaced with the MAC address
        #01234567890123456789
SPLASH_DELAY = const(0)                # Splash screen delay on the LCD

MAX_NUMBER_RECEIVERS = const(5)        # The max number of receivers

SHOW_BROADCAST_MESSAGES = const(True)  # enable/disable showing revceived broadcast messages

BROADCAST_INTERVAL = const(1000 * 60)  # Troubleshooting auto broadcast interval in ms, 0 = no broadcast

MY_NAME = const("Bo")                  # Your own handle

########################################
# EEPROM MAP
EEPROM_TEMP_1 = const(4096)            # Float, 4 bytes
EEPROM_TEMP_2 = const(4100)            # Float, 4 bytes
EEPROM_ADC_1 = const(4104)             # Word, 2 bytes
EEPROM_ADC_2 = const(4106)             # Word, 2 bytes
EEPROM_MAC_ADDR_START = const(4108)    # Six bytes per entry * MAX_NUMBER_RECEIVERS

########################################
# OBJECTS
# Push buttons
pb1 = Pin(4, Pin.IN)                   # External pull-up and debounce
pb2 = Pin(0, Pin.IN)                   # Direct connection with pull-up thus inverted

# LED1
led1 = Pin(26, Pin.OUT)                # LED1 is the red LED, LED2 and LED3 via port expander

# LCD contrast
potmeter_adc = ADC(Pin(34))            # The ADC object
potmeter_adc.width(ADC.WIDTH_10BIT)    # Set the potmeter ADC to 10 bits to match the PWM width. THIS APPLIES TO ALL ADC USE HEREAFTER!
potmeter_adc.atten(ADC.ATTN_11DB)      # Full range: 3,3 V
lcd_contrast = PWM(Pin(23))            # Create PWM object from a pin

# UART
uart = UART(2, 9600)                   # UART object creation
# GPS
gps = GPS_SIMPLE(uart, False)          # GPS object creation

# I2C bus
i2c = I2C(0)                           # I2C H/W 0 object
# EEPROM
eeprom = EEPROM_24xx64(i2c, 0x50)      # The EEPROM object on I2C address 0x50

# SPI BUS
hspi = SPI(1, 10000000)                # Create the SPI bus object running on HSPI/1 at 10 MHz
# MCP23S08
pin_portexp_cs = 15                    # The MCP23S08 CS pin number
pin_portexp_int = 2                    # The MCP23S08 interrupt pin on the ESP32
port_exp_addr = 0                      # The MSP23S08 subaddress, not a real SPI thing!
port_exp = PortExp_MCP23S08(hspi, pin_portexp_cs, port_exp_addr)

usb = uselect.poll()                   # Set up an input polling but non-blocking object
usb.register(sys.stdin, uselect.POLLIN)# Register polling object

########################################
# VARIABLES
mac_addr_receiver = [                  # The list holding the MAC address of the receivers
    [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF],
    [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF],
    [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF],
    [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF],
    [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]]

# Non blocking flow control broadcast
time_last_broadcast = 0

########################################
# FUNCTIONS
def ctrlC():
    try:
        pass
    except KeyboardInterrupt:
        print("Ctrl+C pressed - exiting program.")
        sys.exit()
        
        
def get_mac_addr_bstring(index):
    if index < MAX_NUMBER_RECEIVERS:
        mac_addc_bstring = bytes([mac_addr_receiver[index][0],
                                 mac_addr_receiver[index][1],
                                 mac_addr_receiver[index][2],
                                 mac_addr_receiver[index][3],
                                 mac_addr_receiver[index][4],
                                 mac_addr_receiver[index][5]])
        return mac_addc_bstring
   
   
def print_mac_addr_list():
    for i in range(MAX_NUMBER_RECEIVERS):
        print("MAC%2d: " % i, end = "")
        for j in range(6):             # Each entry takes six bytes
            byte = mac_addr_receiver[i][j]
            if j < 5:
                print("%02X:" % byte, end = "")
            else:
                print("%02X" % byte)   # Print the last byte without the trailing colon


def usb_scan_and_parse(cmd_echo = True):
    # Receive user input from the USB and send commands to the remote UART
    if usb.poll(0):                    # Check if there is any USB data available
        string = sys.stdin.readline()  # Read one line at a time
        sys.stdin.readline()           # WEIRD! - Needed to avoid a second handling of the same input
        string = string.strip()        # Remove leading and trailing white spaces and control characters from received string
        print("Command: " + string)    # Echo the USB string on the USB port
        
        # Check if the input is a valid command and if so send it to the remote unit
        
        # Print the dashboard's MAC address, rd mac addr
        if string == "rd mac addr":
            mac_addr = misc.get_mac_address()
            print(mac_addr)            
        
        # List all the MAC addresses, rd mac list
        elif string == "rd mac list":
            print_mac_addr_list()
            
        # Clear the MAC address list
        elif string == "wr mac clear":
            for i in range(6 * MAX_NUMBER_RECEIVERS):    # Each entry takes six bytes and there are max 20 entries
                eeprom.write_byte(EEPROM_MAC_ADDR_START, 0xFF)
                
        # Update a receiver's MAC address, wr mac add NUM ADDR 
        elif string[0:11] == "wr mac upd ":
            parts = string.split()
            if len(parts) == 5:
                try:
                    number = int(parts[3])
                    mac_addr = str(parts[4])
                    
                    # Just a simple check of number and MAC address
                    if number >= 0 and number < MAX_NUMBER_RECEIVERS and len(mac_addr) == 17:
                        # Delete old entry from ESP-Now if any
                        existing_mac_addr_bstring = get_mac_addr_bstring(number)
                        try:
                            en.esp_now_delete_mac_address(existing_mac_addr_bstring)
                        except ValueError:
                            print("Failed to delete existing MAC address") 
                        
                        # Update the MAC address entry in the EEPROM
                        mac_addr_parts = mac_addr.split(':')
                        
                        for i in range(6):
                            mac_addr_byte = int(mac_addr_parts[i], 16)
                            if mac_addr_byte >= 0 and mac_addr_byte <= 0xFF:
                                eeprom.write_byte(EEPROM_MAC_ADDR_START + 6 * number + i, mac_addr_byte)# EEPROM: Each entry takes six bytes and there are max 20 entries
                            
                                mac_addr_receiver[number][i] = mac_addr_byte # MAC address list
                            else:
                                  print("Invalid MAC address")
                                  return    # No need to continue
                            
                        # Update ESP-Now
                        mac_addr_bstring = get_mac_addr_bstring(number)
                        en.esp_now_add_mac_address(mac_addr_bstring)
                        print(mac_addr_bstring)                        
                    else:
                        print("Invalid number and/or MAC address")
                except ValueError:
                   print("Invalid value(s)")             
            else:
                print("Invalid number of parameters")

        # Read the temperature ADC, rd temp adc
        elif string == "rd temp adc":
            adc_val = misc.get_temp_adc()
            print(adc_val)
            
        # Read the temperature, wr temp
        elif string == "rd temp":
            temp = misc.get_temperature()
            print("%.1f" % temp)
            
        # Broadcast a message, wr bc MESSAGE
        elif string[0:6] == "wr bc ":
            msg = string[6:]
            if len(msg) > 0 and len(msg) <= 250:
                esp_now_send_message(en.MAC_ADDR_BROADCAST, msg)
            else:
                print("Message missing or to long")
                
        # Send a mesage to a receiver, wr rx NUM MESSAGE
        elif string[0:6] == "wr rx ":
            parts = string.split()
            if len(parts) >= 4:
                try:
                    number = int(parts[2])
                    if number >= 0 and number < MAX_NUMBER_RECEIVERS:
                        pos_of_number = string.find(parts[2]) # Find the start of the message by finding the location of the number of receiver
                        msg = string[pos_of_number + 2:] # Extract the message from the string, +2 because of the number and the following space
                        if len(msg) > 0 and len(msg) <= 250:
                            mac_addr_bstring = get_mac_addr_bstring(number)  # Replace with receiver index
                            en.esp_now_send_message(mac_addr_bstring, msg)
                        else:
                            print("Message missing or to long")
                    else:
                        print("Invalid receiver")
                except ValueError:
                   print("Invalid value(s)")                    
            else:
                print("Incomplete command")                
            
        # Write the temperature calibration values, wr temp cal T1 ADC1 T2 ADC2 (wr temp cal 0 750 21.5 666)
        elif string[0:12] == "wr temp cal ":
            parts = string.split()
            if len(parts) == 7:
                try:
                    t1 = float(parts[3])
                    adc1 = int(parts[4])
                    t2 = float(parts[5])
                    adc2 = int(parts[6])
                    misc.set_temp_calibration(t1, adc1, t2, adc2)
                    
                    # Save the calibration values to the EEPROM
                    eeprom.write_float(EEPROM_TEMP_1, t1)
                    eeprom.write_word(EEPROM_ADC_1, adc1)
                    eeprom.write_float(EEPROM_TEMP_2, t2)
                    eeprom.write_word(EEPROM_ADC_2, adc2)
                except ValueError:
                   print("Invalid value(s)")                    
            else:
                print("Invalid number of parameters")
            
        
        # Print help texts
        elif string == "help" or string == "?":
            print("\nAvailable commands")
            print("------------------")
            print("rd mac addr               to read this device\'s MAC address")
            print("rd mac list               to list the MAC addresses of the receivers")
            print("wr mac clear              to clear the MAC address list")
            print("wr mac upd NUM ADDR       to update receiver NUMber\'s MAC ADDRess")
            print()
            print("rd temp                   to read the LMT84 temperature")
            print("rd temp adc               to read the LMT84 ADC value at the present temperature")
            print("wr temp cal T1 A1 T2 A2   to write the LMT84 ADC calibration values, where X# is temp. is A# values")
            print()
            print("wr bc MESSAGE             to broadcast the MESSAGE")
            print("wr rx NUM MESSAGE         to send a MESSAGE to receiver NUMber")
            
            print("\nReplace upper case words with relevant data\n")

        else:                                
            print("Unknown command")   # Command not found so prompt the user

########################################
# PROGRAM

# INITIALIZATION
# Splash screen on USB and LCD
splash_strings[3] = " " + misc.get_mac_address() # MAC address in fourth line, overwriting existing data if any
for i in range(3):
    print(splash_strings[i])           # Print on the USB port
print("\nMAC  :" + splash_strings[3])
lcd.print_splash_screen(splash_strings)

# Load temperature coefficients from the EEPROM and set the calibration
t1 = eeprom.read_float(EEPROM_TEMP_1)
adc1 = eeprom.read_word(EEPROM_ADC_1)
t2 = eeprom.read_float(EEPROM_TEMP_2)
adc2 = eeprom.read_word(EEPROM_ADC_2)
misc.set_temp_calibration(t1, adc1, t2, adc2)

# Load receivers' MAC addresses into list and print to dashboard
for i in range(MAX_NUMBER_RECEIVERS):
    for j in range(6):
        mac_addr_receiver[i][j] = eeprom.read_byte(EEPROM_MAC_ADDR_START + 6 * i + j)
        
print("Receivers\' MAC addresses")
print_mac_addr_list()            
        
# Load ESP-Now with MAC-addresses
for i in range(MAX_NUMBER_RECEIVERS):
    mac_addr_bstring = get_mac_addr_bstring(i)  # Get a binary string with the MAC address
    if mac_addr_bstring != en.MAC_ADDR_BROADCAST: # Don't add broadcast MAC address (same as cleared list)
        en.esp_now_add_mac_address(mac_addr_bstring) # Add the MAC address to ESP-NOW
en.esp_now_add_mac_address(en.MAC_ADDR_BROADCAST)  # Always add broadcast address

# Initialize the port expander
port_exp.write_register(port_exp.IODIR, 0xF0) # Bulk setting of GP7:4 as input and GP3:0 as output, datasheet 1.6.1
port_exp.gp_pullup(5, port_exp.ON)     # Enable pull-up on GP5, datasheet 1.6.7
port_exp.gp_pullup(6, port_exp.ON)     # Enable pull-up on GP6, datasheet 1.6.7

# Initialization done, now ready for use
sleep(SPLASH_DELAY)
print("\nEnter   help   or   ?   for available commands\n")


# MAIN (super loop)
while True:
    # Check local devices
    pb1_val = pb1.value()              # Read onboard push button 1, active low
    pb2_val = pb2.value()              # Read onboard push button 2, active low
    pb3_val = port_exp.gp_get_value(5) # Read external push button via the port expander GP5, active low
    pb4_val = port_exp.gp_get_value(6) # Read external push button via the port expander GP6, active low
    
    temp = misc.get_temperature()      # Read the temperature from the LMT84
    
    pot_val = potmeter_adc.read()      # Read the potmeter and set the LCD contrast level
    lcd_contrast.duty(pot_val)
    
    gps_data_available = gps.receive_nmea_data()
    
    
    # Check ESP-NOW                    ************************************************************
    tx, msg = en.esp_now_receive_message() # Use (True) to echo received data while troubleshooting
    if msg:
        if tx != en.MAC_ADDR_BROADCAST:
            # now do something about it here
           print("Message from " + str(tx) + ": " + str(msg))
        elif SHOW_BROADCAST_MESSAGES == True: # Only show broadcast messages if wanted. Control in Configuration
            lcd.print_broadcast(msg)
            print("Broadcast from " + str(tx) + ": " + str(msg))
    
    
    # Control local devices
    led1.value(not pb1_val)            # LED1 control, active high but PB1 is active low so invert
    port_exp.gp_set_value(2, pb2_val)  # GP2: LED2 control, active low but PB2 is also active low
    port_exp.gp_set_value(3, not pb3_val) # GP3: LED3 control, active high but PB3 is active low so invert
    port_exp.gp_set_value(0, pb4_val)  # GP0: external LED4 via T1 control, active high, PB4 is active low, but T1 inverts so no invert
    
    # Hjemmearbejde: skriv temperatur og GPS info på LCD, find indspirtion i roamer.py
    if gps_data_available == True:
        None # Slet og lav noget selv her via en funktion in smarthome_lcd.py
    
    
    # Control ESP-NOW devices          ************************************************************
    # Send only if there is a change since last time!
    # mac_addr_bstring = get_mac_addr_bstring(0)  # Replace with receiver index 
    # en.esp_now_send_message(mac_addr_bstring, "The message")

    
    # Check USB port for commands
    usb_scan_and_parse()
    
    
    # Auto broadcast
    if BROADCAST_INTERVAL > 0:
        if time.ticks_diff(time.ticks_ms(), time_last_broadcast) > BROADCAST_INTERVAL:
            time_last_broadcast = time.ticks_ms() # Update the time for next time comparison
            en.esp_now_send_message(en.MAC_ADDR_BROADCAST, "Broadcast " + MY_NAME + ": " + str(time_last_broadcast))
            print("Broadcast " + MY_NAME + ": " + str(time_last_broadcast))

    
    # Check if Ctrl-C is pressed
    ctrlC()

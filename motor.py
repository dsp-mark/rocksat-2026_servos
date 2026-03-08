import os
import can
import time
import struct


## Super simple code: Just moves the servo 90 degrees forward, 90 degrees backwars, 180 forwards
## and then 180 backwards

INTERFACE = 'can0'
BITRATE = 1000000
MOTOR_ID = 0x141


# Takes the response from the servo and decodes it into something that can be read
# Bytes 4-7 have angle data
# Little-endian
def decode_position(data):
    pos_bytes = data[4:8]
    pos = struct.unpack('<i', pos_bytes)[0]
    # Need to turn it back into degrees
    return pos / 100.0

# 0x92 is a command asking to read current position
def read_position(bus):
    msg = can.Message(arbitration_id=MOTOR_ID, data=[0x92, 0, 0, 0, 0, 0, 0, 0])
    bus.send(msg)
    reply = bus.recv(timeout=0.5)
    # 0x241 is a reply from the servo
    if reply and reply.arbitration_id == 0x241 and reply.data[0] == 0x92:
        return decode_position(reply.data)
    return None

# Using the encoder to send absolute positions with the 0xA4 command
def move_absolute(bus, target_degrees, max_speed_dps=500):
    angle_raw = int(target_degrees * 100)
    max_speed_raw = max_speed_dps
    
    ## Providing the angle to go to (end) and the speed to go there with (first)
    ## It's CAN, so we gotta split it up.
    data = [0xA4, 0x00, max_speed_raw & 0xFF, (max_speed_raw >> 8) & 0xFF,
            angle_raw & 0xFF, (angle_raw >> 8) & 0xFF, (angle_raw >> 16) & 0xFF, (angle_raw >> 24) & 0xFF]
    
    ## Actually sending the message to the motor
    msg = can.Message(arbitration_id=MOTOR_ID, data=data)
    bus.send(msg)
    print(f"Sent move to {target_degrees}° (max {max_speed_dps} dps)")

# Waiting for the servo to get to a certain angle
def wait_for_target(bus, target_degrees, tolerance=2.0, timeout=10.0):
    print(f"Waiting to reach {target_degrees}°...")
    
    # Uses timeout to ensure the servo doesn't get stuck.
    start_time = time.time()
    while time.time() - start_time < timeout:
        pos = read_position(bus)
        if pos is not None:
            print(f"Current position: {pos:.1f}")

            if abs(pos - target_degrees) <= tolerance:
                print(f"Reached target {pos:.1f}")
                return True
        time.sleep(0.1)

    print("Timeout reaching target")
    return False

# Super basic run code.
def run_motion_sequence():
    # Setting up the bus using terminal
    os.system(f"sudo ip link set {INTERFACE} up type can bitrate {BITRATE} 2>/dev/null")
    
    # Setting up the actual bus used to communicate
    bus = can.interface.Bus(channel=INTERFACE, interface='socketcan')
    print(f"Connected to Motor 0x{MOTOR_ID:03X}")
    
    # Contacting servo to ask for status:
    # CURRENT PROBLEM: Servo not being found; sends a not acknowledged.
    print("Requesting Status (0x9C)...")
    msg = can.Message(arbitration_id=MOTOR_ID, data=[0x9C, 0, 0, 0, 0, 0, 0, 0])
    bus.send(msg)
    reply = bus.recv(1.0)

    # I'm not checking for errors here, so the error is read as actual values
    # even though it shouldn't be
    if reply:
        print(f"Status: {reply.data.hex()}, Temp: {reply.data[1]} deg C")
    
    # Realeasing brake for servos
    print("Releasing brake (0x77)...")
    bus.send(can.Message(arbitration_id=MOTOR_ID, data=[0x77, 0, 0, 0, 0, 0, 0, 0]))
    time.sleep(0.5)
    
    # This is basically just the arbitrary move forward then back
    sequence = [
        (90, "90 forward"),
        (-90, "90 backward"), 
        (180, "180 forward"),
        (-180, "180 backward")
    ]
    
    # Need to figure out where the servo is starting
    current_pos = read_position(bus)
    print(f"Starting position: {current_pos:.1f}" if current_pos else "Could not read initial position")
    
    # Tell servo to move, wait until it gets there, etc.
    for target_deg, description in sequence:
        move_absolute(bus, target_deg)
        wait_for_target(bus, target_deg)
        time.sleep(1.0)
    
    # Return servo to the beginning
    print("Returning to start...")
    if current_pos:
        move_absolute(bus, current_pos)
        wait_for_target(bus, current_pos)
    
    # Stopping motor
    print("Stopping motor (0x81)...")
    bus.send(can.Message(arbitration_id=MOTOR_ID, data=[0x81, 0, 0, 0, 0, 0, 0, 0]))
    
    bus.shutdown()


# Runs the run_motion_sequence() when program run (python motor.py)
if __name__ == "__main__":
    run_motion_sequence()
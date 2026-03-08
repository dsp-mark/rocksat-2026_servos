#!/bin/bash
INTERFACE="can0"
BITRATE=1000000

# Basically it runs through all the possible ids for the servo to see what the actual id is
# It closes and opens a new bus each time to avoid error passive from interfering
for ID in $(seq 1 32); do
    HEXID=$(printf "%03X" $((0x140 + ID)))
    echo "Scanning ID $ID (0x$HEXID)..."

    sudo ip link set $INTERFACE down
    sudo ip link set $INTERFACE up type can bitrate $BITRATE
    
    # Running general commands to see if it's able to get a response from this id
    cansend $INTERFACE ${HEXID}#9A00000000000000
    sleep 0.02
    cansend $INTERFACE ${HEXID}#9C00000000000000
    sleep 0.05

    # Checking the state to make sure it's okay
    STATE=$(ip -d link show $INTERFACE | grep -Po 'state \K[A-Z-]+')
    
    # ERROR-ACTIVE is default for CAN bus, so if it's ERROR-ACTIVE, it's working okay
    # Typically if it goes to ERROR-PASSIVE, it's not finding a servo (finding anything on the bus)
    if [[ "$STATE" == "ERROR-ACTIVE" || "$STATE" == "UP" ]]; then
        if candump $INTERFACE -n 1 -t d > /dev/null 2>&1; then
             echo ">>> MOTOR FOUND ON ID $ID!"
             exit 0
        fi
    fi
done
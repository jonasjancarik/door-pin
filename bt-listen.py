import utils
import time

bt = utils.Bluetoothctl()

approved_devices = utils.get_approved_devices()

approved_devices_by_mac = {
    approved_device["mac"]: approved_device for approved_device in approved_devices
}

while True:
    devices = bt.list_available_devices(scan_duration=11)

    if not devices:
        continue

    nearby_devices = set()

    print(devices)

    for mac, name in devices:
        nearby_devices.add(mac)

    # check if any of the nearby_devices are in paired_devices
    nearby_approved_devices = []

    for mac in nearby_devices:
        if mac in approved_devices_by_mac:
            nearby_approved_devices.append(approved_devices_by_mac[mac])

    if nearby_approved_devices:
        print(f"Unlocking, nearby approved devices: {nearby_approved_devices}")
        utils.unlock_door()
        time.sleep(3)

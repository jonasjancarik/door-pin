import bluetooth


def discover_devices():
    print("Searching for devices...")
    nearby_devices = bluetooth.discover_devices(duration=8, lookup_names=True)
    if not nearby_devices:
        print(
            "No devices found. Make sure your Bluetooth device is in discoverable mode."
        )
        return None
    return nearby_devices


def display_devices(devices):
    print("Found devices:")
    for index, device in enumerate(devices):
        addr, name = device
        print(f"{index + 1}: {name} ({addr})")


def select_device(devices):
    while True:
        choice = input("Enter the number of the device to pair: ")
        if choice.isdigit() and 1 <= int(choice) <= len(devices):
            return devices[int(choice) - 1]
        else:
            print("Invalid selection. Please try again.")


def pair_device(device):
    addr, name = device
    # The actual pairing process may require more than what's shown here, including handling PINs
    port = 1  # RFCOMM port used by most devices
    try:
        sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        sock.connect((addr, port))
        sock.close()
        print(f"Successfully connected to {name}.")
        return True
    except bluetooth.btcommon.BluetoothError as err:
        print(f"Failed to connect to {name}: {err}")
        return False


def main():
    devices = discover_devices()
    if devices:
        display_devices(devices)
        device_to_pair = select_device(devices)
        if pair_device(device_to_pair):
            print(f"Device {device_to_pair[1]} paired successfully.")
        else:
            print("Pairing failed.")


if __name__ == "__main__":
    main()

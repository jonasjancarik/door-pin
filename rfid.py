import utils
import datetime

try:
    from evdev import InputDevice, categorize, ecodes, list_devices

    evdev_imported = True
except ImportError:
    evdev_imported = False

RFID_LENGTH = 10  # Adjust this as per your RFID reader's UUID length


def save_rfid(apartment_number, rfid, creator_email, label):
    data = utils.load_data()
    salt = utils.generate_salt()
    hashed_rfid = utils.hash_secret(salt=salt, payload=rfid)
    entry = {
        "label": label,
        "hashed_rfid": hashed_rfid,
        "salt": salt,
        "creator_email": creator_email,
        "created_at": datetime.datetime.now().isoformat(),
    }
    data["apartments"].setdefault(
        apartment_number, {"users": [], "rfids": [], "devices": []}
    )
    data["apartments"][apartment_number].setdefault("rfids", [])
    data["apartments"][apartment_number]["rfids"].append(entry)
    utils.save_data(data)
    print(f"New RFID for apartment number {apartment_number} stored.")


def find_keyboards():
    """Find and return a list of keyboard devices."""
    devices = [InputDevice(path) for path in list_devices()]
    keyboards = [
        device
        for device in devices
        if "keyboard" in device.name.lower() or "event" in device.path
    ]
    return keyboards


def read_rfid_from_keyboards():
    keyboards = find_keyboards()
    if not keyboards:
        print("No keyboards found.")
        return None

    print("Scan RFID: ", end="", flush=True)
    rfid_input = ""

    while True:
        for keyboard in keyboards:
            for event in keyboard.read_loop():
                if event.type == ecodes.EV_KEY:
                    data = categorize(event)
                    if data.keystate == 1:  # Key down events only
                        if isinstance(data.keycode, list):
                            key_code = data.keycode[0]
                        else:
                            key_code = data.keycode

                        if "KEY_" in key_code:
                            key = key_code.split("_")[1].replace("KP", "")
                            if key.isdigit():
                                rfid_input += key
                                rfid_input = rfid_input[-RFID_LENGTH:]
                                print(f"\rScan RFID: {rfid_input}", end="", flush=True)

                                if len(rfid_input) == RFID_LENGTH:
                                    print(f"\nRFID input: {rfid_input}")
                                    return rfid_input
                            else:
                                print(
                                    "\nA non-digit key was pressed. Please only enter digits."
                                )
                                rfid_input = ""
                                print("Scan RFID: ", end="", flush=True)


def add_rfid(apartment_number, creator_email, label):
    if evdev_imported:
        print(
            "Would you like to enter RFID manually or scan using a connected reader? (m/s): ",
            end="",
            flush=True,
        )
        choice = input().strip().lower()
        if choice == "m":
            rfid = input("Enter RFID: ").strip()
        elif choice == "s":
            rfid = read_rfid_from_keyboards()
            if not rfid:
                print("Failed to read RFID from connected readers.")
                return
        else:
            print("Invalid choice.")
            return
    else:
        rfid = input("Enter RFID: ").strip()

    save_rfid(apartment_number, rfid, creator_email, label)


def delete_rfid(apartment_number, hashed_rfid):
    """Delete an existing RFID entry."""
    data = utils.load_data()

    if apartment_number not in data["apartments"]:
        print("Apartment number not found.")
        return False
    if "rfids" not in data["apartments"][apartment_number]:
        print("No RFIDs stored for this apartment.")
        return False
    new_rfids = [
        rfid
        for rfid in data["apartments"][apartment_number]["rfids"]
        if rfid["hashed_rfid"] != hashed_rfid
    ]
    data["apartments"][apartment_number]["rfids"] = new_rfids
    utils.save_data(data)
    print("RFID not found.")
    return False


def list_rfids():
    """List all RFIDs."""
    data = utils.load_data()
    for apartment_number, apartment in data["apartments"].items():
        print(f"Apartment Number: {apartment_number}")
        if "rfids" not in apartment or not apartment["rfids"]:
            print("  No RFIDs stored for this apartment.")
            continue
        for rfid in apartment.get("rfids", []):
            print(
                f"  Hashed RFID: {rfid['hashed_rfid']}, Creator: {rfid['creator_email']}, Label: {rfid['label']}, Created At: {rfid['created_at']}"
            )


def main():
    data = utils.load_data()
    while True:
        print("\n1. Create RFID\n2. Delete RFID\n3. List RFIDs\n4. Exit")
        choice = input("Enter your choice: ")
        if choice == "1":
            apartment_number = input("Enter apartment number (two digits): ")
            creator_email = input("Enter your email address: ")
            label = input("Enter a label for this RFID: ")
            add_rfid(apartment_number, creator_email, label)
        elif choice == "2":
            apartment_number = input("Enter apartment number (two digits): ")
            rfids = data["apartments"][apartment_number].get("rfids", [])
            if not rfids:
                print("No RFIDs stored for this apartment.")
                continue
            print("Select a RFID to delete:")
            for index, rfid in enumerate(rfids):
                print(
                    f"{index + 1}. Created by {rfid['creator_email']} on {rfid['created_at']}"
                )
            choice = int(input("Enter the number of the RFID to delete: ")) - 1
            if 0 <= choice < len(rfids):
                if delete_rfid(apartment_number, rfids[choice]["hashed_rfid"]):
                    print("RFID deleted.")
        elif choice == "3":
            print("\n")
            list_rfids()
        elif choice == "4":
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")


if __name__ == "__main__":
    main()

from dotenv import load_dotenv
import os
import utils
import db
import time

load_dotenv()

try:
    from evdev import InputDevice, categorize, ecodes, list_devices

    evdev_imported = True
except ImportError:
    evdev_imported = False

RFID_LENGTH = 10  # Adjust this as per your RFID tags UUID length


def find_keyboards():
    """Find and return a list of keyboard devices."""
    devices = [InputDevice(path) for path in list_devices()]
    keyboards = [
        device
        for device in devices
        if "keyboard" in device.name.lower() or "event" in device.path
    ]
    return keyboards


def read_rfid_from_keyboards(timeout=None):
    """
    Reads RFID input from keyboards (which can be an RFID reader) with an optional timeout.

    This function searches for keyboards and continuously reads input events from them.
    It expects the input events to be key down events and only considers digits as valid input.
    Once it receives a complete RFID input of a specified length, it returns the RFID input.
    If a timeout is specified and exceeded, the function returns None.

    Args:
        timeout (float, optional): The time limit in seconds for reading the RFID input. Defaults to None.

    Returns:
        str: The RFID input or None if the timeout is exceeded.

    Raises:
        None
    """
    try:
        keyboards = find_keyboards()
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

    if not keyboards:
        print("No keyboards found.")
        return None

    print("Scan RFID: ", end="", flush=True)
    rfid_input = ""
    start_time = time.time()

    while True:
        if timeout is not None and (time.time() - start_time) > timeout:
            print("\nTime limit exceeded. Failed to read RFID.")
            return None

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
                                rfid_input = rfid_input[-os.getenv("RFID_LENGTH", 10) :]
                                print(f"\rScan RFID: {rfid_input}", end="", flush=True)

                                if len(rfid_input) == os.getenv("RFID_LENGTH", 10):
                                    print(f"\nRFID input: {rfid_input}")
                                    return rfid_input
                            else:
                                print(
                                    "\nA non-digit key was pressed. Please only enter digits."
                                )
                                rfid_input = ""
                                print("Scan RFID: ", end="", flush=True)


def add_rfid(apartment_number, user_email, label):
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
        print("RFID reader not found. Please enter RFID manually.")
        rfid = input("Enter RFID: ").strip()

    salt = utils.generate_salt()
    hashed_rfid = utils.hash_secret(salt=salt, payload=rfid)

    # get creator id from email
    if user := db.get_user(user_email):
        user_id = user.id
    else:
        print("User not found.")
        return

    db.save_rfid(user_id, hashed_rfid, salt, label)
    print(f"New RFID for apartment number {apartment_number} stored.")


def main():
    while True:
        print("\n1. Create RFID\n2. Delete RFID\n3. List RFIDs\n4. Exit")
        choice = input("Enter your choice: ")
        if choice == "1":
            apartment_number = input("Enter apartment number: ")
            creator_email = input("Enter owner's email: ")
            label = input("Enter a label for this RFID: ")
            add_rfid(apartment_number, creator_email, label)
        elif choice == "2":
            apartment_number = input("Enter apartment number (empty for all): ")
            rfids = (
                db.get_all_rfids()
                if not apartment_number
                else [
                    rfid
                    for rfid in db.get_all_rfids()
                    if rfid.apartment.number == apartment_number
                ]
            )
            if not rfids:
                print("No RFIDs stored for this apartment.")
                continue
            print("Select a RFID to delete:")
            for index, rfid in enumerate(rfids):
                print(
                    f"{index + 1}. User: {rfid.user.email}, created at {rfid.created_at}, label: {rfid.label}"
                )
            choice = int(input("Enter the number of the RFID to delete: ")) - 1
            if 0 <= choice < len(rfids):
                if db.remove_rfid(rfids[choice].id):
                    print("RFID deleted.")
                else:
                    print("RFID not found.")
        elif choice == "3":
            print("\n")
            for rfid in db.get_all_rfids():
                print(
                    f"User: {rfid.user.email}, Label: {rfid.label}, Created at: {rfid.created_at}"
                )
        elif choice == "4":
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")


if __name__ == "__main__":
    main()

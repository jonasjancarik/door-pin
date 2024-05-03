import hashlib
import json
import datetime


def hash_pin(apartment_number, pin):
    """Hash a PIN using SHA-256 with apartment number as salt and return the hexadecimal string."""
    salted_pin = apartment_number + pin  # Combine apartment number and PIN for salting
    hasher = hashlib.sha256()
    hasher.update(salted_pin.encode("utf-8"))
    return hasher.hexdigest()


def load_pins():
    """Load PIN data from the JSON file."""
    try:
        with open("hashed_pins.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_pins(pins):
    """Save PIN data to the JSON file."""
    with open("hashed_pins.json", "w") as file:
        json.dump(pins, file, indent=4)


def create_pin(pins):
    """Create a new PIN entry."""
    apartment_number = input("Enter apartment number (two digits): ")
    pin = input("Enter PIN (four digits): ")
    creator_name = input("Enter your name: ")
    hashed_pin = hash_pin(apartment_number, pin)
    entry = {
        "hashed_pin": hashed_pin,
        "creator": creator_name,
        "created_at": datetime.datetime.now().isoformat(),
    }
    if apartment_number in pins:
        pins[apartment_number].append(entry)
    else:
        pins[apartment_number] = [entry]
    print(f"New PIN for apartment number {apartment_number} stored.")


def delete_pin(pins):
    """Delete an existing PIN entry."""
    apartment_number = input("Enter apartment number to delete PIN from (two digits): ")
    if apartment_number in pins:
        print("Select a PIN to delete:")
        for index, pin in enumerate(pins[apartment_number]):
            print(f"{index + 1}. Created by {pin['creator']} on {pin['created_at']}")
        choice = int(input("Enter the number of the PIN to delete: ")) - 1
        if 0 <= choice < len(pins[apartment_number]):
            del pins[apartment_number][choice]
            print("PIN deleted.")
            if not pins[apartment_number]:  # Remove the entry if no pins left
                del pins[apartment_number]
        else:
            print("Invalid PIN selection.")
    else:
        print("Apartment number not found.")


def list_pins(pins):
    """List all PINs."""
    for apartment_number, entries in pins.items():
        print(f"Apartment Number: {apartment_number}")
        for pin in entries:
            print(
                f"    Hashed PIN: {pin['hashed_pin']}, Creator: {pin['creator']}, Created At: {pin['created_at']}"
            )


def main():
    pins = load_pins()
    while True:
        print("\n1. Create PIN\n2. Delete PIN\n3. List PINs\n4. Exit")
        choice = input("Enter your choice: ")
        if choice == "1":
            create_pin(pins)
        elif choice == "2":
            delete_pin(pins)
        elif choice == "3":
            list_pins(pins)
        elif choice == "4":
            save_pins(pins)
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")
        save_pins(pins)  # Save after every operation


if __name__ == "__main__":
    main()

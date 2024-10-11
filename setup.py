import db
import csv
import os
import sqlalchemy.exc as sqlalchemy_exc

# Initialize the database
db.init_db()

# Ask user if they want to load a CSV file with apartments and users, if not, they'll do it interactively
load_csv = input(
    "Do you want to load a CSV file (users.csv) with apartments and users? (Y/n) "
)

if load_csv.lower() == "y" or load_csv == "":
    if not os.path.exists("users.csv"):
        print("users.csv file not found.")
        # ask for path
        csv_file = input("Enter the path to the CSV file: ")
    else:
        csv_file = "users.csv"

    try:
        data = csv.DictReader(open(csv_file))
    except FileNotFoundError:
        print("File not found.")

    # Loop through the CSV file and create a DB entry for each apartment
    for row in data:
        apartment_number = row["apartment_number"]
        apartment = db.get_apartment_by_number(apartment_number)
        if not apartment:
            apartment = db.add_apartment(apartment_number)
        row["apartment_id"] = apartment.id
        del row["apartment_number"]

        # Remove 'admin' and 'guest' keys
        row.pop("admin", None)
        row.pop("guest", None)

        created_user = db.add_user(row)
        if created_user:
            print(
                f"Added user {created_user.name} ({created_user.email}) to apartment {apartment_number} with role {created_user.role}"
            )
        else:
            print(
                f"Failed to add user {row['name']} ({row['email']}) to apartment {apartment_number}"
            )

else:
    # Ask user how many apartments to set up
    num_apartments = int(input("How many apartments would you like to set up? "))

    # Loop through the number of apartments and create a DB entry for each apartment
    for i in range(num_apartments):
        db.add_apartment(i + 1)

    # Ask if the user wants to add any users to the apartments
    add_users = input("Do you want to add users to the apartments? (y/n) ")

    if add_users.lower() == "y":
        # Loop through the apartments and add users to each apartment
        for i in range(num_apartments):
            apartment_number = i + 1
            num_users = None
            while not num_users:
                try:
                    num_users = int(
                        input(
                            f"How many users would you like to add to apartment {apartment_number}? "
                        )
                    )
                    if num_users == 0:
                        break
                except ValueError:
                    print("Invalid input. Please enter a number.")
                    continue
            for j in range(num_users):
                # ask for name, email, and role
                name = input(f"Enter the name for user {j + 1}: ")
                email = input(f"Enter the email for user {j + 1}: ")
                role = input(
                    f"Enter the role for user {name} (admin/apartment_admin/guest) [apartment_admin]: "
                ).lower()
                if role not in ["admin", "apartment_admin", "guest"]:
                    role = "apartment_admin"

                user = {
                    "name": name,
                    "email": email,
                    "role": role,
                    "apartment_id": db.get_apartment_by_number(apartment_number).id,
                }

                created_user = db.add_user(user)
                if created_user:
                    print(
                        f"Added user {created_user.name} ({created_user.email}) to apartment {apartment_number} with role {created_user.role}"
                    )
                else:
                    print(
                        f"Failed to add user {name} ({email}) to apartment {apartment_number}"
                    )

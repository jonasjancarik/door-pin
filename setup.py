from src import db
from src.logger import logger
import csv
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def init_database():
    try:
        db.init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        exit(1)


def validate_csv_structure(file_path: str) -> bool:
    required_columns = {"apartment_number", "name", "email", "role"}
    try:
        with open(file_path, "r") as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader, [])
            header_set = set(headers)

            if not required_columns.issubset(header_set):
                missing_columns = required_columns - header_set
                logger.error(
                    f"CSV is missing required columns: {', '.join(missing_columns)}"
                )
                return False

            logger.info(f"CSV headers: {headers}")

            for row_num, row in enumerate(reader, start=2):
                if len(row) != len(headers):
                    logger.error(f"Row {row_num} has an incorrect number of columns")
                    return False

                row_dict = dict(zip(headers, row))
                if not row_dict["apartment_number"].isdigit():
                    logger.error(
                        f"Row {row_num}: apartment_number must be a number, got {row_dict['apartment_number']} instead."
                    )
                    return False

                if not row_dict["email"]:
                    logger.error(f"Row {row_num}: email cannot be empty")
                    return False

                if row_dict["role"] not in ["admin", "apartment_admin", "guest"]:
                    logger.error(
                        f"Row {row_num}: invalid role. Must be admin, apartment_admin, or guest, got {row_dict['role']} instead."
                    )
                    return False

        return True
    except Exception as e:
        logger.error(f"Error validating CSV file: {e}")
        return False


def load_csv_data(file_path: str) -> List[Dict[str, str]]:
    if not validate_csv_structure(file_path):
        logger.error("CSV validation failed. Please check the file and try again.")
        return []

    try:
        with open(file_path, "r") as csvfile:
            reader = csv.DictReader(csvfile)
            data = list(reader)
            logger.debug(f"CSV headers: {reader.fieldnames}")
            logger.debug(f"First row: {data[0] if data else 'No data'}")
            return data
    except FileNotFoundError:
        logger.error(f"CSV file not found: {file_path}")
        return []
    except csv.Error as e:
        logger.error(f"Error reading CSV file: {e}")
        return []


def process_csv_row(row: Dict[str, str]) -> Optional[Dict[str, str]]:
    apartment_number = row.get("apartment_number")
    if not apartment_number:
        logger.warning(f"Skipping row without apartment number: {row}")
        return None

    apartment = db.get_apartment_by_number(apartment_number)
    if not apartment:
        apartment = db.add_apartment(apartment_number)
        logger.info(f"Created new apartment: {apartment_number}")

    user_data = {
        "apartment_id": apartment.id,
        "name": row.get("name"),
        "email": row.get("email"),
        "role": row.get("role", "apartment_admin"),
    }

    logger.debug(f"Processing row: {row}")
    logger.debug(f"Created user data: {user_data}")

    return user_data


def add_user(user_data: Dict[str, str]) -> None:
    created_user = db.add_user(user_data)
    if created_user:
        logger.info(
            f"Added user {created_user.name} ({created_user.email}) to apartment {user_data['apartment_id']} with role {created_user.role}"
        )
    else:
        logger.error(
            f"Failed to add user {user_data['name']} ({user_data['email']}) to apartment {user_data['apartment_id']}"
        )


def setup_from_csv(csv_file: str) -> bool:
    data = load_csv_data(csv_file)
    if not data:
        return False
    for row in data:
        user_data = process_csv_row(row)
        if user_data:
            add_user(user_data)
    return True


def setup_interactively() -> None:
    num_apartments = int(input("How many apartments would you like to set up? "))

    for i in range(num_apartments):
        apartment_number = i + 1
        db.add_apartment(apartment_number)
        logger.info(f"Added apartment {apartment_number}")

    add_users = (
        input("Do you want to add users to the apartments? (y/n) ").lower() == "y"
    )

    if add_users:
        for i in range(num_apartments):
            apartment_number = i + 1
            while True:
                try:
                    num_users = int(
                        input(
                            f"How many users would you like to add to apartment {apartment_number}? "
                        )
                    )
                    break
                except ValueError:
                    print("Please enter a valid number.")

            for j in range(num_users):
                name = input(f"Enter the name for user {j + 1}: ")
                email = input(f"Enter the email for user {j + 1}: ")
                role = input(
                    f"Enter the role for user {name} (admin/apartment_admin/guest) [apartment_admin]: "
                ).lower()
                if role not in ["admin", "apartment_admin", "guest"]:
                    role = "apartment_admin"

                user_data = {
                    "name": name,
                    "email": email,
                    "role": role,
                    "apartment_id": db.get_apartment_by_number(apartment_number).id,
                }
                add_user(user_data)


def main():
    # check if data.db exists and ask user if they want to delete it or rename it or exit
    if os.path.exists("data.db"):
        print("data.db already exists.")
        overwrite = input("Do you want to delete it? (y/n) ").lower()
        if overwrite == "y":
            os.remove("data.db")
            logger.info("data.db deleted.")
        else:
            new_name = input("Enter a new name for the database file: ")
            os.rename("data.db", new_name)
            logger.info(f"data.db renamed to {new_name}.")

    init_database()

    setup_method = input(
        "Do you want to load a CSV file (users.csv) with apartments and users? (Y/n) "
    ).lower()

    setup_successful = False
    if setup_method in ["y", ""]:
        csv_file = "users.csv"
        if not os.path.exists(csv_file):
            csv_file = input("Enter the path to the CSV file: ")
        setup_successful = setup_from_csv(csv_file)
    else:
        setup_interactively()
        setup_successful = True

    if setup_successful:
        logger.info("Setup completed successfully")
    else:
        logger.error("Setup failed. Please check the errors above and try again.")


if __name__ == "__main__":
    main()

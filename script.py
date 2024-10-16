# script.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import requests
import time
import uuid

app = FastAPI()

# Matrix domain and server URL
#matrix_domain = "localhost"  # Remote server domain
matrix_domain = "unifyhn.de"  # Remote server domain
server_url = f"http://{matrix_domain}:8081"

# Pydantic models for request data
class Course(BaseModel):
    course_name: str
    course_id: str
    students: List[str]

class MatrixLoginData(BaseModel):
    userId: str
    password: str
    courses: List[Course]

# Matrix login function
def login(username: str, password: str):
    url = f"{server_url}/_matrix/client/r0/login"
    headers = {"Content-Type": "application/json"}
    payload = {"type": "m.login.password", "user": username, "password": password}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        print(f"Logged in as {username}")
        return data.get("access_token"), data.get("user_id")
    except requests.RequestException as e:
        print(f"Login error: {e}")
        return None, None

# Matrix room creation function
def create_room(access_token: str, room_name: str, room_topic: str):
    url = f"{server_url}/_matrix/client/r0/createRoom"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": room_name,
        "topic": room_topic,
        "preset": "private_chat"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        room_id = response.json().get("room_id")
        print(f"Created room '{room_name}' with ID: {room_id}")
        return room_id
    except requests.RequestException as e:
        print(f"Error creating room: {e}")
        return None

# Fetch the list of rooms the user has joined
def get_joined_rooms(access_token: str):
    url = f"{server_url}/_matrix/client/r0/joined_rooms"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("joined_rooms", [])
    except requests.RequestException as e:
        print(f"Error getting joined rooms: {e}")
        return []

# Check if a room with the desired name already exists
def find_room_by_name(access_token: str, room_name: str):
    joined_rooms = get_joined_rooms(access_token)

    for room_id in joined_rooms:
        url = f"{server_url}/_matrix/client/r0/rooms/{room_id}/state/m.room.name"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                room_state = response.json()
                if room_state.get("name") == room_name:
                    print(f"Room '{room_name}' already exists with ID: {room_id}")
                    return room_id
        except requests.RequestException as e:
            print(f"Error checking room name: {e}")

    return None

# Invite users to room with rate limiting and improved error handling
def invite_users_to_room(access_token: str, room_id: str, user_list: List[str]):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    added_member_list_into_matrix_rooms = []
    for user in user_list:
        max_retries = 5
        retries = 0
        success = False
        while retries < max_retries and not success:
            # Removed txn_id and corrected the URL
            url = f"{server_url}/_matrix/client/r0/rooms/{room_id}/invite"
            payload = {"user_id": user}
            try:
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', '1'))
                    print(f"Rate limited when inviting {user}. Retrying after {retry_after} seconds.")
                    time.sleep(retry_after)
                    retries += 1
                    continue
                response.raise_for_status()
                print(f"Successfully invited {user} to room {room_id}")
                added_member_list_into_matrix_rooms.append(user)
                success = True
            except requests.HTTPError as http_err:
                status_code = http_err.response.status_code
                error_text = http_err.response.text
                print(f"HTTP error inviting {user}: {status_code} - {error_text}")
                if status_code == 403:
                    print(f"Permission denied when inviting {user}. Skipping.")
                    break  # Do not retry on permission errors
                elif status_code == 429:
                    retry_after = int(http_err.response.headers.get('Retry-After', '1'))
                    print(f"Rate limited when inviting {user}. Retrying after {retry_after} seconds.")
                    time.sleep(retry_after)
                    retries += 1
                else:
                    retries += 1
                    time.sleep(1)
            except Exception as err:
                print(f"Unexpected error inviting {user}: {err}")
                retries += 1
                time.sleep(1)
            if not success and retries >= max_retries:
                print(f"Failed to invite {user} after {max_retries} attempts.")

            time.sleep(0.1)  # Small delay between requests

    return added_member_list_into_matrix_rooms

# Matrix logout function
def logout(access_token: str):
    url = f"{server_url}/_matrix/client/r0/logout"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        print("Logout successful!")
    except requests.RequestException as e:
        print(f"Error logging out: {e}")

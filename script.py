from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import requests

app = FastAPI()

#matrix_domain = 'localhost'  # local
matrix_domain = '85.215.118.180'  # remote

# Synapse server details
server_url = "http://"+matrix_domain+":8081"


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
        return room_id
    except requests.RequestException as e:
        print(f"Error creating room: {e}")
        return None


# Invite users to room
def invite_users_to_room(access_token: str, room_id: str, user_list: List[str]):
    url = f"{server_url}/_matrix/client/r0/rooms/{room_id}/invite"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    added_member_list_into_matrix_rooms = []
    for user in user_list:
        payload = {"user_id": user}
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            print('response')
            print(response)
            print(f"Successfully invited {user} to room {room_id}")
            added_member_list_into_matrix_rooms.append(user)
        except requests.RequestException as e:
            print(f"Error inviting {user}: {e}")

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
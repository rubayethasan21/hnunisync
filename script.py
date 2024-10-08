import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI()

#matrix_domain = 'localhost'  # local
matrix_domain = "unifyhn.de"  # remote
#matrix_domain = '85.215.118.180'  # remote

# Synapse server details
server_url = "http://" + matrix_domain + ":8081"


# Pydantic models for request data
class Course(BaseModel):
    course_name: str
    course_id: str
    students: List[str]


class MatrixLoginData(BaseModel):
    userId: str
    password: str
    courses: List[Course]


# Matrix login function (async)
async def login(username: str, password: str):
    url = f"{server_url}/_matrix/client/r0/login"
    headers = {"Content-Type": "application/json"}
    payload = {"type": "m.login.password", "user": username, "password": password}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("access_token"), data.get("user_id")
        except httpx.HTTPStatusError as e:
            print(f"Login error: {e}")
            return None, None


# Matrix room creation function (async)
async def create_room(access_token: str, room_name: str, room_topic: str):
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

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            room_id = response.json().get("room_id")
            return room_id
        except httpx.HTTPStatusError as e:
            print(f"Error creating room: {e}")
            return None


# Invite users to room (async)
async def invite_users_to_room(access_token: str, room_id: str, user_list: List[str]):
    url = f"{server_url}/_matrix/client/r0/rooms/{room_id}/invite"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    added_member_list_into_matrix_rooms = []

    async with httpx.AsyncClient() as client:
        for user in user_list:
            payload = {"user_id": user}
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                print(f"Successfully invited {user} to room {room_id}")
                added_member_list_into_matrix_rooms.append(user)
            except httpx.HTTPStatusError as e:
                print(f"Error inviting {user}: {e}")

    return added_member_list_into_matrix_rooms


# Fetch the list of rooms the user has joined (async)
async def get_joined_rooms(access_token: str):
    url = f"{server_url}/_matrix/client/r0/joined_rooms"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("joined_rooms", [])
        except httpx.HTTPStatusError as e:
            print(f"Error getting joined rooms: {e}")
            return []


# Check if a room with the desired name already exists (async)
async def find_room_by_name(access_token: str, room_name: str):
    joined_rooms = await get_joined_rooms(access_token)

    async with httpx.AsyncClient() as client:
        for room_id in joined_rooms:
            url = f"{server_url}/_matrix/client/r0/rooms/{room_id}/state/m.room.name"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    room_state = response.json()
                    if room_state.get("name") == room_name:
                        print(f"Room '{room_name}' already exists with ID: {room_id}")
                        return room_id
            except httpx.HTTPStatusError as e:
                print(f"Error checking room name: {e}")

    return None


# Matrix logout function (async)
async def logout(access_token: str):
    url = f"{server_url}/_matrix/client/r0/logout"
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers)
            response.raise_for_status()
            print("Logout successful!")
        except httpx.HTTPStatusError as e:
            print(f"Error logging out: {e}")

# script.py

from typing import List
import asyncio
from nio import (
    AsyncClient,
    LoginResponse,
    RoomCreateResponse,
    RoomInviteResponse,
    RoomPreset,
)

# Matrix domain and server URL
#matrix_domain = "localhost"  # Remote server domain
matrix_domain = "unifyhn.de"  # Remote server domain
homeserver = f"http://{matrix_domain}:8081"

# Matrix login function
async def login(username: str, password: str):
    client = AsyncClient(homeserver, username)
    try:
        response = await client.login(password)
        if isinstance(response, LoginResponse) and response.access_token:
            print(f"Logged in as {username}")
            return client
        else:
            print(f"Failed to log in as {username}: {response}")
            await client.close()
            return None
    except Exception as e:
        print(f"Login error: {e}")
        await client.close()
        return None

# Matrix room creation function
async def create_room(client: AsyncClient, room_name: str, room_topic: str):
    try:
        response = await client.room_create(
            name=room_name,
            topic=room_topic,
            preset=RoomPreset.private_chat
        )
        if isinstance(response, RoomCreateResponse) and response.room_id:
            print(f"Created room '{room_name}' with ID: {response.room_id}")
            return response.room_id
        else:
            print(f"Failed to create room '{room_name}': {response}")
            return None
    except Exception as e:
        print(f"Error creating room: {e}")
        return None

# Fetch the list of rooms the user has joined
async def get_joined_rooms(client: AsyncClient):
    try:
        response = await client.joined_rooms()
        if response.rooms:
            return response.rooms
        else:
            return []
    except Exception as e:
        print(f"Error getting joined rooms: {e}")
        return []

# Check if a room with the desired name already exists
async def find_room_by_name(client: AsyncClient, room_name: str):
    joined_rooms = await get_joined_rooms(client)
    for room_id in joined_rooms:
        try:
            response = await client.room_get_state_event(room_id, "m.room.name")
            if response.content.get("name") == room_name:
                print(f"Room '{room_name}' already exists with ID: {room_id}")
                return room_id
        except Exception as e:
            print(f"Error checking room name: {e}")
    return None

# Invite users to room concurrently with error handling
async def invite_users_to_room(client: AsyncClient, room_id: str, user_list: List[str]):
    added_member_list_into_matrix_rooms = []
    tasks = []
    for user in user_list:
        task = invite_single_user(client, room_id, user, added_member_list_into_matrix_rooms)
        tasks.append(task)
    await asyncio.gather(*tasks)
    return added_member_list_into_matrix_rooms

# Helper function to invite a single user
async def invite_single_user(client, room_id, user, added_member_list_into_matrix_rooms):
    max_retries = 5
    retries = 0
    success = False
    while retries < max_retries and not success:
        try:
            response = await client.room_invite(room_id, user)
            if isinstance(response, RoomInviteResponse):
                print(f"Successfully invited {user} to room {room_id}")
                added_member_list_into_matrix_rooms.append(user)
                success = True
            else:
                print(f"Failed to invite {user}: {response}")
                retries += 1
                await asyncio.sleep(1)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                # Rate limit exceeded (429)
                retry_after = 1  # Adjust based on server response
                print(f"Rate limited when inviting {user}. Retrying after {retry_after} seconds.")
                await asyncio.sleep(retry_after)
                retries += 1
            elif "403" in error_str:
                # Forbidden error (403)
                print(f"Permission denied when inviting {user}. Skipping.")
                break  # Do not retry on permission errors
            else:
                print(f"Error inviting {user}: {e}")
                retries += 1
                await asyncio.sleep(1)
    if not success and retries >= max_retries:
        print(f"Failed to invite {user} after {max_retries} attempts.")

# Matrix logout function
async def logout(client: AsyncClient):
    try:
        await client.logout()
        await client.close()
        print("Logout successful!")
    except Exception as e:
        print(f"Error logging out: {e}")
        await client.close()
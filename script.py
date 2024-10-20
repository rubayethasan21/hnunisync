from typing import List
import asyncio
import logging
from nio import (
    AsyncClient,
    LoginResponse,
    RoomCreateResponse,
    RoomInviteResponse,
    RoomPreset,
)
from aiohttp import ClientConnectionError, ClientResponseError

# Matrix domain and server URL
matrix_domain = "unifyhn.de"  # Remote server domain
homeserver = f"http://{matrix_domain}:8081"

# Configure logging
logging.basicConfig(
    filename='hnunisync.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

# Matrix login function
async def login(username: str, password: str):
    client = AsyncClient(homeserver, username)
    try:
        response = await client.login(password)
        if isinstance(response, LoginResponse) and response.access_token:
            logging.info(f"Logged in as {username}")
            return client
        else:
            logging.error(f"Failed to log in as {username}: {response}")
            await client.close()
            return None
    except (ClientConnectionError, ClientResponseError) as e:
        logging.exception(f"Login error for user {username}: {e}")
        await client.close()
        return None

# Matrix room creation function with encryption
async def create_room(client: AsyncClient, room_name: str, room_topic: str):
    # First, check if a room with the same name already exists
    existing_room_id = await find_room_by_name(client, room_name)
    if existing_room_id:
        logging.info(f"Room '{room_name}' already exists with ID: {existing_room_id}. Returning existing room.")
        return existing_room_id

    # Proceed with room creation if it does not exist
    try:
        response = await client.room_create(
            name=room_name,
            topic=room_topic,
            preset=RoomPreset.private_chat
        )
        if isinstance(response, RoomCreateResponse) and response.room_id:
            room_id = response.room_id
            logging.info(f"Created room '{room_name}' with ID: {room_id}")

            # Enable encryption in the room
            encryption_response = await client.room_put_state(
                room_id,
                "m.room.encryption",
                {
                    "algorithm": "m.megolm.v1.aes-sha2"
                }
            )
            if encryption_response:
                logging.info(f"Encryption enabled for room '{room_name}' with ID: {room_id}")
            else:
                logging.error(f"Failed to enable encryption for room '{room_name}'")

            return room_id
        else:
            logging.error(f"Failed to create room '{room_name}': {response}")
            return None
    except (ClientConnectionError, ClientResponseError) as e:
        logging.exception(f"Error creating room '{room_name}': {e}")
        return None

# Fetch the list of rooms the user has joined
async def get_joined_rooms(client: AsyncClient):
    try:
        response = await client.joined_rooms()
        if response.rooms:
            logging.info(f"Retrieved joined rooms for user {client.user_id}")
            return response.rooms
        else:
            logging.info(f"No joined rooms found for user {client.user_id}")
            return []
    except (ClientConnectionError, ClientResponseError) as e:
        logging.exception(f"Error getting joined rooms for user {client.user_id}: {e}")
        return []

# Check if a room with the desired name already exists
async def find_room_by_name(client: AsyncClient, room_name: str):
    joined_rooms = await get_joined_rooms(client)
    for room_id in joined_rooms:
        try:
            response = await client.room_get_state_event(room_id, "m.room.name")
            if response.content.get("name") == room_name:
                logging.info(f"Room '{room_name}' already exists with ID: {room_id}")
                return room_id
        except (ClientConnectionError, ClientResponseError) as e:
            logging.warning(f"Error checking room name '{room_name}' in room {room_id}: {e}")
    logging.info(f"Room '{room_name}' does not exist for user {client.user_id}")
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
                logging.info(f"Successfully invited {user} to room {room_id}")
                added_member_list_into_matrix_rooms.append(user)
                success = True
            else:
                logging.warning(f"Failed to invite {user}: {response}")
                retries += 1
                await asyncio.sleep(1)
        except (ClientConnectionError, ClientResponseError) as e:
            error_str = str(e)
            if "429" in error_str:
                # Rate limit exceeded (429)
                retry_after = 1  # Adjust based on server response
                logging.warning(f"Rate limited when inviting {user}. Retrying after {retry_after} seconds.")
                await asyncio.sleep(retry_after)
                retries += 1
            elif "403" in error_str:
                # Forbidden error (403)
                logging.warning(f"Permission denied when inviting {user}. Skipping.")
                break  # Do not retry on permission errors
            else:
                logging.exception(f"Error inviting {user}: {e}")
                retries += 1
                await asyncio.sleep(1)
    if not success and retries >= max_retries:
        logging.error(f"Failed to invite {user} after {max_retries} attempts.")

# Matrix logout function
async def logout(client: AsyncClient):
    try:
        await client.logout()
        await client.close()
        logging.info(f"Logout successful for user {client.user_id}")
    except (ClientConnectionError, ClientResponseError) as e:
        logging.exception(f"Error logging out user {client.user_id}: {e}")
        await client.close()

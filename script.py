# script.py

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
    except Exception as e:
        logging.exception(f"Login error for user {username}: {e}")
        await client.close()
        return None

# Matrix room creation function with retry and backoff
async def create_room(client: AsyncClient, room_name: str, room_topic: str):
    max_retries = 5
    retry_delay = 1  # Initial delay of 1 second
    try:
        for attempt in range(max_retries):
            try:
                response = await client.room_create(
                    name=room_name,
                    topic=room_topic,
                    preset=RoomPreset.private_chat
                )
                if isinstance(response, RoomCreateResponse) and response.room_id:
                    logging.info(f"Created room '{room_name}' with ID: {response.room_id}")
                    return response.room_id
                else:
                    logging.error(f"Failed to create room '{room_name}': {response}")
            except Exception as e:
                logging.exception(f"Error creating room '{room_name}': {e}")
                if "429" in str(e):  # Handle rate limiting
                    retry_delay = min(30, retry_delay * 2)  # Exponential backoff, capped at 30s
                    logging.warning(f"Rate limited while creating room. Retrying in {retry_delay} seconds.")
                    await asyncio.sleep(retry_delay)
                else:
                    retry_delay = min(30, retry_delay * 2)  # Increase delay for any other error
                    await asyncio.sleep(retry_delay)
        return None  # Return None if retries fail
    except Exception as e:
        logging.exception(f"Critical error in room creation: {e}")
        return None

# Invite users to room concurrently with retry and backoff
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
    retry_delay = 1  # Start with a 1-second delay
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
                retry_delay = min(30, retry_delay * 2)  # Exponential backoff, capped at 30 seconds
                await asyncio.sleep(retry_delay)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                # Rate limit exceeded (429)
                retry_delay = min(30, retry_delay * 2)  # Increase retry delay exponentially
                logging.warning(f"Rate limited when inviting {user}. Retrying in {retry_delay} seconds.")
                await asyncio.sleep(retry_delay)
            elif "403" in error_str:
                # Forbidden error (403)
                logging.warning(f"Permission denied when inviting {user}. Skipping.")
                break  # Do not retry on permission errors
            else:
                logging.exception(f"Error inviting {user}: {e}")
                retries += 1
                retry_delay = min(30, retry_delay * 2)  # Increase retry delay for other errors
                await asyncio.sleep(retry_delay)
    if not success and retries >= max_retries:
        logging.error(f"Failed to invite {user} after {max_retries} attempts.")

# Matrix logout function
async def logout(client: AsyncClient):
    try:
        await client.logout()
        await client.close()
        logging.info(f"Logout successful for user {client.user_id}")
    except Exception as e:
        logging.exception(f"Error logging out user {client.user_id}: {e}")
        await client.close()

from nio import AsyncClient, RoomCreateResponse, LoginResponse, RoomInviteError, LoginError
import asyncio

matrix_domain = 'localhost'  # local
#matrix_domain = '85.215.118.180'  # remote

# Synapse server details
homeserver_url = f"http://{matrix_domain}:8081"

# Create an asynchronous client
client = AsyncClient(homeserver_url, "")


# Matrix login function using matrix-nio
async def login(username: str, password: str):
    # Create an instance of the Matrix client
    client = AsyncClient(homeserver_url, username)

    # Attempt to log in with the provided username and password
    response = await client.login(password)

    # Check the type of response
    if isinstance(response, LoginResponse):
        print(f"Login successful for {response.user_id}")
        return client.access_token, client.user_id
    else:
        print(f"Login failed: {response.message}")
        return None, None
#except Exception as e:
    #print(f"Login error: {e}")
    #return None, None

# Matrix room creation function using matrix-nio
async def create_room(access_token: str, room_name: str, room_topic: str):
    try:
        response = await client.room_create(name=room_name, topic=room_topic)
        if isinstance(response, RoomCreateResponse):
            print(f"Room '{room_name}' created with ID: {response.room_id}")
            return response.room_id
        else:
            print(f"Error creating room: {response}")
            return None
    except Exception as e:
        print(f"Error creating room: {e}")
        return None


# Invite users to room using matrix-nio
async def invite_users_to_room(access_token: str, room_id: str, user_list: list):
    added_member_list_into_matrix_rooms = []
    for user in user_list:
        try:
            response = await client.room_invite(room_id, user)
            if isinstance(response, RoomInviteError):
                print(f"Failed to invite {user}: {response.message}")
            else:
                print(f"Successfully invited {user} to room {room_id}")
                added_member_list_into_matrix_rooms.append(user)
        except Exception as e:
            print(f"Error inviting users: {e}")

    return added_member_list_into_matrix_rooms

# Fetch the list of rooms the user has joined using matrix-nio
async def get_joined_rooms(access_token: str):
    try:
        response = await client.joined_rooms()
        return response.rooms if hasattr(response, 'rooms') else []
    except Exception as e:
        print(f"Error getting joined rooms: {e}")
        return []


# Check if a room with the desired name already exists
async def find_room_by_name(access_token: str, room_name: str):
    joined_rooms = await get_joined_rooms(access_token)

    for room_id in joined_rooms:
        try:
            response = await client.room_get_state_event(room_id, "m.room.name")
            if response and response.content.get("name") == room_name:
                print(f"Room '{room_name}' already exists with ID: {room_id}")
                return room_id
        except Exception as e:
            print(f"Error checking room name: {e}")

    return None


# Matrix logout function using matrix-nio
async def logout(access_token: str):
    try:
        await client.logout()
        print("Logout successful!")
    except Exception as e:
        print(f"Error logging out: {e}")

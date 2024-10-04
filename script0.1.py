from nio import AsyncClient, RoomCreateResponse, RoomGetStateResponse, RoomInviteResponse, LoginResponse
import asyncio

# Matrix client initialization
client = AsyncClient("http://localhost:8080", "@admin:localhost")
password = "Hosting+12345"

async def ensure_user_in_room(client, user_id, room_name):
    room_id = None
    # Fetch the list of joined rooms
    joined_rooms = await client.joined_rooms()

    if joined_rooms.rooms:
        for room in joined_rooms.rooms:
            state = await client.room_get_state(room)
            if isinstance(state, RoomGetStateResponse):
                for event in state.events:
                    if event['type'] == 'm.room.name' and event['content'].get('name') == room_name:
                        room_id = room
                        break
            if room_id:
                break

    if room_id:
        # Room exists, invite the user to the room
        try:
            response = await client.room_invite(room_id, user_id)
            if isinstance(response, RoomInviteResponse):
                print(f"User {user_id} invited to room {room_id}")
            else:
                print(f"Failed to invite user {user_id} to room {room_id}: {response}")
        except Exception as e:
            print(f"Error inviting user {user_id} to room {room_id}: {e}")
    else:
        # Room does not exist, create the room and invite the user
        try:
            response = await client.room_create(name=room_name)
            if isinstance(response, RoomCreateResponse):
                room_id = response.room_id
                print(f"Room {room_name} created with ID {room_id}")
                invite_response = await client.room_invite(room_id, user_id)
                if isinstance(invite_response, RoomInviteResponse):
                    print(f"User {user_id} invited to new room {room_id}")
                else:
                    print(f"Failed to invite user {user_id} to new room {room_id}: {invite_response}")
            else:
                print(f"Failed to create room {room_name}: {response}")
        except Exception as e:
            print(f"Error creating room {room_name} and inviting user {user_id}: {e}")


async def add_user_to_rooms(user_id, rooms):
    try:
        await client.login(password)
        for room in rooms:
            room_name = room.get('room_name')
            if room_name:
                await ensure_user_in_room(client, user_id, room_name)
        await client.close()
        return {"status": "User added to specified rooms"}
    except Exception as e:
        print(f"Error: {e}")
        raise Exception(f"Failed to add user to rooms: {str(e)}")


# Matrix sync loop
async def sync_loop(client):
    while True:
        await client.sync(timeout=30000)  # Sync every 30 seconds


async def start_matrix_sync():
    try:
        login_response = await client.login(password)
        if isinstance(login_response, LoginResponse) and login_response.user_id:
            print(f"Logged in as {login_response.user_id}")
            asyncio.create_task(sync_loop(client))  # Run the sync loop in the background
        else:
            print("Failed to log in, missing user_id in response")
    except Exception as e:
        print(f"Failed to log in: {e}")
        raise Exception("Failed to start Matrix sync")
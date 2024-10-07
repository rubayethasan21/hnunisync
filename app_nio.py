from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from typing import List
import uuid
import asyncio  # Import asyncio for async matrix-nio functions

from script import (
    login, create_room, invite_users_to_room, logout, find_room_by_name, matrix_domain
)  # Import Matrix functions from script.py


app = FastAPI()

class Course(BaseModel):
    course_name: str
    course_id: str
    students: List[str]

# Add model to handle matrix login data from frontend
class MatrixLoginData(BaseModel):
    userId: str
    password: str
    courses: List[Course]


# Enable CORS to allow requests from frontend (localhost:8080)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for development)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Store browser session globally with unique session IDs
session_data = {}

# Define Pydantic models to handle incoming JSON data
class LoginData(BaseModel):
    username: str
    password: str
    loginOtp: str

class OtpData(BaseModel):
    otp: str
    session_id: str  # Send back the session_id with OTP submission


# Function to convert email domain for Matrix user IDs and exclude the logged-in user
def convert_emails_to_matrix_user_ids(emails, logged_in_user):
    matrix_user_ids = []
    for email in emails:
        username = email.split('@')[0]  # Extract username before the '@'
        # Exclude the logged-in user
        if username != logged_in_user:
            matrix_user_id = f"@{username}:{matrix_domain}"  # Construct Matrix user ID
            matrix_user_ids.append(matrix_user_id)

    return matrix_user_ids


# Endpoint to sync with Matrix and invite users to rooms
@app.post("/sync-with-matrix")
async def syncWithMatrix(matrix_login_data: MatrixLoginData):
    matrix_user_id = matrix_login_data.userId  # Logged-in Matrix user ID
    matrix_password = matrix_login_data.password
    courses = matrix_login_data.courses

    # Step 1: Login to Matrix (using `await` since it's an async function now)
    access_token, user_id = await login(matrix_user_id, matrix_password)
    if not access_token:
        raise HTTPException(status_code=401, detail="Login to Matrix failed.")

    # Step 2: Create rooms for each course and invite students
    rooms = []
    for course in courses:
        room_name = course.course_name
        matrix_user_ids = convert_emails_to_matrix_user_ids(course.students, matrix_user_id)

        # Step 2.1: Check if the room already exists (using `await`)
        room_id = await find_room_by_name(access_token, room_name)

        # Step 2.2: If the room doesn't exist, create a new one (using `await`)
        if not room_id:
            print(f"Room '{room_name}' does not exist. Creating a new one...")
            room_id = await create_room(access_token, room_name, f"Room for {room_name}")
            if not room_id:
                raise HTTPException(status_code=500, detail=f"Failed to create room {room_name}.")

        # Step 3: Invite users to the room (using `await`)
        added_member_list_into_matrix_rooms = await invite_users_to_room(access_token, room_id, matrix_user_ids)

        if added_member_list_into_matrix_rooms:
            added_member_list_into_matrix_rooms.append(f"@{matrix_user_id}:{matrix_domain}")
            rooms.append({"room_name": room_name, "room_id": room_id, "members": added_member_list_into_matrix_rooms})

    # Step 4: Logout after completing the task (using `await`)
    await logout(access_token)

# Playwright-based login and ILIAS course member extraction remains unchanged
@app.post("/ilias-login-and-get-course-member-info")
async def iliasLoginAndGetCourseMemberInfo(login_data: LoginData):
    login_url = ('https://login.hs-heilbronn.de/realms/hhn/protocol/openid-connect/auth'
                 '?response_mode=form_post&response_type=id_token&redirect_uri=https%3A%2F%2Filias.hs-heilbronn.de%2Fopenidconnect.php'
                 '&client_id=hhn_common_ilias&nonce=badc63032679bb541ff44ea53eeccb4e&state=2182e131aa3ed4442387157cd1823be0&scope=openid+openid')

    session_id = str(uuid.uuid4())

    # Launch Playwright and configure it to bypass detection
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    page = await context.new_page()

    # Use the following tricks to hide the headless browser:
    await page.evaluate("""() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'mimeTypes', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'userAgent', { get: () => navigator.userAgent.replace('HeadlessChrome', 'Chrome') });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });
    }""")

    session_data[session_id] = {"browser": browser, "page": page, "playwright": p}
    await page.goto(login_url)
    await page.fill('input[name="username"]', login_data.username)
    await page.fill('input[name="password"]', login_data.password)
    await page.click('input[name="login"]')

    await page.wait_for_selector('a[id="try-another-way"]', timeout=10000)
    await page.click('a[id="try-another-way"]')
    await page.wait_for_selector("button[name='authenticationExecution'][value='f3ab6699-08c5-422b-a48b-befb53dd758a']", timeout=10000)
    await page.click("button[name='authenticationExecution'][value='f3ab6699-08c5-422b-a48b-befb53dd758a']")

    await page.wait_for_selector("input[id='otp']", timeout=10000)
    await page.fill("input[id='otp']", login_data.loginOtp)
    await page.click('input[id="kc-login"]')
    await page.wait_for_url("**/ilias.php?baseClass=ilDashboardGUI&cmd=jumpToSelectedItems", timeout=60000)

    course_list_url = 'https://ilias.hs-heilbronn.de/ilias.php?cmdClass=ilmembershipoverviewgui&cmdNode=jr&baseClass=ilmembershipoverviewgui'
    await page.goto(course_list_url)
    await page.wait_for_url("**/ilias.php?cmdClass=ilmembershipoverviewgui&cmdNode=jr&baseClass=ilmembershipoverviewgui", timeout=60000)

    html_content = await page.content()
    courses = extract_courses(html_content)

    all_email_column_data = []
    for course in courses:
        course_html_content, emails = await visit_course_page_and_scrape(page, course)
        all_email_column_data.append({
            'course_name': course['name'],
            'course_id': course['refId'],
            'students': emails
        })

    return JSONResponse({"status": "success", "all_email_column_data": all_email_column_data})


def extract_courses(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    courses = []
    course_rows = soup.select('.il-std-item')
    for course_row in course_rows:
        img_element = course_row.select_one('img.icon')
        if img_element and img_element.get('alt') != 'Symbol Gruppe':
            course_name_element = course_row.select_one('.il-item-title a')
            if course_name_element:
                course_name = course_name_element.get_text(strip=True)
                course_url = course_name_element.get('href')
                course_ref_id = re.search(r'ref_id=(\d+)', course_url).group(1)
                courses.append({'name': course_name, 'refId': course_ref_id, 'url': course_url})
    return courses


async def visit_course_page_and_scrape(page, course):
    dynamic_url = f"https://ilias.hs-heilbronn.de/ilias.php?baseClass=ilrepositorygui&cmdNode=yc:ml:95&cmdClass=ilCourseMembershipGUI&ref_id={course['refId']}"
    await page.goto(dynamic_url)
    course_html_content = await page.content()
    emails = extract_email_column_from_table(course_html_content)
    return course_html_content, emails


def extract_email_column_from_table(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table', {'class': 'table table-striped fullwidth'})
    email_column_data = []
    for row in table.find('tbody').find_all('tr'):
        columns = row.find_all('td')
        if len(columns) >= 5:
            email_column_data.append(columns[4].text.strip())
    return email_column_data


# Root route to render index.html
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")

# app.py

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import re
from typing import List
import uuid
import asyncio
import logging

# Import Matrix functions from script.py
from script import (
    login,
    create_room,
    invite_users_to_room,
    logout,
    find_room_by_name,
    matrix_domain,
    demo_students_emails
)

# Configure logging
logging.basicConfig(
    filename='hnunisync.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

app = FastAPI()

# Enable CORS to allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (adjust as needed)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Define Pydantic models to handle incoming JSON data
class LoginData(BaseModel):
    username: str
    password: str
    loginOtp: str

class Course(BaseModel):
    course_name: str
    course_id: str
    students: List[str]

class MatrixLoginData(BaseModel):
    userId: str
    password: str
    courses: List[Course]

# Function to convert email addresses to Matrix user IDs and exclude the logged-in user
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
async def sync_with_matrix(matrix_login_data: MatrixLoginData):
    matrix_user_id = matrix_login_data.userId  # Logged-in Matrix user ID
    matrix_password = matrix_login_data.password
    courses = matrix_login_data.courses

    logging.info(f"Matrix sync initiated by user: {matrix_user_id}")

    # Step 1: Login to Matrix (async function call)
    client = await login(matrix_user_id, matrix_password)
    if not client:
        logging.error(f"Login to Matrix failed for user {matrix_user_id}")
        raise HTTPException(status_code=401, detail="Login to Matrix failed.")

    try:
        # Step 2: Create rooms for each course and invite students
        rooms = []
        for course in courses:
            room_name = course.course_name
            matrix_user_ids = convert_emails_to_matrix_user_ids(course.students, matrix_user_id)
            matrix_demo_user_ids = convert_emails_to_matrix_user_ids(demo_students_emails, matrix_user_id)

            matrix_user_ids = matrix_user_ids + matrix_demo_user_ids

            logging.info(f"Matrix User ids are listed: {matrix_user_ids}")

            logging.info(f"Processing course: {room_name}")

            # Step 2.1: Check if the room already exists (async function call)
            room_id = await find_room_by_name(client, room_name)

            # Step 2.2: If the room doesn't exist, create a new one (async function call)
            if not room_id:
                logging.info(f"Room '{room_name}' does not exist. Creating a new one...")
                room_id = await create_room(client, room_name, f"Room for {room_name}")
                if not room_id:
                    logging.error(f"Failed to create room '{room_name}' for user {matrix_user_id}")
                    raise HTTPException(status_code=500, detail=f"Failed to create room {room_name}.")

            # Step 3: Invite users to the room (async function call)
            added_member_list_into_matrix_rooms = await invite_users_to_room(client, room_id, matrix_user_ids)

            if added_member_list_into_matrix_rooms:
                added_member_list_into_matrix_rooms.append(f"@{matrix_user_id}:{matrix_domain}")
                rooms.append({
                    "room_name": room_name,
                    "room_id": room_id,
                    "members": added_member_list_into_matrix_rooms
                })
                logging.info(f"Users invited to room '{room_name}': {added_member_list_into_matrix_rooms}")

        # Step 4: Logout after completing the task (async function call)
        await logout(client)

    except Exception as e:
        logging.exception(f"An error occurred during synchronization for user {matrix_user_id}: {e}")
        await logout(client)
        raise HTTPException(status_code=500, detail=f"An error occurred during synchronization: {e}")

    logging.info(f"Matrix sync completed successfully for user {matrix_user_id}")
    return {
        "status": "success",
        "message": "Rooms created and users invited successfully.",
        "rooms": rooms
    }

# Playwright-based login and ILIAS course member extraction
@app.post("/ilias-login-and-get-course-member-info")
async def ilias_login_and_get_course_member_info(login_data: LoginData):
    login_url = (
        'https://login.hs-heilbronn.de/realms/hhn/protocol/openid-connect/auth'
        '?response_mode=form_post&response_type=id_token&redirect_uri=https%3A%2F%2Filias.hs-heilbronn.de%2Fopenidconnect.php'
        '&client_id=hhn_common_ilias&nonce=badc63032679bb541ff44ea53eeccb4e&state=2182e131aa3ed4442387157cd1823be0&scope=openid+openid'
    )

    session_id = str(uuid.uuid4())
    logging.info(f"ILIAS login initiated for user: {login_data.username}")

    # Launch Playwright and configure it to bypass detection
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            page = await context.new_page()

            # Use the following tricks to hide the headless browser
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'mimeTypes', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'userAgent', { get: () => navigator.userAgent.replace('HeadlessChrome', 'Chrome') });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });
            """)

            await page.goto(login_url)
            await page.fill('input[name="username"]', login_data.username)
            await page.fill('input[name="password"]', login_data.password)
            await page.click('input[name="login"]')

            # Handle OTP login
            try:
                await page.wait_for_selector('a[id="try-another-way"]', timeout=10000)
                await page.click('a[id="try-another-way"]')
                await page.wait_for_selector("button[name='authenticationExecution'][value='f3ab6699-08c5-422b-a48b-befb53dd758a']", timeout=10000)
                await page.click("button[name='authenticationExecution'][value='f3ab6699-08c5-422b-a48b-befb53dd758a']")

                await page.wait_for_selector("input[id='otp']", timeout=10000)
                await page.fill("input[id='otp']", login_data.loginOtp)
                await page.click('input[id="kc-login"]')
            except PlaywrightTimeoutError:
                logging.error(f"OTP login failed for user {login_data.username}")
                raise HTTPException(status_code=400, detail="OTP login failed. Please check your credentials and OTP.")

            # Wait for redirection to the dashboard
            try:
                await page.wait_for_url("**/ilias.php?baseClass=ilDashboardGUI&cmd=jumpToSelectedItems", timeout=60000)
                logging.info(f"ILIAS login successful for user {login_data.username}")
            except PlaywrightTimeoutError:
                logging.error(f"Failed to log in to ILIAS for user {login_data.username}")
                raise HTTPException(status_code=400, detail="Failed to log in to ILIAS. Please check your credentials.")

            # Navigate to course list
            course_list_url = 'https://ilias.hs-heilbronn.de/ilias.php?cmdClass=ilmembershipoverviewgui&cmdNode=jr&baseClass=ilmembershipoverviewgui'
            await page.goto(course_list_url)
            await page.wait_for_url("**/ilias.php?cmdClass=ilmembershipoverviewgui&cmdNode=jr&baseClass=ilmembershipoverviewgui", timeout=60000)

            html_content = await page.content()
            courses = extract_courses(html_content)
            logging.info(f"Extracted courses for user {login_data.username}: {[course['name'] for course in courses]}")

            all_email_column_data = []
            for course in courses:
                course_html_content, emails = await visit_course_page_and_scrape(page, course)
                all_email_column_data.append({
                    'course_name': course['name'],
                    'course_id': course['refId'],
                    'students': emails
                })
                logging.info(f"Extracted students for course '{course['name']}': {emails}")

            # Close browser sessions to free up resources
            await browser.close()
            logging.info(f"ILIAS data extraction completed for user {login_data.username}")

            return JSONResponse({"status": "success", "all_email_column_data": all_email_column_data})

    except Exception as e:
        logging.exception(f"An error occurred during ILIAS login for user {login_data.username}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during ILIAS login.")

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
                course_ref_id_match = re.search(r'ref_id=(\d+)', course_url)
                if course_ref_id_match:
                    course_ref_id = course_ref_id_match.group(1)
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
    if table:
        tbody = table.find('tbody')
        if tbody:
            for row in tbody.find_all('tr'):
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

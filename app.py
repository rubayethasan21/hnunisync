from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright
#from playwright_stealth import stealth
from bs4 import BeautifulSoup
import re
from typing import List

#from script import add_user_to_rooms
#import asyncio
import uuid

app = FastAPI()


# Pydantic models for request validation
class RoomData(BaseModel):
    user_id: str
    rooms: list

class Course(BaseModel):
    course_name: str
    course_id: str
    students: List[str]


# @app.post("/add_user_to_rooms")
# async def add_user_to_matrix_rooms(room_data: RoomData):
#     try:
#         result = await add_user_to_rooms(room_data.user_id, room_data.rooms)
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error adding user to rooms: {str(e)}")


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


def extract_courses(html_content):
    """Extracts course information from the provided HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    courses = []

    def get_ref_id(url):
        match = re.search(r'ref_id=(\d+)', url)
        return match.group(1) if match else ''

    course_rows = soup.select('.il-std-item')
    for course_row in course_rows:
        img_element = course_row.select_one('img.icon')
        if img_element and img_element.get('alt') != 'Symbol Gruppe':
            course_name_element = course_row.select_one('.il-item-title a')
            if course_name_element:
                course_name = course_name_element.get_text(strip=True)
                course_url = course_name_element.get('href')
                course_ref_id = get_ref_id(course_url)
                courses.append({
                    'name': course_name,
                    'refId': course_ref_id,
                    'url': course_url,
                })

    return courses


async def visit_course_page_and_scrape(page, course):
    """Creates a dynamic URL for each course, navigates to it, and scrapes the content."""
    dynamic_url = f"https://ilias.hs-heilbronn.de/ilias.php?baseClass=ilrepositorygui&cmdNode=yc:ml:95&cmdClass=ilCourseMembershipGUI&ref_id={course['refId']}"
    print(f"Visiting dynamic URL: {dynamic_url}")
    await page.goto(dynamic_url)

    course_html_content = await page.content()
    emails = extract_email_column_from_table(course_html_content)
    print(f"Email Column Data for {course['name']}:", emails)

    return course_html_content, emails


def extract_email_column_from_table(html_content):
    """Extracts the email column (Anmeldename) from the table in the provided HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table', {'class': 'table table-striped fullwidth'})

    email_column_data = []
    for row in table.find('tbody').find_all('tr'):
        columns = row.find_all('td')
        if len(columns) >= 5:
            email_column_data.append(columns[4].text.strip())  # Extract the text from the fifth column

    return email_column_data


# Root route to render index.html
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/ilias-login-and-get-course-member-info")
async def iliasLoginAndGetCourseMemberInfo(login_data: LoginData):
    login_url = ('https://login.hs-heilbronn.de/realms/hhn/protocol/openid-connect/auth'
                 '?response_mode=form_post&response_type=id_token&redirect_uri=https%3A%2F%2Filias.hs-heilbronn.de%2Fopenidconnect.php'
                 '&client_id=hhn_common_ilias&nonce=badc63032679bb541ff44ea53eeccb4e&state=2182e131aa3ed4442387157cd1823be0&scope=openid+openid')

    session_id = str(uuid.uuid4())

    # Launch Playwright and configure it to bypass detection
    p = await async_playwright().start()

    # Configure launch options to avoid headless detection
    browser = await p.chromium.launch(
        headless=True,  # Keep headless, but with tweaks
        args=["--disable-blink-features=AutomationControlled"],
    )

    # Create a new browser context with a custom User-Agent
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    page = await context.new_page()

    # Use the following tricks to hide the headless browser:
    await page.evaluate("""() => {
        // Override navigator.webdriver to false
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false,
        });

        // Mock the plugins and mimeTypes arrays
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],  // Fake plugins
        });

        Object.defineProperty(navigator, 'mimeTypes', {
            get: () => [1, 2, 3],  // Fake mime types
        });

        // Mock the user-agent to not show headless
        const newUA = navigator.userAgent.replace('HeadlessChrome', 'Chrome');
        Object.defineProperty(navigator, 'userAgent', {
            get: () => newUA,
        });

        // Other features, like the languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });

        // Disable detection of missing Chrome features
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 4,  // Fake CPU cores count
        });
    }""")

    # Store browser session for OTP handling
    session_data[session_id] = {"browser": browser, "page": page, "playwright": p}

    await page.goto(login_url)

    # Fill in login details
    await page.fill('input[name="username"]', login_data.username)
    await page.fill('input[name="password"]', login_data.password)

    await page.click('input[name="login"]')

    # Handle two-factor authentication selection
    await page.wait_for_selector('a[id="try-another-way"]', timeout=10000)
    await page.click('a[id="try-another-way"]')

    await page.wait_for_selector("button[name='authenticationExecution'][value='f3ab6699-08c5-422b-a48b-befb53dd758a']",
                                 timeout=10000)
    await page.click("button[name='authenticationExecution'][value='f3ab6699-08c5-422b-a48b-befb53dd758a']")

    # Wait for the OTP input field to appear
    await page.wait_for_selector("input[id='otp']", timeout=10000)

    # Fill OTP and submit
    await page.fill("input[id='otp']", login_data.loginOtp)
    await page.click('input[id="kc-login"]')

    # Ensure login is successful and take a screenshot for verification
    await page.wait_for_url("**/ilias.php?baseClass=ilDashboardGUI&cmd=jumpToSelectedItems", timeout=60000)
    #await page.screenshot(path="screenshot_full.png", full_page=True)

    # Navigate to the course list
    course_list_url = 'https://ilias.hs-heilbronn.de/ilias.php?cmdClass=ilmembershipoverviewgui&cmdNode=jr&baseClass=ilmembershipoverviewgui'
    await page.goto(course_list_url)
    await page.wait_for_url(
        "**/ilias.php?cmdClass=ilmembershipoverviewgui&cmdNode=jr&baseClass=ilmembershipoverviewgui", timeout=60000)

    html_content = await page.content()
    courses = extract_courses(html_content)

    # Extract email column data for each course
    all_email_column_data = []
    for course in courses:
        try:
            course_html_content, emails = await visit_course_page_and_scrape(page, course)
            all_email_column_data.append({
                'course_name': course['name'],
                'course_id': course['refId'],
                'students': emails
            })
        except Exception as e:
            print(f"An error occurred while processing course {course['name']}: {e}")
            continue

    return JSONResponse({
        "status": "success",
        "all_email_column_data": all_email_column_data
    })


@app.post("/sync-with-matrix")
async def syncWithMatrix(courses: List[Course]):
    course_dicts = [course.dict() for course in courses]  # Convert each Course object to a dictionary
    for course in course_dicts:
        print(f"Syncing course: {course['course_name']}")
        print(f"Students: {', '.join(course['students'])}")

    # Return a success response, JSON serializable by default
    return {"status": "success", "courses_synced": course_dicts}



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")

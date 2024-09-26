from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from script import add_user_to_rooms, start_matrix_sync  # Importing from script.py
import asyncio

import uuid


app = FastAPI()



# Pydantic models for request validation
class RoomData(BaseModel):
    user_id: str
    rooms: list


@app.post("/add_user_to_rooms")
async def add_user_to_matrix_rooms(room_data: RoomData):
    try:
        result = await add_user_to_rooms(room_data.user_id, room_data.rooms)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding user to rooms: {str(e)}")


#When FastAPI starts, we want to start the Matrix client and sync
# @app.on_event("startup")
# async def on_startup():
#     try:
#         await start_matrix_sync()  # Start Matrix sync loop
#         print("Matrix client started")
#     except Exception as e:
#         print(f"Error starting Matrix client: {e}")
#         raise HTTPException(status_code=500, detail="Failed to start Matrix client")






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

# Mount the static files directory for serving local static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Store browser session globally with unique session IDs
session_data = {}

# Define Pydantic models to handle incoming JSON data
class LoginData(BaseModel):
    username: str
    password: str

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
    print('visit_course_page_and_scrape')
    print(f"Scraped HTML for {course['name']} at {dynamic_url}:", course_html_content)


    emails = extract_email_column_from_table(course_html_content)
    #emails = 'extract_email_column_from_table(course_html_content)'
    print(f"Email Column Data for {course['name']}:", emails)

    return course_html_content, emails

def extract_email_column_from_table(html_content):
    """Extracts the email column (Anmeldename) from the table in the provided HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the table by class
    table = soup.find('table', {'class': 'table table-striped fullwidth'})

    # List to hold the username data
    email_column_data = []

    # Loop through all rows in the table body
    for row in table.find('tbody').find_all('tr'):
        # Get all columns (td elements)
        columns = row.find_all('td')
        if len(columns) >= 5:  # Ensure there are at least 5 columns
            email_column_data.append(columns[4].text.strip())  # Extract the text from the fifth column

    return email_column_data


# Root route to render index.html
@app.get("/")
async def index(request: Request):
    print('index')
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(login_data: LoginData):
    print('login')
    login_url = ('https://login.hs-heilbronn.de/realms/hhn/protocol/openid-connect/auth'
                 '?response_mode=form_post&response_type=id_token&redirect_uri=https%3A%2F%2Filias.hs-heilbronn.de%2Fopenidconnect.php'
                 '&client_id=hhn_common_ilias&nonce=badc63032679bb541ff44ea53eeccb4e&state=2182e131aa3ed4442387157cd1823be0&scope=openid+openid')

    try:
        # Create a unique session ID
        session_id = str(uuid.uuid4())

        # Launch Playwright (we no longer use `async with` to keep the browser running)
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=False)
        #browser = await p.chromium.launch(headless=True)
        #browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()


        # Store the browser, page, and playwright instance in session data
        session_data[session_id] = {"browser": browser, "page": page, "playwright": p}

        # Go to the login page
        await page.goto(login_url)

        # Fill in the username and password from the JSON data
        await page.fill('input[name="username"]', login_data.username)
        await page.fill('input[name="password"]', login_data.password)

        # Submit the login form
        await page.click('input[name="login"]')
        await page.wait_for_selector('a[id="try-another-way"]', timeout=6000)
        await page.click('a[id="try-another-way"]')
        #await page.wait_for_selector(
            #"button[name='authenticationExecution']:has-value('Eingabe eines Verifizierungscodes aus der Authenticator-Anwendung.')",
            #timeout=6000)
        await page.wait_for_selector(
            "button[name='authenticationExecution'][value='f3ab6699-08c5-422b-a48b-befb53dd758a']",
            timeout=6000
        )
        # Click the two-factor authentication button (OTP form)
        #await page.click(
            #"button[name='authenticationExecution']:has-text('Eingabe eines Verifizierungscodes aus der Authenticator-Anwendung.')")

        await page.click(
            "button[name='authenticationExecution'][value='f3ab6699-08c5-422b-a48b-befb53dd758a']"
        )

        await page.wait_for_selector('input[id="otp"]', timeout=6000)

        #html_content = await page.content()
        #print('html_content1', html_content)

        #session_data[session_id] = {"browser": browser, "page": page, "playwright": p}
        # Return a response to the frontend indicating OTP is needed and send session_id
        return JSONResponse({"status": "otp_required", "session_id": session_id})

    except Exception as e:
        # Handle errors such as timeouts or missing elements
        raise HTTPException(status_code=500, detail=f"An error occurred during login: {str(e)}")

# Submit OTP and continue the login process
@app.post("/submit-otp")
async def submit_otp(otp_data: OtpData):
    session_id = otp_data.session_id
    print('session_id', session_id)
    print('session_data', session_data)

    if session_id not in session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    page = session_data[session_id]["page"]
    browser = session_data[session_id]["browser"]

    print('page',page)
    print('browser',browser)

    #logging.debug(f"otp_data.otp: {otp_data.otp}")
    print('otp_data.otp', otp_data.otp)
    # Fill in the OTP from the JSON data
    await page.fill('input[id="otp"]', otp_data.otp)

    await page.click('input[id="kc-login"]')

    await page.wait_for_url("**/ilias.php?baseClass=ilDashboardGUI&cmd=jumpToSelectedItems",
                            timeout=60000)  # Wait up to 60 seconds


    course_list_url = 'https://ilias.hs-heilbronn.de/ilias.php?cmdClass=ilmembershipoverviewgui&cmdNode=jr&baseClass=ilmembershipoverviewgui'
    #course_list_url = 'https://ilias.hs-heilbronn.de/ilias.php?baseClass=ilmembershipoverviewgui'

    #await page.click("a[class='il-link link-bulky']:has-text('Meine Kurse und Gruppen')")

    await page.goto(course_list_url)
    await page.wait_for_url("**/ilias.php?cmdClass=ilmembershipoverviewgui&cmdNode=jr&baseClass=ilmembershipoverviewgui",
                            timeout=60000)

    #await page.goto(course_list_url)

    page_title = await page.title()
    print('page_title', page_title)
    #html_content = await page.content()
    #print('html_content4', html_content)
    #page_title = html_content
    #page_title = await page.title()

    html_content = await page.content()
    print('html_content',html_content)
    courses = extract_courses(html_content)
    print('Extracted Courses:', courses)

    all_email_column_data = []
    for course in courses:
        try:
            course_html_content, emails = await visit_course_page_and_scrape(page, course)
            all_email_column_data.append(
                {
                    'course_name': course['name'],
                    'course_id': course['refId'],
                    'students': emails
                }
            )


        except Exception as e:
            # If an error occurs, print it and continue with the next course
            print(f"An error occurred while processing course {course['name']}: {e}")
            continue

    # print('all_username_column_data', all_username_column_data)
    print('all_email_column_data', all_email_column_data)



    try:
        # Return the final page title
        return JSONResponse({"status": "success", "page_title": page_title, "all_email_column_data":all_email_column_data})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during OTP submission: {str(e)}")

    finally:
        # Ensure that the browser is closed after success or failure
        await browser.close()
        p = session_data[session_id]["playwright"]
        await p.stop()  # Stop Playwright instance
        session_data.pop(session_id, None)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")

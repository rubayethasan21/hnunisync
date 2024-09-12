from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright
import uuid

app = FastAPI()

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

# Root route to render index.html
@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/login")
async def login(login_data: LoginData):
    login_url = ('https://login.hs-heilbronn.de/realms/hhn/protocol/openid-connect/auth'
                 '?response_mode=form_post&response_type=id_token&redirect_uri=https%3A%2F%2Filias.hs-heilbronn.de%2Fopenidconnect.php'
                 '&client_id=hhn_common_ilias&nonce=badc63032679bb541ff44ea53eeccb4e&state=2182e131aa3ed4442387157cd1823be0&scope=openid+openid')

    print('here0')

    try:
        # Create a unique session ID
        session_id = str(uuid.uuid4())

        # Launch Playwright (we no longer use `async with` to keep the browser running)
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True)
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

        await page.click('a[id="try-another-way"]')

        # Click the two-factor authentication button (OTP form)
        await page.click(
            "button[name='authenticationExecution']:has-text('Eingabe eines Verifizierungscodes aus der Authenticator-Anwendung.')")

        html_content = await page.content()
        print('html_content1', html_content)

        # Return a response to the frontend indicating OTP is needed and send session_id
        return JSONResponse({"status": "otp_required", "session_id": session_id})

    except Exception as e:
        # Handle errors such as timeouts or missing elements
        raise HTTPException(status_code=500, detail=f"An error occurred during login: {str(e)}")

# Submit OTP and continue the login process
@app.post("/submit-otp")
async def submit_otp(otp_data: OtpData):
    session_id = otp_data.session_id
    if session_id not in session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    print('session_data', session_data)
    page = session_data[session_id]["page"]
    browser = session_data[session_id]["browser"]

    print('otp_data.otp', otp_data.otp)
    # Fill in the OTP from the JSON data
    await page.fill('input[id="otp"]', otp_data.otp)

    await page.click('input[id="kc-login"]')

    await page.wait_for_url("**/ilias.php?baseClass=ilDashboardGUI&cmd=jumpToSelectedItems",
                            timeout=60000)  # Wait up to 60 seconds

    page_title = await page.title()

    print('page_title', page_title)
    html_content = await page.content()
    print('html_content4', html_content)

    try:
        # Return the final page title
        return JSONResponse({"status": "success", "page_title": page_title})

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
    uvicorn.run(app, host="0.0.0.0", port=8000)

# HNUnisync.de - Synchronizing ILIAS Courses with Matrix Rooms

**HNUnisync.de** is a web application designed to streamline communication and collaboration for educational institutions by synchronizing **ILIAS** (a popular learning management system) courses with **Matrix** communication rooms. The tool automates the process of syncing enrolled students from ILIAS into Matrix rooms, creating a seamless integration between course content and collaborative discussion environments.

## Key Features

1. **User Authentication**:
   - Secure login using **HHN (Heilbronn University)** account credentials.
   - Authentication is managed via **OpenID Connect**.
   - Supports **two-step verification** using an authenticator app for added security.

2. **Course Synchronization**:
   - Automatically retrieves course data and enrolled student information from the **ILIAS** platform using web scraping.
   - Displays course and participant information, enabling quick synchronization with Matrix rooms.

3. **Matrix Integration**:
   - Users log into the Matrix server hosted at **[unifyhn.de](https://unifyhn.de)** to complete the course synchronization process.
   - Automatically creates Matrix rooms named after each course and adds enrolled students as members.

4. **Matrix-Based Communication**:
   - Students and instructors can use any Matrix-based messaging app (e.g., **Element** or **FluffyChat**) to join the created rooms and engage in discussions.

## Technologies Used

- **Python FastAPI**: For building the web application.
- **Playwright**: For web scraping ILIAS data.
- **Uvicorn**, **Pydantic**, **Jinja2**, **Gunicorn**: For server deployment, data validation, and template rendering.
- **BeautifulSoup4**: For parsing HTML data from ILIAS.
- **Matrix-Nio**: For interacting with the Matrix protocol.
- **Quart**, **Requests**, **Httpx**: For asynchronous operations and API requests.

## Installation & Setup

1. **Clone the Repository, Create Virtual Environment**:
   ```bash
   git clone https://github.com/rubayethasan21/hnunisync.git
   cd hnunisync
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Create Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   
4. **Start the Application**:
   ```bash
   uvicorn main:app --reload
   ```

5. **Access the Web Interface**:
   Open your browser and navigate to **[hnunisync.de](https://hnunisync.de)** to access the HNUnisync interface.

## Usage

- **Login**: Use your **HHN** credentials to log in securely.
- **Synchronize Courses**: Select the courses you want to synchronize and initiate the sync process.
- **Matrix Room Management**: Automatically manages the creation and updating of Matrix rooms for each course.
- **Real-time Collaboration**: Students can join the Matrix rooms using their preferred Matrix-based messaging apps.

## Contributing

Contributions are welcome! If you want to improve this project, please fork the repository and submit a pull request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the project.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a pull request.

## Contact

For questions or support, please reach out to the repository owner or open an issue in the repository.

## Links

- Project URL: [https://hnunisync.de](https://hnunisync.de)
- GitHub Repository: [https://github.com/rubayethasan21/hnunisync](https://github.com/rubayethasan21/hnunisync)

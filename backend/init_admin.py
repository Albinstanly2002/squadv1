import requests
import json
import os
from dotenv import load_dotenv

def init_admin():
    # Load environment variables
    load_dotenv()
    
    # Get admin credentials from environment variables
    credentials = {
        "username": os.getenv('ADMIN_USERNAME'),
        "password": os.getenv('ADMIN_PASSWORD')
    }
    
    if not all(credentials.values()):
        print("Error: Admin credentials not found in environment variables")
        return
    
    # Make request to initialize admin
    response = requests.post(
        "http://127.0.0.1:5000/api/admin/init",
        json=credentials
    )
    
    if response.status_code == 201:
        print("Admin credentials initialized successfully!")
        print(f"Username: {credentials['username']}")
        print("Password: [hidden]")
    else:
        print("Failed to initialize admin credentials")
        print("Response:", response.text)

if __name__ == "__main__":
    init_admin() 
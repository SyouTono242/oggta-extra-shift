import argparse
from pathlib import Path
import smtplib
from datetime import datetime, timedelta
import time

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from tqdm import tqdm
from plyer import notification
import smtplib
from email.mime.text import MIMEText


def read_credentials(path: Path) -> dict:
    """Reads the credentials from a file and returns them as a dictionary
    Expected format:
    URL: <url>
    Username: <username>
    Password: <password>

    Args:
        path (Path): Path to the credentials file

    Returns:
        dict: Dictionary with the credentials
    """
    
    with open(path, 'r') as file:
        
        if not file:
            raise FileNotFoundError('Credentials file not found')
        
        lines = file.readlines()
    
    credentials_dict = {}
    for line in lines:
        key, value = line.split(': ')
        credentials_dict[key.strip().lower()] = value.strip()
        
        
    if 'url' not in credentials_dict or 'username' not in credentials_dict or 'password' not in credentials_dict:
        raise ValueError('Credentials file must contain URL, Username and Password')
    
    return credentials_dict


def initialize_webdriver(headless: bool = True) -> webdriver.chrome.webdriver.WebDriver:
    
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    return driver
    

def login(driver: webdriver.chrome.webdriver.WebDriver,
          credentials_dict: dict):
    """Logs in to the OGGTA website using the provided credentials

    Args:
        credentials_dict (dict): Dictionary with the credentials

    Returns:
        webdriver.chrome.webdriver.WebDriver: Selenium WebDriver object
    """
    username_field = driver.find_element(By.ID, "txtUserName")
    password_field = driver.find_element(By.ID, "txtPassword")
    
    username_field.send_keys(credentials_dict['username'])
    password_field.send_keys(credentials_dict['password'])
    
    login_button = driver.find_element(By.ID, "cmdLogin")
    login_button.click()
    
    # Wait for longer if needed -- 3s has not been tested
    time.sleep(3)

    return driver


def find_dates(max_days: int) -> list:
    
    today = datetime.today()
    date_list = [
        (today + timedelta(days=i)).strftime("%Y%m%d") for i in range(max_days)
    ]
    return date_list


def check_shift(driver: webdriver.chrome.webdriver.WebDriver,
                date: str):
    
    # Extract anti-CSRF token
    anti_csrf_token = driver.execute_script("return window.antiCsrfToken;")
    
    # Get cookies from Selenium and convert them for requests
    session = requests.Session()
    for cookie in driver.get_cookies():
        session.cookies.set(cookie['name'], cookie['value'])
    
    
    # Find work
    url = "https://scheduling.oggta.com/ess/ws/ess.asmx/FindWork"
    
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "X-CSRF-Token": anti_csrf_token,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://scheduling.oggta.com/ess/Default.aspx?"
    }
    
    payload = {
        "dateString": date,
        "excludedWorkChecksums": None
    }
    
    # Send POST request
    response = session.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
    else:
        print(f"Request failed with status {response.status_code}")
        
    
    # When there are shifts available, return list of shifts
    if data['d']['Shifts'] is not None:
        shifts = data['d']['Shifts']
        return shifts
    else:
        return None
    

def send_notification(shift: str,
                      sender_email: str,
                      receiver_email: str,
                      sender_password: str,
                      desktop: bool = True,
                      email: bool = False):
    
    if desktop:
        notification.notify(
            title="Extra Shift Available",
            message="Extra shift found at " + shift,
            timeout=10 
        )
    
    if email:
        msg = MIMEText("Extra Shift Available at " + shift)
        msg["Subject"] = "Extra Shift Available"
        msg["From"] = sender_email
        msg["To"] = receiver_email
        
        with smtplib.SMTP_SSL("smtp.zohocloud.ca", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
            

def main():
    
    parser = argparse.ArgumentParser(description='Check for extra shifts in OGGTA')
    parser.add_argument('credentials', type=str, help='Path to the credentials file')
    parser.add_argument('--max_days', type=int, default=14, help='Number of days to check for extra shifts')
    parser.add_argument('--frequency', type=int, default=30, help='Frequency of checking for shifts in minutes')
    parser.add_argument('-d', '--desktop_notice', action='store_true', help='Send desktop notifications')
    parser.add_argument('-e', '--email_notice', action='store_true', help='Send email notifications')
    parser.add_argument('-l', '--headless', action='store_true', help='Run in headless mode')
    
    args = parser.parse_args()
    
    # Get credentials from input file 
    credentials_dict = read_credentials(Path(args.credentials))
    
    while True:
        
        print(f"Checking for shifts at {datetime.now()}")
        
        # Initialize webdriver
        driver = initialize_webdriver(args.headless)
        
        # Open OGGTA website
        driver.get(credentials_dict['url'])
        
        # Login with credentials
        driver = login(driver, credentials_dict)
        
        # Check for shifts
        days_to_check = find_dates(args.max_days)
        found = False
        for date in tqdm(days_to_check, desc='Checking shifts', unit='day'):
            shift = check_shift(driver, date)
            
            # If shift found, send notification
            if shift:
                found = True
                send_notification(date + " " + str(shift), 
                                  sender_email = credentials_dict['sender_email'],
                                  receiver_email = credentials_dict['receiver_email'],
                                  sender_password = credentials_dict['sender_password'],
                                  desktop = args.desktop_notice, 
                                  email = args.email_notice)
        
        if not found:
            print("No shifts found. Retrying in 30 minutes.")
        
        # Close browser
        driver.quit()
        
        # Wait for 30 minutes before checking again
        time.sleep(args.frequency * 60)
        

if __name__ == '__main__':
    main()
    
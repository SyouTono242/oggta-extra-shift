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

    Args:
        path (Path): Path to the credentials file

    Returns:
        dict: Dictionary with the credentials
    """
    
    with open(path, 'r') as file:
        if not file:
            raise FileNotFoundError('Credentials file not found')
        lines = file.readlines()
    
    credentials = {}
    for line in lines:
        key, value = line.split(': ')
        credentials[key.strip().lower()] = value.strip()
    
    required_keys = {'url', 'username', 'password', 'sender_email', 'receiver_email', 'sender_password'}    
    if not required_keys.issubset(set(credentials.keys())):
        raise ValueError('Credentials file must contain URL, Username and Password')
    
    return credentials


def initialize_webdriver(headless: bool,
                         credentials: dict) -> webdriver.chrome.webdriver.WebDriver:
    """Initializes a Chrome WebDriver with the specified options

    Args:
        headless (bool, optional): _description_. Defaults to True.

    Returns:
        webdriver.chrome.webdriver.WebDriver: _description_
    """
    
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(credentials['url'])
    
    # Login
    driver.find_element(By.ID, "txtUserName").send_keys(credentials['username'])
    driver.find_element(By.ID, "txtPassword").send_keys(credentials['password'])
    driver.find_element(By.ID, "cmdLogin").click()
    time.sleep(3)
    
    # Retrieve anti-CSRF token
    anti_csrf_token = driver.execute_script("return window.antiCsrfToken;")
    session = requests.Session()
    for cookie in driver.get_cookies():
        session.cookies.set(cookie['name'], cookie['value'])
    
    return driver, session, anti_csrf_token


def find_dates(max_days: int) -> list:
    """Find the dates for the next `max_days` days

    Args:
        max_days (int): Number of days in the future to check for shifts

    Returns:
        list: List of dates as strings in the format YYYYMMDD
    """
    
    today = datetime.today()
    return [(today + timedelta(days=i)).strftime("%Y%m%d") for i in range(max_days)]


def check_shift(session: requests.Session,
                anti_csrf_token: str,
                date: str):
    """Check for extra shifts on a given date

    Args:
        session (requests.Session): Requests session object with cookies
        anti_csrf_token (str): Anti-CSRF token
        date (str): Date to check for shifts as string in the format YYYYMMDD

    Returns:
        str: Shift time if found, None otherwise
    """
    
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
    
    response = session.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data['d']['Shifts'] if data['d']['Shifts'] else None
    else:
        print(f"Request failed with status {response.status_code}")
        return None
    

def send_notification(shift: str, 
                      config: dict, 
                      desktop: bool, 
                      email: bool):
    """Send desktop or email notification containing info about the extra shift found

    Args:
        shift (str): Shift time
        config (dict): Dictionary containing the configuration for sending notifications
        desktop (bool): Whether to send a desktop notification
        email (bool): Whether to send an email notification
    """
    
    if desktop:
        notification.notify(
            title="Extra Shift Available",
            message="Extra shift found at " + shift,
            timeout=10 
        )
    
    if email:
        msg = MIMEText("Extra Shift Available at " + shift)
        msg["Subject"] = "Extra Shift Available"
        msg["From"] = config["sender_email"]
        msg["To"] = config["receiver_email"]
        
        with smtplib.SMTP_SSL("smtp.zohocloud.ca", 465) as server:
            server.login(config["sender_email"], config["sender_password"])
            server.sendmail(config['sender_email'], 
                            config['receiver_email'], 
                            msg.as_string())
            

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
    config = read_credentials(Path(args.credentials))
    
    # Initialize webdriver and session
    driver, session, anti_csrf_token = initialize_webdriver(args.headless, config)
    
    try:
        while True:
            print(f"Checking for shifts at {datetime.now()}")
            
            days_to_check = find_dates(args.max_days)
            found = False
            
            for date in tqdm(days_to_check, desc='Checking shifts', unit='day'):
                shifts = check_shift(session, anti_csrf_token, date)
                if shifts:
                    found = True
                    for shift in shifts:
                        send_notification(date + " " + str(shift), 
                                          config = config,
                                          desktop = args.desktop_notice, 
                                          email = args.email_notice)
            
            if not found:
                print(f"No shifts found. Retrying in {args.frequency} minutes.")
            
            time.sleep(args.frequency * 60)
            
    except KeyboardInterrupt:
        print("Keyboard interrupt detected. Exiting...")
    
    finally:
        # Ensure browser is closed
        driver.quit()
            
        
if __name__ == '__main__':
    main()
    
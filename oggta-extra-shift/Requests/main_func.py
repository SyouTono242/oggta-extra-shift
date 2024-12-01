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

from . import config


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
        if ': ' not in line:
            raise ValueError('Credentials file must contain key-value pairs separated by ": "')
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
                      credentials: dict, 
                      desktop: bool, 
                      email: bool):
    """Send desktop or email notification containing info about the extra shift found

    Args:
        shift (str): Shift time
        credentials (dict): Dictionary containing the configuration for sending notifications
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
        msg["From"] = credentials["sender_email"]
        msg["To"] = credentials["receiver_email"]
        
        with smtplib.SMTP_SSL("smtp.zohocloud.ca", 465) as server:
            server.login(credentials["sender_email"], credentials["sender_password"])
            server.sendmail(credentials['sender_email'], 
                            credentials['receiver_email'], 
                            msg.as_string())
            

def main_driver(credentials: str,
         max_days: int = 14,
         frequency: int = 30,
         desktop_notice: bool = False,
         email_notice: bool = False,
         headless: bool = True):
    
    print(f"Checking for shift in the next {max_days} days...")
    
    # Get credentials from input file 
    credentials = read_credentials(Path(credentials))
    
    # Initialize webdriver and session
    driver, session, anti_csrf_token = initialize_webdriver(headless, credentials)
    
    try:
        while config.thread_running:
            print(f"Checking for shifts at {datetime.now()}")
            
            days_to_check = find_dates(max_days)
            found = False
            
            for date in tqdm(days_to_check, desc='Checking shifts', unit='day'):
                shifts = check_shift(session, anti_csrf_token, date)
                if shifts:
                    found = True
                    for shift in shifts:
                        send_notification(date + " " + str(shift), 
                                          credentials = credentials,
                                          desktop = desktop_notice, 
                                          email = email_notice)
            
            if not found:
                print(f"\n\nNo shifts found. Retrying in {frequency} minutes.")
            
            for _ in range(10*60*frequency):
                if not config.thread_running:
                    break
                time.sleep(0.1)
    
    finally:
        # Ensure browser is closed
        driver.quit()
# OGGTA-Extra-Shift
OGGTA-Extra-Shift is really just a python script for finding extra shifts available on OGGTA.

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install OGGTA-Extra-Shift -- or you probably can just download it lol.

```bash
pip install git+https://github.com/SyouTono242/oggta-extra-shift.git
```

## Usage

```
usage: main.py [-h] [--max_days MAX_DAYS] [--frequency FREQUENCY] [-d] [-e]
               [-l]
               credentials

Check for extra shifts in OGGTA

positional arguments:
  credentials           Path to the credentials file

options:
  -h, --help            show this help message and exit
  --max_days MAX_DAYS   Number of days to check for extra shifts
  --frequency FREQUENCY
                        Frequency of checking for shifts in minutes
  -d, --desktop_notice  Send desktop notifications
  -e, --email_notice    Send email notifications
  -l, --headless        Run in headless mode
```


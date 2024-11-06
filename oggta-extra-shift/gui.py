from pathlib import Path
import threading
import sys
import os
import signal

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from main import main
import config

class RedirectText:
    """Class to redirect program outputs to a text widget."""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, string):
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)  # Auto-scroll to the bottom

    def flush(self):  # Needed for compatibility with sys.stdout
        pass


def browse_file(entry):
    """Open a file dialog and set the selected file path in the entry widget."""
    file_path = filedialog.askopenfilename()
    if file_path:
        entry.delete(0, tk.END)
        entry.insert(0, file_path)


def quit_program():
    """Stop running threads and quit the application."""
    config.thread_running = False
    print("Quitting the program...")
    
    if work_thread in globals() and work_thread.is_alive():
        work_thread.join()
    
    root.quit()
    root.destroy()


def start_script():
    """Retrieve input values and start the main script in a separate thread."""
    credentials_path = credentials_entry.get()
    max_days = int(max_days_entry.get())
    frequency = int(frequency_entry.get())
    desktop_notice = desktop_var.get()
    email_notice = email_var.get()
    headless_mode = headless_var.get()

    # Check if credentials file exists
    if not Path(credentials_path).is_file() or not credentials_path.endswith('.txt'):
        messagebox.showerror("Error", "Invalid credentials file path; expecting a txt file.")
        return

    # Define the arguments
    args = {
        'credentials': credentials_path,
        'max_days': max_days,
        'frequency': frequency,
        'desktop_notice': desktop_notice,
        'email_notice': email_notice,
        'headless': headless_mode
    }

    # Run the main script in a separate thread to avoid freezing the GUI
    global work_thread
    config.thread_running = True
    work_thread = threading.Thread(target=main, kwargs=args)
    work_thread.start()
    
    # Show quit button and output window
    quit_button.pack(pady=5)
    output_window.pack(pady=5)
    
    
# Create the main GUI window
root = tk.Tk()
root.title("OGGTA Extra Shift Checker")
root.geometry("500x500")

# Credentials file selection
tk.Label(root, text="Credentials File:").pack(pady=5)
credentials_entry = tk.Entry(root, width=40)
credentials_entry.pack(pady=5)
tk.Button(root, text="Browse", command=lambda: browse_file(credentials_entry)).pack(pady=5)

# Max days input
tk.Label(root, text="Max Days to Check:").pack(pady=5)
max_days_entry = tk.Entry(root, width=10)
max_days_entry.insert(0, "14")  # Default value
max_days_entry.pack(pady=5)

# Frequency input
tk.Label(root, text="Check Frequency (minutes):").pack(pady=5)
frequency_entry = tk.Entry(root, width=10)
frequency_entry.insert(0, "30")  # Default value
frequency_entry.pack(pady=5)

# Desktop notification checkbox
desktop_var = tk.BooleanVar(value=True)
tk.Checkbutton(root, text="Enable Desktop Notifications", variable=desktop_var).pack(pady=5)

# Email notification checkbox
email_var = tk.BooleanVar(value=False)
tk.Checkbutton(root, text="Enable Email Notifications", variable=email_var).pack(pady=5)

# Headless mode checkbox
headless_var = tk.BooleanVar(value=True)
tk.Checkbutton(root, text="Run in Headless Mode", variable=headless_var).pack(pady=5)

# Start button
tk.Button(root, text="Start Checking", command=start_script).pack(pady=20)

# Quit button to safely stop the script
quit_button = tk.Button(root, text="Quit", command=quit_program)

# Output window (ScrolledText widget)
output_window = scrolledtext.ScrolledText(root, width=70, height=15, state='normal')

# Redirect stdout and stderr to the output window
sys.stdout = RedirectText(output_window)
sys.stderr = RedirectText(output_window)

# Run the GUI loop
root.mainloop()
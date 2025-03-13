import os
import sys
import threading
import time
import webbrowser

from django.core.management import execute_from_command_line

# Django-Settings setzen
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dkverwaltung.settings")

def format_host_port(value):
    value = value.strip()
    if value.isdigit():
        return f"localhost:{value}"
    parts = value.split(":")
    if len(parts) == 2 and parts[1].isdigit():
        return value
    return None

def delayed_browser_open(url):
    time.sleep(1)
    webbrowser.open(url)

def run():
    if len(sys.argv) == 1:
        threading.Thread(target=delayed_browser_open, args=("http://localhost:8000",), daemon=True).start()
        execute_from_command_line(["manage.py", "runserver", "--noreload", "localhost:8000"])
    elif len(sys.argv) == 2 and (v := format_host_port(sys.argv[1])):
        threading.Thread(target=delayed_browser_open, args=(f"http://{v}",), daemon=True).start()
        execute_from_command_line(["manage.py", "runserver", "--noreload", v])
    else:
        execute_from_command_line(["manage.py"] + sys.argv[1:])


if __name__ == "__main__":
    run()

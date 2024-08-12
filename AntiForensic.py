import os
import sys
import time
from getpass import getpass

from pynput import mouse, keyboard
import threading
import platform
import psutil
import pygame
import ctypes
import subprocess
from colorama import init, Fore

# Debug
debug_mode = False


# Globale Variablen
os_system = None
safe_mode = None
blackscreen = None
timer = 0
timer_thread = None
timer_runs = False
password = []
current_sequence = []
shutdown_flag = threading.Event()
critical_keys = [
    keyboard.Key.cmd, keyboard.Key.cmd_r,
    keyboard.Key.f1, keyboard.Key.f2, keyboard.Key.f3, keyboard.Key.f4,
    keyboard.Key.f5, keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8,
    keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f11, keyboard.Key.f12,
    keyboard.Key.shift_r, keyboard.Key.ctrl_l,
    keyboard.Key.ctrl_r, keyboard.Key.alt_l, keyboard.Key.alt_r,
    keyboard.Key.alt_gr
]


def manager():
    try:
        time.sleep(2)
        # Start Threads
        mouse_thread = threading.Thread(target=mouseListener)
        keyboard_thread = threading.Thread(target=keyboardListener)
        mouse_thread.start()
        keyboard_thread.start()
        if safe_mode == 1:
            usb_thread = threading.Thread(target=usbListener)
            usb_thread.start()
        print("Started all security meausures. Hide console")
        time.sleep(2)

        # Hide console and start blackscreen if wanted
        if not debug_mode:
            hide_console()
        if blackscreen == 1:
            show_blackscreen()

    except Exception as e:
        print(f"Problem with starting the thread {e}")
        sys.exit(1)
    finally:
        # Warten auf Thread-Beendigung
        shutdown_flag.set()
        mouse_thread.join()
        keyboard_thread.join()
        if safe_mode == 1:
            usb_thread.join()


def hide_console():
    global os_system

    if os_system == "Windows":
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 6)
    elif os_system == "Darwin":
        os.system(
            """osascript -e 'tell application "System Events" to set miniaturized of first window of (first 
            application process whose frontmost is true) to true'""")

    elif os_system == "Linux":
        subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-b", "add,hidden"])


def create_fullscreen_window(display_number):
    global os_system
    pygame.display.init()
    pygame.display.set_caption(f"Blackscreen {display_number}")

    screen = pygame.display.set_mode((0, 0), pygame.NOFRAME | pygame.FULLSCREEN, display=display_number)
    screen.fill((0, 0, 0))
    pygame.display.update()

    if os_system == "Windows":
        import ctypes
        hwnd = pygame.display.get_wm_info()['window']
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001)
    elif os_system == "Darwin":
        from AppKit import NSApplication, NSApp, NSWindow
        from PyObjCTools import AppHelper

        def bring_to_front():
            NSApp.activateIgnoringOtherApps_(True)
            window = NSApp.windows()[0]
            window.setLevel_(NSWindow.NSStatusWindowLevel)

        AppHelper.callAfter(bring_to_front)
    elif os_system == "Linux":
        import subprocess
        wm_name = subprocess.run(['wmctrl', '-m'], capture_output=True, text=True).stdout
        if 'GNOME' in wm_name or 'KWin' in wm_name:
            hwnd = pygame.display.get_wm_info()['window']
            subprocess.run(['wmctrl', '-i', '-r', str(hwnd), '-b', 'add,above'])

    return screen


def show_blackscreen():
    global os_system
    pygame.init()
    num_displays = pygame.display.get_num_displays()
    screens = []

    for i in range(num_displays):
        screen = create_fullscreen_window(i)
        screens.append(screen)

    #Keeps window open until shutdown is initalizied
    while not shutdown_flag.is_set():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        time.sleep(0.1)


def mouseListener():
    with mouse.Listener(on_move=lambda x, y: mouse_event(x, y, move=1),
                        on_click=lambda x, y, button, pressed: mouse_event(x, y, button=button, pressed=pressed),
                        on_scroll=lambda x, y, dx, dy: mouse_event(x, y, dx=dx, dy=dy)) as listener:
        listener.join()


def mouse_event(x=None, y=None, move=0, dx=0, dy=0, button=None, pressed=None):
    global safe_mode
    #If safe mode is activated every movement leads to a shutdown otherwise only klicks
    if safe_mode == 1:
        shutdown()
    elif safe_mode == 0:
        if move == 0 and pressed is not None:
            shutdown()


def keyboardListener():
    with keyboard.Listener(on_press=criticalKeys, on_release=keyboardInput) as listener:
        listener.join()


# For safety reasons, some buttons lead to a shutdown as soon as they are pressed
def criticalKeys(key):
    global critical_keys
    if key in critical_keys:
        print("Critical keys were pressed")
        shutdown()


# Handles normal keys and test if they are the password
def keyboardInput(key):
    global current_sequence
    global timer_thread
    global timer_runs

    # Start timer
    if not timer_runs:
        start_timer()

    if isinstance(key, keyboard.KeyCode):
        current_char = key.char.lower()

        if len(current_sequence) < len(password) and current_char == password[len(current_sequence)]:
            current_sequence.append(current_char)
            if current_sequence == password:
                print("password correct. Exit programm")
                os._exit(0)
        else:
            shutdown()


def start_timer():
    global timer
    global timer_runs
    global timer_thread
    print("Timer started")
    timer_thread = threading.Timer(timer, shutdown)
    timer_thread.start()
    timer_runs = True

# Listen if new USB Devices are added
def usbListener():
    initialUSB = getUSBDevices()

    while True:
        currentDevices = getUSBDevices()
        if currentDevices != initialUSB:
            print("New USB Device detected. Shutdown")
            shutdown()
        time.sleep(1)


def getUSBDevices():
    devices = []
    partitions = psutil.disk_partitions(all=True)
    for partition in partitions:
        if 'removable' in partition.opts or 'media' in partition.mountpoint:
            devices.append(partition.device)
    return set(devices)


def shutdown():
    global debug_mode
    global os_system
    shutdown_flag.set()

    if os_system == "Linux":
        if debug_mode:
            os.system('echo "PC would now be shut down (Linux)"')
            os._exit(0)
        else:
            os.system("sudo shutdown -h now")
    elif os_system == "Windows":
        if debug_mode:
            os.system("echo PC would now be shut down (Windows)")
            os._exit(0)
        else:
            os.system("shutdown /s /f /t 0")
    else:
        if debug_mode:
            os.system('echo "PC would now be shut down (Apple)"')
            os._exit(0)
        else:
            os.system("sudo shutdown -h now")


if __name__ == '__main__':

    init()
    if debug_mode:
        print(Fore.RED + '\nAttention: Debugmode is active. This mode does NOT shutdown your pc\n' + Fore.RESET)

    print("Welcome to AntiForensik Protection. I am not an expert and give NO guarantee on this program. \n "
          "If you find a mistake please report it on github: https://github.com/Prtheus/AntiForensikProtection"
          "\n \n This program does not allow any inputs other than the password. As soon as a wrong button is clicked,"
          "\n the PC switches off")
    # Test if System is supported
    os_system = platform.system()

    if os_system not in ["Linux", "Windows", "Darwin"]:
        print(Fore.RED + "This system is not supported. Exiting program." + Fore.RESET)
        exit()
    if os_system in ["Linux", "Darwin"] and os.getuid() != 0:
        print(Fore.RED + "You have to start the program with sudo rights." + Fore.RESET)
        exit()
    print(Fore.RED + os_system + Fore.RESET +
          " detected as operating system. If it is not correct, there could be safety problems")

    # Abfrage für Safe Mode
    while True:
        print(
            "\nSafe mode shuts down the PC if it recognizes mouse movement or a new USB stick. "
            "We recommend using everytime safe mode")
        safe_mode = input("Do you want Safe Mode [Y/N]: ")

        if safe_mode in ["Y", "y"]:
            safe_mode = 1
            break
        elif safe_mode in ["N", "n"]:
            safe_mode = 0
            break
        print("Invalid character. Only 'Y' or 'N' allowed")

    # Abfrage für Blackscreen
    while True:
        blackscreen = input("Do you want a black screen during the time for additional security [Y/N]: ")
        if blackscreen in ["Y", "y"]:
            blackscreen = 1
            break
        elif blackscreen in ["N", "n"]:
            blackscreen = 0
            break
        print("Invalid character. Only 'Y' or 'N' allowed")

    # Abfrage für Timer
    while True:
        timer = input(
            "How much time do you want to have, until the first input is made (if empty, the timer will be set to 20 seconds): ")

        if timer.isnumeric():
            timer = int(timer)
            break
        elif timer == "":
            timer = 20
            break
        print("Time is not a number. Please type in a valid number.")

    # Get Password
    while True:
        print("\nUpper and lower case is ignored\n")
        password1 = getpass("Please put in your password: ")
        password2 = getpass("Please repeat your password: ")
        if password1 == password2:
            print("Valid password.")
            password = password1.lower()
            break
        print("Passwords do not match. Please try again.")
    manager()

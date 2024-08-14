"""
v. 1.1
    _            _    _   _____                                 _
   / \    _ __  | |_ (_) |  ___|  ___   _ __   ___  _ __   ___ (_)  ___
  / _ \  | '_ \ | __|| | | |_    / _ \ | '__| / _ \| '_ \ / __|| | / __|
 / ___ \ | | | || |_ | | |  _|  | (_) || |   |  __/| | | |\__ \| || (__
/_/   \_\|_| |_| \__||_| |_|     \___/ |_|    \___||_| |_||___/|_| \___|

 ____                _                _    _
|  _ \  _ __   ___  | |_   ___   ___ | |_ (_)  ___   _ __
| |_) || '__| / _ \ | __| / _ \ / __|| __|| | / _ \ | '_ \
|  __/ | |   | (_) || |_ |  __/| (__ | |_ | || (_) || | | |
|_|    |_|    \___/  \__| \___| \___| \__||_| \___/ |_| |_|

This tool helps you to protect your computer when you are not allowed to lock the screen.
When enabled, you cannot press any key except the password (and Shift), and mouse clicks are also locked.
In safe mode, you cannot insert a USB stick or move the mouse.

To insert the password, just type it into the empty field. The program will recognize it.
If you enter the wrong password, the computer will be shut down.
"""
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
from art import *
import argparse
import shutil
import pyautogui

# Variabls to set if you want to edit it something. Can be edited through the file or as arguments.
debug_mode = False                   # Doesn't shutdown your pc and some other smaller changes
other_mode = False                  # Allows another command to be executed instead of shutdown.
command = ""                        # The command that will be executed, if other_mode is active
keep_alive = True                   # Keeps the screen awake
hide_console = True                 # Controls if the console should be hidden.
ignore_security_risks = False       # If True it ignores security risk like missing software or missing rights


# Variables set in both modes
safe_mode = False
blackscreen = False
timer = 20

# System variables. Do not edit.
os_system = None
timer_runs = False
timer_thread = None
password = []
current_sequence = []
shutdown_flag = threading.Event()
miss_software = False


def manager():
    global keep_alive, miss_software
    try:
        time.sleep(1)

        #If Linux software is missed you have 10 seconds to minimize the window
        if miss_software is True:
            print("Because of missing software you have to minimize it on your own. You have 10 seconds for this")
            for i in range(10, 0, -1):
                print(Fore.RED, f"Please minimize your window. You have {i} seconds left before the programm starts", Fore.RESET)
                time.sleep(1)

        # Start Threads
        init()
        mouse_thread = threading.Thread(target=mouseListener, daemon=True)
        keyboard_thread = threading.Thread(target=keyboardListener, daemon=True)
        mouse_thread.start()
        print("Started mouse listener")
        keyboard_thread.start()
        print("Started keyboard listener")
        if safe_mode == 1:
            usb_thread = threading.Thread(target=usbListener, daemon=True)
            usb_thread.start()
            print("Started usb listener")

        #Prevent Sleep Mode
        if keep_alive:
            print("keep alive")
            keep_alive_thread = threading.Thread(target=preventSleeping, daemon=True)
            print("start keep alive")
            keep_alive_thread.start()
            print("Screen will be keeped alive")

        print("Started all security meausures. Hide console")
        time.sleep(1)

        # Hide console and start blackscreen if wanted
        if not debug_mode or hide_console is not False:
            hide_console()
        if blackscreen == 1:
            show_blackscreen()
        else:
            shutdown_flag.wait()

    except Exception as e:
        print(f"Problem with starting the thread {e}")
        sys.exit(1)
    finally:
        sys.exit(0)


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
    global os_system, shutdown_flag
    pygame.init()
    num_displays = pygame.display.get_num_displays()
    screens = []

    for i in range(num_displays):
        screen = create_fullscreen_window(i)
        screens.append(screen)

    # Keeps window open until shutdown is initalizied
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
    # If safe mode is activated every movement leads to a shutdown otherwise only klicks
    if safe_mode == 1:
        shutdown()
    elif safe_mode == 0:
        if move == 0 and pressed is not None:
            shutdown()


def keyboardListener():
    with keyboard.Listener(on_press=keyboardInput) as listener:
        listener.join()


# Handles key input and test if they are the password // Shutdown system interrupts
def keyboardInput(key):
    global current_sequence, password

    # Shift-Key Status updaten
    if key == keyboard.Key.shift or key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
        return

    if not timer_runs:
        start_timer()

    if isinstance(key, keyboard.KeyCode) and key.char is not None:
        if len(current_sequence) < len(password) and key.char == password[len(current_sequence)]:
            current_sequence.append(key.char)
            if current_sequence == password:
                print("Password correct. Exit program")
                shutdown_flag.set()
                # sys.exit(0)
        else:
            shutdown()
    else:
        shutdown()


def preventSleeping():
    while True:
        time.sleep(60)
        pyautogui.press("shift")


def start_timer():
    global timer, timer_runs, timer_thread
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
    global debug_mode, os_system
    shutdown_flag.set()

    if os_system == "Linux":
        if other_mode:
            os.system(command)
            sys.exit("Critical Event")
        elif debug_mode:
            os.system('echo "PC would now be shut down (Linux)"')
            sys.exit("Debug Shutdown")
        else:
            os.system("sudo shutdown -h now")
    elif os_system == "Windows":
        if other_mode:
            os.system(command)
            sys.exit("Critical Event")
        elif debug_mode:
            os.system("echo PC would now be shut down (Windows)")
            sys.exit("Shutdown event")
        else:
            os.system("shutdown /s /f /t 0")
    else:
        if other_mode:
            os.system(command)
            sys.exit("Critical Event")
        elif debug_mode:
            os.system('echo "PC would now be shut down (Apple)"')
            sys.exit("Debug Shutdown")
        else:
            os.system("sudo shutdown -h now")


def get_args_from_user():
    global safe_mode, blackscreen, timer

    art_1 = text2art("Anti  Forensic\nProtection")  # Verwende eine unterstützte Schriftart
    print(Fore.YELLOW + art_1 + Fore.RESET)

    print("This tool helps you to protect your computer when you are not allowed to lock the screen.\n"
          "When enabled, you cannot press any key except the password (and Shift), and mouse clicks are also locked.\n"
          "In safe mode, you cannot insert a USB stick or move the mouse. To insert the password, just type it into the empty field.\n"
          "The program will recognize it. If you enter the wrong password, the computer will be shut down.\n",
          Fore.YELLOW, "Version 1.1, If you find Bugs, please report them: https://github.com/Prtheus/AntiForensikProtection\n", Fore.RESET)

    print(Fore.RED + os_system + Fore.RESET + " detected as operating system. If it is not correct, there could be safety problems")
    # Abfrage für Safe Mode
    while True:
        print(
            "\nSafe mode shuts down the PC if it recognizes mouse movement or a new USB stick. "
            "We recommend using everytime safe mode")
        safe_mode = input("Do you want Safe Mode [Y/N]: ")

        if safe_mode in ["Y", "y"]:
            break
        elif safe_mode in ["N", "n"]:
            safe_mode = False
            break
        print("Invalid character. Only 'Y' or 'N' allowed")

    # Abfrage für Blackscreen
    while True:
        blackscreen = input("\nDo you want a black screen during the time for additional security [Y/N]: ")
        if blackscreen in ["Y", "y"]:
            blackscreen = True
            break
        elif blackscreen in ["N", "n"]:
            break
        print("Invalid character. Only 'Y' or 'N' allowed")

    # Abfrage für Timer
    while True:
        timer = input(
            "\nHow much time do you want to have, until the first input is made (if empty, the timer will be set to 20 seconds): ")

        if timer.isnumeric():
            timer = int(timer)
            break
        elif timer == "":
            timer = 20
            break
        print("Time is not a number. Please type in a valid number.")

    # Get Password
    get_password()
    return


# Test if System is supported
def test_operating_system():
    global os_system, ignore_security_risks, miss_software
    os_system = platform.system()
    # Test if operating system is supported and started with sudo rights
    if os_system not in ["Linux", "Windows", "Darwin"]:
        print(Fore.RED + "This system is not supported. Exiting program." + Fore.RESET)
        exit(1)
    if os_system in ["Linux", "Darwin"] and os.getuid() != 0 and ignore_security_risks is False:
        print(Fore.RED + "You have to start the program without sudo rights. This can lead to security issues "
                         "(f.e. that the pc doesnt shutdown" + Fore.RESET)
        while True:
            ignore_problem_r = input("Do you want to ignore this warning and proceed anyway? [Y/N]")
            if ignore_problem_r in ["Y", "y"]:
                break
            elif ignore_problem_r in ["N", "n"]:
                print("Please start with sudo rights (\"sudo python [filename]\")")
                exit(1)
            print("Please type Y/N")

    # Test if necessary Software is installed
    if os_system == "Linux" and shutil.which("wmctrl") is None and ignore_security_risks is False:
        print(Fore.RED + "You need to install   \"wmctrl\" for this programm to hide the console. Do you want to install "
                         "it or ignore the problem (not reccommended because someone could stop the program if you do not minimize it on your own before)")
        while True:
            ignore_problem = input("Ignore security Problem anyway? [Y/N]")
            if ignore_problem in ["Y", "y"]:
                miss_software = True
                break
            elif ignore_problem in ["N", "n"]:
                print("Please install wmctrl (\"sudo apt-get install wmctrl\n)")
                sys.exit(1)
    elif os_system == "Darwin":
        from AppKit import NSApplication, NSApp, NSWindow
        from PyObjCTools import AppHelper
    return


# Takes care to become a password (if missing)
def get_password():
    global password, debug_mode

    if debug_mode:
        password = list(input("\nPlease type in your password: "))
        return

    while True:
        password1 = getpass("\nPlease put in your password: ")
        password2 = getpass("Please repeat your password: ")
        if password1 == password2:
            print("Valid password.")
            password = list(password1)
            break
        print("Passwords do not match. Please try again.")

    return


# Handling with args
def sys_args(args):
    global timer, safe_mode, blackscreen, password, keep_alive, debug_mode, other_mode, command, hide_console

    if args.time:
        timer = args.time
    if args.safe_mode:
        safe_mode = True
    if args.blackscreen:
        blackscreen = True
    if args.password:
        password = list(args.password)
    else:
        get_password()
    if args.keep_alive:
        keep_alive = False
    if args.debug_mode:
        debug_mode = True
    if args.other_mode:
        other_mode = True
        command = args.other_mode
    if args.show_console:
        hide_console = False

    return


if __name__ == '__main__':
    # Handling args
    parser = argparse.ArgumentParser(
        description="Anti Forensic Protection. Doesnt any keyboard interrupt besides the password")
    parser.add_argument("-t", "--time", type=int,
                        help="Time (in seconds) you have from the first input. Standard: 20 seconds")
    parser.add_argument("-s", "--safe_mode", action="store_true",
                        help="Safe Mode does not allow any mouse movements or the insertion of usb sticks")
    parser.add_argument("-b", "--blackscreen", action="store_true",
                        help="Shows a Blackscreen when the program started")
    parser.add_argument("-p", "--password",
                        help="The password to unlock the PC. Attention: Do not use a secret password here. It will be safed in the bash history.")
    parser.add_argument("-a", "--keep_alive", action="store_true",
                        help="Deactivates the function, that the screen is kept alive")
    parser.add_argument("-d", "--debug_mode", action="store_true",
                        help="Activates Debuggermode. Doesnt shutdown your PC")
    parser.add_argument("-o", "--other_mode",
                        help="Instead of shutdown, a different action happens. Please type in the command for your operating system afterwards.")
    parser.add_argument("-z", "--show_console", action="store_true",
                        help="If set, the console will not hide (not recommended because of security risks)")
    parser.add_argument("-x", "--ignore_risks", action="store_true",
                        help="Ignores Security Risks like missing rights or missing software (Not recommended).")
    args = parser.parse_args()

    test_operating_system()

    if len(sys.argv) == 1:
        get_args_from_user()
    else:
        sys_args(args)

    if debug_mode:
        print(Fore.RED + '\nAttention: Debugmode is active. This mode does NOT shutdown your pc\n' + Fore.RESET)

    manager()

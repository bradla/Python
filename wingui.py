import subprocess
import pyautogui
import time

subprocess.Popen("mstsc")

time.sleep(5)

pyautogui.write("192.168.1.10")
pyautogui.press("enter")

time.sleep(10)

pyautogui.write("password")
pyautogui.press("enter")

pyautogui.hotkey("win", "r")
pyautogui.write("notepad")
pyautogui.press("enter")

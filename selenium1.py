from selenium import webdriver
from Screenshot import Screenshot

#from autoselenium import Driver

# from selenium import webdriver
# from selenium.webdriver.common.by import By

driver = webdriver.Chrome()
driver.get("https://selenium.dev/documentation")

ss = Screenshot(driver)

#table_to_hide = driver.find_element("css selector", "#p-search")

ss.capture_full_page(
    output_path="python_2.png",
    hide_selectors=[".vector-sticky-header", "#mw-head"] #, table_to_hide]  
)

driver.quit()

# with Driver('chrome', root='drivers') as driver:
#     driver.get('https://www.google.com/')
#     # Selenium Webdriver command examples
#     driver.find_elements_by_tag_name('div')
#     driver.refresh()

# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager

# driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service

# service = Service(r"C:\Users\env\Lib\site-packages\chromedriver_py\chromedriver_win64.exe")

# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager

# #driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
# service = Service(r"C:\Users\drivers\chromedriver.exe")
# driver = webdriver.Chrome(service=service)

# #driver = webdriver.Chrome()

# driver.get('https://selenium.dev/documentation')
# assert 'Selenium' in driver.title

# elem = driver.find_element(By.ID, 'm-documentationwebdriver')
# elem.click()
# assert 'WebDriver' in driver.title

# driver.quit()

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Setup the driver (make sure you have the appropriate driver installed)
driver = webdriver.Chrome()  # or Firefox(), Safari(), etc.

try:
    # Navigate to the login page
    driver.get("https://example.com/login")
    
    # Wait for the page to load
    time.sleep(2)
    
    # Find username and password fields and fill them
    username_field = driver.find_element(By.ID, "username")  # or By.NAME, By.CSS_SELECTOR, etc.
    password_field = driver.find_element(By.ID, "password")
    
    # Enter credentials
    username_field.send_keys("your_username")
    password_field.send_keys("your_password")
    
    # Find and click the login button
    login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
    login_button.click()
    
    # Wait for login to complete and verify
    time.sleep(3)
    
    # Check if login was successful (example)
    if "dashboard" in driver.current_url:
        print("Login successful!")
    else:
        print("Login failed")
        
finally:
    # Close the browser
    driver.quit()

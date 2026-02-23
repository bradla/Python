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

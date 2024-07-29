import asyncio
import hashlib
from datetime import datetime, timedelta
from time import sleep
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from telegram import Bot,InlineKeyboardButton,InlineKeyboardMarkup
import schedule
from sqlalchemy import create_engine, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import List
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Constants
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SITE_DOMAIN = os.getenv('SITE_DOMAIN')
ENDPOINT_PATH = os.getenv('ENDPOINT_PATH')
URL = '{SITE_DOMAIN}{ENDPOINT_PATH}?create_time=gte,{}'

# import js code from the content.js file
js_code = """
Object.defineProperty(navigator, "languages", {
	get: function () {
		return ["en-US", "en"];
	},
});

Object.defineProperty(navigator, "plugins", {
	get: function () {
		return [1, 2, 3, 4, 5];
	},
});

const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function (parameter) {
	// UNMASKED_VENDOR_WEBGL
	if (parameter === 37445) {
		return "Intel Open Source Technology Center";
	}
	// UNMASKED_RENDERER_WEBGL
	if (parameter === 37446) {
		return "Mesa DRI Intel(R) Ivybridge Mobile ";
	}
	return getParameter(parameter);
};
"""

# ----------------------------------------------------------------------------
Base = declarative_base()


# Initialize Telegram Bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Define a class to represent a result entry
class Entry(Base):
    __tablename__ = 'entries'
    id = Column(String, primary_key=True)
    link = Column(String, unique=True, nullable=False)
    title = Column(String)
    price = Column(String)
    specs = Column(String)
    description = Column(String)
    location_string = Column(String)
    
    def __init__(self, link:str, title:str, price:str, specs:str, description:str, location:dict):
        self.id = generate_url_hash(link)
        self.link = link
        self.title = title
        self.price = price
        self.specs = specs
        self.description = description
        self.location = location

        # Convert the location dictionary to a string
        self.location_string = f"{self.location['city']} {self.location['neighborhood']}"

    def __hash__(self):
        return hash(self.link)
        
    def __eq__(self, other):
        if isinstance(other, Entry):
            return self.id == other.id
        return False

    def __str__(self):
        return f"Link: {self.link}\nTitle: {self.title}\nPrice: {self.price}\nSpecs: {self.specs}\nDescription: {self.description}\nLocation: {self.location_string}"
    
    def __repr__(self):
        return f"Entry(link={self.link}, title={self.title}, price={self.price}, specs={self.specs}, description={self.description}, location={self.location_string})"

def save_entries_to_text_file(entries: List[Entry]):
    # Create a file to save the entries, in the root/entries directory 
    file_name = 'entries/entries.txt'
    with open(file_name, 'w', encoding='utf-8') as file:
        for entry in entries:
            file.write(str(entry) + '\n')
            file.write('------------------------------\n')
            
    print(f"Entries saved to {file_name}")

def save_to_html_file(html_content, file_name):
    # if file exists, create a new file with a the current hr_min_sec timestamp
    file_name = f"body/{file_name}".replace(".html", f"_{datetime.now().strftime('%H_%M_%S')}.html")

    with open(file_name, 'w', encoding='utf-8') as file:
        file.write(html_content)
    print(f"HTML file saved to {file_name}")
    
def generate_url_hash(url: str) -> str:
    # Use SHA-256 to generate a hash of the URL
    return hashlib.sha256(url.encode()).hexdigest()

    
def get_start_of_today_timestamp():
    # Get current date and time
    now = datetime.now()

    # Set time to midnight (start of the day)
    start_of_today = datetime(now.year, now.month, now.day, 0, 0, 0)

    # Get timestamp in seconds since epoch
    timestamp = int(start_of_today.timestamp())

    return timestamp

# returns the timestamp of check_delay minutes ago
def get_timestamp_minutes_ago(minutes: int):
    time_ago = datetime.now() - timedelta(minutes=minutes)
    return int(time_ago.timestamp())


# Retrieve an entry by id
def get_entry_by_id(id: str):
    return session.query(Entry).filter_by(id=id).first()

# Retrieve an entry by URL
def get_entry_by_url(url: str):
    return get_entry_by_id(generate_url_hash(url))


def extract_entries(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # Initialize an empty list to store the entries
    # propery type the list with all the entries (dict)
    # link, title, price, specs, description, location
    entries: List[Entry] = []
    
    # Find all elements with class "_listingCard__PoR_B"
    listing_cards = soup.find_all('div', class_='_listingCard__PoR_B')

    for card in listing_cards:

        # Extract link to full details
        link_element = card.find_parent('a')
        # Extract other details
        title_element = card.find('h4')
        price_element = card.find('p', class_='_price__X51mi')
        specs_element = card.find('div', class_='_spec__SIJiK')
        description_element = card.find('div', class_='_description__zVaD6')
        location_elements = card.find_all('span')

        if link_element:
            # set the full url
            link_element = f"{SITE_DOMAIN}{link_element.get('href')}"
        if title_element:
            title_element = title_element.text.strip()
        if price_element:
            price_element = price_element.text.strip()
        if specs_element:
            specs_element = specs_element.text.strip()
        if description_element:
            description_element = description_element.text.strip()
        if location_elements and len(location_elements) >= 2:
            location_elements = [
                location_elements[0].text.strip(),
                location_elements[1].text.strip()
            ]
        entry = Entry(
            link=link_element,
            title=title_element,
            price=price_element,
            specs=specs_element,
            description=description_element,
            location={
                'city': location_elements[0],
                'neighborhood': location_elements[1]
            }
        )
        # Append entry to list
        entries.append(entry)

    return entries

def insert_entry(entry: Entry):
    session.add(entry)
    session.commit()

async def send_telegram_notification(message: str, link: str):
    async with bot:
        await (bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text='Open in Browser', url=link)]])))

# store in the  (memory) and in sqlite db
def store_as_seen(entry: Entry):
    insert_entry(entry)


async def validate_entries(entries: List[Entry]):
    # if we've already seen this listing, skip it
    for entry in entries:
        store_as_seen(entry)
        await send_telegram_notification(
            message=f"New listing found!\n\n{entry}",
                link=entry.link,
            )


async def check_new_listings(after_timestamp: int):
    # Generate current timestamp
    formatted_url = URL.format(after_timestamp)
    print("Getting from url", formatted_url)

    user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36'
    
    #  up options
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent={}'.format(user_agent))
    options.add_argument('--disable-blink-features=AutomationControlled')
    # enable automation and logging
    options.add_argument('--enable-automation')
    options.add_argument('--log-level=0')
    options.add_argument("start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-gpu')

    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    driver = webdriver.Chrome(options=options)

    try:
        # cdp stands for Chrome DevTools Protocol
        driver.execute_cdp_cmd('Page.enable', {})
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': js_code
        })

        # Load the page
        driver.get(formatted_url)

        body = driver.find_element(By.TAG_NAME, 'body')
        # if the body includes "blocked" text anywhere, means we've been blocked
        if body.text.find('blocked') != -1:
            print("Blocked!")
        else:
            # save the html of the body element to file
            save_to_html_file(body.get_attribute('innerHTML'), 'body.html')

        # Example: Find all listing elements by class name
        listing_elements = extract_entries(body.get_attribute('innerHTML'))

        # for debugging purposes, print the listing elements
        save_entries_to_text_file(listing_elements)
        
        await validate_entries(listing_elements)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

is_just_starting = True

async def async_job_wrapper():
    timestamp_to_check_after = 0
    if is_just_starting:
        timestamp_to_check_after = get_start_of_today_timestamp()
    else:
        timestamp_to_check_after = get_timestamp_minutes_ago(check_delay)
    
    print("Checking for new listings after...", 
        # convert timestamp to datetime object
          datetime.fromtimestamp(timestamp_to_check_after).strftime('%Y-%m-%d %H:%M:%S')
          )
    await check_new_listings(timestamp_to_check_after)

def job():
    asyncio.run(async_job_wrapper())


# 5 minutes
check_delay = 3

# Schedule the job every hour
schedule.every(check_delay).minutes.do(job)

if __name__ == "__main__":
    
    # Database setup
    engine = create_engine('sqlite:///entries.db')
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()
    
    # delete all entries
    session.query(Entry).delete()

    # to store the hashes of URLs we have already seen

    # Run the job once at the start
    job()
    is_just_starting = False

    while True:
        schedule.run_pending()
        sleep(2)


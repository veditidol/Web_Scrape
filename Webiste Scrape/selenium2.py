from flask import Flask, request, jsonify
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import re
import time
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

final_company_name = ""

def scrape_company_info(url):
    try:
        # Setup Selenium with Chrome in headless mode
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")

        service = Service("./drivers/chromedriver.exe")  # Update path
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Navigate to the company website
        driver.get(url)
        time.sleep(2)

        # Extract potential company names
        company_name = driver.find_element(By.TAG_NAME, "h1").text.strip() if driver.find_elements(By.TAG_NAME, "h1") else None
        title = driver.title.strip() if driver.title else None

        og_title = driver.find_elements(By.XPATH, "//meta[@property='og:title']")
        og_title_content = og_title[0].get_attribute("content").strip() if og_title else None

        og_site_name = driver.find_elements(By.XPATH, "//meta[@property='og:site_name']")
        og_site_name_content = og_site_name[0].get_attribute("content").strip() if og_site_name else None

        # Use if-else to determine the most appropriate company name
        global final_company_name
        final_company_name = company_name or title or og_title_content or og_site_name_content or "Company Name Not Found"

        # Extract OG description or look for content on About Us page
        og_description = driver.find_elements(By.XPATH, "//meta[@property='og:description']")
        og_description_content = og_description[0].get_attribute("content").strip() if og_description else None

        company_description = og_description_content if og_description_content else extract_about_us_description(driver)

        # Truncate description if needed
        if len(company_description) > 150:
            company_description = company_description[:147] + "..."

        # Find LinkedIn URL
        linked_in_url = None
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href and "linkedin.com" in href:
                linked_in_url = href
                break

        # Store details in a dictionary
        # company_details = {
        #     "linkedin_url": linked_in_url or 'LinkedIn URL Not Found',
        #     "company_description": company_description,
        # }

        company_details = {}
        if linked_in_url:
            linkedin_url_value = linked_in_url
        else:
            linkedin_url_value = 'LinkedIn URL Not Found'
            company_details["company_name"] = "Not Found"
            company_details["size"] = "Not Found"
            company_details["location"] = "Not Found"
            

        company_details["linkedin_url"] = linkedin_url_value
        company_details["company_description"]=company_description

        if linked_in_url:
            linkedin_details = scrape_linkedin_details(linked_in_url)
            company_details.update(linkedin_details)  # Add LinkedIn details to the dictionary

        driver.quit()

        # Return the dictionary
        return company_details

    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}

def extract_about_us_description(driver):
    try:
        links = driver.find_elements(By.TAG_NAME, "a")
        about_us_url = None
        for link in links:
            href = link.get_attribute("href")
            text = link.text.lower()
            if href and ("about" in href or "about" in text):
                about_us_url = href
                break

        if about_us_url:
            driver.get(about_us_url)
            time.sleep(2)

            paragraphs = driver.find_elements(By.TAG_NAME, "p")
            description = " ".join([p.text.strip() for p in paragraphs if len(p.text.strip()) > 50])

            return description if description else "No description found on About Us page."

        return "About Us page not found."
    except Exception:
        return "An error occurred while extracting About Us description."

def scrape_linkedin_details(linked_in_url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"
        }

        response = requests.get(linked_in_url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        text_content = soup.get_text(separator=" ", strip=True)

        company_name_pattern = r"^(.*?)\s*\|"
        company_name_match = re.search(company_name_pattern, text_content)

        company_name = company_name_match.group(1).strip() if company_name_match or final_company_name else "Company Name Not Found"

        size_pattern = r"Company size\s*(.*?)\s*(?:employees|people)"
        size_match = re.search(size_pattern, text_content, re.IGNORECASE)
        company_size = size_match.group(1).strip() if size_match else "Company size not found."

        location_pattern = r"Location\s*(.*?)\s*(?:Company size|Employees|Industry|Founded)"
        location_match = re.search(location_pattern, text_content, re.IGNORECASE)
        location = location_match.group(1).strip() if location_match else "Location not found."

        unwanted_phrases = ["s","Primary", "Get direction", "Headquarters"]
        for phrase in unwanted_phrases:
            location = location.replace(phrase, "").strip()

        # Clean up extra spaces and commas
        location = re.sub(r"\s{2,}", " ", location)  # Replace multiple spaces with a single space
        location = location.rstrip(",")

        if len(location) > 150:
            location = location[:147] + "..."

        return {
            "company_name": company_name,
            "company_size": company_size,
            "location": location
        }


    except Exception as e:
        print(f"An error occurred while scraping LinkedIn: {e}")
        return {
            "error": str(e)
        }

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "URL is required"}), 400

    result = scrape_company_info(url)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from urllib.parse import urljoin, urlparse
import threading
import phonenumbers
from concurrent.futures import ThreadPoolExecutor, as_completed

class ContactSyncScraper:
    def __init__(self, root):
        self.root = root
        self.root.title("Scrapster")
        self.root.geometry("1200x600")
        self.root.configure(bg="black")
        
        self.results = []
        self.stop_flag = False
        self.stats = {"detected": 0, "successful": 0, "unsuccessful": 0, "phones_found": 0, "phones_not_found": 0}
        
        self.create_gui()

    def create_gui(self):
        heading = ttk.Label(self.root, text="Scrapster", font=("Trebuchet MS", 18, "bold"), foreground="white", background="black")
        heading.grid(row=0, column=0, columnspan=2, pady=15)

        input_frame = ttk.Frame(self.root, padding="15", style="Navy.TFrame")
        input_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        ttk.Label(input_frame, text="Enter URLs:", font=("Trebuchet MS", 12, "bold"), foreground="white", background="navy").grid(row=0, column=0, pady=5)
        self.raw_data_text = tk.Text(input_frame, height=8, width=50, bg="navy", fg="yellow", font=("Georgia", 10), insertbackground="white")
        self.raw_data_text.grid(row=1, column=0, pady=10)

        button_frame = ttk.Frame(input_frame, style="Navy.TFrame")
        button_frame.grid(row=2, column=0, pady=10)
        ttk.Button(button_frame, text="Start Scraping", command=self.start_scraping, style="White.TButton").grid(row=0, column=0, padx=5)
        self.stop_button = ttk.Button(button_frame, text="Stop Scraping", command=self.stop_scraping, state="disabled", style="White.TButton")
        self.stop_button.grid(row=0, column=1, padx=5)

        self.progress_label = ttk.Label(input_frame, text="Ready", font=("Georgia", 10), foreground="white", background="navy")
        self.progress_label.grid(row=3, column=0, pady=5)

        report_frame = ttk.Frame(self.root, padding="15", style="Navy.TFrame")
        report_frame.grid(row=1, column=1, sticky="nsew", padx=20, pady=10)
        ttk.Label(report_frame, text="Scraping Report:", font=("Trebuchet MS", 12, "bold"), foreground="white", background="navy").grid(row=0, column=0, pady=5)
        self.report_text = tk.Text(report_frame, height=8, width=25, bg="navy", fg="white", font=("Georgia", 10), state="disabled")
        self.report_text.grid(row=1, column=0, pady=10)

        results_frame = ttk.Frame(self.root, padding="15", style="Black.TFrame")
        results_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=20, pady=10)

        self.tree = ttk.Treeview(results_frame, columns=("Name", "URL", "Country", "Email", "Phone", "Facebook", "Instagram"), show="headings", style="White.Treeview")
        self.tree.heading("Name", text="Website Name", anchor="center")
        self.tree.heading("URL", text="Website URL", anchor="center")
        self.tree.heading("Country", text="Country", anchor="center")
        self.tree.heading("Email", text="Email", anchor="center")
        self.tree.heading("Phone", text="Phone", anchor="center")
        self.tree.heading("Facebook", text="Facebook", anchor="center")
        self.tree.heading("Instagram", text="Instagram", anchor="center")
        self.tree.column("Name", width=120)
        self.tree.column("URL", width=200)
        self.tree.column("Country", width=80)
        self.tree.column("Email", width=180)
        self.tree.column("Phone", width=120)
        self.tree.column("Facebook", width=150)
        self.tree.column("Instagram", width=150)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        ttk.Button(results_frame, text="Export to Excel", command=self.export_to_excel, style="White.TButton").grid(row=1, column=0, pady=10)

        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=2)
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=1)
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("Navy.TFrame", background="navy")
        style.configure("Black.TFrame", background="black")
        style.configure("White.TButton", font=("Georgia", 10), foreground="black", background="white")
        style.configure("White.Treeview", font=("Georgia", 10), foreground="black", background="white")
        style.configure("White.Treeview.Heading", font=("Trebuchet MS", 10, "bold"), foreground="black", background="white")

    def start_scraping(self):
        self.results.clear()
        self.tree.delete(*self.tree.get_children())
        self.stop_flag = False
        self.stats = {"detected": 0, "successful": 0, "unsuccessful": 0, "phones_found": 0, "phones_not_found": 0}
        self.stop_button.config(state="normal")
        raw_data = self.raw_data_text.get("1.0", tk.END).strip()
        threading.Thread(target=self.scrape_urls, args=(raw_data,), daemon=True).start()

    def stop_scraping(self):
        self.stop_flag = True
        self.progress_label.config(text="Stopping...")
        self.stop_button.config(state="disabled")

    def scrape_urls(self, raw_data):
        self.progress_label.config(text="Detecting URLs...")
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', raw_data)
        self.stats["detected"] = len(urls)
        
        if not urls:
            self.progress_label.config(text="No URLs found!")
            self.stop_button.config(state="disabled")
            return

        total_urls = len(urls)
        processed = 0
        max_workers = min(10, max(1, threading.active_count() + 1))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(self.scrape_website, url): url for url in urls}
            for future in as_completed(future_to_url):
                if self.stop_flag:
                    break
                processed += 1
                url = future_to_url[future]
                self.progress_label.config(text=f"Scraping {processed}/{total_urls} ({processed/total_urls*100:.1f}%): {url}")
                self.root.update_idletasks()
                try:
                    data = future.result()
                    if data and data["phone"]:
                        self.results.append(data)
                        self.stats["successful"] += 1
                        self.stats["phones_found"] += 1
                        self.tree.insert("", "end", values=(data["name"], data["url"], data["country"], data["email"], data["phone"], data["facebook"], data["instagram"]))
                    else:
                        self.stats["unsuccessful"] += 1
                        self.stats["phones_not_found"] += 1
                except Exception as e:
                    self.stats["unsuccessful"] += 1
                    self.stats["phones_not_found"] += 1
                    print(f"Error scraping {url}: {e}")

        self.progress_label.config(text="Scraping Complete!" if not self.stop_flag else "Scraping Stopped!")
        self.stop_button.config(state="disabled")
        self.display_report()

    def display_report(self):
        report = (
            f"URLs Detected: {self.stats['detected']}\n"
            f"Successfully Scraped: {self.stats['successful']}\n"
            f"Unsuccessful Scrapes: {self.stats['unsuccessful']}\n"
            f"Phone Numbers Found: {self.stats['phones_found']}\n"
            f"Phone Numbers Not Found: {self.stats['phones_not_found']}"
        )
        self.report_text.config(state="normal")
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", report)
        self.report_text.config(state="disabled")

    def scrape_website(self, url):
        if self.stop_flag:
            return None
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            home_soup = BeautifulSoup(response.text, 'html.parser')

            data = {
                "name": self.extract_domain_name(url),
                "url": url,
                "country": "",
                "email": "",
                "phone": "",
                "facebook": "",
                "instagram": ""
            }

            # Step 1: Determine country intelligently
            data["country"] = self.extract_country(url, home_soup)

            # Step 2: Exhaustive phone number search
            data["phone"] = self.extract_intelligent_phone(home_soup, data["country"])
            if not data["phone"]:
                for page in self.find_relevant_pages(url, home_soup):
                    try:
                        page_response = requests.get(page, headers=headers, timeout=10)
                        page_soup = BeautifulSoup(page_response.text, 'html.parser')
                        data["phone"] = self.extract_intelligent_phone(page_soup, data["country"])
                        if data["phone"]:
                            break
                    except:
                        continue
            if not data["phone"]:
                return None  # Skip if no phone found

            # Step 3: Exhaustive email search
            contact_soup = BeautifulSoup(requests.get(self.find_contact_page(url, home_soup) or url, headers=headers, timeout=10).text, 'html.parser')
            data["email"] = self.extract_intelligent_email(home_soup, contact_soup)
            if not data["email"]:
                for page in self.find_relevant_pages(url, home_soup):
                    try:
                        page_response = requests.get(page, headers=headers, timeout=10)
                        page_soup = BeautifulSoup(page_response.text, 'html.parser')
                        data["email"] = self.extract_intelligent_email(home_soup, page_soup)
                        if data["email"]:
                            break
                    except:
                        continue

            # Step 4: Extract social media links (Facebook and Instagram)
            data["facebook"], data["instagram"] = self.extract_social_media(url, home_soup)
            if not (data["facebook"] or data["instagram"]):
                for page in self.find_relevant_pages(url, home_soup):
                    try:
                        page_response = requests.get(page, headers=headers, timeout=10)
                        page_soup = BeautifulSoup(page_response.text, 'html.parser')
                        fb, ig = self.extract_social_media(page, page_soup)
                        data["facebook"] = data["facebook"] or fb
                        data["instagram"] = data["instagram"] or ig
                        if data["facebook"] and data["instagram"]:
                            break
                    except:
                        continue

            return data

        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None

    def extract_domain_name(self, url):
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        domain = re.sub(r'^www\.', '', domain)
        domain = re.sub(r'\..*', '', domain)
        return domain

    def find_relevant_pages(self, base_url, soup):
        keywords = ["contact", "about", "support", "call-us", "get-in-touch", "team", "directory", "help", "info", "staff", "faculty", "location"]
        pages = []
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if any(keyword in href for keyword in keywords) and not href.startswith("mailto:"):
                full_url = urljoin(base_url, href)
                if full_url not in pages and len(pages) < 5:
                    pages.append(full_url)
        return pages

    def find_contact_page(self, base_url, soup):
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if "contact" in href or "call" in href or "email" in href:
                return urljoin(base_url, href)
        return None

    def extract_intelligent_phone(self, soup, country):
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if href.startswith("tel:"):
                phone = href.replace("tel:", "").replace(" ", "").replace("-", "").replace(".", "")
                try:
                    parsed_phone = phonenumbers.parse(phone, self.country_to_region(country))
                    if phonenumbers.is_valid_number(parsed_phone):
                        return self.format_phone_number(parsed_phone, country)
                except phonenumbers.phonenumberutil.NumberParseException:
                    continue

        text = soup.get_text(separator=" ").lower() + " ".join([script.get_text() for script in soup.find_all("script") if script.get_text()])
        phone_patterns = [
            r'(\+\d{1,3}\s?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,5}',
            r'\d{2,4}-\d{3,4}-\d{3,5}',
            r'\d{8,12}',
            r'\d{2,4}\s\d{3,4}\s\d{3,5}'
        ]

        scored_phones = []
        region = self.country_to_region(country)
        for pattern in phone_patterns:
            candidates = re.findall(pattern, text)
            for phone in candidates:
                try:
                    parsed_phone = phonenumbers.parse(phone, region)
                    if not phonenumbers.is_valid_number(parsed_phone):
                        continue
                    formatted_phone = self.format_phone_number(parsed_phone, country)
                    score = 0
                    context = text[max(0, text.index(phone) - 150):text.index(phone) + 150]
                    if any(keyword in context for keyword in ["contact", "call", "phone", "tel", "reach", "support", "emergency", "hotline"]):
                        score += 40
                    if any(keyword in context for keyword in ["footer", "header", "team", "directory", "staff"]):
                        score += 20
                    if "toll" in context or "free" in context or "24/7" in context:
                        score += 15
                    scored_phones.append((formatted_phone, score))
                except phonenumbers.phonenumberutil.NumberParseException:
                    continue

        if scored_phones:
            best_phone, _ = max(scored_phones, key=lambda x: x[1])
            parsed_best = phonenumbers.parse(best_phone)
            country_code = str(parsed_best.country_code)
            expected_country = self.region_to_country(region)
            if country_code in phonenumbers.COUNTRY_CODE_TO_REGION_CODE and expected_country in phonenumbers.COUNTRY_CODE_TO_REGION_CODE[int(country_code)]:
                return best_phone
            else:
                for phone, score in scored_phones:
                    try:
                        parsed_phone = phonenumbers.parse(phone, None)
                        if phonenumbers.is_valid_number(parsed_phone):
                            return self.format_phone_number(parsed_phone, self.extract_country_from_phone(phone))
                    except:
                        continue
        return ""

    def format_phone_number(self, parsed_phone, country):
        country_code = phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.INTERNATIONAL).split(" ")[0]
        national_number = phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.NATIONAL).replace(" ", "").replace("-", "")
        
        if country == "Australia" and len(national_number) == 9:
            return f"{country_code}{national_number}"
        elif country in ["USA", "Canada"] and len(national_number) == 10:
            return f"{country_code}{national_number}"
        return phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)

    def extract_intelligent_email(self, home_soup, contact_soup):
        soups = [contact_soup, home_soup]
        for soup in soups:
            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                if href.startswith("mailto:"):
                    email = href.replace("mailto:", "").split("?")[0]
                    if re.match(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', email):
                        return email

        for soup in soups:
            text = soup.get_text().lower() + " ".join([script.get_text() for script in soup.find_all("script") if script.get_text()])
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            encoded_emails = re.findall(r'[\w\.-]+(?:\s*\[at\]\s*|\s*@\s*|\s*at\s*)[\w\.-]+\.(?:com|org|net|edu|gov|[a-z]{2})', text)
            if emails:
                for email in emails:
                    if any(keyword in email.lower() for keyword in ["info", "contact", "support", "hello", "sales", "enquiries", "admin"]):
                        return email
                return emails[0]
            if encoded_emails:
                return encoded_emails[0].replace("[at]", "@").replace(" at ", "@").replace(" ", "")

        return ""

    def extract_social_media(self, base_url, soup):
        facebook = ""
        instagram = ""
        
        # Check all <a> tags for href attributes
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            full_url = urljoin(base_url, href)
            
            # Facebook detection
            if "facebook.com" in full_url and not facebook:
                if not any(x in full_url for x in ["share", "login", "dialog", "plugins"]):
                    fb_path = full_url.split("facebook.com/")[-1].split("?")[0].rstrip("/")
                    if fb_path:
                        facebook = f"@{fb_path}"
            
            # Instagram detection
            if "instagram.com" in full_url and not instagram:
                if not any(x in full_url for x in ["explore", "login", "accounts"]):
                    ig_path = full_url.split("instagram.com/")[-1].split("?")[0].rstrip("/")
                    if ig_path:
                        instagram = f"@{ig_path}"
            
            if facebook and instagram:
                break
        
        # Fallback: Check text for encoded or plain URLs
        if not (facebook and instagram):
            text = soup.get_text().lower()
            fb_matches = re.findall(r'(?:https?://)?(?:www\.)?facebook\.com/([a-zA-Z0-9._-]+)/?', text)
            ig_matches = re.findall(r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9._-]+)/?', text)
            if fb_matches and not facebook:
                facebook = f"@{fb_matches[0]}"
            if ig_matches and not instagram:
                instagram = f"@{ig_matches[0]}"

        return facebook, instagram

    def extract_country(self, url, soup):
        tld = urlparse(url).netloc.split('.')[-1].lower()
        tld_country_map = {code.lower(): country for country, code in phonenumbers.COUNTRY_CODE_TO_REGION_CODE.items() for code in phonenumbers.COUNTRY_CODE_TO_REGION_CODE[country]}
        tld_country_map.update({"com": "USA", "uk": "United Kingdom", "au": "Australia", "ca": "Canada"})
        
        if tld in tld_country_map:
            return tld_country_map[tld]

        text = soup.get_text().lower()
        for country in phonenumbers.COUNTRY_CODE_TO_REGION_CODE.keys():
            if country.lower() in text or country.lower().replace(" ", "") in text:
                return country if country != "United States" else "USA"

        return tld_country_map.get(tld, "Unknown")

    def extract_country_from_phone(self, phone):
        try:
            parsed_phone = phonenumbers.parse(phone)
            country_code = str(parsed_phone.country_code)
            for country, codes in phonenumbers.COUNTRY_CODE_TO_REGION_CODE.items():
                if int(country_code) in codes:
                    return country if country != "United States" else "USA"
        except:
            return "Unknown"
        return "Unknown"

    def country_to_region(self, country):
        region_map = {country: code[0] for country, code in phonenumbers.COUNTRY_CODE_TO_REGION_CODE.items()}
        return region_map.get(country, "US")

    def region_to_country(self, region):
        for country, codes in phonenumbers.COUNTRY_CODE_TO_REGION_CODE.items():
            if region in codes:
                return country if country != "United States" else "USA"
        return "Unknown"

    def export_to_excel(self):
        if not self.results:
            messagebox.showwarning("No Data", "No data available to export!")
            return
        
        df = pd.DataFrame(self.results)
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            df.to_excel(file_path, index=False)
            messagebox.showinfo("Success", f"Data exported to {file_path}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ContactSyncScraper(root)
    root.mainloop()
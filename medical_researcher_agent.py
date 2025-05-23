import os
import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
import openai
from typing import List, Dict, Any, Optional, Tuple

class MedicalResearcherAgent:
    """
    Agent for extracting detailed information about medical researchers from various sources.
    """
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize the medical researcher agent with necessary configurations."""
        self.openai_api_key = openai_api_key
        
        
        if openai_api_key:
            try:
                openai.api_key = openai_api_key
                print("OpenAI API key set successfully")
            except Exception as e:
                print(f"Error setting OpenAI API key: {e}")
        else:
            from dotenv import load_dotenv
            load_dotenv()
            
            env_api_key = os.getenv("OPENAI_API_KEY")
            if env_api_key:
                openai.api_key = env_api_key
                self.openai_api_key = env_api_key
                print("OpenAI API key loaded from environment variables")
            else:
                print("No OpenAI API key found in environment variables")
        
        try:   
            pass 
        except Exception as e:
            print(f"Error loading OpenAI API key from environment: {e}")
            print("No OpenAI API key provided. AI-enhanced features will be disabled.")
        
        # Base URLs for medical research websites
        self.sources = {
            "pubmed": "https://pubmed.ncbi.nlm.nih.gov",
            "researchgate": "https://www.researchgate.net",
            "google_scholar": "https://scholar.google.com",
            "clinical_trials": "https://clinicaltrials.gov"
        }
        
        # Headers to simulate browser requests
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        }
        
        # Storing researcher data
        self.researchers_data = {}
        self.csv_data = None

    def load_csv_data(self, file_path: str) -> pd.DataFrame:
        """Load researcher data from CSV file."""
        try:
            self.csv_data = pd.read_csv(file_path)
            # here we are converting column names to title case for consistency
            self.csv_data.columns = [col.title() for col in self.csv_data.columns]
            print(f"Successfully loaded data for {len(self.csv_data)} researchers from CSV")
            return self.csv_data
        except Exception as e:
            print(f"Error loading CSV file: {e}")
            return pd.DataFrame()

    def search_researcher(self, name: str, specialization: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for information about a specific researcher across all sources.
        
        Args:
            name: Name of the researcher
            specialization: Optional specialization to narrow down search results
            
        Returns:
            Dictionary with all collected information about the researcher
        """

        # Validating the input
        if not name or not isinstance(name, str):
            raise ValueError("Researcher name must be a non-empty string")
            
        researcher_info = {
            "name": name,
            "specialization": specialization,
            "basic_info": {},
            "publications": [],
            "research_interests": [],
            "affiliations": [],
            "education": [],
            "clinical_trials": [],
            "citations": {},
            "collaborators": [],
            "source_urls": {},
            "raw_data": {}
        }
        
        # Checking if we have data in CSV first
        csv_data_found = False
        if self.csv_data is not None:
            researcher_from_csv = self._get_researcher_from_csv(name)
            if researcher_from_csv is not None:
                for key, value in researcher_from_csv.items():
                    if key in researcher_info:
                        researcher_info[key] = value
                researcher_info["data_sources"] = ["csv"]
                csv_data_found = True
                print(f"Found data in CSV for {name}")
        

        
        web_search_success = False
        
        # Scraping data from each source with retry mechanism
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for source, base_url in self.sources.items():
                futures.append(executor.submit(self._search_source_with_retry, source, base_url, name, specialization))
            
            for future in futures:
                try:
                    source_data = future.result()
                    if source_data and not source_data.get("error"):
                        source_name = source_data.get("source")
                        researcher_info["source_urls"][source_name] = source_data.get("url", "")
                        researcher_info["raw_data"][source_name] = source_data.get("raw_data", {})
                        
                        
                        if (source_data.get("publications") or 
                            source_data.get("affiliations") or 
                            source_data.get("research_interests") or 
                            source_data.get("basic_info")):
                            web_search_success = True
                        
                        # we merge publication data here
                        if "publications" in source_data and source_data["publications"]:
                            researcher_info["publications"].extend(source_data["publications"])
                        
                        # we merge other data here
                        for key in ["research_interests", "affiliations", "education", "clinical_trials", "collaborators"]:
                            if key in source_data and source_data[key]:
                                if isinstance(source_data[key], list):
                                    researcher_info[key].extend(source_data[key])
                        
                       
                        if "basic_info" in source_data and source_data["basic_info"]:
                            researcher_info["basic_info"].update(source_data["basic_info"])
                        
                        
                        if "citations" in source_data and source_data["citations"]:
                            researcher_info["citations"].update(source_data["citations"])
                except Exception as e:
                    print(f"Error processing search results: {e}")
        
        # removing duplicates or things which are repeating
        for key in ["publications", "research_interests", "affiliations", "education", "clinical_trials", "collaborators"]:
            if isinstance(researcher_info[key], list):
                try:
                    # we have to convert to string for comparison if not already strings
                    cleaned_items = []
                    seen = set()
                    for item in researcher_info[key]:
                        item_str = json.dumps(item) if isinstance(item, dict) else str(item)
                        if item_str not in seen:
                            seen.add(item_str)
                            cleaned_items.append(item)
                    researcher_info[key] = cleaned_items
                except Exception as e:
                    print(f"Error deduplicating {key}: {e}")
        
     
        if not csv_data_found and not web_search_success and self.openai_api_key:
            print("No data found from CSV or web searches, using OpenAI to generate information")
            try:
                ai_data = self._generate_researcher_info_with_ai(name, specialization)
                
                for key, value in ai_data.items():
                    if key in researcher_info and not researcher_info[key] and value:
                        researcher_info[key] = value
                
                
                researcher_info["ai_generated"] = True
            except Exception as e:
                print(f"Error generating information with AI: {e}")
        
        # enhance data with ai if we have some data and an OpenAI API key
        if (csv_data_found or web_search_success) and self.openai_api_key:
            try:
                enhanced_data = self._enhance_data_with_ai(researcher_info)
                researcher_info.update(enhanced_data)
            except Exception as e:
                print(f"Error enhancing data with AI: {e}")
        
        # saving data for this researcher
        self.researchers_data[name] = researcher_info
        
        return researcher_info
    
    def _search_source_with_retry(self, source: str, base_url: str, name: str, specialization: Optional[str] = None, 
                               max_retries: int = 2, delay: float = 1.0) -> Dict[str, Any]:
        """Search a specific source with retry logic."""
        retries = 0
        while retries <= max_retries:
            try:
                result = self._search_source(source, base_url, name, specialization)
                return result
            except Exception as e:
                print(f"Error searching {source} (attempt {retries+1}/{max_retries+1}): {e}")
                retries += 1
                if retries <= max_retries:
                    time.sleep(delay)  
                else:
                    return {"source": source, "error": str(e)}

    def _get_researcher_from_csv(self, name: str) -> Optional[Dict[str, Any]]:
        """Extract researcher information from loaded CSV data."""
        if self.csv_data is None:
            return None
        
        try:
            # First checking if the column names exist and are properly formatted
            if 'Name' not in self.csv_data.columns:
                if 'name' in self.csv_data.columns:
                    self.csv_data.rename(columns={'name': 'Name'}, inplace=True)
                else:
                    print("CSV file doesn't have a 'Name' column")
                    return None
            
           
            matches = self.csv_data[self.csv_data['Name'].str.lower() == name.lower()]
            if len(matches) == 0:
                matches = self.csv_data[self.csv_data['Name'].str.lower().str.contains(name.lower())]
            
            if len(matches) == 0:
                return None
            
            # taking out the first match
            researcher_row = matches.iloc[0]
            result = {}
            
            
            row_dict = researcher_row.to_dict()
            
            # Map CSV columns to our fields - this would need to be adjusted based on actual CSV structure right now I have mapped and show details here using sample_researchers.csv
            field_mapping = {
                'Name': 'name',
                'Specialization': 'specialization',
                'Affiliation': 'affiliations',
                'Research Interests': 'research_interests',
                'Publications': 'publications',
                'Email': ['basic_info', 'email'],
                'Phone': ['basic_info', 'phone'],
                'Location': ['basic_info', 'location'],
            }
            
            for csv_field, result_field in field_mapping.items():
                if csv_field in row_dict and not pd.isna(row_dict[csv_field]):
                    if isinstance(result_field, list):
                        if result_field[0] not in result:
                            result[result_field[0]] = {}
                        result[result_field[0]][result_field[1]] = row_dict[csv_field]
                    else:
                        # here we are handling list fields that might be comma-separated in CSV
                        if result_field in ['affiliations', 'research_interests', 'publications']:
                            if isinstance(row_dict[csv_field], str):
                                result[result_field] = [item.strip() for item in row_dict[csv_field].split(',')]
                            else:
                                result[result_field] = [row_dict[csv_field]]
                        else:
                            result[result_field] = row_dict[csv_field]
            
            return result
        except Exception as e:
            print(f"Error extracting researcher from CSV: {e}")
            return None

    def _search_source(self, source: str, base_url: str, name: str, specialization: Optional[str] = None) -> Dict[str, Any]:
        """Search a specific source for researcher information."""
        print(f"Searching {source} for information about {name}...")
        
        try:
            if source == "pubmed":
                return self._search_pubmed(name, specialization)
            elif source == "researchgate":
                return self._search_researchgate(name, specialization)
            elif source == "google_scholar":
                return self._search_google_scholar(name, specialization)
            elif source == "clinical_trials":
                return self._search_clinical_trials(name, specialization)
            else:
                print(f"Unknown source: {source}")
                return {"source": source, "error": f"Unknown source: {source}"}
        except Exception as e:
            print(f"Error searching {source}: {e}")
            return {"source": source, "error": str(e)}

    def _search_pubmed(self, name: str, specialization: Optional[str] = None) -> Dict[str, Any]:
        """Search PubMed for researcher information."""
        search_query = name
        if specialization:
            search_query = f"{name} {specialization}"
            
        search_url = f"{self.sources['pubmed']}/?term={search_query.replace(' ', '+')}"
        
        try:
            try:
                response = requests.get(search_url, headers=self.headers, timeout=10)
            except requests.exceptions.ConnectionError:
                return {"source": "pubmed", "url": search_url, "error": "Connection error. Check your internet connection."}
            except requests.exceptions.Timeout:
                return {"source": "pubmed", "url": search_url, "error": "Request timed out. The server might be overloaded."}
            except requests.exceptions.RequestException as e:
                return {"source": "pubmed", "url": search_url, "error": f"Request error: {str(e)}"}
                
            if response.status_code == 429:
                return {"source": "pubmed", "url": search_url, "error": "Rate limit exceeded. Try again later."}
            if response.status_code != 200:
                return {"source": "pubmed", "url": search_url, "error": f"Status code: {response.status_code}"}
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # extracting publication data
            publications = []
            results = soup.select(".docsum-content")
            
            for result in results[:10]:  # only first 10 results I am showing
                title_elem = result.select_one(".docsum-title")
                authors_elem = result.select_one(".docsum-authors")
                journal_elem = result.select_one(".docsum-journal")
                
                if title_elem:
                    pub = {
                        "title": title_elem.text.strip(),
                        "authors": authors_elem.text.strip() if authors_elem else "",
                        "journal": journal_elem.text.strip() if journal_elem else "",
                        "url": urljoin(self.sources['pubmed'], title_elem.parent['href']) if title_elem.parent.has_attr('href') else ""
                    }
                    publications.append(pub)
            
            return {
                "source": "pubmed",
                "url": search_url,
                "publications": publications,
                "raw_data": {"html": response.text[:5000]}  # Storing truncated HTML for further processing
            }
        except Exception as e:
            print(f"Error searching PubMed: {e}")
            return {"source": "pubmed", "url": search_url, "error": str(e)}

    def _search_researchgate(self, name: str, specialization: Optional[str] = None) -> Dict[str, Any]:
        """Search ResearchGate for researcher information."""
        search_url = f"{self.sources['researchgate']}/search/researcher?q={name.replace(' ', '+')}"
        
        try:
            response = requests.get(search_url, headers=self.headers)
            if response.status_code != 200:
                return {"source": "researchgate", "url": search_url, "error": f"Status code: {response.status_code}"}
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find researcher profile
            researcher_link = None
            researchers = soup.select(".nova-legacy-c-card__body")
            
            for researcher in researchers:
                name_elem = researcher.select_one("a.nova-legacy-e-link")
                if name_elem and name.lower() in name_elem.text.lower():
                    researcher_link = name_elem['href']
                    break
            
            if not researcher_link:
                return {"source": "researchgate", "url": search_url, "error": "Researcher profile not found"}
            
           
            profile_url = urljoin(self.sources['researchgate'], researcher_link)
            profile_response = requests.get(profile_url, headers=self.headers)
            
            if profile_response.status_code != 200:
                return {"source": "researchgate", "url": profile_url, "error": f"Profile status code: {profile_response.status_code}"}
            
            profile_soup = BeautifulSoup(profile_response.text, 'html.parser')
            
           
            basic_info = {}
            name_elem = profile_soup.select_one("h1")
            if name_elem:
                basic_info["full_name"] = name_elem.text.strip()
            
            
            affiliations = []
            affiliation_elems = profile_soup.select(".institution-name")
            for elem in affiliation_elems:
                affiliations.append(elem.text.strip())
            
            
            interests = []
            interest_elems = profile_soup.select(".research-interest-item")
            for elem in interest_elems:
                interests.append(elem.text.strip())
            
            
            publications = []
            publication_elems = profile_soup.select(".research-item-title")
            for elem in publication_elems[:10]:  # Limit to 10 publications
                pub_link = elem.find("a")
                if pub_link:
                    publications.append({
                        "title": pub_link.text.strip(),
                        "url": urljoin(self.sources['researchgate'], pub_link['href']) if pub_link.has_attr('href') else ""
                    })
            
            return {
                "source": "researchgate",
                "url": profile_url,
                "basic_info": basic_info,
                "affiliations": affiliations,
                "research_interests": interests,
                "publications": publications,
                "raw_data": {"html": profile_response.text[:5000]}  # Store truncated HTML
            }
        except Exception as e:
            print(f"Error searching ResearchGate: {e}")
            return {"source": "researchgate", "url": search_url, "error": str(e)}

    def _search_google_scholar(self, name: str, specialization: Optional[str] = None) -> Dict[str, Any]:
        """Search Google Scholar for researcher information."""
        search_url = f"{self.sources['google_scholar']}/scholar?q={name.replace(' ', '+')}"
        
        try:
            response = requests.get(search_url, headers=self.headers)
            if response.status_code != 200:
                return {"source": "google_scholar", "url": search_url, "error": f"Status code: {response.status_code}"}
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            
            publications = []
            results = soup.select(".gs_ri")
            
            for result in results[:10]:  
                title_elem = result.select_one(".gs_rt")
                authors_elem = result.select_one(".gs_a")
                snippet_elem = result.select_one(".gs_rs")
                
                if title_elem:
                    link = title_elem.find("a")
                    pub = {
                        "title": title_elem.text.strip(),
                        "authors": authors_elem.text.strip() if authors_elem else "",
                        "snippet": snippet_elem.text.strip() if snippet_elem else "",
                        "url": link['href'] if link and link.has_attr('href') else ""
                    }
                    publications.append(pub)
            
            
            citations = {}
            citation_elem = soup.select_one(".gs_rnd")
            if citation_elem:
                match = re.search(r'Cited by (\d+)', citation_elem.text)
                if match:
                    citations["total"] = int(match.group(1))
            
            return {
                "source": "google_scholar",
                "url": search_url,
                "publications": publications,
                "citations": citations,
                "raw_data": {"html": response.text[:5000]}  
            }
        except Exception as e:
            print(f"Error searching Google Scholar: {e}")
            return {"source": "google_scholar", "url": search_url, "error": str(e)}

    def _search_clinical_trials(self, name: str, specialization: Optional[str] = None) -> Dict[str, Any]:
        """Search ClinicalTrials.gov for researcher information."""
        search_url = f"{self.sources['clinical_trials']}/search?term={name.replace(' ', '+')}&recrs=e&type=Intr"
        
        try:
            response = requests.get(search_url, headers=self.headers)
            if response.status_code != 200:
                return {"source": "clinical_trials", "url": search_url, "error": f"Status code: {response.status_code}"}
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            
            clinical_trials = []
            results = soup.select(".ct-search-result")
            
            for result in results[:10]:  # Limit to first 10 results
                title_elem = result.select_one(".ct-title")
                if title_elem:
                    link = title_elem.find("a")
                    status_elem = result.select_one(".ct-status")
                    condition_elem = result.select_one(".ct-condition")
                    
                    trial = {
                        "title": title_elem.text.strip(),
                        "status": status_elem.text.strip() if status_elem else "",
                        "condition": condition_elem.text.strip() if condition_elem else "",
                        "url": urljoin(self.sources['clinical_trials'], link['href']) if link and link.has_attr('href') else ""
                    }
                    clinical_trials.append(trial)
            
            return {
                "source": "clinical_trials",
                "url": search_url,
                "clinical_trials": clinical_trials,
                "raw_data": {"html": response.text[:5000]}  
            }
        except Exception as e:
            print(f"Error searching Clinical Trials: {e}")
            return {"source": "clinical_trials", "url": search_url, "error": str(e)}

    def _generate_researcher_info_with_ai(self, name: str, specialization: Optional[str] = None) -> Dict[str, Any]:
        """Generate researcher information using OpenAI when no data is found from other sources."""
        if not self.openai_api_key:
            print("No OpenAI API key available for generating researcher information.")
            return {
                "name": name,
                "specialization": specialization,
                "summary": "No detailed information available. Please provide an OpenAI API key for enhanced data.",
                "ai_generated": False
            }
            
        try:
            spec_text = f" who specializes in {specialization}" if specialization else ""
            
            prompt = f"""
            I need comprehensive information about medical researcher {name}{spec_text}.
            Please search the web and provide:
            1. A summary of their background and expertise
            2. Their key research contributions
            3. Their affiliations (with current position and institution)
            4. Research interests
            5. Notable publications (with DIRECT LINKS to PubMed, Google Scholar, or journal websites)
            6. Educational background and degrees (with institutions, years, and degree types)
            7. Any clinical trials they're involved in (with DIRECT LINKS to ClinicalTrials.gov or other sources)
            
            For publications and clinical trials, it's ESSENTIAL to include the direct URLs to the source pages.
            For educational background, include complete details about degrees, institutions, and years when available.
            
            Format the response as a JSON with these keys:
            - basic_info (object with fields like email if public, position, etc.)
            - summary (string)
            - key_contributions (string)
            - education (array of strings, each with complete information)
            - affiliations (array of strings)
            - research_interests (array of strings)
            - publications (array of objects with title, authors, journal, url)
            - clinical_trials (array of objects with title, status, condition, url)
            
            For all URLs, provide direct links that actually work and point to the correct resources.
            """
            
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o", 
                    messages=[
                        {"role": "system", "content": "You are a research assistant specializing in medical research. Provide the most accurate information possible about medical researchers in JSON format. Use web search capabilities to find the most up-to-date information. Focus specifically on providing accurate education history and direct, valid URLs to publications and clinical trials."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                
                # extracting and parsing the JSON response
                ai_content = response.choices[0].message.content
                
                # extracting JSON from response (it might be surrounded by markdown code blocks may be...)
                json_match = re.search(r'```json\n(.*?)\n```', ai_content, re.DOTALL)
                if json_match:
                    ai_content = json_match.group(1)
                
                researcher_data = json.loads(ai_content)
                researcher_data["ai_generated"] = True
                
                # checking if publication URLs are valid or not
                if "publications" in researcher_data:
                    for pub in researcher_data["publications"]:
                        if "url" not in pub or not pub["url"] or not pub["url"].startswith(("http://", "https://")):
                            # Try to construct a search URL if missing
                            if "title" in pub and pub["title"]:
                                pub_title = pub["title"].replace(" ", "+")
                                pub["url"] = f"https://pubmed.ncbi.nlm.nih.gov/?term={pub_title}"
                
                # checking clinical trial URLs are valid or not
                if "clinical_trials" in researcher_data:
                    for trial in researcher_data["clinical_trials"]:
                        if "url" not in trial or not trial["url"] or not trial["url"].startswith(("http://", "https://")):
                            # Add a default clinical trials search if URL is missing
                            if "title" in trial and trial["title"]:
                                trial_title = trial["title"].replace(" ", "+")
                                trial["url"] = f"https://clinicaltrials.gov/search?term={trial_title}"
                
                return researcher_data
            except openai.error.AuthenticationError:
                print("Authentication error with OpenAI API. Check your API key.")
                return {
                    "name": name,
                    "specialization": specialization,
                    "summary": "Could not retrieve information: OpenAI API authentication failed. Please check your API key.",
                    "ai_generated": False
                }
            except openai.error.RateLimitError:
                print("OpenAI API rate limit exceeded.")
                return {
                    "name": name,
                    "specialization": specialization,
                    "summary": "Could not retrieve information: OpenAI API rate limit exceeded. Please try again later.",
                    "ai_generated": False
                }
        except Exception as e:
            print(f"Error generating researcher info with AI: {e}")
            return {
                "name": name,
                "specialization": specialization,
                "summary": f"Error retrieving information. Please try again later.",
                "ai_generated": False
            }

    def _enhance_data_with_ai(self, researcher_info: Dict[str, Any]) -> Dict[str, Any]:
        """Use OpenAI API to enhance researcher data by extracting additional insights."""
        if not self.openai_api_key:
            return {}
            
        try:
            # prompt with data (we can customize it..)
            prompt = f"""
            I have collected the following information about medical researcher {researcher_info['name']}:
            
            Basic Info: {json.dumps(researcher_info['basic_info'], indent=2)}
            
            Affiliations: {', '.join(researcher_info['affiliations']) if researcher_info['affiliations'] else 'None found'}
            
            Research Interests: {', '.join(researcher_info['research_interests']) if researcher_info['research_interests'] else 'None found'}
            
            Publications: {json.dumps(researcher_info['publications'][:5], indent=2) if researcher_info['publications'] else 'None found'}
            
            Clinical Trials: {json.dumps(researcher_info['clinical_trials'][:3], indent=2) if researcher_info['clinical_trials'] else 'None found'}
            
            Education: {json.dumps(researcher_info.get('education', []), indent=2)}
            
            Based on this information, please:
            1. Summarize this researcher's background and main areas of expertise in 2-3 sentences
            2. Identify their key research contributions
            3. Extract any additional insights about their career, impact, or specialization
            4. Note any collaborations or research networks they might be part of
            5. Fill in any missing educational details (degrees, institutions, years) that can be inferred
            6. Validate and fix any publication URLs, ensuring they point to valid sources (PubMed, journal sites, etc.)
            7. Validate and fix any clinical trial URLs, ensuring they point to ClinicalTrials.gov or other valid sources
            
            Format your response as a structured JSON with the following keys:
            - summary
            - key_contributions
            - additional_insights
            - research_network
            - education (if you can add details beyond what's already provided)
            - publication_urls (list of objects with publication title and corrected URL)
            - clinical_trial_urls (list of objects with trial title and corrected URL)
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-4o", 
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that specializes in analyzing medical researcher profiles and extracting key insights. You also verify and correct publication and clinical trial URLs, and ensure complete educational information. Your responses should be strictly in valid JSON format with the fields requested."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            # extracting and parsing the JSON response
            ai_content = response.choices[0].message.content
            
           
            json_match = re.search(r'```json\n(.*?)\n```', ai_content, re.DOTALL)
            if json_match:
                ai_content = json_match.group(1)
            
            enhanced_data = json.loads(ai_content)
            enhanced_data["ai_enhanced"] = True
            
           
            if "education" in enhanced_data and enhanced_data["education"]:
                if not researcher_info.get("education") or len(enhanced_data["education"]) > len(researcher_info.get("education", [])):
                    researcher_info["education"] = enhanced_data["education"]
            
            # Updating publication URLs if provided
            if "publication_urls" in enhanced_data and enhanced_data["publication_urls"]:
                for pub_url_info in enhanced_data["publication_urls"]:
                    if "title" in pub_url_info and "url" in pub_url_info and pub_url_info["url"]:
                        # Find matching publication and update URL
                        for pub in researcher_info.get("publications", []):
                            if pub.get("title") and pub_url_info["title"] in pub["title"]:
                                pub["url"] = pub_url_info["url"]
                                break
            
            # Updating clinical trial URLs if provided
            if "clinical_trial_urls" in enhanced_data and enhanced_data["clinical_trial_urls"]:
                for trial_url_info in enhanced_data["clinical_trial_urls"]:
                    if "title" in trial_url_info and "url" in trial_url_info and trial_url_info["url"]:
                        # Find matching clinical trial and update URL
                        for trial in researcher_info.get("clinical_trials", []):
                            if trial.get("title") and trial_url_info["title"] in trial["title"]:
                                trial["url"] = trial_url_info["url"]
                                break
            
            return enhanced_data
        
        except Exception as e:
            print(f"Error enhancing data with AI: {e}")
            return {"ai_enhanced": False, "ai_error": str(e)}

    def ask_question(self, question: str, researcher_name: Optional[str] = None) -> str:
        """
        Ask a question about a researcher and get an AI-generated response.
        
        Args:
            question: The question to ask
            researcher_name: Optional name of researcher to focus on
            
        Returns:
            AI-generated answer to the question
        """
        if not self.openai_api_key:
            return "OpenAI API key is required to ask questions. Please add it in the sidebar or set it in your environment variables."
        
        try:
           
            context = ""
            
            if researcher_name and researcher_name in self.researchers_data:
                # if we have data about this researcher, use it for context
                researcher = self.researchers_data[researcher_name]
                
                # here build context with information we have
                context_parts = []
                
                if researcher.get('basic_info'):
                    context_parts.append(f"Basic Info: {json.dumps(researcher['basic_info'], indent=2)}")
                
                if researcher.get('affiliations'):
                    context_parts.append(f"Affiliations: {', '.join(researcher['affiliations'])}")
                
                if researcher.get('research_interests'):
                    context_parts.append(f"Research Interests: {', '.join(researcher['research_interests'])}")
                
                if researcher.get('publications'):
                    pub_data = researcher['publications'][:5]
                    context_parts.append(f"Publications: {json.dumps(pub_data, indent=2)}")
                
                if researcher.get('clinical_trials'):
                    trial_data = researcher['clinical_trials'][:3]
                    context_parts.append(f"Clinical Trials: {json.dumps(trial_data, indent=2)}")
                
                if researcher.get('summary'):
                    context_parts.append(f"Summary: {researcher['summary']}")
                
                if researcher.get('key_contributions'):
                    context_parts.append(f"Key Contributions: {researcher['key_contributions']}")
                
                # Joining all parts
                if context_parts:
                    context = f"Information about {researcher_name}:\n\n" + "\n\n".join(context_parts)
                else:
                    context = f"I have limited information about {researcher_name}."
            
            elif researcher_name:
                # We don't have data yet, but a name was specified
                context = f"I don't have detailed information about {researcher_name} in my database, but I'll search for information online."
                try:
                   
                    researcher_data = self._generate_researcher_info_with_ai(researcher_name)
                    if researcher_data:
                        self.researchers_data[researcher_name] = researcher_data
                        new_context_parts = []
                        
                        if researcher_data.get('summary'):
                            new_context_parts.append(f"Summary: {researcher_data['summary']}")
                        
                        if researcher_data.get('key_contributions'):
                            new_context_parts.append(f"Key Contributions: {researcher_data['key_contributions']}")
                            
                        if researcher_data.get('affiliations'):
                            new_context_parts.append(f"Affiliations: {', '.join(researcher_data['affiliations'])}")
                        
                        if researcher_data.get('research_interests'):
                            new_context_parts.append(f"Research Interests: {', '.join(researcher_data['research_interests'])}")
                        
                        if new_context_parts:
                            context = f"Information I found about {researcher_name}:\n\n" + "\n\n".join(new_context_parts)
                except Exception as e:
                    print(f"Error getting researcher info from web: {e}")
                    
            
            elif self.researchers_data:
                # No specific researcher, but we have data on some researchers
                context = "I have information on the following researchers: " + ", ".join(self.researchers_data.keys())
            
            
            prompt = f"""
            {context}
            
            Question: {question}
            
            Please provide a detailed answer based on the information available. 
            If you don't have enough information in the provided context, feel free to use your knowledge to answer the question. 
            When using information not provided in the context, please indicate this in your answer.
            """
            
            
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o",  # Use GPT-4 for better responses
                    messages=[
                        {"role": "system", "content": "You are a knowledgeable assistant specializing in medical research. Provide detailed information about medical researchers based on the available data. If asked a question that requires additional information, use your knowledge to provide the best answer possible, but indicate when you're going beyond the directly provided context."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5
                )
                
                # returning the response content
                return response.choices[0].message.content
                
            except openai.error.AuthenticationError:
                return "Authentication error: Your OpenAI API key is invalid. Please check your API key and try again."
            except openai.error.APIConnectionError:
                return "Connection error: Unable to connect to the OpenAI API. Please check your internet connection and try again."
            except openai.error.RateLimitError:
                return "Rate limit error: You've exceeded your OpenAI API rate limit. Please try again later."
            except Exception as api_error:
                return f"OpenAI API error: {str(api_error)}"
        
        except Exception as e:
            print(f"Error asking question: {e}")
            return f"Error processing your question: {str(e)}"
    
    def search_researcher_without_csv(self, name: str, specialization: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for information about a specific researcher when no CSV data is available.
        This is a convenience method that doesn't rely on pre-loaded CSV data.
        """
        # temporarily set csv_data to None to bypass CSV search
        original_csv_data = self.csv_data
        self.csv_data = None
        
        try:
            result = self.search_researcher(name, specialization)
            return result
        finally:
            # Restore original csv_data
            self.csv_data = original_csv_data

    def generate_researcher_report(self, researcher_name: str) -> str:
        """
        Generate a comprehensive formatted report about a researcher.
        
        Args:
            researcher_name: Name of the researcher to generate a report for
            
        Returns:
            A formatted text report about the researcher
        """
        if researcher_name not in self.researchers_data:
            return f"No data available for {researcher_name}. Please search for this researcher first."
        
        researcher = self.researchers_data[researcher_name]
        
        report = [
            f"# Research Profile: {researcher_name}",
            "\n## Basic Information",
        ]
        
       
        if researcher['basic_info']:
            for key, value in researcher['basic_info'].items():
                report.append(f"- {key.replace('_', ' ').title()}: {value}")
        else:
            report.append("- No basic information available")
        
        
        if 'summary' in researcher and researcher['summary']:
            report.append("\n## Summary")
            report.append(researcher['summary'])
        
      
        report.append("\n## Affiliations")
        if researcher['affiliations']:
            for affiliation in researcher['affiliations']:
                report.append(f"- {affiliation}")
        else:
            report.append("- No affiliations found")
        
        
        report.append("\n## Research Interests")
        if researcher['research_interests']:
            for interest in researcher['research_interests']:
                report.append(f"- {interest}")
        else:
            report.append("- No research interests found")
        
        # adding key contributions if available
        if 'key_contributions' in researcher and researcher['key_contributions']:
            report.append("\n## Key Contributions")
            report.append(researcher['key_contributions'])
        
        # adding publications
        report.append("\n## Publications")
        if researcher['publications']:
            for i, pub in enumerate(researcher['publications'][:10], 1):  # Limit to 10 publications
                title = pub.get('title', 'Untitled')
                authors = pub.get('authors', 'Unknown authors')
                journal = pub.get('journal', '')
                
                pub_entry = f"{i}. {title}"
                if authors:
                    pub_entry += f"\n   Authors: {authors}"
                if journal:
                    pub_entry += f"\n   Journal: {journal}"
                
                report.append(pub_entry)
                report.append("")  # Add empty line for readability
        else:
            report.append("- No publications found")
        
       
        report.append("\n## Clinical Trials")
        if researcher['clinical_trials']:
            for i, trial in enumerate(researcher['clinical_trials'], 1):
                title = trial.get('title', 'Untitled trial')
                status = trial.get('status', 'Unknown status')
                condition = trial.get('condition', 'Unknown condition')
                
                trial_entry = f"{i}. {title}"
                if status:
                    trial_entry += f"\n   Status: {status}"
                if condition:
                    trial_entry += f"\n   Condition: {condition}"
                
                report.append(trial_entry)
                report.append("")  
        else:
            report.append("- No clinical trials found")
        
      
        if 'additional_insights' in researcher and researcher['additional_insights']:
            report.append("\n## Additional Insights")
            report.append(researcher['additional_insights'])
        
       
        if 'research_network' in researcher and researcher['research_network']:
            report.append("\n## Research Network")
            report.append(researcher['research_network'])
        
        
        report.append("\n## Data Sources")
        if researcher['source_urls']:
            for source, url in researcher['source_urls'].items():
                if url:
                    report.append(f"- {source.title()}: {url}")
        else:
            report.append("- Data extracted from local files only")
        
        return "\n".join(report)

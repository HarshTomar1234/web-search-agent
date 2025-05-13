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
        
        # Set the OpenAI API key if provided
        if openai_api_key:
            try:
                openai.api_key = openai_api_key
                print("OpenAI API key set successfully")
            except Exception as e:
                print(f"Error setting OpenAI API key: {e}")
        else:
            # Try to get API key from environment variables
            env_api_key = os.getenv("OPENAI_API_KEY")
            if env_api_key:
                try:
                    openai.api_key = env_api_key
                    self.openai_api_key = env_api_key
                    print("OpenAI API key loaded from environment variables")
                except Exception as e:
                    print(f"Error setting OpenAI API key from environment: {e}")
            else:
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
        
        # Store researcher data
        self.researchers_data = {}
        self.csv_data = None

    def load_csv_data(self, file_path: str) -> pd.DataFrame:
        """Load researcher data from CSV file."""
        try:
            self.csv_data = pd.read_csv(file_path)
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
        # Validate inputs
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
        
        # Check if we have data in CSV first
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
        
        # Track success of web searches
        web_search_success = False
        
        # Scrape data from each source with retry mechanism
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
                        
                        # Check if useful data was found
                        if (source_data.get("publications") or 
                            source_data.get("affiliations") or 
                            source_data.get("research_interests") or 
                            source_data.get("basic_info")):
                            web_search_success = True
                        
                        # Merge publication data
                        if "publications" in source_data and source_data["publications"]:
                            researcher_info["publications"].extend(source_data["publications"])
                        
                        # Merge other data
                        for key in ["research_interests", "affiliations", "education", "clinical_trials", "collaborators"]:
                            if key in source_data and source_data[key]:
                                if isinstance(source_data[key], list):
                                    researcher_info[key].extend(source_data[key])
                        
                        # Update basic info
                        if "basic_info" in source_data and source_data["basic_info"]:
                            researcher_info["basic_info"].update(source_data["basic_info"])
                        
                        # Update citations
                        if "citations" in source_data and source_data["citations"]:
                            researcher_info["citations"].update(source_data["citations"])
                except Exception as e:
                    print(f"Error processing search results: {e}")
        
        # Remove duplicates
        for key in ["publications", "research_interests", "affiliations", "education", "clinical_trials", "collaborators"]:
            if isinstance(researcher_info[key], list):
                try:
                    # Convert to string for comparison if not already strings
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
        
        # If no data found from web searches or CSV, use OpenAI to generate some information
        if not csv_data_found and not web_search_success and self.openai_api_key:
            print("No data found from CSV or web searches, using OpenAI to generate information")
            try:
                ai_data = self._generate_researcher_info_with_ai(name, specialization)
                # Merge AI-generated data with existing data
                for key, value in ai_data.items():
                    if key in researcher_info and not researcher_info[key] and value:
                        researcher_info[key] = value
                
                # Mark as AI-generated
                researcher_info["ai_generated"] = True
            except Exception as e:
                print(f"Error generating information with AI: {e}")
        
        # Enhance data with AI if we have some data and an OpenAI API key
        if (csv_data_found or web_search_success) and self.openai_api_key:
            try:
                enhanced_data = self._enhance_data_with_ai(researcher_info)
                researcher_info.update(enhanced_data)
            except Exception as e:
                print(f"Error enhancing data with AI: {e}")
        
        # Save data for this researcher
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
                    time.sleep(delay)  # Wait before retrying
                else:
                    return {"source": source, "error": str(e)}

    def _get_researcher_from_csv(self, name: str) -> Optional[Dict[str, Any]]:
        """Extract researcher information from loaded CSV data."""
        if self.csv_data is None:
            return None
        
        try:
            # First check if the column names exist and are properly formatted
            if 'Name' not in self.csv_data.columns:
                if 'name' in self.csv_data.columns:
                    self.csv_data.rename(columns={'name': 'Name'}, inplace=True)
                else:
                    print("CSV file doesn't have a 'Name' column")
                    return None
            
            # Case insensitive search for researcher name
            matches = self.csv_data[self.csv_data['Name'].str.lower() == name.lower()]
            if len(matches) == 0:
                # Try to find partial matches
                matches = self.csv_data[self.csv_data['Name'].str.lower().str.contains(name.lower())]
            
            if len(matches) == 0:
                return None
            
            # Take the first match
            researcher_row = matches.iloc[0]
            result = {}
            
            # Convert row to dictionary and map to our schema
            row_dict = researcher_row.to_dict()
            
            # Map CSV columns to our fields - this would need to be adjusted based on actual CSV structure
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
                        # Nested field
                        if result_field[0] not in result:
                            result[result_field[0]] = {}
                        result[result_field[0]][result_field[1]] = row_dict[csv_field]
                    else:
                        # Handle list fields that might be comma-separated in CSV
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
            
            # Extract publication data
            publications = []
            results = soup.select(".docsum-content")
            
            for result in results[:10]:  # Limit to first 10 results to avoid overloading
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
                "raw_data": {"html": response.text[:5000]}  # Store truncated HTML for further processing
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
            
            # Visit researcher profile
            profile_url = urljoin(self.sources['researchgate'], researcher_link)
            profile_response = requests.get(profile_url, headers=self.headers)
            
            if profile_response.status_code != 200:
                return {"source": "researchgate", "url": profile_url, "error": f"Profile status code: {profile_response.status_code}"}
            
            profile_soup = BeautifulSoup(profile_response.text, 'html.parser')
            
            # Extract basic info
            basic_info = {}
            name_elem = profile_soup.select_one("h1")
            if name_elem:
                basic_info["full_name"] = name_elem.text.strip()
            
            # Extract affiliations
            affiliations = []
            affiliation_elems = profile_soup.select(".institution-name")
            for elem in affiliation_elems:
                affiliations.append(elem.text.strip())
            
            # Extract research interests
            interests = []
            interest_elems = profile_soup.select(".research-interest-item")
            for elem in interest_elems:
                interests.append(elem.text.strip())
            
            # Extract publications
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
            
            # Extract publications
            publications = []
            results = soup.select(".gs_ri")
            
            for result in results[:10]:  # Limit to first 10 results
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
            
            # Extract citations info
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
                "raw_data": {"html": response.text[:5000]}  # Store truncated HTML
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
            
            # Extract clinical trials
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
                "raw_data": {"html": response.text[:5000]}  # Store truncated HTML
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
            Please provide:
            1. A summary of their background and expertise
            2. Their key research contributions
            3. Their affiliations
            4. Research interests
            5. Notable publications
            6. Any clinical trials they're involved in (if applicable)
            
            Format the response as a JSON with these keys:
            - basic_info (object)
            - summary (string)
            - key_contributions (string)
            - affiliations (array of strings)
            - research_interests (array of strings)
            - publications (array of objects with title, authors, journal)
            - clinical_trials (array of objects with title, status, condition)
            """
            
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o",  # You can change to a different model if needed
                    messages=[
                        {"role": "system", "content": "You are a research assistant specializing in medical research. Provide the most accurate information possible about medical researchers in JSON format."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                
                # Extract and parse the JSON response
                ai_content = response.choices[0].message.content
                
                # Extract JSON from response (it might be surrounded by markdown code blocks)
                json_match = re.search(r'```json\n(.*?)\n```', ai_content, re.DOTALL)
                if json_match:
                    ai_content = json_match.group(1)
                
                researcher_data = json.loads(ai_content)
                researcher_data["ai_generated"] = True
                
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
            # Prepare prompt with researcher data
            prompt = f"""
            I have collected the following information about medical researcher {researcher_info['name']}:
            
            Basic Info: {json.dumps(researcher_info['basic_info'], indent=2)}
            
            Affiliations: {', '.join(researcher_info['affiliations']) if researcher_info['affiliations'] else 'None found'}
            
            Research Interests: {', '.join(researcher_info['research_interests']) if researcher_info['research_interests'] else 'None found'}
            
            Publications: {json.dumps(researcher_info['publications'][:5], indent=2) if researcher_info['publications'] else 'None found'}
            
            Clinical Trials: {json.dumps(researcher_info['clinical_trials'][:3], indent=2) if researcher_info['clinical_trials'] else 'None found'}
            
            Based on this information, please:
            1. Summarize this researcher's background and main areas of expertise in 2-3 sentences
            2. Identify their key research contributions
            3. Extract any additional insights about their career, impact, or specialization
            4. Note any collaborations or research networks they might be part of
            
            Format your response as a structured JSON with the following keys:
            - summary
            - key_contributions
            - additional_insights
            - research_network
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-4o",  # You can change to a different model if needed
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that specializes in analyzing medical researcher profiles and extracting key insights. Your responses should be strictly in valid JSON format with the fields requested."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            # Extract and parse the JSON response
            ai_content = response.choices[0].message.content
            
            # Extract JSON from response (it might be surrounded by markdown code blocks)
            json_match = re.search(r'```json\n(.*?)\n```', ai_content, re.DOTALL)
            if json_match:
                ai_content = json_match.group(1)
            
            enhanced_data = json.loads(ai_content)
            enhanced_data["ai_enhanced"] = True
            
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
            # Prepare context for the question
            context = ""
            
            if researcher_name and researcher_name in self.researchers_data:
                # We have data about this researcher, use it for context
                researcher = self.researchers_data[researcher_name]
                
                # Build context with information we have
                context_parts = []
                
                if researcher.get('basic_info'):
                    context_parts.append(f"Basic Info: {json.dumps(researcher['basic_info'], indent=2)}")
                
                if researcher.get('affiliations'):
                    context_parts.append(f"Affiliations: {', '.join(researcher['affiliations'])}")
                
                if researcher.get('research_interests'):
                    context_parts.append(f"Research Interests: {', '.join(researcher['research_interests'])}")
                
                if researcher.get('publications'):
                    # Limit to 5 publications to keep context size reasonable
                    pub_data = researcher['publications'][:5]
                    context_parts.append(f"Publications: {json.dumps(pub_data, indent=2)}")
                
                if researcher.get('clinical_trials'):
                    # Limit to 3 trials
                    trial_data = researcher['clinical_trials'][:3]
                    context_parts.append(f"Clinical Trials: {json.dumps(trial_data, indent=2)}")
                
                if researcher.get('summary'):
                    context_parts.append(f"Summary: {researcher['summary']}")
                
                if researcher.get('key_contributions'):
                    context_parts.append(f"Key Contributions: {researcher['key_contributions']}")
                
                # Join all parts with newlines
                if context_parts:
                    context = f"Information about {researcher_name}:\n\n" + "\n\n".join(context_parts)
                else:
                    context = f"I have limited information about {researcher_name}."
            
            elif researcher_name:
                # We don't have data yet, but a name was specified
                context = f"I don't have detailed information about {researcher_name} yet. Let me search for information first."
                # You could automatically trigger a search here
                return context
            
            elif self.researchers_data:
                # No specific researcher, but we have data on some researchers
                context = "I have information on the following researchers: " + ", ".join(self.researchers_data.keys())
            
            # Prepare the question prompt
            prompt = f"""
            {context}
            
            Question: {question}
            
            Please provide a detailed answer based on the information available.
            """
            
            # Make the API call
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o",  # You can change to a different model if needed
                    messages=[
                        {"role": "system", "content": "You are a knowledgeable assistant specializing in medical research. Provide detailed information about medical researchers based on the available data. If information is not available, acknowledge this limitation."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5
                )
                
                # Return the response content
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
        # Temporarily set csv_data to None to bypass CSV search
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
        
        # Build the report sections
        report = [
            f"# Research Profile: {researcher_name}",
            "\n## Basic Information",
        ]
        
        # Add basic info
        if researcher['basic_info']:
            for key, value in researcher['basic_info'].items():
                report.append(f"- {key.replace('_', ' ').title()}: {value}")
        else:
            report.append("- No basic information available")
        
        # Add AI-generated summary if available
        if 'summary' in researcher and researcher['summary']:
            report.append("\n## Summary")
            report.append(researcher['summary'])
        
        # Add affiliations
        report.append("\n## Affiliations")
        if researcher['affiliations']:
            for affiliation in researcher['affiliations']:
                report.append(f"- {affiliation}")
        else:
            report.append("- No affiliations found")
        
        # Add research interests
        report.append("\n## Research Interests")
        if researcher['research_interests']:
            for interest in researcher['research_interests']:
                report.append(f"- {interest}")
        else:
            report.append("- No research interests found")
        
        # Add key contributions if available
        if 'key_contributions' in researcher and researcher['key_contributions']:
            report.append("\n## Key Contributions")
            report.append(researcher['key_contributions'])
        
        # Add publications
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
        
        # Add clinical trials
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
                report.append("")  # Add empty line for readability
        else:
            report.append("- No clinical trials found")
        
        # Add additional insights if available
        if 'additional_insights' in researcher and researcher['additional_insights']:
            report.append("\n## Additional Insights")
            report.append(researcher['additional_insights'])
        
        # Add research network if available
        if 'research_network' in researcher and researcher['research_network']:
            report.append("\n## Research Network")
            report.append(researcher['research_network'])
        
        # Add data sources
        report.append("\n## Data Sources")
        if researcher['source_urls']:
            for source, url in researcher['source_urls'].items():
                if url:
                    report.append(f"- {source.title()}: {url}")
        else:
            report.append("- Data extracted from local files only")
        
        return "\n".join(report) 
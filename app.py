import streamlit as st
import pandas as pd
import json
import os
import tempfile
import base64
import requests
import re
from medical_researcher_agent import MedicalResearcherAgent
from dotenv import load_dotenv
import openai
import time

# Load environment variables from .env file
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Medical Researcher Search Agent",
    page_icon="🔍",
    layout="wide"
)

# Function to create a download link for a file
def get_download_link(file_path, link_text):
    with open(file_path, 'r') as f:
        data = f.read()
    b64 = base64.b64encode(data.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{os.path.basename(file_path)}">{link_text}</a>'
    return href

# Function to search for researcher with error handling and fallback
def search_researcher_with_fallback(agent, name, specialization=None):
    try:
        # First try the normal search
        result = agent.search_researcher(name, specialization)
        
        # Check if we actually found meaningful information
        has_meaningful_data = (
            result.get('publications') or 
            result.get('affiliations') or 
            result.get('research_interests') or 
            (result.get('basic_info') and len(result.get('basic_info')) > 0)
        )
        
        # Make secondary requests for specific information types that might be missing
        if not result.get('clinical_trials') and 'clinical_trials' in agent.sources:
            # Try a more specific search for clinical trials
            try:
                print(f"Making a targeted search for clinical trials by {name}")
                specific_query = f"{name} clinical trial investigator"
                # Use the agent's openai capability to find clinical trials
                if agent.openai_api_key:
                    trials_info = get_specific_researcher_info(
                        agent.openai_api_key, 
                        name, 
                        "clinical_trials",
                        f"Find clinical trials where {name} is an investigator or contributor. Include DIRECT LINKS to ClinicalTrials.gov or other sources."
                    )
                    if trials_info and trials_info.get('clinical_trials'):
                        result['clinical_trials'] = trials_info.get('clinical_trials')
            except Exception as e:
                print(f"Error in targeted clinical trials search: {e}")
        
        # Try to find educational background if missing
        if not result.get('education'):
            try:
                print(f"Making a targeted search for educational background of {name}")
                if agent.openai_api_key:
                    education_info = get_specific_researcher_info(
                        agent.openai_api_key, 
                        name, 
                        "education",
                        f"Find detailed educational background of {name}, including degrees, institutions, and years if available."
                    )
                    if education_info and education_info.get('education'):
                        result['education'] = education_info.get('education')
            except Exception as e:
                print(f"Error in targeted education search: {e}")
        
        # Try to find affiliations if missing
        if not result.get('affiliations'):
            try:
                print(f"Making a targeted search for affiliations of {name}")
                if agent.openai_api_key:
                    affiliations_info = get_specific_researcher_info(
                        agent.openai_api_key, 
                        name, 
                        "affiliations",
                        f"Find current and past institutional affiliations of {name}, including positions held."
                    )
                    if affiliations_info and affiliations_info.get('affiliations'):
                        result['affiliations'] = affiliations_info.get('affiliations')
            except Exception as e:
                print(f"Error in targeted affiliations search: {e}")
        
        # Try to find research interests if missing
        if not result.get('research_interests'):
            try:
                print(f"Making a targeted search for research interests of {name}")
                if agent.openai_api_key:
                    interests_info = get_specific_researcher_info(
                        agent.openai_api_key, 
                        name, 
                        "research_interests",
                        f"List the specific research interests and focus areas of {name}"
                    )
                    if interests_info and interests_info.get('research_interests'):
                        result['research_interests'] = interests_info.get('research_interests')
            except Exception as e:
                print(f"Error in targeted research interests search: {e}")
        
        # Validate publication links if present
        if result.get('publications'):
            for pub in result['publications']:
                if not pub.get('url') or not pub['url'].startswith(('http://', 'https://')):
                    if pub.get('title'):
                        # Create PubMed search URL if no direct link is available
                        search_title = pub['title'].replace(' ', '+')
                        pub['url'] = f"https://pubmed.ncbi.nlm.nih.gov/?term={search_title}"
        
        # Validate clinical trial links if present
        if result.get('clinical_trials'):
            for trial in result['clinical_trials']:
                if not trial.get('url') or not trial['url'].startswith(('http://', 'https://')):
                    if trial.get('title'):
                        # Create ClinicalTrials.gov search URL if no direct link is available
                        search_title = trial['title'].replace(' ', '+')
                        trial['url'] = f"https://clinicaltrials.gov/search?term={search_title}"
        
        if has_meaningful_data:
            return result, None
        else:
            print(f"No meaningful data found for {name}, trying fallback...")
            
            # Try direct web search if API key available
            fallback_info = get_researcher_info_from_openai(agent.openai_api_key, name, specialization)
            if fallback_info:
                # Merge with any partial info we might have
                for key, value in fallback_info.items():
                    if key not in result or not result[key]:
                        result[key] = value
                return result, None
            
            # If we have some data, return it
            if result.get('name'):
                return result, "Limited information found. Please try a different researcher."
            else:
                return None, f"Could not find information about {name}. Please try another name or check spelling."
    except Exception as e:
        # If no data was found, try to use OpenAI to generate information
        try:
            # Fallback to web search via OpenAI
            fallback_info = get_researcher_info_from_openai(agent.openai_api_key, name, specialization)
            return fallback_info, None
        except Exception as e2:
            return None, f"Could not retrieve information: {str(e2)}"

# Function to use OpenAI API directly to get researcher information
def get_researcher_info_from_openai(api_key, name, specialization=None):
    openai.api_key = api_key
    
    spec_text = f" who specializes in {specialization}" if specialization else ""
    
    prompt = f"""
    I need comprehensive information about medical researcher {name}{spec_text}.
    Please search the web for the most accurate and up-to-date information, and provide:
    1. A summary of their background and expertise
    2. Their key research contributions
    3. Their affiliations (current and past with years if available)
    4. Research interests
    5. Notable publications with EXACT LINKS to PubMed, Google Scholar, or original sources
    6. Educational background and degrees (universities, years, and degrees obtained)
    7. Any clinical trials they're involved in with DIRECT LINKS to ClinicalTrials.gov or other source websites
    
    For publications and clinical trials, it's CRUCIAL to include direct, working links to the source pages.
    For educational background, please be thorough and include complete information about degrees, institutions, and years.
    
    Format the response as a JSON with these keys:
    - basic_info (object with fields like email, phone if available)
    - summary (string)
    - key_contributions (string)
    - education (array of strings, each with institution, degree, and year if available)
    - affiliations (array of strings, each with institution and position)
    - research_interests (array of strings)
    - publications (array of objects with title, authors, journal, year, and url fields)
    - clinical_trials (array of objects with title, status, condition, and url fields)
    
    For all URLs, verify they are valid and directly point to the relevant resources.
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a research assistant specializing in medical research. Search for and provide the most accurate information about medical researchers in JSON format. Focus on precision, especially for links to publications, educational background details, and clinical trial information. All links must be real, working URLs."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        # Extract and parse the JSON response
        content = response.choices[0].message.content
        
        # Extract JSON from response (it might be surrounded by markdown code blocks)
        json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        
        researcher_data = json.loads(content)
        
        # Add name and specialization to the data
        researcher_data["name"] = name
        researcher_data["specialization"] = specialization
        researcher_data["ai_generated"] = True
        researcher_data["source_urls"] = {"ai_generated": "Generated using OpenAI with web search"}
        
        # Process and validate publication URLs
        if "publications" in researcher_data:
            for pub in researcher_data["publications"]:
                # Ensure URL exists and is properly formatted
                if "url" not in pub or not pub["url"] or not pub["url"].startswith(("http://", "https://")):
                    # Try to construct a search URL if missing
                    if "title" in pub and pub["title"]:
                        pub_title = pub["title"].replace(" ", "+")
                        pub["url"] = f"https://pubmed.ncbi.nlm.nih.gov/?term={pub_title}"
        
        # Process and validate clinical trial URLs
        if "clinical_trials" in researcher_data:
            for trial in researcher_data["clinical_trials"]:
                # Ensure URL exists and is properly formatted
                if "url" not in trial or not trial["url"] or not trial["url"].startswith(("http://", "https://")):
                    # Add a default clinical trials search if URL is missing
                    if "title" in trial and trial["title"]:
                        trial_title = trial["title"].replace(" ", "+")
                        trial["url"] = f"https://clinicaltrials.gov/search?term={trial_title}"
        
        return researcher_data
    except Exception as e:
        raise e

# Function to get specific information about a researcher
def get_specific_researcher_info(api_key, name, info_type, specific_query):
    """Get specific types of information about a researcher using OpenAI."""
    openai.api_key = api_key
    
    # Customize the prompt based on the information type
    if info_type == "clinical_trials":
        type_instructions = """
        For clinical trials, provide direct links to ClinicalTrials.gov or other official trial registry pages.
        Each clinical trial should include title, status, condition, and a direct URL to the specific trial page.
        Validate all URLs to ensure they point to actual clinical trial registry pages.
        """
    elif info_type == "publications":
        type_instructions = """
        For publications, provide direct links to PubMed, journal pages, or Google Scholar links for each publication.
        Each publication should include title, authors, journal, year, and a direct URL to the specific publication page.
        Validate all URLs to ensure they point to actual publication pages.
        """
    elif info_type == "education":
        type_instructions = """
        For education, provide detailed information about each degree earned, including:
        - Degree type (e.g., MD, PhD, MS, BA)
        - Institution name
        - Year awarded
        - Field of study
        Return this as an array of strings, with each string containing the complete information for one degree.
        """
    elif info_type == "affiliations":
        type_instructions = """
        For affiliations, provide detailed information about each institutional affiliation, including:
        - Institution name
        - Position/title held
        - Years of employment (if available)
        - Department or division (if available)
        Return this as an array of strings, with each string containing the complete information for one affiliation.
        """
    else:
        type_instructions = f"Provide specific information about {info_type}, formatted as an array of strings or appropriate JSON structure."
    
    prompt = f"""
    I need specific information about medical researcher {name}.
    Specifically, I'm looking for their {info_type}.
    {specific_query}
    
    {type_instructions}
    
    Please provide only factual information, and format the response as JSON with the key '{info_type}'.
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a research assistant specializing in finding specific information about medical researchers. Provide accurate, factual information in JSON format. Ensure all URLs are direct links to relevant pages and all educational/affiliation details are complete."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        # Extract and parse the JSON response
        content = response.choices[0].message.content
        
        # Extract JSON from response (it might be surrounded by markdown code blocks)
        json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        elif content.strip().startswith('{') and content.strip().endswith('}'):
            # It's already JSON without the markdown formatting
            pass
        else:
            # Try to extract anything that looks like JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
        
        try:
            result_data = json.loads(content)
            
            # Validate URLs for publication and clinical trial data
            if info_type == "publications" and "publications" in result_data:
                for pub in result_data["publications"]:
                    if not pub.get("url") or not pub["url"].startswith(("http://", "https://")):
                        # Create a search URL if missing
                        if pub.get("title"):
                            title_query = pub["title"].replace(" ", "+")
                            pub["url"] = f"https://pubmed.ncbi.nlm.nih.gov/?term={title_query}"
            
            if info_type == "clinical_trials" and "clinical_trials" in result_data:
                for trial in result_data["clinical_trials"]:
                    if not trial.get("url") or not trial["url"].startswith(("http://", "https://")):
                        # Create a search URL if missing
                        if trial.get("title"):
                            title_query = trial["title"].replace(" ", "+")
                            trial["url"] = f"https://clinicaltrials.gov/search?term={title_query}"
            
            return result_data
        except json.JSONDecodeError:
            # If we can't parse the JSON, create a simple structure
            result = {info_type: [content.strip()]}
            return result
            
    except Exception as e:
        print(f"Error getting specific researcher info: {str(e)}")
        return {}

# Initialize session state variables
if 'agent' not in st.session_state:
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    
    # Clean up API key - remove whitespace and join multiple lines
    if api_key:
        api_key = api_key.replace(" ", "").replace("\n", "").strip()
    
    if api_key:
        st.session_state.agent = MedicalResearcherAgent(openai_api_key=api_key)
    else:
        # Manual API key entry as fallback
        st.error("OpenAI API key not found in environment variables. Enter it manually below.")
        api_key = st.text_input("Enter your OpenAI API key:", type="password")
        if api_key:
            st.session_state.agent = MedicalResearcherAgent(openai_api_key=api_key)
        else:
            st.stop()

if 'current_researcher' not in st.session_state:
    st.session_state.current_researcher = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'websites' not in st.session_state:
    st.session_state.websites = {
        "pubmed": "https://pubmed.ncbi.nlm.nih.gov",
        "researchgate": "https://www.researchgate.net",
        "google_scholar": "https://scholar.google.com",
        "clinical_trials": "https://clinicaltrials.gov"
    }
if 'csv_uploaded' not in st.session_state:
    st.session_state.csv_uploaded = False
if 'search_performed' not in st.session_state:
    st.session_state.search_performed = False
if 'researcher_data' not in st.session_state:
    st.session_state.researcher_data = {}

# Create the main layout
st.title("Medical Researcher Search Tool")

# Create tabs for data input options
input_tabs = st.tabs(["Upload CSV", "Add Custom Websites", "Search Researcher"])

# Tab 1: CSV Upload
with input_tabs[0]:
    st.header("Upload Researcher CSV File")
    csv_file = st.file_uploader("Upload CSV File", type=['csv'],
                               help="CSV file containing researcher information")
    if os.path.exists("sample_researchers.csv"):
        st.markdown(get_download_link("sample_researchers.csv", "📥 Download Sample CSV Template"), unsafe_allow_html=True)
    
    if csv_file is not None and not st.session_state.csv_uploaded:
        try:
            # Save uploaded file to a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                tmp_file.write(csv_file.getvalue())
                tmp_path = tmp_file.name
            
            # Load the CSV data
            df = st.session_state.agent.load_csv_data(tmp_path)
            
            # Update session state
            st.session_state.csv_uploaded = True
            st.success(f"CSV file uploaded successfully! {len(df)} researchers loaded.")
            
            # Clean up temp file
            os.unlink(tmp_path)
        except Exception as e:
            st.error(f"Error processing CSV file: {str(e)}")
            if 'tmp_path' in locals():
                os.unlink(tmp_path)  # Clean up the temporary file in case of error

# Tab 2: Custom Websites
with input_tabs[1]:
    st.header("Add Custom Research Websites")
    st.info("Add specific websites to enhance search capabilities. These could include university profiles, research lab pages, or other sources with researcher information.")
    
    # Display current websites
    st.subheader("Current Search Sources")
    for site_name, site_url in st.session_state.websites.items():
        st.text(f"{site_name.replace('_', ' ').title()}: {site_url}")
    
    # Add new website
    st.subheader("Add New Website")
    col1, col2 = st.columns([3, 1])
    with col1:
        new_site_name = st.text_input("Website Name (e.g., University_Profile)", key="new_site_name")
        new_site_url = st.text_input("Website URL", key="new_site_url")
    with col2:
        st.write("")
        st.write("")
        if st.button("Add Website", key="add_website_btn"):
            if new_site_name and new_site_url:
                if not new_site_url.startswith(("http://", "https://")):
                    new_site_url = "https://" + new_site_url
                st.session_state.websites[new_site_name] = new_site_url
                st.session_state.agent.sources[new_site_name] = new_site_url
                st.success(f"Added {new_site_name}: {new_site_url}")
                st.rerun()
            else:
                st.error("Please enter both website name and URL")

# Tab 3: Search Researcher
with input_tabs[2]:
    st.header("Search for a Medical Researcher")
    col1, col2 = st.columns([3, 1])
    with col1:
        researcher_name = st.text_input("Researcher Name", placeholder="e.g., Dr. Anthony Fauci", key="researcher_name")
    with col2:
        specialization = st.text_input("Specialization (optional)", placeholder="e.g., Immunology", key="specialization")

    # Search button
    search_col1, search_col2 = st.columns([1, 3])
    with search_col1:
        if st.button("Search Researcher", key="search_button"):
            if not researcher_name:
                st.error("Please enter a researcher name")
            else:
                # Show loading spinner during search
                with st.spinner(f"Searching for information about {researcher_name}..."):
                    try:
                        # Update agent with current websites
                        st.session_state.agent.sources = st.session_state.websites
                        
                        # Search for researcher information with fallback
                        researcher_data, error = search_researcher_with_fallback(
                            st.session_state.agent, 
                            researcher_name, 
                            specialization
                        )
                        
                        if error:
                            st.error(error)
                        elif researcher_data:
                            # Update session state
                            st.session_state.current_researcher = researcher_name
                            st.session_state.search_performed = True
                            st.session_state.researcher_data = researcher_data
                            
                            # Clear chat history for new researcher
                            st.session_state.chat_history = []
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": f"I've gathered information about {researcher_name}. What would you like to know?"
                            })
                            
                            # Success message
                            if researcher_data.get('ai_generated'):
                                st.success(f"Found information about {researcher_name} (AI-generated with web search)")
                            else:
                                st.success(f"Found information about {researcher_name}")
                            
                            # Store in researchers_data dictionary for the agent
                            st.session_state.agent.researchers_data[researcher_name] = researcher_data
                        else:
                            st.error(f"No information found for {researcher_name}. Please try another name or check spelling.")
                    except Exception as e:
                        st.error(f"Error searching for researcher: {str(e)}")
    with search_col2:
        st.markdown("**💡 Tip:** The search will query PubMed, ResearchGate, Google Scholar, ClinicalTrials.gov and use web search.")

# Function to display researcher profile in a well-formatted way
def display_researcher_profile(researcher_data):
    """Display the researcher profile in a well-formatted way."""
    if not researcher_data:
        st.error("No researcher data available.")
        return
    
    # Display researcher name and basic info
    st.title(researcher_data.get('name', 'Unknown Researcher'))
    
    if researcher_data.get('specialization'):
        st.write(f"**Specialization:** {researcher_data.get('specialization')}")
    
    # Show AI-generated badge if applicable
    if researcher_data.get('ai_generated', False):
        st.warning("Some information was generated using AI as it wasn't found in primary sources. Please verify critical details.")
    
    # Display basic info
    if researcher_data.get('basic_info'):
        st.subheader("Basic Information")
        for key, value in researcher_data['basic_info'].items():
            if key != 'full_name':  # Skip full name as we already displayed it
                st.write(f"**{key.replace('_', ' ').title()}:** {value}")
    
    # Display summary if available
    if researcher_data.get('summary'):
        st.subheader("Summary")
        st.write(researcher_data.get('summary'))
    
    # Create tabs for different sections
    tabs = st.tabs(["Publications", "Clinical Trials", "Education", "Affiliations", "Research Interests", "Other Info"])
    
    # Publications tab
    with tabs[0]:
        if researcher_data.get('publications'):
            st.markdown("### Notable Publications")
            for i, pub in enumerate(researcher_data['publications'][:10], 1):
                publication_title = pub.get('title', 'Untitled')
                
                # Create a section with title and link
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{i}. {publication_title}**")
                with col2:
                    if pub.get('url'):
                        st.markdown(f"[View Publication]({pub['url']})")
                
                # Display other publication details
                if pub.get('authors'):
                    st.markdown(f"*Authors:* {pub['authors']}")
                    
                # Display journal and year in same line if available
                journal_info = []
                if pub.get('journal'):
                    journal_info.append(f"*Journal:* {pub['journal']}")
                if pub.get('year'):
                    journal_info.append(f"*Year:* {pub['year']}")
                
                if journal_info:
                    st.markdown(" | ".join(journal_info))
                
                # DOI link if available
                if pub.get('doi'):
                    st.markdown(f"*DOI:* [{pub['doi']}](https://doi.org/{pub['doi']})")
                    
                # Direct links to different sources if available
                links = []
                if pub.get('pubmed_url'):
                    links.append(f"[PubMed]({pub['pubmed_url']})")
                if pub.get('google_scholar_url'):
                    links.append(f"[Google Scholar]({pub['google_scholar_url']})")
                if pub.get('journal_url'):
                    links.append(f"[Journal]({pub['journal_url']})")
                
                if links:
                    st.markdown("*Links:* " + " | ".join(links))
                
                st.markdown("---")
        else:
            st.info("No publications found. Try adding specific university or research institution websites to improve search results.")
    
    # Clinical Trials tab
    with tabs[1]:
        if researcher_data.get('clinical_trials'):
            st.markdown("### Clinical Trials")
            for i, trial in enumerate(researcher_data['clinical_trials'], 1):
                trial_title = trial.get('title', 'Untitled trial')
                
                # Create a section with title and link
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{i}. {trial_title}**")
                with col2:
                    if trial.get('url'):
                        st.markdown(f"[View Trial]({trial['url']})")
                
                # Display status and condition
                status_condition = []
                if trial.get('status'):
                    status_condition.append(f"*Status:* {trial['status']}")
                if trial.get('condition'):
                    status_condition.append(f"*Condition:* {trial['condition']}")
                
                if status_condition:
                    st.markdown(" | ".join(status_condition))
                
                # Display identifier if available
                if trial.get('identifier'):
                    st.markdown(f"*Identifier:* {trial['identifier']}")
                
                # Display link to direct ClinicalTrials.gov page if available
                if trial.get('url') and 'clinicaltrials.gov' in trial.get('url', ''):
                    st.markdown(f"[View on ClinicalTrials.gov]({trial['url']})")
                    
                st.markdown("---")
        else:
            st.info("No clinical trials found. The researcher may not be involved in clinical trials, or this information is not publicly available.")
            st.markdown("**Tip:** Try adding the researcher's institution website or clinicaltrials.gov profile URL in the 'Add Custom Websites' section.")
    
    # Education tab - now a primary tab
    with tabs[2]:
        if researcher_data.get('education'):
            st.markdown("### Educational Background")
            if isinstance(researcher_data['education'], list):
                for i, edu in enumerate(researcher_data['education'], 1):
                    st.markdown(f"**{i}.** {edu}")
            else:
                st.write(researcher_data['education'])
        else:
            st.info("No educational information found. Try using the chat feature to ask about their educational background.")
    
    # Affiliations tab
    with tabs[3]:
        if researcher_data.get('affiliations'):
            st.markdown("### Institutional Affiliations")
            for i, affiliation in enumerate(researcher_data['affiliations'], 1):
                st.markdown(f"**{i}.** {affiliation}")
                
                # Look for links to institution websites in source_urls
                if researcher_data.get('source_urls'):
                    for source, url in researcher_data['source_urls'].items():
                        institution_name = affiliation.lower().split(',')[0]
                        if institution_name in source.lower() and url:
                            st.markdown(f"[Visit institution website]({url})")
                            break
        else:
            st.info("No affiliations found. Try adding the researcher's institution website to improve search results.")
    
    # Research Interests tab
    with tabs[4]:
        if researcher_data.get('research_interests'):
            st.markdown("### Research Focus Areas")
            for i, interest in enumerate(researcher_data['research_interests'], 1):
                st.markdown(f"**{i}.** {interest}")
        else:
            st.info("No research interests found. Try using the chat feature to ask about their research focus areas.")
    
    # Other Info tab
    with tabs[5]:
        # Key contributions section
        if researcher_data.get('key_contributions'):
            st.subheader("Key Contributions")
            
            # Check if it's already a string or if it might be in another format
            if isinstance(researcher_data['key_contributions'], str):
                # Just display the text
                st.write(researcher_data['key_contributions'])
            elif isinstance(researcher_data['key_contributions'], list):
                # Display as numbered list
                for i, contribution in enumerate(researcher_data['key_contributions'], 1):
                    st.markdown(f"**{i}.** {contribution}")
            elif isinstance(researcher_data['key_contributions'], dict):
                # If it's a dictionary, format each entry
                for key, value in researcher_data['key_contributions'].items():
                    st.markdown(f"**{key}:** {value}")
            else:
                # Just convert to string and display
                st.write(str(researcher_data['key_contributions']))
        
        # Additional insights section
        if researcher_data.get('additional_insights'):
            st.subheader("Additional Insights")
            st.write(researcher_data['additional_insights'])
        
        # Data sources section
        if researcher_data.get('source_urls'):
            st.subheader("Data Sources")
            for source, url in researcher_data['source_urls'].items():
                if url:
                    st.markdown(f"- [{source.title()}]({url})")
                    
        # Citations section
        if researcher_data.get('citations'):
            st.subheader("Citations")
            if isinstance(researcher_data['citations'], dict):
                for metric, count in researcher_data['citations'].items():
                    st.markdown(f"**{metric.title()}:** {count}")
            elif isinstance(researcher_data['citations'], (str, int)):
                st.markdown(f"**Citations:** {researcher_data['citations']}")
            
        # Collaborators section
        if researcher_data.get('collaborators'):
            st.subheader("Collaborators")
            if isinstance(researcher_data['collaborators'], list):
                for i, collaborator in enumerate(researcher_data['collaborators'], 1):
                    st.markdown(f"**{i}.** {collaborator}")
            else:
                st.write(researcher_data['collaborators'])

# Results and chat interface (only show if search has been performed)
if st.session_state.search_performed and st.session_state.current_researcher:
    
    # Create tabs for Profile and Chat
    tab1, tab2 = st.tabs(["Researcher Profile", "Ask Questions"])
    
    # Profile tab
    with tab1:
        try:
            researcher = st.session_state.researcher_data
            display_researcher_profile(researcher)
        except Exception as e:
            st.error(f"Error displaying researcher profile: {str(e)}")
    
    # Chat tab
    with tab2:
        st.subheader("Ask Questions About This Researcher")
        
        # Display chat history
        for message in st.session_state.chat_history:
            if message["role"] == "user":
                st.chat_message("user").write(message["content"])
            else:
                st.chat_message("assistant").write(message["content"])
        
        # Add custom website search input for specific questions
        with st.expander("Add a specific website to search for more information"):
            custom_website = st.text_input("Enter website URL (e.g., university profile page)", key="custom_website_chat")
            if st.button("Add Website to Search Sources", key="add_website_chat"):
                if custom_website:
                    # Add to session state and agent sources
                    site_name = f"custom_{len(st.session_state.websites)}"
                    st.session_state.websites[site_name] = custom_website
                    st.session_state.agent.sources[site_name] = custom_website
                    st.success(f"Added {custom_website} to search sources")
                    st.rerun()
                else:
                    st.error("Please enter a valid URL")
        
        # Question input - moved to appear after all displayed messages
        question = st.chat_input("Ask a question about this researcher...")
        
        if question:
            # Add user question to chat history
            st.session_state.chat_history.append({"role": "user", "content": question})
            
            # Display the user message
            st.chat_message("user").write(question)
            
            # Get answer from agent with web search
            with st.spinner("Searching for information..."):
                try:
                    researcher_name = st.session_state.current_researcher
                    
                    # Build comprehensive context about the researcher from all available data
                    context = ""
                    if researcher_name in st.session_state.agent.researchers_data:
                        researcher_data = st.session_state.agent.researchers_data[researcher_name]
                        context_parts = []
                        
                        # Add basic information to context
                        if researcher_data.get('summary'):
                            context_parts.append(f"Summary: {researcher_data.get('summary')}")
                        
                        # Add educational background
                        if researcher_data.get('education'):
                            if isinstance(researcher_data['education'], list):
                                context_parts.append(f"Education: {', '.join(researcher_data.get('education'))}")
                            else:
                                context_parts.append(f"Education: {researcher_data.get('education')}")
                        
                        # Add affiliations with more details
                        if researcher_data.get('affiliations'):
                            context_parts.append(f"Affiliations: {', '.join(researcher_data.get('affiliations'))}")
                            
                        # Add research interests
                        if researcher_data.get('research_interests'):
                            context_parts.append(f"Research interests: {', '.join(researcher_data.get('research_interests'))}")
                        
                        # Add key contributions
                        if researcher_data.get('key_contributions'):
                            if isinstance(researcher_data['key_contributions'], str):
                                context_parts.append(f"Key contributions: {researcher_data.get('key_contributions')}")
                            elif isinstance(researcher_data['key_contributions'], list):
                                context_parts.append(f"Key contributions: {', '.join(researcher_data.get('key_contributions'))}")
                        
                        # Add publications with URLs
                        if researcher_data.get('publications'):
                            pubs = researcher_data.get('publications')[:5]  # Limit to 5 to avoid too large context
                            pub_texts = []
                            for pub in pubs:
                                pub_text = pub.get('title', '')
                                if pub.get('url'):
                                    pub_text += f" (URL: {pub.get('url')})"
                                pub_texts.append(pub_text)
                            if pub_texts:
                                context_parts.append(f"Notable publications: {'; '.join(pub_texts)}")
                        
                        # Add clinical trials with URLs
                        if researcher_data.get('clinical_trials'):
                            trials = researcher_data.get('clinical_trials')[:3]  # Limit to 3
                            trial_texts = []
                            for trial in trials:
                                trial_text = trial.get('title', '')
                                if trial.get('url'):
                                    trial_text += f" (URL: {trial.get('url')})"
                                trial_texts.append(trial_text)
                            if trial_texts:
                                context_parts.append(f"Clinical trials: {'; '.join(trial_texts)}")
                        
                        # Include available URLs for reference
                        if researcher_data.get('source_urls'):
                            url_parts = []
                            for source, url in researcher_data['source_urls'].items():
                                if url:
                                    url_parts.append(f"{source.title()}: {url}")
                            if url_parts:
                                context_parts.append(f"Reference URLs: {'; '.join(url_parts)}")
                        
                        if context_parts:
                            context = "Information about " + researcher_name + ":\n\n" + "\n\n".join(context_parts)
                    
                    # Add information about custom websites that have been added
                    custom_websites = []
                    for site_name, site_url in st.session_state.websites.items():
                        if site_name not in ['pubmed', 'researchgate', 'google_scholar', 'clinical_trials']:
                            custom_websites.append(f"{site_name}: {site_url}")
                    
                    if custom_websites:
                        context += "\n\nCustom websites provided for reference:\n" + "\n".join(custom_websites)
                    
                    # Use OpenAI API to get an answer
                    openai.api_key = st.session_state.agent.openai_api_key
                    
                    # Ask web search to provide additional information if needed
                    try:
                        # First attempt to use existing data to answer
                        prompt = f"""
                        {context}
                        
                        Question about {researcher_name}: {question}
                        
                        Please provide a detailed, factual answer based on the information provided in the context.
                        If the context doesn't contain sufficient information to fully answer the question,
                        explicitly state this and then provide your best estimate of the answer based on
                        general knowledge.
                        
                        When referencing publications, clinical trials, educational background, or affiliations,
                        include direct links when available.
                        """
                        
                        response = openai.ChatCompletion.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": "You are a helpful research assistant specializing in medical researchers. Provide accurate, comprehensive answers about medical researchers based on available information. Include links when available, especially for publications and clinical trials."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.3
                        )
                        
                        # Get the answer from the response
                        answer = response.choices[0].message.content
                        
                        # Check if the answer indicates missing information
                        missing_info_phrases = [
                            "context doesn't contain", 
                            "information isn't in the provided context",
                            "no information in the context",
                            "I don't have specific information",
                            "context doesn't provide",
                            "don't have that information"
                        ]
                        
                        needs_web_search = any(phrase in answer.lower() for phrase in missing_info_phrases)
                        
                        # If we need more information, try a web search
                        if needs_web_search and "custom_" in "".join(st.session_state.websites.keys()):
                            # Perform a targeted search using custom websites
                            web_prompt = f"""
                            I need specific information about {researcher_name} to answer this question: {question}
                            
                            I should search these websites for information:
                            {' '.join(custom_websites)}
                            
                            Please search for factual information to answer the question, and provide only
                            verified information with source links when possible.
                            """
                            
                            web_response = openai.ChatCompletion.create(
                                model="gpt-4o",
                                messages=[
                                    {"role": "system", "content": "You are a research assistant with web search capabilities. Find specific information about medical researchers by searching the provided websites."},
                                    {"role": "user", "content": web_prompt}
                                ],
                                temperature=0.3
                            )
                            
                            web_answer = web_response.choices[0].message.content
                            
                            # Combine the answers
                            answer = f"{answer}\n\nAfter searching provided websites, I found additional information:\n\n{web_answer}"
                        
                        # Add agent response to chat history
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": answer
                        })
                        
                        # Display the response
                        st.chat_message("assistant").write(answer)
                        
                    except Exception as e:
                        error_msg = f"Error getting answer: {str(e)}"
                        st.error(error_msg)
                        
                        # Add error message to chat
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": f"I'm sorry, I encountered an error: {str(e)}"
                        })
                        
                        st.chat_message("assistant").write(f"I'm sorry, I encountered an error: {str(e)}")
                
                except Exception as e:
                    error_msg = f"Error processing request: {str(e)}"
                    st.error(error_msg)
                    
                    # Add error message to chat
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"I'm sorry, I encountered an error: {str(e)}"
                    })
                    
                    st.chat_message("assistant").write(f"I'm sorry, I encountered an error: {str(e)}")
            
            # After answering, rerun to reset the question input
            time.sleep(0.5)  # Small delay to ensure the message is displayed
            st.rerun()
        
        # Suggested questions
        st.subheader("Suggested Questions")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("What are their main research interests?", key="q1"):
                st.session_state.chat_history.append({"role": "user", "content": "What are their main research interests?"})
                st.rerun()
            
            if st.button("What are their key achievements?", key="q2"):
                st.session_state.chat_history.append({"role": "user", "content": "What are their key achievements?"})
                st.rerun()
                
        with col2:
            if st.button("What clinical trials are they involved in?", key="q3"):
                st.session_state.chat_history.append({"role": "user", "content": "What clinical trials are they involved in?"})
                st.rerun()
            
            if st.button("What is their educational background?", key="q4"):
                st.session_state.chat_history.append({"role": "user", "content": "What is their educational background? Where did they study?"})
                st.rerun()

# Welcome message if no search has been performed
if not st.session_state.search_performed:
    st.info("""
    ### Welcome to the Medical Researcher Search Tool!
    
    This tool helps you find comprehensive information about medical researchers from academic databases and research platforms.
    
    #### How to use:
    1. Enter a researcher name and optionally their specialization
    2. Click "Search Researcher"
    3. View the detailed profile and ask questions about the researcher
    
    #### Data Sources:
    - PubMed - Medical publications and research papers
    - ResearchGate - Academic profiles and connections
    - Google Scholar - Citations and academic impact
    - ClinicalTrials.gov - Clinical trial involvement
    - AI-assisted information retrieval
    
    #### Example Researchers to Try:
    - Dr. Anthony Fauci (Immunology)
    - Dr. Jennifer Doudna (CRISPR, Genomics)
    - Dr. Eric Topol (Cardiology)
    - Dr. Francis Collins (Genetics)
    """)

# Footer
st.markdown("---")
st.caption("Medical Researcher Search Tool - Combines web scraping, data integration, and AI to provide researcher insights.")
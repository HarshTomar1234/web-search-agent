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
        
        if has_meaningful_data:
            return result, None
        else:
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
                return None, f"Could not find information about {name}. Please try another name or specialization."
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
    3. Their affiliations
    4. Research interests
    5. Notable publications
    6. Educational background and degrees
    7. Any clinical trials they're involved in (if applicable)
    
    Format the response as a JSON with these keys:
    - basic_info (object)
    - summary (string)
    - key_contributions (string)
    - education (array of strings)
    - affiliations (array of strings)
    - research_interests (array of strings)
    - publications (array of objects with title, authors, journal)
    - clinical_trials (array of objects with title, status, condition)
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a research assistant specializing in medical research. Search for and provide the most accurate information about medical researchers in JSON format. Search for specific details about the researcher's education, affiliations, and research."},
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
        
        return researcher_data
    except Exception as e:
        raise e

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
    tabs = st.tabs(["Publications", "Clinical Trials", "Affiliations", "Research Interests", "Other Info"])
    
    # Publications tab
    with tabs[0]:
        if researcher_data.get('publications'):
            for i, pub in enumerate(researcher_data['publications'][:10], 1):
                st.markdown(f"**{i}. {pub.get('title', 'Untitled')}**")
                if pub.get('authors'):
                    st.markdown(f"*Authors:* {pub['authors']}")
                if pub.get('journal'):
                    st.markdown(f"*Journal:* {pub['journal']}")
                if pub.get('url'):
                    st.markdown(f"[View Publication]({pub['url']})")
                st.markdown("---")
        else:
            st.info("No publications found")
    
    # Clinical Trials tab
    with tabs[1]:
        if researcher_data.get('clinical_trials'):
            for i, trial in enumerate(researcher_data['clinical_trials'], 1):
                st.markdown(f"**{i}. {trial.get('title', 'Untitled trial')}**")
                if trial.get('status'):
                    st.markdown(f"*Status:* {trial['status']}")
                if trial.get('condition'):
                    st.markdown(f"*Condition:* {trial['condition']}")
                if trial.get('url'):
                    st.markdown(f"[View Trial]({trial['url']})")
                st.markdown("---")
        else:
            st.info("No clinical trials found")
    
    # Affiliations tab
    with tabs[2]:
        if researcher_data.get('affiliations'):
            for affiliation in researcher_data['affiliations']:
                st.markdown(f"- {affiliation}")
        else:
            st.info("No affiliations found")
    
    # Research Interests tab
    with tabs[3]:
        if researcher_data.get('research_interests'):
            for interest in researcher_data['research_interests']:
                st.markdown(f"- {interest}")
        else:
            st.info("No research interests found")
    
    # Other Info tab
    with tabs[4]:
        # Key contributions section
        if researcher_data.get('key_contributions'):
            st.subheader("Key Contributions")
            st.write(researcher_data['key_contributions'])
        
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
                    
                    # Try to add specific context about the researcher
                    context = ""
                    if researcher_name in st.session_state.agent.researchers_data:
                        researcher_data = st.session_state.agent.researchers_data[researcher_name]
                        context_parts = []
                        
                        if researcher_data.get('summary'):
                            context_parts.append(f"Summary: {researcher_data.get('summary')}")
                        
                        if researcher_data.get('affiliations'):
                            context_parts.append(f"Affiliations: {', '.join(researcher_data.get('affiliations'))}")
                            
                        if researcher_data.get('research_interests'):
                            context_parts.append(f"Research interests: {', '.join(researcher_data.get('research_interests'))}")
                        
                        if context_parts:
                            context = "Information about " + researcher_name + ":\n\n" + "\n\n".join(context_parts)
                    
                    # Use OpenAI API to get an answer
                    openai.api_key = st.session_state.agent.openai_api_key
                    
                    prompt = f"""
                    {context}
                    
                    Question about {researcher_name}: {question}
                    
                    Please provide a detailed, factual answer. If the information isn't in the provided context,
                    use your knowledge to give the best possible answer, stating clearly when you're providing
                    information not in the context.
                    """
                    
                    response = openai.ChatCompletion.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are a helpful research assistant specializing in medical researchers. Provide accurate, comprehensive answers about medical researchers based on available information."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.5
                    )
                    
                    # Get the answer from the response
                    answer = response.choices[0].message.content
                    
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
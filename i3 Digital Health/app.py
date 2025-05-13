import streamlit as st
import pandas as pd
import json
import os
import tempfile
import time
import base64
import requests
import re
from medical_researcher_agent import MedicalResearcherAgent

# Page configuration
st.set_page_config(
    page_title="Medical Researcher Search Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS to fix black box issue and improve styling
st.markdown("""
<style>
    /* Global text color fix */
    body, p, h1, h2, h3, h4, h5, h6, li, span, div {
        color: #31333F !important;
    }
    
    /* Main content styles */
    .main-header {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        color: #31333F !important;
    }
    .sub-header {
        font-size: 1.5rem;
        margin-bottom: 1rem;
        color: #31333F !important;
    }
    .researcher-name {
        font-size: 1.8rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        color: #31333F !important;
    }
    .section-header {
        font-size: 1.3rem;
        font-weight: bold;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        color: #31333F !important;
    }
    .info-box {
        background-color: #f0f2f6 !important;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .source-link {
        font-size: 0.8rem;
        color: #4a4a4a;
    }
    
    /* Chat UI */
    .chat-user {
        background-color: #e1f5fe !important;
        padding: 10px 15px;
        border-radius: 15px 15px 0 15px;
        margin-bottom: 10px;
        max-width: 80%;
        margin-left: auto;
        float: right;
        clear: both;
        color: #31333F !important;
    }
    .chat-agent {
        background-color: #f0f2f6 !important;
        padding: 10px 15px;
        border-radius: 15px 15px 15px 0;
        margin-bottom: 10px;
        max-width: 80%;
        float: left;
        clear: both;
        color: #31333F !important;
    }
    .chat-container {
        height: 400px;
        overflow-y: auto;
        margin-bottom: 20px;
        padding: 10px;
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        background-color: white !important;
    }
    
    /* Content boxes */
    .publication-item {
        padding: 10px;
        margin-bottom: 10px;
        border-left: 3px solid #3498db;
        background-color: #f8f9fa !important;
        color: #31333F !important;
    }
    .trial-item {
        padding: 10px;
        margin-bottom: 10px;
        border-left: 3px solid #2ecc71;
        background-color: #f8f9fa !important;
        color: #31333F !important;
    }
    .affiliation-item {
        padding: 10px;
        margin-bottom: 10px;
        border-left: 3px solid #9b59b6;
        background-color: #f8f9fa !important;
        color: #31333F !important;
    }
    .interest-item {
        display: inline-block;
        padding: 5px 10px;
        margin: 5px;
        border-radius: 15px;
        background-color: #3498db !important;
        color: white !important;
    }
    
    /* Fix any dark mode issues */
    .stApp {
        background-color: white !important;
    }
    
    /* Force white backgrounds */
    .st-emotion-cache-uf99v8, 
    .st-emotion-cache-ue6h4q,
    .st-emotion-cache-1n76uvr,
    .st-emotion-cache-1wrcr25,
    .st-emotion-cache-6qob1r,
    .st-emotion-cache-1kyxreq,
    .st-emotion-cache-16txtl3,
    .st-emotion-cache-4z1n4l,
    .st-emotion-cache-5rimss,
    .st-emotion-cache-1gulkj5 {
        background-color: white !important;
    }
    
    /* Fix tabs */
    div.stTabs {
        background-color: white !important;
    }
    div.stTabs > div {
        background-color: white !important;
    }
    div.stTabs [data-baseweb="tab-list"] {
        background-color: white !important;
    }
    div.stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6 !important;
        border-radius: 4px 4px 0 0;
        padding: 0.5rem 1rem;
        margin-right: 4px;
        color: #31333F !important;
    }
    div.stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #3498db !important;
        color: white !important;
    }
    div.stTabs [data-baseweb="tab-panel"] {
        background-color: white !important;
        color: #31333F !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #f0f2f6 !important;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdown"] {
        color: #31333F !important;
    }
    
    /* Block container */
    .block-container {
        padding-top: 2rem;
        background-color: white !important;
    }
    
    /* Text inputs */
    .stTextInput > div {
        background-color: white !important;
    }
    .stTextInput input {
        background-color: white !important;
        color: #31333F !important;
    }
    
    /* All input elements */
    input, textarea, [contenteditable] {
        color: #31333F !important;
        background-color: white !important;
    }
    
    /* Alerts */
    .stAlert {
        border-radius: 0.5rem;
        color: #31333F !important;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        background-color: #f8f9fa !important;
        color: #31333F !important;
    }
    .streamlit-expanderContent {
        background-color: white !important;
    }
    
    /* Additional fixes for markdown content */
    .element-container, .stMarkdown {
        color: #31333F !important;
    }
    
    /* Button styles */
    .stButton button {
        color: #31333F !important;
    }
    .stButton button[data-baseweb="button"] {
        background-color: #f0f2f6 !important;
    }
    .stButton button[kind="primary"] {
        background-color: #3498db !important;
        color: white !important;
    }
    .search-button {
        background-color: #3498db;
        color: white;
        border-radius: 5px;
    }
    .clear-button {
        background-color: #95a5a6;
        color: white;
        border-radius: 5px;
    }
    
    /* Table styles */
    .stDataFrame {
        border-radius: 0.5rem;
        overflow: hidden;
    }
    .stDataFrame [data-testid="stTable"] {
        background-color: white !important;
    }
    .stDataFrame th {
        background-color: #f0f2f6 !important;
        color: #31333F !important;
    }
    .stDataFrame td {
        background-color: white !important;
        color: #31333F !important;
    }
</style>
""", unsafe_allow_html=True)

# Function to create a download link for a file
def get_download_link(file_path, link_text):
    with open(file_path, 'r') as f:
        data = f.read()
    b64 = base64.b64encode(data.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{os.path.basename(file_path)}" class="download-link">{link_text}</a>'
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
            print(f"No meaningful data found for {name}, trying fallback...")
            
            # Try direct web search if API key available
            if agent.openai_api_key:
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
        st.error(f"Error in primary search: {str(e)}")
        
        # If no data was found, try to use OpenAI to generate information
        if agent.openai_api_key:
            try:
                # Fallback to web search via OpenAI
                fallback_info = get_researcher_info_from_openai(agent.openai_api_key, name, specialization)
                return fallback_info, None
            except Exception as e2:
                return None, f"Could not retrieve information: {str(e2)}"
        else:
            return None, f"Error searching for researcher: {str(e)}"

# Function to use OpenAI API directly to get researcher information
def get_researcher_info_from_openai(api_key, name, specialization=None):
    import openai
    openai.api_key = api_key
    
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
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a research assistant specializing in medical research. Provide accurate information about medical researchers in JSON format."},
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
        researcher_data["source_urls"] = {"ai_generated": "Generated using OpenAI"}
        
        return researcher_data
    except Exception as e:
        st.error(f"Error getting information from OpenAI: {str(e)}")
        raise e

# Initialize session state variables
if 'agent' not in st.session_state:
    st.session_state.agent = None
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

# Sidebar
with st.sidebar:
    st.markdown('<div class="sub-header">Configuration</div>', unsafe_allow_html=True)
    
    # OpenAI API Key input
    env_api_key = os.getenv("OPENAI_API_KEY")
    openai_api_key = st.text_input("OpenAI API Key (required for AI features)", 
                                  type="password",
                                  value=env_api_key if env_api_key else "",
                                  help="Your API key is used only for this session and never stored.")
    
    if st.button("Save API Key"):
        if openai_api_key:
            # Initialize or update the agent with the API key
            if st.session_state.agent is None:
                st.session_state.agent = MedicalResearcherAgent(openai_api_key=openai_api_key)
            else:
                st.session_state.agent.openai_api_key = openai_api_key
            st.success("API key saved successfully!")
        else:
            st.error("Please enter a valid API key")
    
    # If env API key is available, initialize agent automatically
    if env_api_key and 'agent' not in st.session_state:
        st.session_state.agent = MedicalResearcherAgent(openai_api_key=env_api_key)
        st.success("API key loaded from environment variables")
    
    st.markdown("---")
    
    st.markdown('<div class="sub-header">Data Sources</div>', unsafe_allow_html=True)
    
    # CSV upload
    csv_file = st.file_uploader("Upload Researcher CSV File", type=['csv'],
                                help="CSV file containing researcher information")
    
    # Sample CSV download link
    if os.path.exists("sample_researchers.csv"):
        st.markdown(get_download_link("sample_researchers.csv", "📥 Download Sample CSV Template"), unsafe_allow_html=True)
    
    if csv_file is not None and not st.session_state.csv_uploaded:
        try:
            # Save uploaded file to a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                tmp_file.write(csv_file.getvalue())
                tmp_path = tmp_file.name
            
            # Initialize agent if not already initialized
            if st.session_state.agent is None:
                st.session_state.agent = MedicalResearcherAgent(openai_api_key=openai_api_key)
            
            # Load the CSV data
            df = st.session_state.agent.load_csv_data(tmp_path)
            
            # Remove temporary file
            os.unlink(tmp_path)
            
            if not df.empty:
                st.session_state.csv_uploaded = True
                st.success(f"Successfully loaded data for {len(df)} researchers!")
                
                # Show preview of the loaded data
                with st.expander("Preview Loaded Data"):
                    st.dataframe(df)
            else:
                st.error("Failed to load CSV file. Please check the format.")
        except Exception as e:
            st.error(f"Error: {str(e)}")
    
    # Website links
    st.markdown("### Add Custom Website")
    
    website_name = st.text_input("Website Name", placeholder="e.g., scopus")
    website_url = st.text_input("Website URL", placeholder="e.g., https://www.scopus.com")
    
    if st.button("Add Website"):
        if website_name and website_url:
            if website_url.startswith("http"):
                st.session_state.websites[website_name.lower()] = website_url
                st.success(f"Added {website_name} to data sources")
                
                # Update agent sources if the agent exists
                if st.session_state.agent:
                    st.session_state.agent.sources = st.session_state.websites
            else:
                st.error("URL must start with http:// or https://")
        else:
            st.error("Please enter both website name and URL")
    
    # Display current websites
    st.markdown("### Current Data Sources")
    for name, url in st.session_state.websites.items():
        st.markdown(f"- **{name.title()}**: {url}")

# Main content
st.markdown('<h1 class="main-header">Medical Researcher Search Agent</h1>', unsafe_allow_html=True)
st.markdown("Search for detailed information about medical researchers from various sources including PubMed, ResearchGate, Google Scholar, and ClinicalTrials.gov.")

# Researcher search form
col1, col2 = st.columns([3, 1])
with col1:
    researcher_name = st.text_input("Researcher Name", placeholder="Enter researcher name (e.g., 'Dr. Jane Smith')")
with col2:
    specialization = st.text_input("Specialization (Optional)", placeholder="e.g., Oncology, Cardiology")

search_col1, search_col2 = st.columns([4, 1])
with search_col1:
    search_button = st.button("🔍 Search Researcher", use_container_width=True, type="primary")
with search_col2:
    clear_button = st.button("🗑️ Clear Results", use_container_width=True)

# Clear results if clear button is clicked
if clear_button:
    st.session_state.current_researcher = None
    st.session_state.search_performed = False
    st.session_state.chat_history = []
    st.session_state.researcher_data = {}
    st.rerun()

# Search for researcher
if search_button:
    if not researcher_name:
        st.error("Please enter a researcher name")
    else:
        # Initialize agent if not already initialized
        if st.session_state.agent is None:
            # First check for environment variable
            env_api_key = os.getenv("OPENAI_API_KEY")
            if env_api_key:
                st.session_state.agent = MedicalResearcherAgent(openai_api_key=env_api_key)
                st.success("Using OpenAI API key from environment variables")
            elif openai_api_key:
                st.session_state.agent = MedicalResearcherAgent(openai_api_key=openai_api_key)
            else:
                with st.warning("No OpenAI API key provided. Some features will be limited."):
                    st.info("You can still search for researchers, but AI-enhanced features will be disabled.")
                st.session_state.agent = MedicalResearcherAgent()
            
        # Update agent sources with custom websites
        st.session_state.agent.sources = st.session_state.websites
        
        # Show loading spinner during search
        with st.spinner(f"Searching for information about {researcher_name}..."):
            try:
                # Create a placeholder for status updates
                status_placeholder = st.empty()
                status_placeholder.info("Searching for information in multiple sources...")
                
                # Search for researcher information with fallback
                researcher_data, error = search_researcher_with_fallback(
                    st.session_state.agent, 
                    researcher_name, 
                    specialization
                )
                
                # Clear the status placeholder
                status_placeholder.empty()
                
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
                        "role": "agent",
                        "content": f"I've gathered information about {researcher_name}. What would you like to know?"
                    })
                    
                    # Success message
                    if researcher_data.get('ai_generated'):
                        st.success(f"Found information about {researcher_name} (AI-generated)")
                        st.info("The information was generated using AI and may not be 100% accurate.")
                    elif researcher_data.get('ai_enhanced'):
                        st.success(f"Found information about {researcher_name}")
                        st.info("Some of the information was enhanced using AI.")
                    else:
                        st.success(f"Found information about {researcher_name}")
                    
                    # Store in researchers_data dictionary for the agent
                    st.session_state.agent.researchers_data[researcher_name] = researcher_data
                else:
                    st.error(f"No information found for {researcher_name}. Please try another name or check spelling.")
                    st.info("You can try specifying the researcher's specialization to improve search results.")
            except Exception as e:
                st.error(f"Error searching for researcher: {str(e)}")
                st.info("Please try again or search for a different researcher.")

# Results and chat interface (only show if search has been performed)
if st.session_state.search_performed and st.session_state.current_researcher:
    
    # Create tabs for Profile and Chat
    tab1, tab2 = st.tabs(["📝 Researcher Profile", "💬 Ask Questions"])
    
    # Profile tab
    with tab1:
        try:
            researcher = st.session_state.researcher_data
            
            # Basic information section
            st.markdown(f'<h2 class="researcher-name">{st.session_state.current_researcher}</h2>', unsafe_allow_html=True)
            
            if researcher.get('specialization'):
                st.markdown(f'<p><strong>Specialization:</strong> {researcher["specialization"]}</p>', unsafe_allow_html=True)
            
            # Display basic info
            if researcher.get('basic_info'):
                basic_col1, basic_col2 = st.columns(2)
                with basic_col1:
                    for key, value in researcher['basic_info'].items():
                        if key != 'full_name':  # Skip full name as we already displayed it
                            st.markdown(f'<p><strong>{key.replace("_", " ").title()}:</strong> {value}</p>', unsafe_allow_html=True)
            
            # Display AI-generated summary if available
            if researcher.get('summary'):
                st.markdown('<h3 class="section-header">Summary</h3>', unsafe_allow_html=True)
                st.info(researcher['summary'])
            
            # Create columns for main sections
            col1, col2 = st.columns([3, 2])
            
            # Left column - Publications and Clinical Trials
            with col1:
                # Publications section
                if researcher.get('publications'):
                    with st.expander("Publications", expanded=True):
                        for i, pub in enumerate(researcher['publications'][:10], 1):
                            pub_html = f'<div class="publication-item"><strong>{i}. {pub.get("title", "Untitled")}</strong>'
                            if pub.get('authors'):
                                pub_html += f'<br><em>Authors:</em> {pub["authors"]}'
                            if pub.get('journal'):
                                pub_html += f'<br><em>Journal:</em> {pub["journal"]}'
                            if pub.get('url'):
                                pub_html += f'<br><a href="{pub["url"]}" target="_blank">View Publication</a>'
                            pub_html += '</div>'
                            st.markdown(pub_html, unsafe_allow_html=True)
                else:
                    with st.expander("Publications", expanded=True):
                        st.info("No publications found")
                
                # Clinical Trials section
                if researcher.get('clinical_trials'):
                    with st.expander("Clinical Trials", expanded=True):
                        for i, trial in enumerate(researcher['clinical_trials'], 1):
                            trial_html = f'<div class="trial-item"><strong>{i}. {trial.get("title", "Untitled trial")}</strong>'
                            if trial.get('status'):
                                trial_html += f'<br><em>Status:</em> {trial["status"]}'
                            if trial.get('condition'):
                                trial_html += f'<br><em>Condition:</em> {trial["condition"]}'
                            if trial.get('url'):
                                trial_html += f'<br><a href="{trial["url"]}" target="_blank">View Trial</a>'
                            trial_html += '</div>'
                            st.markdown(trial_html, unsafe_allow_html=True)
                else:
                    with st.expander("Clinical Trials", expanded=False):
                        st.info("No clinical trials found")
            
            # Right column - Affiliations, Research Interests, and more
            with col2:
                # Affiliations section
                if researcher.get('affiliations'):
                    with st.expander("Affiliations", expanded=True):
                        for affiliation in researcher['affiliations']:
                            st.markdown(f'<div class="affiliation-item">{affiliation}</div>', unsafe_allow_html=True)
                else:
                    with st.expander("Affiliations", expanded=True):
                        st.info("No affiliations found")
                
                # Research Interests section
                if researcher.get('research_interests'):
                    with st.expander("Research Interests", expanded=True):
                        interests_html = '<div>'
                        for interest in researcher['research_interests']:
                            interests_html += f'<span class="interest-item">{interest}</span> '
                        interests_html += '</div>'
                        st.markdown(interests_html, unsafe_allow_html=True)
                else:
                    with st.expander("Research Interests", expanded=True):
                        st.info("No research interests found")
                
                # Key contributions section
                if researcher.get('key_contributions'):
                    with st.expander("Key Contributions", expanded=True):
                        st.markdown(researcher['key_contributions'])
                
                # Additional insights section
                if researcher.get('additional_insights'):
                    with st.expander("Additional Insights", expanded=False):
                        st.markdown(researcher['additional_insights'])
                
                # Data sources section
                if researcher.get('source_urls'):
                    with st.expander("Data Sources", expanded=False):
                        for source, url in researcher['source_urls'].items():
                            if url:
                                st.markdown(f"- [{source.title()}]({url})")
                        
                        if researcher.get('ai_generated') or researcher.get('ai_enhanced'):
                            st.info("Some information was enhanced using AI")
                
            # Check if this was AI generated and show disclaimer
            if researcher.get('ai_generated'):
                st.warning("Note: This profile was generated using AI and may not be 100% accurate. Verify important information from official sources.")
            
        except Exception as e:
            st.error(f"Error displaying researcher profile: {str(e)}")
    
    # Chat tab
    with tab2:
        st.markdown('<div class="sub-header">Ask Questions About This Researcher</div>', unsafe_allow_html=True)
        
        # Display chat history
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for message in st.session_state.chat_history:
            if message["role"] == "user":
                st.markdown(f'<div class="chat-user">{message["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-agent">{message["content"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Question input
        question = st.text_input("Ask a question about this researcher", key="question_input", 
                               placeholder="e.g., What are their key contributions to the field?")
        
        # Suggested questions
        st.markdown("### Suggested Questions")
        questions_col1, questions_col2 = st.columns(2)
        with questions_col1:
            if st.button("🔬 What are their research interests?"):
                question = "What are their main research interests?"
            if st.button("🏆 What are their key achievements?"):
                question = "What are their key achievements and contributions to the field?"
        with questions_col2:
            if st.button("🏥 What clinical trials are they involved in?"):
                question = "What clinical trials are they involved in or have led?"
            if st.button("🔗 Who do they collaborate with?"):
                question = "Who are their main collaborators and research partners?"

        # Send button
        if st.button("Send Question", type="primary") or question != st.session_state.get("previous_question", ""):
            if question and question != st.session_state.get("previous_question", ""):
                # Save current question to avoid duplicate processing
                st.session_state.previous_question = question
                
                # Check for OpenAI API key
                has_api_key = False
                if st.session_state.agent and st.session_state.agent.openai_api_key:
                    has_api_key = True
                elif openai_api_key:
                    has_api_key = True
                elif os.getenv("OPENAI_API_KEY"):
                    has_api_key = True
                
                if not has_api_key:
                    st.error("OpenAI API key is required for asking questions. Please add it in the sidebar.")
                    
                    # Add information to chat history
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": question
                    })
                    st.session_state.chat_history.append({
                        "role": "agent",
                        "content": "I need an OpenAI API key to answer questions. Please add your API key in the sidebar."
                    })
                    st.rerun()
                else:
                    # Add user question to chat history
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": question
                    })
                    
                    # Show spinner while getting the answer
                    with st.spinner("Getting answer..."):
                        try:
                            # Make sure agent is initialized
                            if st.session_state.agent is None:
                                # Try to use API key from environment first
                                env_api_key = os.getenv("OPENAI_API_KEY")
                                if env_api_key:
                                    st.session_state.agent = MedicalResearcherAgent(openai_api_key=env_api_key)
                                else:
                                    st.session_state.agent = MedicalResearcherAgent(openai_api_key=openai_api_key)
                                
                            # Make sure researcher data is in the agent
                            if st.session_state.current_researcher not in st.session_state.agent.researchers_data:
                                st.session_state.agent.researchers_data[st.session_state.current_researcher] = st.session_state.researcher_data
                            
                            # Get answer from agent
                            answer = st.session_state.agent.ask_question(
                                question, 
                                st.session_state.current_researcher
                            )
                            
                            # Add agent response to chat history
                            st.session_state.chat_history.append({
                                "role": "agent",
                                "content": answer
                            })
                            
                        except Exception as e:
                            error_msg = f"Error getting answer: {str(e)}"
                            st.error(error_msg)
                            
                            # Add error message to chat
                            st.session_state.chat_history.append({
                                "role": "agent",
                                "content": f"I'm sorry, I encountered an error: {str(e)}"
                            })
                    
                    # Rerun to update the chat display
                    st.rerun()

# Display welcome message if no search has been performed
if not st.session_state.search_performed:
    st.markdown("""
    <div class="info-box">
        <div class="section-header">Welcome to the Medical Researcher Search Agent!</div>
        <p>This tool helps you find comprehensive information about medical researchers from various sources including academic databases and research platforms.</p>
        
        <div class="section-header">How to use:</div>
        <ol>
            <li>Enter your OpenAI API key in the sidebar (required for AI-enhanced features)</li>
            <li>Optionally upload a CSV file with researcher information</li>
            <li>Enter a researcher name and click "Search Researcher"</li>
            <li>View the detailed profile and ask questions about the researcher</li>
        </ol>
        
        <div class="section-header">Data Sources:</div>
        <ul>
            <li><b>PubMed</b> - Medical publications and research papers</li>
            <li><b>ResearchGate</b> - Academic profiles and connections</li>
            <li><b>Google Scholar</b> - Citations and academic impact</li>
            <li><b>ClinicalTrials.gov</b> - Clinical trial involvement</li>
            <li>Your uploaded CSV data (if provided)</li>
        </ul>
        
        <div class="section-header">Example Researchers to Try:</div>
        <ul>
            <li>Dr. Anthony Fauci (Immunology)</li>
            <li>Dr. Jennifer Doudna (CRISPR, Genomics)</li>
            <li>Dr. Eric Topol (Cardiology)</li>
            <li>Dr. Francis Collins (Genetics)</li>
            <li>Dr. Devi Sridhar (Global Health)</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown(
    "Medical Researcher Search Agent - Combines web scraping, data integration, and AI to provide researcher insights."
) 
# Medical Researcher Web Search Agent

A powerful web scraping and AI-enhanced search tool for extracting detailed information about medical researchers from multiple sources.

## Features

- Extract researcher information from uploaded CSV files
- Search multiple medical and academic websites:
  - PubMed
  - ResearchGate
  - Google Scholar
  - ClinicalTrials.gov
- Consolidate data from all sources into comprehensive profiles
- Enhance data using OpenAI's GPT models
- Answer natural language questions about researchers
- User-friendly web interfaces (FastAPI and Streamlit)

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd medical-researcher-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application (choose one):

**FastAPI Web Application:**
```bash
python app.py
```
Then open your browser and go to: http://localhost:8000

**Streamlit Application (Recommended):**
```bash
streamlit run streamlit_app.py
```
Then open your browser at the URL provided by Streamlit (typically http://localhost:8501)

## Usage

### Streamlit Application (Recommended)

The Streamlit interface provides a more user-friendly experience with:
- Sidebar for configuration and data source management
- CSV upload with preview functionality 
- Sample CSV template download
- Enhanced researcher profile display
- Interactive question suggestions
- Visually appealing chat interface

To use the Streamlit application:
1. Enter your OpenAI API key in the sidebar
2. Optionally upload a CSV file with researcher information
3. Enter a researcher name and click "Search Researcher"
4. View the comprehensive profile and ask questions

### FastAPI Web Application

The FastAPI version provides a more traditional web interface:

1. Enter your OpenAI API key in the Configuration section
   - This is optional but required for AI-enhanced features
   - The key is stored locally in your browser, not on the server

2. Upload a CSV file (optional) or rely on web scraping
   
3. Enter researcher name and click Search
   
4. View the comprehensive profile and ask questions in the chat interface

### Programmatic Usage

You can also use the agent programmatically in your Python code:

```python
from medical_researcher_agent import MedicalResearcherAgent

# Initialize the agent
agent = MedicalResearcherAgent(openai_api_key="your-api-key")

# Search for a researcher
researcher_data = agent.search_researcher("Dr. Jane Smith", "Oncology")

# Ask questions about the researcher
answer = agent.ask_question("What are Dr. Smith's key research contributions?", "Dr. Jane Smith")

# Generate a formatted report
report = agent.generate_researcher_report("Dr. Jane Smith")
```

## CSV File Format

The system can accept CSV files with information about researchers. The following columns are recognized:

- `Name`: Full name of the researcher
- `Specialization`: Field of expertise
- `Affiliation`: Institution or organization
- `Research Interests`: Comma-separated list of research areas
- `Publications`: List of notable publications
- `Email`: Contact email
- `Phone`: Contact phone number
- `Location`: Geographic location

Example CSV format:
```
Name,Specialization,Affiliation,Research Interests,Email
Dr. Jane Smith,Oncology,Mayo Clinic,"Cancer immunotherapy, Targeted therapy",jane.smith@example.com
Dr. John Doe,Cardiology,Johns Hopkins,"Heart failure, Cardiac imaging",john.doe@example.com
```

A sample CSV template (`sample_researchers.csv`) is included in the repository.

## API Endpoints

The system provides REST API endpoints for programmatic access:

- `POST /api/upload-csv`: Upload researcher data in CSV format
- `POST /api/search-researcher`: Search for information about a specific researcher
- `POST /api/ask-question`: Ask a question about a researcher
- `POST /api/set-api-key`: Set the OpenAI API key for the session
- `POST /api/search-with-websites`: Search with custom website list

## Notes

- Web scraping is subject to rate limiting and may be throttled by the source websites
- The AI enhancement requires an OpenAI API key and may incur usage costs
- All information is collected from publicly available sources
- Always verify critical information from primary sources

## Requirements

- Python 3.8+
- FastAPI and/or Streamlit
- BeautifulSoup4
- OpenAI API key (optional but recommended)
- Other dependencies listed in requirements.txt

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
# Medical Researcher Search Tool

An AI-powered application that helps you find comprehensive information about medical researchers from various sources including academic databases and research platforms.

![Medical Researcher Search Tool](images/Screenshot%202025-05-13%20182955.png)

## Overview

The Medical Researcher Search Tool combines web scraping, data integration, and AI to provide detailed insights about medical researchers. It searches multiple sources for information and presents it in a structured, easy-to-navigate format.

## Features

- **Multi-source Search**: Gathers information from PubMed, ResearchGate, Google Scholar, and ClinicalTrials.gov
- **Custom Website Integration**: Add specific websites (institution pages, university profiles, etc.) to enhance search results
- **Comprehensive Researcher Profiles**: View detailed information including publications, clinical trials, affiliations, research interests, and more
- **Interactive Chat Interface**: Ask specific questions about researchers and receive AI-generated answers
- **CSV Data Import**: Upload researcher information in CSV format

## Installation

### Prerequisites

- Python 3.8 or higher
- OpenAI API key (set in environment variables or .env file)

### Steps

1. Clone the repository or download the source code
2. Install the required dependencies: `pip install -r requirements.txt`
3. Set up your OpenAI API key in a `.env` file
4. Run the application: `streamlit run app.py`

## Usage

- **Search**: Enter a researcher name and their specialization, then click "Search Researcher"
- **Custom Websites**: Add institution pages or profiles to enhance search results
- **Chat**: Ask specific questions about the researcher
- **CSV Upload**: Import researcher data from CSV files

## Data Sources

- PubMed - Medical publications and research papers
- ResearchGate - Academic profiles and connections
- Google Scholar - Citations and academic impact
- ClinicalTrials.gov - Clinical trial involvement

## License

This project is licensed under the MIT License [LICENSE].

---

Created by i3 Digital Health Team 

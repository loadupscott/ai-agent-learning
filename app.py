import os
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from firecrawl import Firecrawl

# Configure page (this helps with context initialization)
st.set_page_config(page_title="Competitor Intelligence Agent", page_icon="🕵️‍♂️")

# Load API keys from .env
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')

# The UI Layout
st.title('🕵️‍♂️ Competitor Intelligence Agent')

# Add a text input box: 'Enter Competitor URL'
url = st.text_input('Enter Competitor URL', placeholder='https://example.com')

# Add a button: 'Analyze Strategy'
if st.button('Analyze Strategy'):
    # The Logic (Run only when button is clicked)
    if not url:
        st.error('Please enter a URL')
    else:
        try:
            # Show a loading spinner ('Scraping website...')
            with st.spinner('Scraping website...'):
                # Initialize FirecrawlApp and scrape the URL (markdown format)
                firecrawl_app = Firecrawl(api_key=FIRECRAWL_API_KEY)
                scrape_result = firecrawl_app.scrape(url, formats=['markdown'])
                
                # Extract markdown content from the result object
                markdown_content = scrape_result.markdown if hasattr(scrape_result, 'markdown') else str(scrape_result)
            
            # Show a success message ('Scraping complete!')
            st.success('Scraping complete!')
            
            # Send the markdown to gpt-4o-mini with the prompt
            with st.spinner('Analyzing content...'):
                openai_client = OpenAI(api_key=OPENAI_API_KEY)
                
                prompt = 'Analyze this landing page. Return a markdown report with headers for: Value Prop, Pricing, and Target Audience.'
                
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "user", "content": f"{prompt}\n\nLanding page content:\n{markdown_content}"}
                    ]
                )
                
                # Get the result
                report = response.choices[0].message.content
            
            # Display the result using st.markdown()
            st.markdown("## Analysis Report")
            st.markdown(report)
            
            # Add a 'Download Report' button to save the result as a text file
            st.download_button(
                label='Download Report',
                data=report,
                file_name='competitor_report.txt',
                mime='text/plain'
            )
            
        except Exception as e:
            # Error Handling: Use st.error if the URL is invalid or the API fails
            st.error(f'Error: {str(e)}')

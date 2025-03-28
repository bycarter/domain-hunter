# Domain Scoring Dashboard

A web application for evaluating and scoring domain names using AI and providing pricing information.

## Overview

This application helps identify and evaluate potential domain names by:
1. Generating short, pronounceable domain names
2. Checking domain availability across popular TLDs
3. Scoring domains using AI on metrics like memorability and brandability
4. Providing pricing information through domain registrar APIs
5. Presenting all this data in an interactive dashboard

## Project Structure

```
domain-hunter/
├── data/                    # Data storage directory
│   └── domains.db           # SQLite database containing domain information
├── src/
│   ├── static/              # Static web assets
│   │   ├── css/
│   │   │   └── dashboard.css   # Dashboard styling
│   │   └── js/
│   │       └── dashboard.js    # Client-side functionality
│   ├── templates/           # HTML templates
│   │   └── index.html       # Main dashboard interface
│   ├── ai_score_domains.py  # AI scoring logic using OpenAI API
│   ├── check_db.py          # Database verification utility
│   ├── check_domains.py     # Domain availability checker
│   ├── dashboard.py         # Flask web application
│   ├── domain_pricing.py    # Domain pricing functionality
│   ├── generate_words.py    # Word generation utility
│   ├── inspect_db.py        # Database inspection utility
│   ├── migrate_schema.py    # Database schema migration
│   ├── run_pipeline.py      # Main pipeline runner
│   └── utils.py             # Shared utility functions
```

## Component Responsibilities

### Backend Components

- **dashboard.py**: Flask server that provides the web interface and API endpoints
- **ai_score_domains.py**: Uses OpenAI API to score domains on memorability, pronunciation, visual appeal, and brandability
- **check_domains.py**: Checks domain availability across various TLDs using RDAP API
- **domain_pricing.py**: Retrieves domain pricing information
- **generate_words.py**: Creates potential domain names by generating short, pronounceable words
- **utils.py**: Common utility functions used across the application

### Frontend Components

- **index.html**: The main dashboard interface
- **dashboard.css**: Styling for the dashboard
- **dashboard.js**: Client-side functionality for filtering, sorting, and displaying domain data

### Database

The application uses SQLite to store domain information with the following main fields:
- Domain name
- Memorability score
- Pronunciation score
- Visual appeal score
- Brandability score
- Average score
- Price information
- Availability status

## API Endpoints

- **/api/domains**: Returns a list of domains matching filter criteria
- **/api/stats**: Returns statistics about the domains in the database
- **/api/debug**: Provides debug information about the database and application

## Getting Started

1. **Setup Environment**:
   ```
   pip install -r requirements.txt
   ```

2. **Set API Keys**:
   Create a `.env` file with the following variables:
   ```
   OPENAI_API_KEY=your_openai_api_key
   NAMECHEAP_API_KEY=your_namecheap_api_key (optional)
   NAMECHEAP_USERNAME=your_namecheap_username (optional)
   CLIENT_IP=your_whitelisted_ip (optional for pricing)
   ```

3. **Generate Domains**:
   ```
   python src/generate_words.py
   ```

4. **Check Domain Availability**:
   ```
   python src/check_domains.py
   ```

5. **Score Domains**:
   ```
   python src/ai_score_domains.py
   ```

6. **Run the Dashboard**:
   ```
   python src/dashboard.py
   ```

7. **Access the Dashboard**:
   Open `http://localhost:5000` in your browser

Alternatively, you can run the entire pipeline with:
```
python src/run_pipeline.py
```

## Key Features

- **AI Domain Scoring**: Uses AI to evaluate domain quality across multiple dimensions
- **Domain Availability**: Checks if domains are available for registration
- **Domain Pricing**: Retrieves pricing information for available domains
- **Interactive Dashboard**: Filter, sort, and explore domains in an easy-to-use interface
- **Data Export**: Export domain data to CSV or JSON for further analysis

## Technologies Used

- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, JavaScript, Bootstrap
- **Database**: SQLite
- **APIs**: OpenAI API, Domain RDAP API, Namecheap API (optional)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
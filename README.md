# Uptrends to Elastic Synthetics Migration Tool

Python tool for migrating Uptrends monitors to Elastic Synthetics format using AI-powered classification.

## Setup

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Environment Variables
Create a `.env` file with:
```
UPTRENDS_USERNAME=your_username
UPTRENDS_PASSWORD=your_password
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
```

## Usage

### Run Migration
```bash
python main.py
```

The tool processes a predefined list of monitors and generates Elastic Synthetics configurations.

## Architecture

### Core Components

- **`main.py`**: Entry point with environment validation and result display
- **`migration_script.py`**: Main orchestrator handling the migration flow
- **`uptrends_client.py`**: Uptrends API client with monitor data models
- **`ai_monitor_classifier.py`**: Hybrid AI/rules classification system
- **`monitor_validator.py`**: Strict validation for generated configurations

### Migration Flow

1. **Predefined List**: Processes specific monitors from hard-coded list
2. **API Fetching**: Gets complete monitor details from Uptrends
3. **AI Classification**: Determines appropriate Elastic monitor type
4. **Config Generation**: Creates YAML (lightweight) or TypeScript (journey) files
5. **Validation**: Ensures generated configs meet Elastic requirements
6. **Output**: Saves organized files with migration reports

### Monitor Type Mapping

| Uptrends Type | Elastic Type | Output Format |
|---------------|--------------|---------------|
| HTTP/HTTPS | http | YAML (lightweight) |
| Ping | icmp | YAML (lightweight) |
| TCP/SMTP/POP3/IMAP | tcp | YAML (lightweight) |
| Transaction/MultiStepApi | browser | TypeScript (journey) |

### Output Structure
```
../nodejs-monitors/monitors/
├── lightweight/           # YAML files for http, tcp, icmp
├── journey/              # TypeScript files for browser  
└── migration_results_*.json  # Migration reports
```

## Dependencies

- `requests`: API communication
- `pydantic`: Data validation
- `tenacity`: Retry logic
- `rich`: Terminal formatting
- `click`: CLI parsing
- `PyYAML`: YAML generation
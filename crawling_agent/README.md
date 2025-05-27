# Crawling Agent

A modular system for crawling multiple data sources based on natural language queries. The Crawling Agent translates natural language into structured task instructions and retrieves raw data from ERP systems (SQL), Knowledge Graphs (SPARQL), and Document Storage (MongoDB).

## Project Overview

The Crawling Agent is designed to be a component in a larger data fusion pipeline. Its sole purpose is to retrieve raw data from various sources according to natural language instructions, which will later be processed by other components.

### Key Features

- Natural language query translation using LLM
- Modular architecture with separate connectors for each data source
- Support for SQL, SPARQL, and MongoDB queries
- Parallel or sequential execution of queries
- Comprehensive logging for auditability
- Configuration via YAML and environment variables

## Architecture

The system consists of the following components:

- **Translator**: Converts natural language queries into structured task instructions
- **Controller**: Coordinates the execution of queries across multiple data sources
- **Connectors**: Interface with specific data sources (ERP, Knowledge Graph, Document Storage)
- **Models**: Define the data structures used throughout the system
- **Utils**: Provide common functionality like logging

## Directory Structure

```
/crawling_agent
│
├── main.py                        # Entry point, handles GUI input and controls the agent
│
├── translator/
│   ├── query_translator.py        # Class: QueryTranslator (natural language → structured task JSON)
│   └── mock_llm.py                # Class: MockLLM (for testing without real model yet)
│
├── controller/
│   └── crawling_controller.py     # Class: CrawlingAgentController (coordinates task execution)
│
├── connectors/
│   ├── erp_connector.py           # Class: ERPConnector (SQL crawler)
│   ├── knowledge_graph_connector.py # Class: KnowledgeGraphConnector (SPARQL crawler)
│   └── document_storage_connector.py # Class: DocumentStorageConnector (MongoDB crawler)
│
├── models/
│   └── task_instruction.py        # Dataclass: TaskInstruction (Structured description of what to crawl)
│
├── utils/
│   └── logger.py                  # Logger utility (for tracking input-output)
│
├── config/
│   └── config.yaml                # Configuration (DB URIs, API endpoints, authentication)
│
└── README.md                      # Project documentation
```

## Getting Started

### Prerequisites

- Python 3.8+
- Access to synthetic data environments for ERP, Knowledge Graph, and Document Storage

### Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

### Configuration

Configure the system by editing `config/config.yaml` or by setting environment variables:

- `ERP_DB_URI`: URI for the ERP database
- `KG_ENDPOINT`: SPARQL endpoint for the Knowledge Graph
- `DOCUMENT_DB_URI`: URI for the MongoDB document storage
- `DOCUMENT_DB_NAME`: Name of the MongoDB database
- `LLM_API_KEY`: API key for the LLM service (when not using mock)
- `CRAWLING_AGENT_LOG_LEVEL`: Logging level (INFO, DEBUG, etc.)
- `CRAWLING_AGENT_LOG_TO_FILE`: Whether to log to a file (true/false)
- `CRAWLING_AGENT_LOG_DIR`: Directory for log files
- `CRAWLING_PARALLEL`: Whether to execute queries in parallel (true/false)

### Usage

Run the Crawling Agent with a natural language query:

```bash
python main.py --query "Find all products with price greater than 100"
```

Or use an input file:

```bash
python main.py --input-file input.json --output-file results.json
```

For testing without real database connections:

```bash
python main.py --query "List all employees in the Sales department" --mock
```

## Development

### Adding a New Data Source

To add a new data source:

1. Add a new source type to `DataSourceType` enum in `models/task_instruction.py`
2. Create a new connector in the `connectors/` directory
3. Update the `CrawlingAgentController` to handle the new source type
4. Update the mock LLM to generate appropriate queries for the new source

### Replacing the Mock LLM

To replace the mock LLM with a real implementation:

1. Create a new class that implements the same interface as `MockLLM`
2. Update the `QueryTranslator` to use the new implementation when `use_mock=False`
3. Update the configuration in `config.yaml` with the appropriate LLM settings

## Integration with Data Fusion Pipeline

The Crawling Agent is designed to be easily integrated with a Fusing Agent:

1. The output of the Crawling Agent is a JSON structure containing raw data from multiple sources
2. This output can be passed directly to the Fusing Agent for further processing
3. The task_id can be used to track the data through the entire pipeline

## License

[Specify your license here]
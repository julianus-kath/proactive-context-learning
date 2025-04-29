/crawling_agent
│
├── main.py                        # Entry point, handles GUI input and controls the agent
│
├── translator/
│   ├── query_translator.py         # Class: QueryTranslator (natural language → structured task JSON)
│   └── mock_llm.py                 # Class: MockLLM (for testing without real model yet)
│
├── controller/
│   └── crawling_controller.py      # Class: CrawlingAgentController (coordinates task execution)
│
├── connectors/
│   ├── erp_connector.py            # Class: ERPConnector (SQL crawler)
│   ├── knowledge_graph_connector.py# Class: KnowledgeGraphConnector (SPARQL crawler)
│   └── document_storage_connector.py# Class: DocumentStorageConnector (MongoDB crawler)
│
├── models/
│   └── task_instruction.py         # Dataclass: TaskInstruction (Structured description of what to crawl)
│
├── utils/
│   └── logger.py                   # Logger utility (for tracking input-output)
│
├── config/
│   └── config.yaml                 # Configuration (DB URIs, API endpoints, authentication)
│
└── README.md                       # Project documentation

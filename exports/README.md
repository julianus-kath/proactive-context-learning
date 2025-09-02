# ADR-0010 Export Files

This directory contains exported versions of **ADR-0010: Dynamic ERP Assistant Complete System Architecture**.

## 📁 Contents

### 📄 Main Documents
- **`ADR-0010-Architecture.pdf`** - Complete PDF version with all content
- **`ADR-0010-Architecture.html`** - Interactive HTML version with diagram links
- **`0010-dynamic-erp-assistant-complete-system-architecture.md`** - Original Markdown source

### 🖼️ Individual Diagrams (`diagrams/` folder)
All 14 architecture diagrams exported as high-quality PNG images:

1. **`01_System_Overview.png`** - High-level system architecture
2. **`02_Component_Architecture.png`** - Detailed component breakdown
3. **`03_Class_Diagram.png`** - Complete object-oriented design
4. **`04_Complete_Query_Processing_Flow.png`** - End-to-end query sequence
5. **`05_Schema_Discovery_Process.png`** - Database introspection flow
6. **`06_Error_Handling_and_Clarification_Flow.png`** - Error handling sequence
7. **`07_Data_Flow_Architecture.png`** - Data processing pipeline
8. **`08_Database_Schema_Structure.png`** - Complete ERD with relationships
9. **`09_Component_Responsibilities.png`** - System responsibilities breakdown
10. **`10_System_Performance_Metrics.png`** - Performance characteristics table
11. **`11_Scalability_Architecture.png`** - Multi-instance deployment design
12. **`12_Security_Layers.png`** - Multi-layered security model
13. **`13_Container_Deployment.png`** - Docker deployment architecture
14. **`14_Monitoring_Stack.png`** - Observability and monitoring design

## 🎯 Usage Options

### For Presentations
- Use individual PNG diagrams from the `diagrams/` folder
- High resolution (1200x800) suitable for projection
- White background for professional appearance

### For Documentation
- Use the **PDF version** for complete documentation
- Use the **HTML version** for interactive viewing
- Reference individual diagrams as needed

### For Development
- Original **Markdown file** contains all Mermaid source code
- Can be edited and re-exported as needed
- Compatible with GitHub, GitLab, and other Markdown viewers

## 🔄 Re-exporting

To regenerate exports after making changes:

```bash
cd "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code"
python3 simple_pdf_export.py
```

## 📊 Diagram Details

### System Architecture Diagrams
- **System Overview**: Complete system with all layers and components
- **Component Architecture**: Detailed breakdown of each architectural layer
- **Component Responsibilities**: Clear separation of concerns

### Interaction Diagrams  
- **Complete Query Processing Flow**: Full user query to response sequence
- **Schema Discovery Process**: Database introspection and metadata extraction
- **Error Handling Flow**: Clarification and error recovery processes

### Data & Infrastructure
- **Data Flow Architecture**: Step-by-step data processing pipeline
- **Database Schema Structure**: Complete ERD with all relationships
- **Scalability Architecture**: Multi-instance deployment design
- **Container Deployment**: Docker-based deployment architecture

### Security & Monitoring
- **Security Layers**: Multi-layered security implementation
- **Monitoring Stack**: Complete observability architecture

### Technical Design
- **Class Diagram**: Complete object-oriented design with relationships
- **System Performance Metrics**: Expected performance characteristics

## 🛠️ Technical Specifications

- **Image Format**: PNG with white background
- **Resolution**: 1200x800 pixels (3x scale factor)
- **PDF**: A4 format with proper margins
- **HTML**: Responsive design with embedded styles

## 📋 Export Tools Used

- **Mermaid CLI**: For diagram generation (`@mermaid-js/mermaid-cli`)
- **Chrome Headless**: For PDF generation
- **Python**: For automation and processing

---

**Generated**: 2024-12-19  
**Source**: ADR-0010 Dynamic ERP Assistant Complete System Architecture  
**Export Script**: `simple_pdf_export.py`
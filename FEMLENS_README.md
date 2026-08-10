# FemLens — Women's Health Research Companion

**FemLens** is a Databricks App that provides a clean research workspace for exploring women's-health clinical research. It helps researchers discover, explore, and organize relevant clinical studies from ClinicalTrials.gov.

---

## 🎯 Features

### 1. Research Companion
- **Natural Language Questions**: Ask research questions in plain English
- **Agent-Powered Search**: Databricks Agent Bricks intelligently routes queries to appropriate MCP tools
- **Clinical Studies Discovery**: Search ClinicalTrials.gov for relevant studies
- **Semantic Knowledge Search**: Vector-powered search through health research documents
- **Study Details**: View comprehensive information about specific clinical trials

### 2. Research Collection
- **Personal Library**: Save relevant studies to your personal research collection
- **Research Notes**: Add notes explaining why each study is relevant
- **Easy Management**: View, organize, and remove studies from your collection
- **User-Scoped**: Each user has their own private research collection

---

## 🏗️ Architecture

```
User Question
     ↓
FemLens UI (Flask + HTML/JS)
     ↓
FemLens Backend (app.py)
     ↓
[Option A: Via MCP Server] → Health MCP Server → Agent Bricks → MCP Tools
     ↓
[Option B: Direct API] → HealthClient → ClinicalTrials.gov API
     ↓
Lakebase (Postgres)
  - health_research_collection (saved studies)
  - health_documents (indexed documents)
  - health_embeddings (vector search)
```

### Components

1. **app.py** - Flask backend serving the UI and API endpoints
2. **templates/index.html** - Modern, responsive research interface
3. **health_client.py** - ClinicalTrials.gov API client
4. **lakebase.py** - Postgres database connector
5. **mcp_server/health_mcp_server.py** - MCP tools server (optional integration)

---

## 📋 Prerequisites

1. **Lakebase Database** with the following tables:
   - `health_research_collection` (created automatically)
   - `health_documents` (for knowledge base, optional)
   - `health_embeddings` (for vector search, optional)

2. **Environment Variables**:
   - `RESEARCH_COLLECTION_TABLE` (default: `health_research_collection`)
   - `MCP_SERVER_URL` (default: `http://localhost:8001`)
   - `FLASK_SECRET_KEY` (optional, auto-generated if not provided)

3. **Databricks Secrets** (for Lakebase connection):
   - Scope: `database`
   - Key: `lakebase-url`

---

## 🚀 Deployment

### Option 1: Deploy as Databricks App (Recommended)

1. **Update app.yaml** with your configuration:

```yaml
name: femlens-health-research

resources:
  - name: femlens-app
    description: "FemLens — Women's Health Research Companion"
    source_code_path: .
```

2. **Deploy**:

```bash
databricks apps deploy \
  --source-code-path /Workspace/Users/<your-email>/FemHealth_RAG_Assist \
  --config app.yaml \
  --app-name femlens-health-research
```

3. **Access**: Navigate to your deployed app URL

### Option 2: Run Locally

```bash
cd /Workspace/Users/<your-email>/FemHealth_RAG_Assist

# Install dependencies
pip install -r requirements.txt

# Run Flask app
python app.py
```

Open `http://localhost:8000` in your browser.

---

## 📖 Usage Guide

### Primary Workflow

1. **Ask a Research Question**
   - Navigate to **Research Companion**
   - Enter your research question (e.g., "Find recruiting menopause studies related to sleep problems")
   - Click **Ask FemLens**

2. **Review Results**
   - FemLens displays relevant clinical studies
   - Each study card shows:
     - Study title
     - NCT ID (ClinicalTrials.gov identifier)
     - Recruitment status (Recruiting, Completed, etc.)
     - Condition being studied
     - Brief summary

3. **View Study Details**
   - Click **View Details** on any study card
   - See comprehensive information:
     - Full study description
     - Eligibility criteria
     - Outcome measures
     - Study type and status
     - Locations and sponsors

4. **Save to Collection**
   - Click **Save to Collection**
   - (Optional) Add research notes explaining relevance
   - Study is added to your personal collection

5. **Manage Collection**
   - Navigate to **Research Collection**
   - View all saved studies
   - Click **View Study** to see details
   - Click **Remove** to delete from collection (with confirmation)

---

## 🔌 API Endpoints

### Research Endpoints

**POST /api/ask**
- Submit a natural-language research question
- Body: `{"question": "your research question"}`
- Returns: Agent response + relevant studies

**GET /api/study/:nct_id**
- Fetch detailed information about a specific study
- Returns: Full study details from ClinicalTrials.gov

### Collection Endpoints

**GET /api/collection**
- Retrieve current user's saved studies
- Returns: Array of saved studies with enriched details

**POST /api/collection**
- Save a study to the research collection
- Body: `{"nct_id": "NCT12345678", "notes": "Optional notes"}`
- Returns: Confirmation with saved details

**DELETE /api/collection/:nct_id**
- Remove a study from the collection
- Returns: Confirmation of deletion

---

## 🎨 User Interface

### Design Principles

- **Clean & Professional**: Healthcare-oriented color palette
- **Research-Focused**: Optimized for information discovery
- **Responsive Layout**: Works on desktop and tablet
- **User-Friendly**: Clear navigation and intuitive interactions

### Key UI Elements

1. **Sidebar Navigation**
   - FemLens branding and tagline
   - Page navigation (Research Companion, Research Collection)
   - User identification

2. **Study Cards**
   - Clean, scannable layout
   - Status badges (color-coded)
   - Primary actions (View Details, Save)

3. **Modals**
   - Save Study (with optional notes)
   - Remove Confirmation

---

## 🔒 Security & Privacy

- **User-Scoped Collections**: Each user's research collection is private
- **Databricks Authentication**: Leverages X-Forwarded-Email header
- **Parameterized SQL**: All database queries use parameterized statements
- **Error Handling**: User-friendly messages (no stack traces exposed)

---

## 🧪 Testing

### Manual Testing Checklist

1. **Research Companion**
   - [ ] Submit a research question
   - [ ] Verify study results display
   - [ ] Click "View Details" on a study
   - [ ] Verify study details load correctly

2. **Save Functionality**
   - [ ] Click "Save to Collection" on a study
   - [ ] Add optional notes
   - [ ] Verify success message
   - [ ] Check study appears in collection

3. **Research Collection**
   - [ ] Navigate to Research Collection page
   - [ ] Verify saved studies display
   - [ ] Click "View Study" on a saved study
   - [ ] Click "Remove" and confirm
   - [ ] Verify study is removed

4. **Error Handling**
   - [ ] Test with invalid NCT ID
   - [ ] Test with empty research question
   - [ ] Test removing non-existent study

---

## 📊 Integration Points

### Agent Bricks Integration

FemLens is designed to integrate with Databricks Agent Bricks:

1. **Natural Language Understanding**: Agent interprets research questions
2. **MCP Tool Orchestration**: Agent decides which MCP tools to invoke
3. **Response Generation**: Agent synthesizes results into readable insights

### MCP Tools Used

When integrated via MCP Server:
- `search_health_studies` - Search ClinicalTrials.gov
- `get_study_details` - Fetch study information
- `search_health_knowledge` - Vector similarity search
- `save_research_study` - Save to collection
- `get_research_collection` - Retrieve saved studies
- `remove_research_study` - Remove from collection

---

## 🛠️ Customization

### Environment Variables

```bash
# Research collection table name
export RESEARCH_COLLECTION_TABLE="health_research_collection"

# MCP server URL (if using Agent Bricks integration)
export MCP_SERVER_URL="http://localhost:8001"

# Flask secret key (for sessions)
export FLASK_SECRET_KEY="your-secret-key"

# Flask host and port
export FLASK_RUN_HOST="0.0.0.0"
export FLASK_RUN_PORT="8000"
```

### Styling

Modify CSS variables in `templates/index.html`:

```css
:root {
  --accent: #7c3aed;        /* Primary purple */
  --recruiting: #10b981;     /* Status: recruiting */
  --completed: #6b7280;      /* Status: completed */
  --danger: #ef4444;         /* Remove button */
}
```

---

## 📝 Example Research Questions

### Menopause Research
- "Find recruiting menopause studies related to sleep problems"
- "What trials are investigating non-hormonal approaches to menopause symptoms?"
- "Show me completed menopause studies from the last 3 years"

### Reproductive Health
- "Find studies about endometriosis treatment options"
- "What clinical trials are investigating PCOS management?"
- "Show me recruiting fertility preservation studies"

### Pregnancy & Maternal Health
- "Find studies about gestational diabetes prevention"
- "What trials are investigating preeclampsia risk factors?"
- "Show me postpartum depression treatment studies"

### Women's Cardiovascular Health
- "Find studies about heart disease in women"
- "What trials are investigating cardiovascular disease prevention in postmenopausal women?"

---

## 🐛 Troubleshooting

### "Research service is unavailable"
- Check MCP_SERVER_URL environment variable
- Verify MCP server is running (if using Agent Bricks integration)
- Test direct HealthClient connection

### "Unable to load research collection"
- Verify Lakebase connection is configured
- Check database secret: `databricks secrets get --scope database --key lakebase-url`
- Ensure `health_research_collection` table exists

### "Study not found"
- Verify NCT ID format (must start with "NCT")
- Check ClinicalTrials.gov API availability
- Try a different NCT ID

### Studies not displaying
- Check browser console for JavaScript errors
- Verify API endpoint responses
- Clear browser cache

---

## 📚 Related Documentation

- [ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/api)
- [Databricks Apps Documentation](https://docs.databricks.com/apps/)
- [Lakebase Documentation](https://docs.databricks.com/lakebase/)
- [Agent Bricks Documentation](https://docs.databricks.com/agents/)

---

## 🤝 Contributing

This project follows established Databricks App conventions:

1. Keep `app.py` focused on frontend presentation
2. Delegate complex logic to clients (`health_client.py`)
3. Use parameterized SQL for all database operations
4. Return user-friendly error messages
5. Follow Flask best practices

---

## 📄 License

This is a Databricks reference implementation for educational purposes.

---

## 🆘 Support

For issues or questions:
1. Check troubleshooting section above
2. Review Databricks documentation
3. Contact your Databricks support team

---

**FemLens** — Empowering Women's Health Research

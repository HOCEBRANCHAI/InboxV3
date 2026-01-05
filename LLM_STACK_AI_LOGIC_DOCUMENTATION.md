# Section 4 – LLM Stack & AI Logic Documentation

## Q4.1: List all places in the codebase where we call LLMs

### LLM Call Locations

#### **1. Primary LLM Service File**

**File Path:** `openai_service.py`

**Functions that call LLMs:**

1. **`classify_document(text: str) -> dict`** (Line 21)
   - **Purpose**: Document routing and topic creation (INBOX vs ARCHIVE)
   - **LLM Call**: OpenAI Chat Completions API
   - **Called from**:
     - `main.py` (lines 425, 589, 1118) - Synchronous endpoints
     - `worker.py` (line 123) - Background worker processing

2. **`analyze_document(text: str, channel: str, topic_type: str, topic_title: str) -> dict`** (Line 78)
   - **Purpose**: Topic-aware document analysis (for INBOX documents only)
   - **LLM Call**: OpenAI Chat Completions API
   - **Called from**:
     - `main.py` (lines 321, 464) - Synchronous endpoints
     - `worker.py` (line 278) - Background worker processing

3. **`analyze_multiple_documents_consolidated(...) -> dict`** (Line 152)
   - **Purpose**: Consolidated channel analysis (DISABLED - not used in current implementation)
   - **LLM Call**: OpenAI Chat Completions API
   - **Status**: Code exists but function is not called (commented out in imports)
   - **Note**: Kept for reference only, not part of active workflow

---

#### **2. Main API File**

**File Path:** `main.py`

**Functions that call LLM service:**

1. **`analyze_single_file_direct(file: UploadFile, timeout_handler: RequestTimeoutHandler) -> dict`** (Line 268)
   - **LLM Call**: `openai_service.analyze_document()` (line 321)
   - **Endpoint**: `POST /analyze` (single document analysis)
   - **Purpose**: Analyze single document without routing

2. **`classify_documents_async(...)`** (Line 700)
   - **LLM Call**: None (creates job, worker processes it)
   - **Endpoint**: `POST /classify-documents-async`
   - **Note**: Does not call LLM directly, delegates to worker

---

#### **3. Worker Process File**

**File Path:** `worker.py`

**Functions that call LLM service:**

1. **`process_classify_job(job: Dict)`** (Line 58)
   - **LLM Call**: `openai_service.classify_document()` (line 123)
   - **Purpose**: Process classification jobs from database
   - **Job Type**: `endpoint_type='classify'`

2. **`process_analyze_job(job: Dict)`** (Line 218)
   - **LLM Call**: `openai_service.analyze_document()` (line 278)
   - **Purpose**: Process analysis jobs from database
   - **Job Type**: `endpoint_type='analyze'`
   - **Note**: Currently not actively used (analyze endpoints removed)

---

### Summary Table: LLM Call Locations

| File | Function | LLM Function Called | Purpose | Endpoint/Usage |
|------|----------|---------------------|---------|----------------|
| `openai_service.py` | `classify_document()` | OpenAI API | Document routing (INBOX/ARCHIVE) | Called by main.py, worker.py |
| `openai_service.py` | `analyze_document()` | OpenAI API | Topic-aware analysis | Called by main.py, worker.py |
| `openai_service.py` | `analyze_multiple_documents_consolidated()` | OpenAI API | Consolidated analysis | **DISABLED** (not used) |
| `main.py` | `analyze_single_file_direct()` | `analyze_document()` | Single document analysis | `POST /analyze` |
| `main.py` | `classify_documents_async()` | None (creates job) | Creates async job | `POST /classify-documents-async` |
| `worker.py` | `process_classify_job()` | `classify_document()` | Background job processing | Worker process |
| `worker.py` | `process_analyze_job()` | `analyze_document()` | Background analysis | Worker process (not used) |

---

## Q4.2: Are there any Streamlit apps or other "mini apps" that call LLMs directly?

**Answer: No**

- **Streamlit Apps**: None found in codebase
- **Other Mini Apps**: None found
- **LLM Calls**: All LLM calls are made through the main API service (`openai_service.py`)

**Verification:**
- Searched for `streamlit` files: No matches found
- All LLM calls are centralized in `openai_service.py`
- No separate applications or scripts that call LLMs independently

---

## Q4.3: Which LLM providers are we using today?

**Answer: OpenAI Only**

### **Provider: OpenAI**

- **Service**: OpenAI API (Chat Completions)
- **Model**: `gpt-4o` (default, configurable via `OPENAI_MODEL` environment variable)
- **API Client**: `AsyncOpenAI` from `openai` Python library
- **Version**: `openai>=1.55.3` (from requirements.txt)

### **Other Providers: None**

- **Anthropic (Claude)**: Not used
- **Google (Gemini)**: Not used
- **Azure OpenAI**: Not used
- **Other providers**: Not used

---

## Q4.4: Are we using any AWS-native AI services?

**Answer: No AWS AI/ML Services for LLM**

### **AWS Services Used (Non-LLM):**

1. **AWS Textract** (OCR Service)
   - **Purpose**: OCR for scanned documents and images
   - **Not an LLM**: This is an OCR service, not an AI/ML language model
   - **File Path**: `textract_service.py`
   - **Usage**: Text extraction only, not document analysis or routing

### **AWS AI/ML Services NOT Used:**

- **Amazon Bedrock**: ❌ Not used
- **Amazon SageMaker**: ❌ Not used
- **Amazon Comprehend**: ❌ Not used
- **Amazon Rekognition**: ❌ Not used
- **Other AWS AI/ML services**: ❌ Not used

### **Conclusion:**

- **LLM functionality**: 100% OpenAI (no AWS)
- **OCR functionality**: AWS Textract (optional, for scanned documents)
- **No AWS dependencies for LLM logic**

---

## Q4.5: Where does LLM code run today?

### **Current Deployment:**

| LLM Feature | Where It Runs | Hosting Platform | Status |
|-------------|---------------|-----------------|--------|
| **Document Classification** | Main API | Render (Free Tier) | ✅ Active |
| **Document Classification** | Worker Process | Render (Pending deployment) | ⏳ Pending |
| **Document Analysis** | Main API | Render (Free Tier) | ✅ Active |
| **Document Analysis** | Worker Process | Render (Pending deployment) | ⏳ Pending |

### **Detailed Breakdown:**

#### **1. Main API (Render - Free Tier)**
- **Service**: Inbox Main API
- **URL**: https://inboxv3-1.onrender.com
- **LLM Calls**: 
  - Synchronous endpoint (`POST /analyze`)
  - Creates async jobs (worker processes LLM calls)
- **Execution**: Runs on Render web service
- **Status**: ✅ Active

#### **2. Worker Process (Render - Pending)**
- **Service**: Inbox Worker
- **LLM Calls**: 
  - Processes classification jobs (`process_classify_job`)
  - Processes analysis jobs (`process_analyze_job`)
- **Execution**: Will run on Render background worker
- **Status**: ⏳ Pending deployment

#### **3. Local Development**
- **LLM Calls**: Same code runs locally for testing
- **Execution**: Developer machines
- **Status**: Available for development

### **NOT Running On:**

- ❌ **AWS EC2/ECS**: Not used
- ❌ **AWS Lambda**: Not used
- ❌ **Railway**: Not used (considering for worker, but decided on Render)
- ❌ **Streamlit Apps**: None exist
- ❌ **Other PaaS**: Not used

---

## Q4.6: Are there any hard dependencies on AWS for LLM logic?

**Answer: No**

### **AWS Dependencies Analysis:**

#### **LLM Logic: Zero AWS Dependencies** ✅

- **No AWS KMS**: LLM calls use OpenAI API key (stored in environment variables)
- **No AWS S3**: No file storage for LLM operations
- **No Amazon Bedrock**: Not used
- **No AWS Secrets Manager**: API keys stored in environment variables
- **No AWS IAM**: Not required for OpenAI API calls

#### **Non-LLM AWS Usage:**

- **AWS Textract**: Used for OCR (text extraction), not LLM
  - **Dependency Level**: Optional (service works without it)
  - **Impact on LLM**: None (LLM receives extracted text, doesn't care about source)

### **Portability Assessment:**

✅ **Fully Portable**: LLM code can run on:
- Render (current)
- Railway
- Heroku
- Any Python hosting platform
- Local development

✅ **No Vendor Lock-in**: 
- Uses standard OpenAI API (not AWS-specific)
- No AWS SDK dependencies for LLM calls
- Can migrate to any platform without code changes

### **Conclusion:**

**LLM logic has zero hard dependencies on AWS.** The code is fully portable and can run on any platform that supports Python and has internet access to OpenAI API.

---

## Q4.7: Where are our prompt templates stored?

**Answer: In Code (Hardcoded)**

### **Storage Location:**

**File Path:** `prompts.py`

**Storage Method:** Hardcoded Python strings in code file

### **Prompt Templates:**

1. **`DOCUMENT_ROUTING_AND_TOPIC_PROMPT`** (Line 3)
   - **Purpose**: Document routing and topic creation (INBOX vs ARCHIVE)
   - **Used by**: `openai_service.classify_document()`
   - **Length**: ~260 lines (comprehensive prompt with examples)

2. **`TOPIC_AWARE_DOCUMENT_ANALYSIS_PROMPT`** (Line 265)
   - **Purpose**: Topic-aware document analysis (for INBOX documents)
   - **Used by**: `openai_service.analyze_document()`
   - **Length**: ~60 lines

3. **`CONSOLIDATED_CHANNEL_ANALYSIS_PROMPT`** (Commented out)
   - **Status**: DISABLED - not used in current implementation
   - **Note**: Code exists but prompt is not imported or used

### **Storage Method Details:**

- **Not in Database**: Prompts are not stored in Supabase or any database
- **Not in Config Files**: No separate config files (e.g., `config/llm/`)
- **Not in Environment Variables**: Prompts are not in `.env` files
- **Hardcoded in Code**: Python string constants in `prompts.py`

### **Import Structure:**

```python
# In openai_service.py
from prompts import (
    DOCUMENT_ROUTING_AND_TOPIC_PROMPT,
    TOPIC_AWARE_DOCUMENT_ANALYSIS_PROMPT
)
```

### **Advantages of Current Approach:**

- ✅ Simple and straightforward
- ✅ Version controlled (Git)
- ✅ Easy to review and modify
- ✅ No external dependencies

### **Potential Improvements (Future):**

- Could move to database for dynamic updates
- Could use config files for easier editing
- Could use environment variables for A/B testing
- Current approach is sufficient for current needs

---

## Q4.8: For each major LLM call, please document:

### **LLM Call 1: Document Classification (Routing)**

**Function:** `classify_document(text: str) -> dict`

**File:** `openai_service.py` (Line 21)

**Purpose:** Route documents to INBOX or ARCHIVE and create topics

#### **Prompt Details:**

**System Prompt:**
- **Content**: `DOCUMENT_ROUTING_AND_TOPIC_PROMPT` (from `prompts.py`)
- **Length**: ~260 lines
- **Key Instructions**:
  - Route documents to INBOX or ARCHIVE
  - Create topics for INBOX documents
  - Use fixed channels (TAX, KVK, LEGAL_COMPLIANCE, etc.)
  - Extract urgency, deadline, authority
  - Return JSON with routing decision

**User Prompt:**
- **Content**: Extracted document text (from OCR or native extraction)
- **Format**: Plain text string

**Examples:**
- Included in system prompt (not separate examples)
- Prompt contains extensive examples and rules

#### **Model Configuration:**

- **Model Name**: `gpt-4o` (default, configurable via `OPENAI_MODEL` env var)
- **Temperature**: `0.2` (low temperature for consistent routing decisions)
- **Max Tokens**: Default (not specified, uses model default)
- **Response Format**: `{"type": "json_object"}` (structured JSON output)

#### **Retry/Backoff Logic:**

- **Max Retries**: `3` attempts (`MAX_RETRIES = 3`)
- **Retry Strategy**: Simple retry loop (no exponential backoff)
- **Error Handling**: 
  - Logs warning on each failed attempt
  - Returns default ARCHIVE routing if all attempts fail
  - No exponential backoff delay between retries

**Code:**
```python
for attempt in range(1, MAX_RETRIES + 1):
    try:
        # LLM call
    except Exception as e:
        logging.warning(f"Routing attempt {attempt} failed: {e}")
# After loop: return default ARCHIVE
```

---

### **LLM Call 2: Topic-Aware Document Analysis**

**Function:** `analyze_document(text: str, channel: str, topic_type: str, topic_title: str) -> dict`

**File:** `openai_service.py` (Line 78)

**Purpose:** Analyze INBOX documents with topic context

#### **Prompt Details:**

**System Prompt:**
- **Content**: `TOPIC_AWARE_DOCUMENT_ANALYSIS_PROMPT` (from `prompts.py`)
- **Length**: ~60 lines
- **Key Instructions**:
  - Analyze document meaning and required actions
  - Extract key details (amounts, dates, references)
  - Identify exact actions required
  - Explain risk if ignored
  - Return structured JSON

**User Prompt:**
- **Content**: Context-aware prompt built dynamically
- **Format**: 
  ```
  Channel: {channel}
  Topic Type: {topic_type}
  Topic Title: {topic_title}
  
  Document text to analyze:
  {text}
  
  Provide a detailed analysis with specific actionable items for this topic.
  ```

**Examples:**
- Included in system prompt
- Prompt contains clear instructions and output format

#### **Model Configuration:**

- **Model Name**: `gpt-4o` (default, configurable via `OPENAI_MODEL` env var)
- **Temperature**: `0.2` (low temperature for consistent analysis)
- **Max Tokens**: Default (not specified, uses model default)
- **Response Format**: `{"type": "json_object"}` (structured JSON output)

#### **Retry/Backoff Logic:**

- **Max Retries**: `3` attempts (`MAX_RETRIES = 3`)
- **Retry Strategy**: Simple retry loop (no exponential backoff)
- **Error Handling**: 
  - Logs warning on each failed attempt
  - Returns default analysis structure if all attempts fail
  - No exponential backoff delay between retries

**Code:**
```python
for attempt in range(1, MAX_RETRIES + 1):
    try:
        # LLM call
    except Exception as e:
        logging.warning(f"Topic analysis attempt {attempt} failed: {e}")
# After loop: return default analysis structure
```

---

### **LLM Call 3: Consolidated Channel Analysis (DISABLED)**

**Function:** `analyze_multiple_documents_consolidated(...) -> dict`

**File:** `openai_service.py` (Line 152)

**Purpose:** Analyze multiple documents in a channel together

**Status:** ⚠️ **DISABLED - Not Used in Current Implementation**

#### **Prompt Details:**

**System Prompt:**
- **Content**: Commented out / not imported
- **Note**: Code exists but prompt is not used

**User Prompt:**
- **Content**: Built dynamically with channel info, topics, and combined text
- **Format**: Includes channel, document count, topics, and combined text

#### **Model Configuration:**

- **Model Name**: `gpt-4o`
- **Temperature**: `0.3` (slightly higher for more creative analysis)
- **Max Tokens**: `3000` (explicitly set for longer responses)
- **Response Format**: `{"type": "json_object"}`

#### **Retry/Backoff Logic:**

- **Max Retries**: `3` attempts
- **Retry Strategy**: Simple retry loop
- **Error Handling**: Returns default consolidated analysis structure

**Note:** This function is not called anywhere in the active codebase.

---

## Summary Table: LLM Call Configuration

| LLM Call | Model | Temperature | Max Tokens | Retries | Response Format |
|----------|-------|-------------|------------|---------|-----------------|
| **Document Classification** | `gpt-4o` | `0.2` | Default | 3 | JSON Object |
| **Topic-Aware Analysis** | `gpt-4o` | `0.2` | Default | 3 | JSON Object |
| **Consolidated Analysis** | `gpt-4o` | `0.3` | `3000` | 3 | JSON Object (DISABLED) |

---

## Additional Notes

### **Concurrent LLM Calls:**

- **Semaphore-based Rate Limiting**: Used in `main.py` for parallel processing
- **Dynamic Concurrency**:
  - 1-10 files: 5 concurrent calls
  - 11-20 files: 8 concurrent calls
  - 21-30 files: 12 concurrent calls
- **Purpose**: Avoid OpenAI rate limits while maximizing throughput

### **Error Handling:**

- **Default Fallbacks**: All LLM calls have default return values if all retries fail
- **Classification**: Defaults to ARCHIVE routing
- **Analysis**: Returns default analysis structure with "Ask AI for Guidance" action

### **Cost Considerations:**

- **Pay-per-use**: OpenAI API charges per token
- **Model**: `gpt-4o` (premium model, higher cost than GPT-3.5)
- **Optimization**: Low temperature (0.2) reduces variability and potential retries
- **Concurrency**: Controlled to avoid rate limit penalties

---

**Documentation Status**: Complete for all LLM calls and configuration.


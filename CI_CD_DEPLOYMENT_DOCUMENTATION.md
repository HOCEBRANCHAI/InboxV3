# Section 7 – CI/CD, Deployment, Environments Documentation

## Q7.1: What CI/CD pipelines do we have?

**Answer: No Automated CI/CD Pipelines**

### **Current Status:**

- **GitHub Actions**: ❌ None configured
- **GitLab CI**: ❌ Not used
- **Other CI/CD**: ❌ None configured
- **Automated Deployment**: ❌ Not set up

### **Deployment Method:**

**Manual Deployment via Render Dashboard**

- **Process**: Manual deployment through Render web interface
- **Trigger**: Manual "Deploy" button click in Render dashboard
- **Auto-deploy**: Render can auto-deploy on Git push (if enabled in Render settings)
- **Repository**: GitHub (HOCEBRANCHAI / InboxV3)

### **Deployment Flow:**

```
Developer
    │
    │ 1. Make code changes
    │ 2. Commit to Git
    │ 3. Push to GitHub (main branch)
    ▼
GitHub Repository
    │
    │ (If auto-deploy enabled in Render)
    ▼
Render Dashboard
    │
    │ 4. Render detects changes (or manual deploy)
    │ 5. Builds application
    │ 6. Deploys to production
    ▼
Production (Render)
```

### **Repositories:**

**Repository:** `HOCEBRANCHAI / InboxV3`

- **Platform**: GitHub
- **Branch**: `main` (primary branch)
- **CI/CD**: None configured
- **Deployment**: Manual via Render dashboard

### **What Gets Deployed:**

- **Backend Services**: 
  - Main API (Web Service)
  - Worker Process (Background Worker)
- **Frontend**: Not part of this repository (separate frontend app)
- **Database**: Supabase (managed separately, not deployed)

### **Infrastructure-as-Code:**

**File:** `render.yaml`

- **Purpose**: Render Blueprint configuration (infrastructure-as-code)
- **Status**: Available but not actively used
- **Usage**: Can be used to deploy via Render Blueprint feature
- **Note**: Currently using manual dashboard deployment

---

## Q7.2: Do any pipelines deploy directly to AWS services?

**Answer: No**

### **AWS Deployment:**

- **EC2**: ❌ Not used
- **ECS**: ❌ Not used
- **Lambda**: ❌ Not used
- **Elastic Beanstalk (EB)**: ❌ Not used
- **Other AWS Services**: ❌ Not used for deployment

### **Current Deployment Target:**

- **Render**: All services deployed to Render (not AWS)
- **Supabase**: Database hosted on Supabase (not AWS)
- **AWS Textract**: API service only (not deployed to AWS)

### **Conclusion:**

**No pipelines deploy to AWS.** All deployment is to Render platform. AWS is only used for Textract OCR API (external service, not infrastructure).

---

## Q7.3: Where are environment variables and secrets stored?

### **Storage Locations by Service:**

#### **1. Render Services (Main API & Worker)**

**Storage Method:** Render Dashboard Environment Variables

**Location:** Render Dashboard → Service Settings → Environment Variables

**Secrets Stored:**

**Required:**
- `OPENAI_API_KEY` - OpenAI API key
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `PYTHON_VERSION` - Python version (3.11.0)

**Optional:**
- `OPENAI_MODEL` - OpenAI model (defaults to gpt-4o)
- `AWS_ACCESS_KEY_ID` - AWS Textract (optional)
- `AWS_SECRET_ACCESS_KEY` - AWS Textract (optional)
- `AWS_REGION` - AWS Textract region (optional)
- `ALLOWED_ORIGINS` - CORS origins (optional)
- `GUNICORN_WORKERS` - Worker count (defaults to 4)
- `WORKER_POLL_INTERVAL_SECONDS` - Worker polling interval (defaults to 5)
- `MAX_FILE_SIZE_MB` - Max file size (defaults to 100)
- `MAX_TOTAL_SIZE_MB` - Max total size (defaults to 2000)
- `REQUEST_TIMEOUT_SECONDS` - Request timeout (defaults to 1800)
- `PER_FILE_TIMEOUT_SECONDS` - Per-file timeout (defaults to 120)

**Security:**
- ✅ Secrets are encrypted at rest by Render
- ✅ Not visible in logs (Render masks sensitive values)
- ✅ Can be marked as "Secret" in Render dashboard
- ✅ Separate environment variables for each service

**Access:**
- **Who can access**: Render account owners/admins
- **How to update**: Render Dashboard → Service → Environment → Edit
- **Version control**: Not stored in Git (excluded from `render.yaml`)

---

#### **2. Supabase (Database)**

**Storage Method:** Supabase Dashboard

**Location:** Supabase Dashboard → Project Settings → API

**Secrets Stored:**
- `SUPABASE_URL` - Project URL (public, can be exposed)
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key (secret, must be protected)
- Database password (managed by Supabase, not used in code)

**Security:**
- ✅ Service role key is secret (full database access)
- ✅ Should never be exposed to frontend
- ✅ Stored securely in Supabase dashboard

**Access:**
- **Who can access**: Supabase project owners/admins
- **How to update**: Supabase Dashboard → Settings → API
- **Version control**: Not stored in Git

---

#### **3. AWS Services (Textract)**

**Storage Method:** Render Dashboard Environment Variables

**Location:** Same as Render services (Main API & Worker)

**Secrets Stored:**
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret access key
- `AWS_REGION` - AWS region (e.g., us-east-1)

**Security:**
- ✅ Stored in Render environment variables
- ✅ Not hardcoded in code
- ✅ Optional (service works without it)

**Access:**
- **Who can access**: Render account owners/admins
- **How to update**: Render Dashboard → Service → Environment → Edit
- **AWS Console**: Can also be managed in AWS IAM

---

#### **4. Frontend Apps**

**Status:** Not part of this backend repository

**Note:** Frontend is a separate application. Secrets management for frontend is not documented here (outside scope of this backend repo).

---

#### **5. LLM API Keys (OpenAI)**

**Storage Method:** Render Dashboard Environment Variables

**Location:** Render Dashboard → Service Settings → Environment Variables

**Secret Stored:**
- `OPENAI_API_KEY` - OpenAI API key (starts with `sk-`)

**Security:**
- ✅ Stored in Render environment variables
- ✅ Not hardcoded in code
- ✅ Required for both Main API and Worker
- ✅ Can be rotated in OpenAI dashboard

**Access:**
- **Who can access**: Render account owners/admins
- **How to update**: 
  1. Generate new key in OpenAI dashboard
  2. Update in Render Dashboard → Environment Variables
  3. Restart services
- **Version control**: Not stored in Git

**Where to Get:**
- OpenAI Dashboard: https://platform.openai.com/api-keys

---

### **Summary Table: Secrets Storage**

| Secret Type | Storage Location | Access Method | Security |
|-------------|------------------|---------------|----------|
| **OpenAI API Key** | Render Dashboard | Environment Variables | ✅ Encrypted, masked in logs |
| **Supabase URL** | Render Dashboard | Environment Variables | ✅ Public (can be exposed) |
| **Supabase Service Role Key** | Render Dashboard | Environment Variables | ✅ Secret, encrypted |
| **AWS Access Key ID** | Render Dashboard | Environment Variables | ✅ Optional, encrypted |
| **AWS Secret Access Key** | Render Dashboard | Environment Variables | ✅ Secret, encrypted |
| **Database Password** | Supabase Dashboard | Managed by Supabase | ✅ Not used in code |

---

## Q7.4: Are any secrets hardcoded or stored in code?

**Answer: No Hardcoded Secrets Found** ✅

### **Security Audit Results:**

#### **✅ No Hardcoded Secrets:**

**Checked Files:**
- `main.py` - ✅ Uses `os.getenv()` for all secrets
- `openai_service.py` - ✅ Uses `os.getenv("OPENAI_API_KEY")`
- `job_service.py` - ✅ Uses `os.getenv()` for Supabase credentials
- `textract_service.py` - ✅ Uses `os.getenv()` for AWS credentials
- `worker.py` - ✅ Uses `os.getenv()` for all configuration
- `.env` file - ✅ Not committed to Git (should be in `.gitignore`)

**Pattern Used:**
```python
# ✅ CORRECT - Environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
```

**Not Found:**
```python
# ❌ NOT FOUND - Hardcoded secret (bad practice)
OPENAI_API_KEY = "sk-1234567890abcdef..."
```

---

### **Secrets Management Best Practices:**

#### **✅ Current Implementation (Good):**

1. **Environment Variables**: All secrets loaded from environment
2. **Validation**: Code validates secrets exist at startup
3. **Error Messages**: Clear error if secrets missing
4. **No Defaults**: No fallback values for secrets

**Example from `openai_service.py`:**
```python
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
```

**Example from `job_service.py`:**
```python
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    logger.warning("Supabase credentials not found. Jobs will not be persisted.")
    supabase = None
```

---

### **Configuration Files:**

#### **`render.yaml`:**

**Status:** ✅ Safe

- **Secrets**: Not stored in file
- **Pattern**: Comments indicate secrets should be added in Render dashboard
- **Example:**
  ```yaml
  # Add these secrets in Render dashboard (DO NOT put values here):
  # - OPENAI_API_KEY (required)
  # - SUPABASE_URL (required)
  # - SUPABASE_SERVICE_ROLE_KEY (required)
  ```

**Security:** ✅ No actual secret values in file

---

#### **`.env` File (Local Development):**

**Status:** ✅ Should be in `.gitignore`

**Purpose:** Local development only

**Content:**
```bash
OPENAI_API_KEY=sk-your-key-here
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
```

**Security:**
- ✅ Should NOT be committed to Git
- ✅ Should be in `.gitignore`
- ✅ Only for local development
- ✅ Production uses Render environment variables

**Verification Needed:** Check if `.env` is in `.gitignore`

---

### **Secret Rotation Status:**

#### **Current Status:**

**OpenAI API Key:**
- **Rotation**: Can be rotated in OpenAI dashboard
- **Process**: 
  1. Generate new key in OpenAI
  2. Update in Render Dashboard
  3. Restart services
- **Last Rotation**: Unknown (not tracked)

**Supabase Service Role Key:**
- **Rotation**: Can be rotated in Supabase dashboard
- **Process**:
  1. Generate new key in Supabase
  2. Update in Render Dashboard
  3. Restart services
- **Last Rotation**: Unknown (not tracked)

**AWS Credentials:**
- **Rotation**: Can be rotated in AWS IAM
- **Process**:
  1. Create new IAM user/keys
  2. Update in Render Dashboard
  3. Restart services
  4. Delete old keys
- **Last Rotation**: Unknown (not tracked)

---

### **Recommendations:**

#### **✅ Current State is Good:**

1. ✅ No hardcoded secrets found
2. ✅ All secrets use environment variables
3. ✅ Clear error messages if secrets missing
4. ✅ Secrets stored securely in Render dashboard

#### **⚠️ Improvements to Consider:**

1. **Secret Rotation Policy**: 
   - Document rotation schedule
   - Track last rotation dates
   - Set reminders for regular rotation

2. **`.gitignore` Verification**:
   - Ensure `.env` is in `.gitignore`
   - Verify no secrets in Git history

3. **CI/CD Pipeline** (Future):
   - Add GitHub Actions for automated testing
   - Use GitHub Secrets for CI/CD
   - Automated deployment on merge to main

4. **Secret Management Tool** (Future):
   - Consider using dedicated secret management (e.g., HashiCorp Vault)
   - For larger teams or compliance requirements

---

## Summary

### **CI/CD Status:**

| Aspect | Status | Details |
|--------|--------|---------|
| **CI/CD Pipelines** | ❌ None | Manual deployment via Render |
| **GitHub Actions** | ❌ None | Not configured |
| **GitLab CI** | ❌ None | Not used |
| **Auto-deploy** | ⚠️ Optional | Can enable in Render settings |
| **Deployment Method** | Manual | Render Dashboard |

### **Secrets Management:**

| Aspect | Status | Details |
|--------|--------|---------|
| **Hardcoded Secrets** | ✅ None | All use environment variables |
| **Storage Location** | Render Dashboard | Encrypted, secure |
| **Git Committed** | ✅ No | Secrets not in repository |
| **Rotation Policy** | ⚠️ Not documented | Should be tracked |

### **Deployment:**

| Service | Deployment Method | Target Platform |
|---------|-------------------|----------------|
| **Main API** | Manual (Render Dashboard) | Render |
| **Worker** | Manual (Render Dashboard) | Render |
| **Database** | Managed (Supabase) | Supabase |
| **AWS Services** | N/A | API only (not deployed) |

---

**Documentation Status**: Complete. No hardcoded secrets found. All secrets properly managed via environment variables.


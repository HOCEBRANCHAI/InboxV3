# Using X-User-ID in Swagger UI

## ✅ Fixed! X-User-ID Header Now Appears in Swagger UI

I've updated all endpoints to show the `X-User-ID` header as an input field in Swagger UI.

---

## How to Use in Swagger UI

### Step 1: Open Swagger UI

1. Start your server: `uvicorn main:app --reload`
2. Go to: `http://localhost:8000/docs`
3. You'll see the Swagger UI interface

### Step 2: Find the X-User-ID Field

When you click on any endpoint (like `/classify-documents-async`), you'll now see:

**Parameters section:**
- `files` (file upload)
- **`X-User-ID`** ← **NEW! This field appears here**

### Step 3: Enter Your User ID

1. Click "Try it out" button
2. Scroll down to see the **Parameters** section
3. You'll see an input field labeled **`X-User-ID`**
4. Enter your user ID (e.g., `"user-123"` or `"test-user"`)
5. Upload your files
6. Click "Execute"

---

## Endpoints with X-User-ID Header

### ✅ POST `/classify-documents-async`
- **X-User-ID**: Optional
- **Location**: In Parameters section
- **Example**: `user-123`

### ✅ POST `/analyze-multiple-async`
- **X-User-ID**: Optional
- **Location**: In Parameters section
- **Example**: `user-123`

### ✅ GET `/job/{job_id}`
- **X-User-ID**: Optional (for security verification)
- **Location**: In Parameters section
- **Example**: `user-123`

### ✅ GET `/jobs`
- **X-User-ID**: **Required** ⚠️
- **Location**: In Parameters section
- **Example**: `user-123`
- **Note**: This field is marked as required, so you must fill it

### ✅ DELETE `/job/{job_id}`
- **X-User-ID**: Optional (for security verification)
- **Location**: In Parameters section
- **Example**: `user-123`

---

## Visual Guide

```
┌─────────────────────────────────────────────────┐
│  POST /classify-documents-async                 │
│  [Try it out]                                   │
├─────────────────────────────────────────────────┤
│  Parameters:                                    │
│                                                 │
│  files * (file)                                 │
│  [Choose Files]                                 │
│                                                 │
│  X-User-ID (string)                            │  ← NEW!
│  [user-123        ]                            │  ← Enter here
│                                                 │
│  [Execute]                                      │
└─────────────────────────────────────────────────┘
```

---

## Example: Testing GET /jobs

1. **Click on** `GET /jobs` endpoint
2. **Click** "Try it out"
3. **Fill in**:
   - **X-User-ID**: `test-user-123` ← **Required field**
   - **status** (optional): `completed`
   - **limit** (optional): `10`
4. **Click** "Execute"
5. **See results** with all jobs for that user

---

## Example: Testing POST /classify-documents-async

1. **Click on** `POST /classify-documents-async`
2. **Click** "Try it out"
3. **Fill in**:
   - **files**: Upload your PDF files
   - **X-User-ID**: `my-user-id` ← **Optional but recommended**
4. **Click** "Execute"
5. **Get job_id** in response

---

## Testing Flow

### 1. Create a Job with User ID

```bash
# In Swagger UI:
POST /classify-documents-async
- files: [upload files]
- X-User-ID: test-user-123
→ Returns: {"job_id": "abc-123"}
```

### 2. Check Job Status

```bash
# In Swagger UI:
GET /job/abc-123
- X-User-ID: test-user-123  ← Optional, but verifies ownership
→ Returns: Job status and results
```

### 3. Get All Jobs for User

```bash
# In Swagger UI:
GET /jobs
- X-User-ID: test-user-123  ← Required!
- status: completed (optional)
→ Returns: All jobs for that user
```

---

## Troubleshooting

### If X-User-ID field doesn't appear:

1. **Refresh the page** (`Ctrl+F5` or `Cmd+Shift+R`)
2. **Clear browser cache**
3. **Restart the server**: `uvicorn main:app --reload`
4. **Check browser console** for errors

### If you get "X-User-ID header is required" error:

- Make sure you filled in the **X-User-ID** field in Swagger UI
- For `/jobs` endpoint, it's **required**
- For other endpoints, it's optional but recommended

---

## What Changed?

**Before:**
- ❌ X-User-ID header was not visible in Swagger UI
- ❌ Had to manually add it in "Authorize" or custom headers

**After:**
- ✅ X-User-ID appears as a parameter field
- ✅ Easy to fill in directly
- ✅ Clear indication if required or optional
- ✅ Works for all endpoints

---

## Summary

✅ **X-User-ID header now appears in Swagger UI**  
✅ **Easy to test** - just fill in the field  
✅ **Required for `/jobs` endpoint**  
✅ **Optional for other endpoints** (but recommended)  

**Try it now:**
1. Go to `http://localhost:8000/docs`
2. Click any endpoint
3. Click "Try it out"
4. Look for **X-User-ID** field in Parameters section! 🎉


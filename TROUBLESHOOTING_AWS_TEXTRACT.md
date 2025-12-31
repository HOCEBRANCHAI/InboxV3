# Troubleshooting AWS Textract Connection Error

## Error Message
```
ERROR:root:Unexpected Textract error: Could not connect to the endpoint URL: "https://textract.us-east-1.amazonaws.com/"
```

## What This Means

This error indicates that your application **cannot reach AWS Textract** servers. Your AWS credentials are set, but the network connection is failing.

---

## Common Causes & Solutions

### 1. **Network Connectivity Issue**

**Problem:** Your computer/network cannot reach AWS servers.

**Check:**
```bash
# Test if you can reach AWS
ping textract.us-east-1.amazonaws.com

# Or test HTTPS connection
curl -I https://textract.us-east-1.amazonaws.com/
```

**Solution:**
- Check your internet connection
- If behind a corporate firewall, contact IT to allow AWS endpoints
- Try a different network (mobile hotspot, different WiFi)

---

### 2. **Firewall/Proxy Blocking AWS**

**Problem:** Corporate firewall or proxy is blocking AWS endpoints.

**Solution:**
- Configure proxy settings in your environment:
  ```bash
  export HTTP_PROXY=http://proxy.company.com:8080
  export HTTPS_PROXY=http://proxy.company.com:8080
  ```
- Or configure boto3 to use proxy (see below)

---

### 3. **Invalid AWS Region**

**Problem:** The region you specified doesn't exist or Textract isn't available there.

**Check your `.env` file:**
```bash
AWS_REGION=us-east-1  # Make sure this is correct
```

**Valid regions for Textract:**
- `us-east-1` (N. Virginia) ✅
- `us-east-2` (Ohio) ✅
- `us-west-1` (N. California) ✅
- `us-west-2` (Oregon) ✅
- `eu-west-1` (Ireland) ✅
- `ap-southeast-1` (Singapore) ✅
- `ap-south-1` (Mumbai) ✅

**Solution:** Use a region where Textract is available.

---

### 4. **Invalid or Expired AWS Credentials**

**Problem:** Your AWS credentials are incorrect or expired.

**Test your credentials:**
```bash
# Install AWS CLI if not installed
pip install awscli

# Test credentials
aws sts get-caller-identity --region us-east-1
```

**Solution:**
- Verify credentials in AWS Console
- Generate new access keys if needed
- Update `.env` file with correct credentials

---

### 5. **AWS Textract Service Unavailable**

**Problem:** AWS Textract service might be down in your region.

**Check:**
- Visit https://status.aws.amazon.com/
- Check if Textract is having issues

**Solution:** Try a different region temporarily.

---

## Quick Fixes

### Option 1: Test AWS Connection

Create a test script `test_aws_connection.py`:

```python
import boto3
import os
from dotenv import load_dotenv

load_dotenv()

try:
    client = boto3.client(
        "textract",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION")
    )
    
    # Test connection (this will fail if can't connect)
    print("Testing AWS Textract connection...")
    print(f"Region: {os.getenv('AWS_REGION')}")
    print("✅ AWS client created successfully")
    print("Note: This doesn't test actual API call, just client creation")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Check AWS credentials in .env file")
    print("2. Check internet connection")
    print("3. Check if behind firewall/proxy")
```

Run it:
```bash
python test_aws_connection.py
```

### Option 2: Configure Proxy (If Behind Corporate Firewall)

Update `textract_service.py` to support proxy:

```python
# In textract_service.py, around line 29
import os

# Get proxy from environment if set
proxies = None
if os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY"):
    proxies = {
        "http": os.getenv("HTTP_PROXY"),
        "https": os.getenv("HTTPS_PROXY")
    }

textract_client = boto3.client(
    "textract",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
    config=boto3.session.Config(
        proxies=proxies
    ) if proxies else None
)
```

### Option 3: Use Different Region

Try changing your region in `.env`:

```bash
# Change from us-east-1 to us-west-2
AWS_REGION=us-west-2
```

Then restart your server.

---

## For Local Development

### If You're Testing Locally:

1. **Check if you can access AWS Console:**
   - Go to https://console.aws.amazon.com/
   - If you can't access, it's a network/firewall issue

2. **Test with AWS CLI:**
   ```bash
   aws textract detect-document-text \
     --document Bytes=file.pdf \
     --region us-east-1
   ```

3. **Check Windows Firewall:**
   - Windows might be blocking outbound connections
   - Temporarily disable to test

---

## For Production (Render/Cloud)

If deploying to Render or another cloud service:

1. **Set environment variables in Render dashboard:**
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_REGION`

2. **Check Render logs** for more detailed error messages

3. **Verify network access** from Render's servers to AWS

---

## Temporary Workaround

If you can't fix the connection issue immediately, the service will:
- Try to extract text using `pdfplumber` or `PyPDF2` first (for PDFs)
- Only fall back to Textract if those fail
- Return an error if Textract is needed but unavailable

**For digital PDFs:** Should work fine without Textract
**For scanned PDFs/images:** Will fail if Textract unavailable

---

## Still Having Issues?

1. **Check logs** for more detailed error messages
2. **Verify credentials** are correct in `.env`
3. **Test network connectivity** to AWS
4. **Try different region**
5. **Check AWS account** has Textract service enabled
6. **Verify IAM permissions** - your AWS user needs `textract:DetectDocumentText` permission

---

## Summary

✅ **Credentials are set** (we verified this)
❌ **Network connection failing** (can't reach AWS)

**Next steps:**
1. Test network connectivity
2. Check firewall/proxy settings
3. Try different region
4. Verify AWS account permissions


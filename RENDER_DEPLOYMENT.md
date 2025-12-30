# Render Deployment Guide

This guide will help you deploy the Document Analysis API to Render.

## Prerequisites

1. A Render account (sign up at https://render.com)
2. Your OpenAI API key
3. (Optional) AWS credentials if using Textract OCR functionality

## Deployment Steps

### Option 1: Deploy via Render Dashboard (Recommended)

1. **Connect Your Repository**
   - Go to https://dashboard.render.com
   - Click "New +" → "Web Service"
   - Connect your Git repository (GitHub, GitLab, or Bitbucket)
   - Select the repository containing this codebase

2. **Configure the Service**
   - **Name**: `document-analysis-api` (or your preferred name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn main:app -w ${GUNICORN_WORKERS:-4} -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 3600 --keep-alive 300 --max-requests 1000 --max-requests-jitter 50 --worker-connections 1000 --preload --graceful-timeout 30`
   - **Health Check Path**: `/health`

3. **Set Environment Variables**
   Click "Advanced" → "Add Environment Variable" and add:

   **Required:**
   ```
   OPENAI_API_KEY=sk-your-openai-api-key-here
   ```

   **Optional (with defaults):**
   ```
   OPENAI_MODEL=gpt-4o
   GUNICORN_WORKERS=4
   MAX_FILE_SIZE_MB=100
   MAX_TOTAL_SIZE_MB=2000
   MAX_FILES_PER_REQUEST=30
   REQUEST_TIMEOUT_SECONDS=1800
   PER_FILE_TIMEOUT_SECONDS=120
   ```

   **For AWS Textract (if using OCR):**
   ```
   AWS_ACCESS_KEY_ID=your-aws-access-key
   AWS_SECRET_ACCESS_KEY=your-aws-secret-key
   AWS_REGION=us-east-1
   ```

   **For CORS (Security - Important!):**
   ```
   ALLOWED_ORIGINS=https://yourfrontend.com,https://app.yourfrontend.com
   ```
   ⚠️ **Do NOT use `*` in production!** Set specific domains.

4. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy your application
   - Wait for the build to complete (usually 2-5 minutes)

### Option 2: Deploy via render.yaml

If you prefer infrastructure-as-code:

1. Push your code (including `render.yaml`) to your repository
2. In Render dashboard, select "New +" → "Blueprint"
3. Connect your repository
4. Render will automatically detect and use `render.yaml`
5. Set your secrets (OPENAI_API_KEY, etc.) in the dashboard

## Post-Deployment

### Verify Deployment

1. Check the service logs in Render dashboard
2. Visit your service URL: `https://your-service-name.onrender.com/health`
3. You should see: `{"status": "ok", "timestamp": ...}`

### Test the API

```bash
# Health check
curl https://your-service-name.onrender.com/health

# Test analyze endpoint (replace with your actual file)
curl -X POST https://your-service-name.onrender.com/analyze \
  -F "file=@test.pdf"
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | - | Your OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model to use |
| `PORT` | No | `8000` | Server port (auto-set by Render) |
| `GUNICORN_WORKERS` | No | `4` | Number of worker processes |
| `MAX_FILE_SIZE_MB` | No | `100` | Max file size per upload (MB) |
| `MAX_TOTAL_SIZE_MB` | No | `2000` | Max total size for multiple files (MB) |
| `MAX_FILES_PER_REQUEST` | No | `30` | Max files per request |
| `REQUEST_TIMEOUT_SECONDS` | No | `1800` | Request timeout (30 min) |
| `PER_FILE_TIMEOUT_SECONDS` | No | `120` | Per-file processing timeout |
| `ALLOWED_ORIGINS` | No | `*` | CORS allowed origins (comma-separated) |
| `AWS_ACCESS_KEY_ID` | No* | - | AWS access key (for Textract) |
| `AWS_SECRET_ACCESS_KEY` | No* | - | AWS secret key (for Textract) |
| `AWS_REGION` | No* | - | AWS region (for Textract) |

*Required only if using AWS Textract OCR functionality

## Scaling Considerations

### Render Plans

- **Starter Plan**: Good for development/testing
  - 512 MB RAM
  - 0.1 CPU
  - Spins down after 15 min of inactivity

- **Standard Plan**: Recommended for production
  - 512 MB - 8 GB RAM
  - 0.5 - 4 CPU
  - Always on

- **Pro Plan**: For high traffic
  - More resources
  - Better performance

### Worker Configuration

Adjust `GUNICORN_WORKERS` based on your plan:
- **Starter**: `2-4` workers
- **Standard**: `4-8` workers
- **Pro**: `8-16` workers

Formula: `(2 × CPU cores) + 1`

## Troubleshooting

### Service Won't Start

1. Check logs in Render dashboard
2. Verify all required environment variables are set
3. Ensure `OPENAI_API_KEY` is valid
4. Check that port is using `$PORT` variable

### Timeout Errors

1. Increase `REQUEST_TIMEOUT_SECONDS` if processing large files
2. Check Render service timeout settings
3. Consider upgrading to a plan with more resources

### CORS Errors

1. Set `ALLOWED_ORIGINS` to your frontend domain(s)
2. Don't use `*` in production
3. Format: `https://domain1.com,https://domain2.com` (no spaces)

### Memory Issues

1. Reduce `GUNICORN_WORKERS`
2. Reduce `MAX_FILE_SIZE_MB`
3. Upgrade to a plan with more RAM

## Security Best Practices

1. ✅ **Never commit secrets** - Use Render environment variables
2. ✅ **Restrict CORS** - Set `ALLOWED_ORIGINS` to specific domains
3. ✅ **Use HTTPS** - Render provides this automatically
4. ✅ **Rate Limiting** - Already configured (12/min for analyze, 7/min for analyze-multiple)
5. ✅ **File Size Limits** - Configured via environment variables

## Monitoring

- View logs in Render dashboard
- Set up alerts for service downtime
- Monitor API usage and costs (OpenAI, AWS)

## Cost Estimation

- **Render**: Free tier available, then ~$7/month for starter plan
- **OpenAI**: Pay-per-use (check OpenAI pricing)
- **AWS Textract**: Pay-per-page (if using OCR)

## Support

- Render Docs: https://render.com/docs
- Render Community: https://community.render.com
- Check application logs in Render dashboard for errors


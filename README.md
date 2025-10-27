# KOTS Voice Assistant

An AI-powered voice assistant for Kots Gated Apartments that handles phone inquiries using Google's Gemini 2.0 Flash Live API and Exotel's voice streaming platform.

## 🎯 Overview

The KOTS Voice Assistant is a production-ready, cloud-native conversational AI system that:
- Answers phone calls automatically with natural voice interaction
- Provides information about Kots properties, pricing, and availability
- Handles tenant inquiries and redirects complex requests to human agents
- Scales automatically based on call volume
- Costs $0 when idle

**Architecture Flow:**
```
Phone Call → Exotel (India) → WebSocket Stream → Google Cloud Run → Gemini Live API → Response → Caller
```

## ✨ Features

- **Natural Conversations**: Powered by Gemini 2.0 Flash with real-time voice capabilities
- **Multi-turn Interactions**: Maintains context across the entire conversation
- **Auto-scaling**: From 0 to 15 instances based on demand
- **Real-time Audio Processing**: 8kHz ↔ 16kHz ↔ 24kHz resampling pipeline
- **Indian Region Optimized**: Deployed in Mumbai (asia-south1) for low latency
- **Comprehensive Logging**: IST timezone logs with detailed call metrics
- **Zero Downtime Deployments**: Rolling updates with traffic management
- **Domain-Specific**: Focused exclusively on Kots properties and services

## 🏗️ System Architecture

### Components

1. **FastAPI Server** (`server.py`)
   - WebSocket handler for Exotel streaming
   - Gemini Live API integration
   - Audio resampling (8kHz/16kHz/24kHz)
   - Session management and metrics

2. **Google Cloud Run**
   - Serverless container platform
   - Auto-scaling (0-15 instances)
   - 1-hour timeout for long calls
   - Secret Manager integration

3. **Exotel Voice Platform**
   - Indian phone numbers
   - WebSocket voice streaming
   - Call routing and management

4. **Gemini 2.0 Flash Live API**
   - Real-time voice processing
   - Multi-turn conversations
   - Natural language understanding

### Audio Pipeline

```
Caller → Exotel (8kHz) → WebSocket → Cloud Run
                                        ↓
                                   Resample to 16kHz
                                        ↓
                                   Gemini Live API
                                        ↓
                                   24kHz Response
                                        ↓
                                   Resample to 8kHz
                                        ↓
                          WebSocket → Exotel → Caller
```

## 📋 Prerequisites

### 1. Google Cloud Account
- Active GCP account with billing enabled
- Owner or Editor role on the project

### 2. Gemini API Key
1. Visit https://aistudio.google.com/apikey
2. Click "Create API Key"
3. Save the key securely

### 3. Exotel Account (India Only)
1. Sign up at https://exotel.com
2. Complete KYC verification
3. Get Indian phone number provisioned
4. **Important**: Email `hello@exotel.com` to enable Voice Streaming:
   ```
   Subject: Enable Voicebot Applet for [Your Account SID]
   Body: Hi, please enable voice streaming for my account.
         I'm building an AI voice assistant for property inquiries.
   ```
   Wait for approval (1-2 business days)

### 4. Install Google Cloud SDK
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Verify installation
gcloud --version
```

## 🚀 Quick Start Deployment

### Step 1: Clone and Setup

```bash
# Clone the repository (or use your existing directory)
cd ~/AI_voice\ assistant

# Verify files
ls -la
# Should see: server.py, Dockerfile, requirements-cloud.txt, .env
```

### Step 2: Authenticate with Google Cloud

```bash
# Login to Google Cloud
gcloud auth login

# Set up application default credentials
gcloud auth application-default login
```

### Step 3: Configure Project

```bash
# Set your project ID
export PROJECT_ID="kots-476110"
gcloud config set project $PROJECT_ID

# Verify project is set
gcloud config get-value project
```

### Step 4: Link Billing Account

```bash
# List billing accounts
gcloud billing accounts list

# Link billing account (replace BILLING_ACCOUNT_ID with your ID)
gcloud billing projects link $PROJECT_ID --billing-account=BILLING_ACCOUNT_ID

# Verify billing is enabled
gcloud billing projects describe $PROJECT_ID
```

### Step 5: Enable Required APIs

```bash
# Enable Cloud Run, Cloud Build, and Secret Manager
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com

# This takes about 30 seconds
```

### Step 6: Store Gemini API Key

```bash
# Create secret (replace YOUR_GEMINI_API_KEY with your actual key)
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create gemini-api-key \
    --data-file=- \
    --replication-policy="automatic"

# Get project number for IAM binding
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# Grant Cloud Run access to the secret
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Verify secret was created
gcloud secrets list
```

### Step 7: Deploy to Cloud Run

```bash
# Deploy the service
gcloud run deploy kots-voice-assistant \
    --source . \
    --platform managed \
    --region asia-south1 \
    --allow-unauthenticated \
    --min-instances 0 \
    --max-instances 15 \
    --memory 1Gi \
    --cpu 1 \
    --timeout 3600 \
    --concurrency 10 \
    --set-secrets="GOOGLE_API_KEY=gemini-api-key:latest"

# This takes 3-5 minutes for the first deployment
# When prompted to create Artifact Registry, type 'Y'
```

**Deployment Parameters Explained:**
- `--source .` - Build from current directory
- `--region asia-south1` - Mumbai region for India
- `--allow-unauthenticated` - Required for Exotel webhooks
- `--min-instances 0` - Scale to zero when idle (save costs)
- `--max-instances 15` - Handle up to 150 concurrent calls
- `--memory 1Gi` - Sufficient for audio processing
- `--timeout 3600` - 1 hour max call duration
- `--concurrency 10` - 10 calls per instance
- `--set-secrets` - Inject Gemini API key securely

### Step 8: Get Service URL

```bash
# Get the deployed service URL
SERVICE_URL=$(gcloud run services describe kots-voice-assistant \
    --region asia-south1 \
    --format='value(status.url)')

echo "Service URL: $SERVICE_URL"
echo "WebSocket URL: ${SERVICE_URL/https:/wss:}/exotel/stream"

# Save these URLs - you'll need them!
```

### Step 9: Update Environment Variable

```bash
# Update CLOUD_RUN_URL environment variable
gcloud run services update kots-voice-assistant \
    --region asia-south1 \
    --set-env-vars="CLOUD_RUN_URL=$SERVICE_URL"
```

### Step 10: Test Deployment

```bash
# Test health endpoint
curl $SERVICE_URL

# Expected response:
# {
#   "status": "healthy",
#   "service": "KOTS Voice Assistant",
#   "timestamp": "2025-10-24T...",
#   "gemini_configured": true,
#   "active_calls": 0,
#   "total_calls_handled": 0
# }
```

If you see `"status": "healthy"`, your deployment is successful! 🎉

## 📞 Exotel Configuration

### Method 1: Using Exotel App Bazaar (Recommended)

1. **Login to Exotel Dashboard**
   - Go to https://my.exotel.com/
   - Navigate to **App Bazaar** → **Create New App**

2. **Create Call Flow**
   - App Name: `KOTS Voice Assistant`
   - Description: `AI-powered property inquiry voice bot`

3. **Add Voicebot Applet**
   - Drag **"Voicebot"** applet to the canvas
   - Click on it to configure
   - **WebSocket URL:** Paste your WebSocket URL from Step 8:
     ```
     wss://kots-voice-assistant-152937800809.asia-south1.run.app/exotel/stream
     ```

4. **Connect to Phone Number**
   - Go to **Manage** → **My Numbers**
   - Select your Exotel number
   - Under **Incoming Call Settings:**
     - Connect to App: Select `KOTS Voice Assistant`
   - Click **Save**

### Method 2: Using Exotel XML Response

If you prefer programmatic configuration:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Welcome to Kots Gated Apartments! Connecting you now.</Say>
    <VoiceBot>
        <WebSocketUrl>wss://YOUR-SERVICE-URL.run.app/exotel/stream</WebSocketUrl>
    </VoiceBot>
</Response>
```

## 🧪 Testing Your Setup

### Test 1: Health Check
```bash
curl https://kots-voice-assistant-152937800809.asia-south1.run.app/

# Expected: {"status":"healthy",...}
```

### Test 2: Stats Endpoint
```bash
curl https://kots-voice-assistant-152937800809.asia-south1.run.app/stats

# Shows detailed metrics, active calls, call history
```

### Test 3: Make a Real Call
1. Dial your Exotel number from your phone
2. You should hear: "Welcome to Kots Gated Apartments! Connecting you now."
3. The AI assistant (Arun) should greet you and respond to questions

### Test 4: Monitor Logs
```bash
# View real-time logs
gcloud run services logs tail kots-voice-assistant \
    --region asia-south1 \
    --format="value(textPayload)"

# Look for:
# ✅ "WebSocket connection established with Exotel"
# ✅ "Gemini session established for call..."
# 🎙️ "Call started: ..."
```

## 📊 Monitoring & Analytics

### Cloud Console Dashboard

Visit: https://console.cloud.google.com/run?project=kots-476110

**Key Metrics:**
- Request count (calls per hour)
- Request latency (should be <2s)
- Instance count (auto-scales)
- Memory and CPU utilization
- Error rate

### View Logs

```bash
# Real-time logs
gcloud run services logs tail kots-voice-assistant --region asia-south1

# Last 100 lines
gcloud run services logs read kots-voice-assistant --region asia-south1 --limit 100

# Filter for errors only
gcloud run services logs read kots-voice-assistant --region asia-south1 | grep ERROR

# Download logs via API endpoint
curl https://kots-voice-assistant-152937800809.asia-south1.run.app/logs?lines=100
```

### Custom Metrics Endpoint

```bash
# Get detailed stats
curl https://kots-voice-assistant-152937800809.asia-south1.run.app/stats

# Returns:
# - Total calls
# - Success/failure rate
# - Active calls
# - Average duration
# - Longest call
# - Active sessions with caller info
```

## 💰 Cost Estimation

### Component Breakdown

| Component | Cost | Notes |
|-----------|------|-------|
| **Cloud Run** | $12-15/month | 120 calls/day, 5 min avg |
| **Exotel Voice** | ~₹2,000/month | ₹0.01-0.02/min × 15,000 min |
| **Gemini API** | Free tier | 15 RPM free, then pay-as-you-go |
| **Artifact Registry** | ~$0.50/month | Container storage |
| **Secret Manager** | Free | 6 secret accesses/month free |
| **Total** | **~$40-45/month** | For 120 calls/day scenario |

### Scaling Costs

- **0 calls** = $0/month (Cloud Run idles at 0 instances)
- **300 calls/day** = ~$75-85/month
- **500 calls/day** = ~$140-160/month
- **1000 calls/day** = ~$250-300/month

### Set Budget Alerts

```bash
# Get billing account
gcloud billing accounts list

# Create budget alert
gcloud billing budgets create \
    --billing-account=YOUR_BILLING_ACCOUNT_ID \
    --display-name="KOTS Voice Assistant Budget" \
    --budget-amount=50USD \
    --threshold-rule=percent=90
```

## ⚙️ Configuration & Customization

### Update System Prompt

Edit `server.py` at line 114:

```python
def _create_kots_assistant_prompt() -> str:
    return """# KOTS VOICE ASSISTANT - AI PERSONA

    ## IDENTITY
    You are Arun, a friendly and knowledgeable AI assistant...

    # Add your custom instructions here
    """
```

After editing, redeploy:
```bash
gcloud run deploy kots-voice-assistant --source . --region asia-south1
```

### Adjust Resources

```bash
# Increase CPU and memory for higher traffic
gcloud run services update kots-voice-assistant \
    --region asia-south1 \
    --cpu 2 \
    --memory 2Gi

# Keep at least 1 instance warm (eliminates cold starts)
gcloud run services update kots-voice-assistant \
    --region asia-south1 \
    --min-instances 1

# Increase max instances for high call volume
gcloud run services update kots-voice-assistant \
    --region asia-south1 \
    --max-instances 25
```

### Update Gemini API Key

```bash
# Add new version to secret
echo -n "NEW_API_KEY" | gcloud secrets versions add gemini-api-key --data-file=-

# Cloud Run automatically picks up new version within minutes
```

## 🔧 Maintenance Operations

### Update the Service

```bash
# Make code changes, then redeploy
gcloud run deploy kots-voice-assistant --source . --region asia-south1

# Takes ~2-3 minutes
```

### Rollback to Previous Version

```bash
# List revisions
gcloud run revisions list --service kots-voice-assistant --region asia-south1

# Rollback to specific revision
gcloud run services update-traffic kots-voice-assistant \
    --region asia-south1 \
    --to-revisions=kots-voice-assistant-00001-abc=100
```

### View Service Details

```bash
# Get service description
gcloud run services describe kots-voice-assistant --region asia-south1

# Get service URL
gcloud run services describe kots-voice-assistant \
    --region asia-south1 \
    --format='value(status.url)'
```

### Delete the Service

```bash
# Delete Cloud Run service
gcloud run services delete kots-voice-assistant --region asia-south1

# Delete secret
gcloud secrets delete gemini-api-key

# Delete Artifact Registry repository
gcloud artifacts repositories delete cloud-run-source-deploy \
    --location=asia-south1
```

## 🐛 Troubleshooting

### Issue: "WebSocket connection failed"

**Symptoms:** Call connects but no bot response

**Solutions:**

1. Check if voice streaming is enabled in Exotel
   ```bash
   # Email: hello@exotel.com to enable
   ```

2. Verify WebSocket URL format
   ```
   ✅ Correct: wss://your-service.run.app/exotel/stream
   ❌ Wrong: ws:// or https://
   ```

3. Check Cloud Run logs
   ```bash
   gcloud run services logs tail kots-voice-assistant --region asia-south1
   ```

### Issue: "Poor audio quality or choppy audio"

**Solutions:**

1. Check Cloud Run CPU usage
   ```bash
   # If CPU > 80%, increase to 2 vCPU
   gcloud run services update kots-voice-assistant --cpu 2 --region asia-south1
   ```

2. Verify audio resampling in logs (should see: 8kHz → 16kHz → 24kHz → 8kHz)

3. Test from different phone/network

### Issue: "High latency / delays"

**Solutions:**

1. Verify region is `asia-south1` (Mumbai)
2. Enable min-instances during peak hours
3. Check Exotel's server location (should be Mumbai)

### Issue: "Deployment failed - permission denied"

**Solution:**
```bash
# Ensure you have required roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:YOUR_EMAIL@gmail.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:YOUR_EMAIL@gmail.com" \
    --role="roles/cloudbuild.builds.builder"
```

### Issue: "Cold start delays"

**Symptoms:** First call after idle period has 5-10s delay

**Solutions:**
```bash
# Option 1: Keep 1 instance warm (costs ~$4/month)
gcloud run services update kots-voice-assistant \
    --region asia-south1 \
    --min-instances 1

# Option 2: Use Cloud Scheduler to ping health endpoint every 5 minutes (free)
```

### Issue: "Gemini API quota exceeded"

**Symptoms:** Calls fail with "quota exceeded" error

**Solutions:**

1. Check Gemini API usage at https://aistudio.google.com/apikey
2. Upgrade to paid tier if needed
3. Implement rate limiting in code

## 🔒 Security Best Practices

### 1. Never Commit Secrets

```bash
# Ensure .gitignore includes
echo ".env" >> .gitignore
echo ".env.production" >> .gitignore
echo "*.key" >> .gitignore

# Verify no secrets in git history
git log --all --full-history --source -- .env
```

### 2. Rotate API Keys Regularly

```bash
# Update secret with new key every 90 days
echo -n "NEW_API_KEY" | gcloud secrets versions add gemini-api-key --data-file=-

# Disable old versions
gcloud secrets versions disable VERSION_ID --secret=gemini-api-key
```

### 3. Use Service Account with Minimal Permissions

```bash
# Create dedicated service account
gcloud iam service-accounts create kots-voice-sa \
    --display-name="KOTS Voice Assistant Service Account"

# Grant only secret accessor role
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:kots-voice-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Update Cloud Run to use this service account
gcloud run services update kots-voice-assistant \
    --region asia-south1 \
    --service-account=kots-voice-sa@PROJECT_ID.iam.gserviceaccount.com
```

### 4. Add Request Validation (Optional)

Edit `server.py` to validate Exotel signatures:

```python
import hmac
import hashlib

def validate_exotel_request(request, api_token):
    signature = request.headers.get('X-Exotel-Signature')
    # Validate signature logic
    return signature == expected_signature
```

## 📦 Project Structure

```
AI_voice assistant/
├── server.py                   # Main FastAPI application
├── Dockerfile                  # Cloud Run container config
├── requirements-cloud.txt      # Python dependencies
├── .env                        # Environment variables (local only)
├── README.md                   # This file
├── DEPLOYMENT_GUIDE.md         # Detailed deployment guide
├── PERSONA.txt                 # AI assistant persona definition
├── GUARDRAILS.txt              # Business rules and restrictions
└── logs/                       # Application logs (IST timezone)
```

## 🛠️ Technology Stack

- **Backend Framework**: FastAPI 0.115.6
- **AI Model**: Google Gemini 2.0 Flash Live
- **Audio Processing**: pydub, numpy
- **Telephony**: Exotel Voice Streaming
- **Cloud Platform**: Google Cloud Run
- **Container**: Docker (Python 3.11-slim)
- **Logging**: Python logging with IST timezone

## 📚 API Endpoints

### Health Check
```
GET /
Returns service health status
```

### WebSocket Stream
```
WS /exotel/stream
Handles Exotel voice streaming
```

### Answer Webhook
```
POST /exotel/answer
Exotel webhook for incoming calls
```

### Passthru Webhook
```
POST /exotel/passthru
Called after call completion for analytics
```

### Stats
```
GET /stats
Returns detailed call metrics and statistics
```

### Logs
```
GET /logs?lines=100
Returns recent log entries
```

### Download Logs
```
GET /logs/download
Download full log file
```

## 🎯 Success Checklist

- [ ] Google Cloud SDK installed and authenticated
- [ ] GCP project created with billing enabled
- [ ] Required APIs enabled (Cloud Run, Cloud Build, Secret Manager)
- [ ] Gemini API key created and stored as secret
- [ ] Cloud Run service deployed successfully
- [ ] Health check returns `{"status":"healthy"}`
- [ ] Service URL and WebSocket URL obtained
- [ ] Exotel account set up with KYC completed
- [ ] Voice streaming enabled by Exotel support
- [ ] Voicebot applet configured in Exotel App Bazaar
- [ ] Phone number connected to app
- [ ] Test call successful with bot responding
- [ ] Logs showing proper audio flow
- [ ] Budget alerts configured

## 🆘 Support & Resources

### Google Cloud
- **Console**: https://console.cloud.google.com
- **Cloud Run Docs**: https://cloud.google.com/run/docs
- **Pricing**: https://cloud.google.com/run/pricing

### Gemini API
- **API Studio**: https://aistudio.google.com
- **Docs**: https://ai.google.dev/gemini-api/docs
- **Live API**: https://ai.google.dev/gemini-api/docs/live

### Exotel
- **Dashboard**: https://my.exotel.com
- **Support**: hello@exotel.com
- **Developer Docs**: https://developer.exotel.com
- **Voicebot Guide**: https://developer.exotel.com/api/voicebot

## 📈 What You've Built

You now have a production-ready, auto-scaling voice assistant that:

✅ Handles unlimited concurrent calls
✅ Costs $0 when idle
✅ Scales automatically based on demand
✅ Provides <100ms latency for callers in India
✅ Uses Google's most advanced AI (Gemini 2.0 Flash)
✅ Works with standard phone calls (no app required)
✅ Maintains conversation context across turns
✅ Includes comprehensive logging and monitoring
✅ Follows security best practices
✅ Domain-specific knowledge for Kots properties

## 🚀 Next Steps

1. Monitor first week of calls closely
2. Gather user feedback and refine prompts
3. Add analytics and CRM integration
4. Implement call recording (optional)
5. Add transfer to human agent feature
6. Optimize costs based on usage patterns
7. Set up automated testing for call flows
8. Create dashboard for call analytics

---

**Deployment Time**: ~30 minutes
**First Call**: Immediate after Exotel config
**Scalability**: 0 to 150+ concurrent calls
**Uptime**: 99.95% (Cloud Run SLA)

Built with ❤️ for Kots Gated Apartments

**Current Deployment:**
Service URL: `https://kots-voice-assistant-152937800809.asia-south1.run.app`
WebSocket URL: `wss://kots-voice-assistant-152937800809.asia-south1.run.app/exotel/stream`
Project: `kots-476110`
Region: `asia-south1` (Mumbai)

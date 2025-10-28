# KOTS Voice Assistant

An intelligent AI-powered voice assistant for Kots Gated Apartments that handles phone inquiries using Google's Gemini 2.0 Flash Live API, Exotel's voice streaming platform, and PostgreSQL for caller intelligence.

## 🎯 Overview

The KOTS Voice Assistant is a production-ready, cloud-native conversational AI system that:
- **Identifies callers automatically** using PostgreSQL database (tenants, leads, new callers)
- **Provides dynamic AI responses** based on caller identity
- **Handles tenant service requests** with automatic ticket creation
- **Manages property inquiries** for leads and new callers with real-time data
- **Captures lead information** automatically during conversations
- **Scales automatically** based on call volume (0-15 instances)
- **Costs $0 when idle** with serverless architecture

**Complete System Flow:**
```
Phone Call → Exotel → WebSocket → Cloud Run → Database (Caller ID) →
Dynamic Prompt Selection → Gemini AI → Function Calling (Properties/Tickets/Leads) →
Database Updates → Voice Response → Caller
```

## ✨ Key Features

### 🔍 Intelligent Caller Identification
- **Automatic Database Lookup**: Queries PostgreSQL to identify caller type
- **Phone Number Normalization**: Handles multiple formats (+91, 91, 0, 10-digit)
- **Three Caller Types**:
  - **Tenants**: Existing customers with service needs
  - **Leads**: Previous inquiries in the system
  - **New Callers**: First-time contacts

### 🎭 Dynamic AI Personas
- **Tenant Prompt**: Service-focused, ticket creation, issue resolution
- **Lead Prompt**: Property-focused, follow-up on previous inquiries
- **New Caller Prompt**: Property information, lead capture, welcoming tone

### 🎫 Automatic Ticket Creation (Tenants)
- **Smart Category Matching**: 20+ issue types with keyword detection
- **Database Integration**: Saves to `tenant_tickets` table
- **Complete Ticket Details**:
  - Department assignment (Maintenance, IT, Housekeeping, etc.)
  - Team routing (Electrical, Plumbing, Carpentry, etc.)
  - Classification and priority
  - Tenant information auto-filled
  - Issue description from conversation

### 🏠 Real-Time Property Search
- **KOTS API Integration**: Live property availability data
- **Search by Area**: "Show me flats in Whitefield"
- **Search by BHK**: "I need a 2BHK apartment"
- **Flat Details**: Specific property information lookup
- **Smart Area Mapping**: Converts colloquial names to database IDs

### 📊 Lead Data Collection
- **Automatic Capture**: Saves lead information during property inquiries
- **Saves to `new_lead` table**:
  - Customer name (if provided)
  - Phone number (auto-extracted)
  - Lead status ("new" for new callers, "existing" for known leads)
  - Call metadata (timestamp, call_sid, duration)
- **Smart Triggering**: Only captures when lead/new caller asks about properties

### 🎙️ Conversation Features
- **Natural Voice Conversations**: Powered by Gemini 2.0 Flash Live
- **Multi-turn Context**: Maintains conversation history
- **Function Calling**: AI actively calls backend functions
- **Low Latency**: <100ms response time in India
- **Real-time Audio**: Bidirectional streaming at 8kHz/16kHz/24kHz
- **Voice Activity Detection**: Instant speech recognition

### 📈 Production Ready
- **Auto-scaling**: 0-15 instances, handles 150+ concurrent calls
- **Comprehensive Logging**: IST timezone, detailed call metrics
- **Health Monitoring**: Real-time stats and metrics endpoints
- **Zero Downtime**: Rolling updates with traffic management
- **Security**: Secret Manager for API keys, IAM policies

## 🏗️ System Architecture

### Components

1. **FastAPI Server** (`server.py`)
   - WebSocket handler for Exotel streaming
   - PostgreSQL database integration
   - Caller identification logic
   - Dynamic prompt selection
   - Function calling handlers
   - Audio resampling (8kHz/16kHz/24kHz)
   - Session management and metrics

2. **PostgreSQL Database** (AWS RDS)
   - **services_tenants**: Tenant information
   - **leads**: Existing lead database
   - **tenant_tickets**: Maintenance ticket system
   - **new_lead**: New lead capture from calls
   - Async connection pooling (asyncpg)

3. **KOTS Property API**
   - Real-time property availability
   - Flat details and pricing
   - Area-based property search

4. **Google Cloud Run**
   - Serverless container platform
   - Auto-scaling (0-15 instances)
   - 1-hour timeout for long calls
   - Secret Manager integration

5. **Exotel Voice Platform**
   - Indian phone numbers
   - WebSocket voice streaming
   - Call routing and management

6. **Gemini 2.0 Flash Live API**
   - Real-time voice processing
   - Multi-turn conversations
   - Function calling capabilities
   - Natural language understanding

### Complete System Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    1. INCOMING CALL                         │
│  Caller → Exotel → WebSocket → Cloud Run                   │
│  Phone number extracted from call metadata                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│         2. CALLER IDENTIFICATION (Database Lookup)          │
│                                                             │
│  Query 1: SELECT * FROM services_tenants WHERE phone=...   │
│           → Found? → TENANT                                 │
│                                                             │
│  Query 2: SELECT * FROM leads WHERE phone=...              │
│           → Found? → LEAD                                   │
│                                                             │
│  Not Found? → NEW CALLER                                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│        3. DYNAMIC SYSTEM PROMPT SELECTION                   │
│                                                             │
│  ┌────────────┬──────────────┬─────────────────┐          │
│  │   TENANT   │     LEAD     │   NEW CALLER    │          │
│  ├────────────┼──────────────┼─────────────────┤          │
│  │ Focus:     │ Focus:       │ Focus:          │          │
│  │ • Services │ • Properties │ • Properties    │          │
│  │ • Tickets  │ • Follow-up  │ • Lead capture  │          │
│  │            │              │                 │          │
│  │ Functions: │ Functions:   │ Functions:      │          │
│  │ • Ticket   │ • Property   │ • Property      │          │
│  │   creation │   search     │   search        │          │
│  │            │ • Lead save  │ • Lead save     │          │
│  └────────────┴──────────────┴─────────────────┘          │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│      4. AI CONVERSATION WITH FUNCTION CALLING               │
│                                                             │
│  Gemini AI converses naturally and calls functions:        │
│                                                             │
│  For TENANTS:                                              │
│  • create_maintenance_ticket(issue_type, description)     │
│    → Saves to tenant_tickets table                        │
│                                                             │
│  For LEADS & NEW CALLERS:                                  │
│  • get_properties_by_area(area)                           │
│  • get_flat_details(flat_id)                              │
│  • get_properties_by_bhk(bhk_type)                        │
│  • collect_lead_information(customer_name)                │
│    → Saves to new_lead table                              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│           5. DATABASE UPDATES (Real-time)                   │
│                                                             │
│  TENANT TICKET:                                            │
│  INSERT INTO tenant_tickets                                │
│    (subject, description, department, team_id,             │
│     classification, issue_type, cf_booking_id...)          │
│  → Ticket #123 created                                     │
│                                                             │
│  LEAD CAPTURE:                                             │
│  INSERT INTO new_lead                                      │
│    (customer_name, caller_number, lead_status,             │
│     call_sid, timestamp...)                                │
│  → Lead #456 saved                                         │
└─────────────────────────────────────────────────────────────┘
```

### Audio Pipeline

```
Caller → Exotel (8kHz µ-law) → WebSocket → Cloud Run
                                              ↓
                                         Resample to 16kHz PCM
                                              ↓
                                         Gemini Live API
                                              ↓
                                         24kHz PCM Response
                                              ↓
                                         Resample to 8kHz µ-law
                                              ↓
                            WebSocket → Exotel → Caller
```

## 📦 Database Schema

### services_tenants
```sql
- bookingid (tenant_id)
- account_name
- phone_number
- email
- flat
```

### leads
```sql
- id
- customer_name
- caller_number
```

### tenant_tickets
```sql
- id (auto-increment)
- subject
- description
- department
- department_id
- channel (AI Voice Assistant)
- status
- priority
- email
- phone
- layout, layout_id
- team_id
- classification
- sub_category
- issue_type
- module
- assigned_to
- cf_booking_id (tenant_id)
- cf_flat_unique_id
- cf_last_name
- cf_issue_description
- created_at, updated_at
```

### new_lead
```sql
- id (auto-increment)
- timestamp
- customer_name (nullable)
- lead_status ('new' or 'existing')
- lead_follow_up_status
- caller_number
- call_sid
- call_duration
- created_at, updated_at
```

## 🎯 Function Calling System

### For Tenants

#### create_maintenance_ticket(issue_type, issue_description)
**Issue Types Supported** (20+ categories):
- **Maintenance**: plumbing, electrical, carpenter, appliance, furniture, pest
- **Internet**: wifi_speed, wifi_disconnection, wifi_login
- **Services**: cleanliness, security, garbage, parking_issues
- **Admin**: check_in, check_out, rental_invoices, payment_link
- **Requests**: one_time_housekeeping, car_parking, duplicate_keys, water_can
- **Other**: callback, other_flat_issues

**Keyword Detection**: Smart matching for natural language
- "AC not working" → appliance
- "WiFi slow" → wifi_speed
- "Tap leaking" → plumbing
- "Door handle broken" → carpenter

**Database Mapping**: Automatic assignment
- Issue type → Department (e.g., plumbing → Maintenance)
- Department → Team (e.g., Maintenance → Plumbing Team)
- Team → Team ID for routing

### For Leads & New Callers

#### get_properties_by_area(area_name)
Search properties by location with smart area mapping:
- "Whitefield" → area_id: whitefield
- "Koramangala" → area_id: koramangala
- "HSR Layout" → area_id: hsr-layout
- Returns: Available properties with flat counts

#### get_flat_details(flat_id)
Get specific property information:
- Pricing details
- Amenities
- Availability
- Contact information

#### get_properties_by_bhk(bhk_type)
Search by bedroom count:
- "1bhk", "2bhk", "3bhk", "studio"
- Returns: All matching properties

#### collect_lead_information(customer_name)
Capture lead data after property inquiry:
- **When to call**: After showing property information
- **Auto-filled**: Phone number, lead status, call metadata
- **User-provided**: Customer name (or "Not provided")
- **Saved to**: new_lead table

## 📋 Prerequisites

### 1. Google Cloud Account
- Active GCP account with billing enabled
- Owner or Editor role on the project

### 2. Gemini API Key
1. Visit https://aistudio.google.com/apikey
2. Click "Create API Key"
3. Save the key securely

### 3. PostgreSQL Database (AWS RDS)
- PostgreSQL 17.4 or higher
- Network access from Cloud Run
- Required tables: services_tenants, leads, tenant_tickets, new_lead

### 4. Exotel Account (India Only)
1. Sign up at https://exotel.com
2. Complete KYC verification
3. Get Indian phone number provisioned
4. **Important**: Email `hello@exotel.com` to enable Voice Streaming

### 5. Install Google Cloud SDK
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Verify installation
gcloud --version
```

## 🚀 Quick Start Deployment

### Step 1: Environment Configuration

Create `.env` file with database credentials:

```bash
# Database Configuration
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_PORT=5432
DB_NAME=kots_prod
DB_USER=your_db_user
DB_PASSWORD=your_db_password

# Gemini API Key (for local testing only, use Secret Manager for production)
GOOGLE_API_KEY=your_gemini_api_key
```

### Step 2: Set Up Google Cloud Secrets

```bash
# Set project
export PROJECT_ID="kots-476110"
gcloud config set project $PROJECT_ID

# Store Gemini API Key
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create gemini-api-key \
    --data-file=- --replication-policy="automatic"

# Store Database Credentials
echo -n "your-rds-endpoint" | gcloud secrets create db-host --data-file=- --replication-policy="automatic"
echo -n "5432" | gcloud secrets create db-port --data-file=- --replication-policy="automatic"
echo -n "kots_prod" | gcloud secrets create db-name --data-file=- --replication-policy="automatic"
echo -n "your_db_user" | gcloud secrets create db-user --data-file=- --replication-policy="automatic"
echo -n "your_db_password" | gcloud secrets create db-password --data-file=- --replication-policy="automatic"

# Grant access to Cloud Run
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

for SECRET in gemini-api-key db-host db-port db-name db-user db-password; do
    gcloud secrets add-iam-policy-binding $SECRET \
        --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor"
done
```

### Step 3: Deploy to Cloud Run

```bash
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
    --set-secrets="GOOGLE_API_KEY=gemini-api-key:latest,\
DB_HOST=db-host:latest,\
DB_PORT=db-port:latest,\
DB_NAME=db-name:latest,\
DB_USER=db-user:latest,\
DB_PASSWORD=db-password:latest"
```

### Step 4: Configure Exotel

1. **Get WebSocket URL**:
   ```bash
   SERVICE_URL=$(gcloud run services describe kots-voice-assistant \
       --region asia-south1 --format='value(status.url)')
   echo "WebSocket URL: ${SERVICE_URL/https:/wss:}/exotel/stream"
   ```

2. **Configure in Exotel App Bazaar**:
   - Login → App Bazaar → Create New App
   - Add "Voicebot" applet
   - Paste WebSocket URL
   - Connect to phone number

### Step 5: Test the System

```bash
# Health check
curl $SERVICE_URL

# Expected response shows database connection status:
# {
#   "status": "healthy",
#   "service": "KOTS Voice Assistant",
#   "gemini_configured": true,
#   "database_connected": true,
#   "active_calls": 0
# }
```

## 🧪 Testing Different Caller Types

### Test as Tenant
1. Call from a phone number in `services_tenants` table
2. AI greets: "Hi, I am an AI assistant from KOTS. How can I help you today?"
3. Say: "My AC is not cooling"
4. AI creates ticket and confirms: "I've created maintenance ticket #123"
5. Check `tenant_tickets` table for new entry

### Test as Lead
1. Call from a phone number in `leads` table
2. AI uses lead-focused greeting
3. Say: "Show me properties in Whitefield"
4. AI calls `get_properties_by_area()` and lists properties
5. AI asks for name and calls `collect_lead_information()`
6. Check `new_lead` table for entry with lead_status='existing'

### Test as New Caller
1. Call from unknown phone number
2. AI uses welcoming new caller greeting
3. Say: "I'm looking for a 2BHK"
4. AI calls `get_properties_by_bhk()` and shows options
5. AI collects name and saves lead
6. Check `new_lead` table for entry with lead_status='new'

## 📊 Monitoring & Analytics

### Real-Time Logs

```bash
# View live logs
gcloud run services logs tail kots-voice-assistant --region asia-south1

# Key log entries:
# ✅ "Database connection pool created successfully"
# ✅ "TENANT identified: John Doe (ID: T12345)"
# ✅ "LEAD identified: Jane Smith (ID: L67890)"
# 📞 "NEW CALLER identified: 09876543210"
# ✅ "Ticket #123 created successfully"
# ✅ "Lead #456 saved successfully!"
```

### Stats Endpoint

```bash
curl https://YOUR-SERVICE-URL/stats

# Returns:
# - Total calls by caller type
# - Active sessions
# - Database query stats
# - Function call counts
# - Average call duration
```

### Database Verification

```sql
-- Check recent tickets
SELECT id, issue_type, cf_booking_id, created_at
FROM tenant_tickets
ORDER BY created_at DESC
LIMIT 10;

-- Check new leads
SELECT id, customer_name, caller_number, lead_status, created_at
FROM new_lead
ORDER BY created_at DESC
LIMIT 10;

-- Verify caller identification
SELECT COUNT(*) FROM services_tenants;  -- Total tenants
SELECT COUNT(*) FROM leads;              -- Total leads
```

## ⚙️ Configuration Files

### prompts.py
Contains three system prompts:
- `create_tenant_prompt(tenant_data)` - For registered tenants
- `create_lead_prompt(lead_data)` - For existing leads
- `create_new_caller_prompt()` - For new callers

Each includes:
- Conversation rules (greeting only once, natural responses)
- Function calling instructions
- Role-specific capabilities
- Response guidelines

### ticket_categories.py
Ticket categorization system with:
- 20+ issue types with keywords
- Department mapping
- Team assignment
- Classification rules

### database.py
Database operations:
- `init_db_pool()` - Connection pool setup
- `identify_caller(phone_number)` - Caller type detection
- `save_ticket()` - Ticket creation
- `save_lead_information()` - Lead capture
- `normalize_phone_number()` - Format handling

## 💰 Cost Estimation

### Monthly Costs (120 calls/day scenario)

| Component | Cost | Details |
|-----------|------|---------|
| **Cloud Run** | $12-15 | Auto-scales, 5 min avg call |
| **Exotel Voice** | ₹2,000 (~$25) | ₹0.01-0.02/min |
| **Gemini API** | Free-$10 | 15 RPM free tier |
| **AWS RDS** | $30-50 | PostgreSQL db.t3.micro |
| **Secret Manager** | Free | <10k accesses/month |
| **Total** | **$70-100/month** | ~3,600 calls/month |

### Cost Optimization
- Scales to zero when idle (no minimum cost)
- Database connection pooling (efficient)
- Async operations (lower CPU usage)
- Smart caching (reduced API calls)

## 🔒 Security Best Practices

### 1. Database Security
- ✅ SSL/TLS encryption for database connections
- ✅ Credentials stored in Secret Manager
- ✅ Connection pooling with timeout (60s)
- ✅ Prepared statements (SQL injection prevention)

### 2. API Key Management
- ✅ Never commit keys to git (.env in .gitignore)
- ✅ Use Secret Manager for production
- ✅ Rotate keys every 90 days
- ✅ Separate keys for dev/staging/prod

### 3. Network Security
- ✅ HTTPS/WSS only
- ✅ Cloud Run service identity
- ✅ VPC connector for database access (optional)
- ✅ Firewall rules on RDS

### 4. Data Privacy
- ✅ Minimal data collection
- ✅ Phone numbers normalized and hashed (if needed)
- ✅ Conversation logs with retention policy
- ✅ GDPR-compliant data handling

## 🐛 Troubleshooting

### Database Connection Failed

**Symptom**: "Database pool not initialized" errors

**Solutions**:
1. Verify database credentials in Secret Manager
2. Check RDS security group allows Cloud Run IP ranges
3. Test connection: `psql -h HOST -U USER -d DB_NAME`
4. Review logs: `gcloud run services logs tail`

### Caller Not Identified Correctly

**Symptom**: Known caller treated as new caller

**Solutions**:
1. Check phone number format in database
2. Test normalization: Call with different formats
3. Verify query: `SELECT * FROM services_tenants WHERE phone_number = '+919876543210'`
4. Check logs for "Phone number variations" debug info

### Ticket Not Created

**Symptom**: Gemini says ticket created but database is empty

**Solutions**:
1. Check tenant_tickets table exists with correct schema
2. Verify AI is calling `create_maintenance_ticket()` function
3. Review logs for "🎯 TOOL CALL DETECTED" entries
4. Test issue type keyword matching in ticket_categories.py

### Lead Data Not Saved

**Symptom**: Property search works but no lead captured

**Solutions**:
1. Verify AI called `collect_lead_information()` after property search
2. Check new_lead table schema matches database.py
3. Review prompt instructions for lead collection flow
4. Test with explicit: "Save my details as a lead"

### Function Not Called

**Symptom**: AI responds but doesn't execute functions

**Solutions**:
1. Check function declarations in server.py
2. Verify function is included in tools list
3. Review Gemini API logs for function call requests
4. Test with explicit function trigger phrases

## 📦 Project Structure

```
AI_voice assistant/
├── server.py                   # Main FastAPI application
├── database.py                 # PostgreSQL integration
├── prompts.py                  # Dynamic system prompts
├── ticket_categories.py        # Ticket categorization
├── Dockerfile                  # Cloud Run container
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (local)
├── .gitignore                  # Git exclusions
├── README.md                   # This file
├── SYSTEM FLOW - KOTS VOICE.txt # Flow diagram
├── PERSONA.txt                 # AI personality definition
├── GUARDRAILS.txt              # Business rules
└── logs/                       # Application logs (IST)
    └── voice_assistant_YYYYMMDD.log
```

## 🛠️ Technology Stack

- **Backend**: FastAPI 0.115.6
- **AI Model**: Google Gemini 2.0 Flash Live
- **Database**: PostgreSQL 17.4 (asyncpg)
- **Audio**: pydub, numpy, audioop
- **Telephony**: Exotel Voice Streaming
- **Cloud**: Google Cloud Run
- **Container**: Docker (Python 3.11-slim)
- **Logging**: Python logging with IST timezone

## 📚 API Endpoints

### Health & Monitoring

```
GET /
Health check with database status

GET /stats
Detailed call statistics and metrics

GET /logs?lines=100
Recent log entries

GET /logs/download
Download full log file
```

### Exotel Integration

```
WS /exotel/stream
WebSocket for voice streaming

POST /exotel/answer
Incoming call webhook

POST /exotel/passthru
Post-call analytics webhook
```

## 🎯 Success Metrics

### Technical KPIs
- ✅ 99.5%+ uptime
- ✅ <100ms response latency
- ✅ 100% caller identification accuracy
- ✅ <2% function call failure rate
- ✅ Zero data loss on tickets/leads

### Business KPIs
- 📊 Calls handled per day
- 📊 Tenant tickets created
- 📊 Leads captured
- 📊 Call duration (efficiency)
- 📊 Caller type distribution

## 🚀 Future Enhancements

### Planned Features
- [ ] Conversation transcription logging (requires model upgrade)
- [ ] WhatsApp integration for ticket updates
- [ ] Email notifications on ticket creation
- [ ] Call recording and playback
- [ ] Sentiment analysis
- [ ] Multi-language support (Hindi, Kannada)
- [ ] Transfer to human agent
- [ ] Appointment scheduling
- [ ] Payment reminders
- [ ] Property tour booking

### Model Upgrade Path
For transcription support, upgrade to:
- **Model**: `gemini-2.5-flash-native-audio-preview-09-2025`
- **SDK**: `google-genai>=1.43.0`
- **Benefits**: Improved function calling, transcription logging, better speech handling

## 📈 What You've Built

You now have a production-ready, intelligent voice assistant that:

✅ **Automatically identifies** tenants, leads, and new callers via database
✅ **Dynamically adapts** conversation based on caller identity
✅ **Creates tickets** for tenant issues with full categorization
✅ **Searches properties** with real-time availability data
✅ **Captures leads** automatically during property inquiries
✅ **Scales infinitely** from 0 to 150+ concurrent calls
✅ **Costs $0 when idle** with serverless architecture
✅ **Maintains context** across entire conversation
✅ **Logs everything** with IST timezone and detailed metrics
✅ **Integrates seamlessly** with existing database and APIs
✅ **Works instantly** - no app download required for callers

## 🆘 Support & Resources

### Google Cloud
- **Console**: https://console.cloud.google.com
- **Cloud Run**: https://cloud.google.com/run/docs

### Gemini API
- **API Studio**: https://aistudio.google.com
- **Live API Docs**: https://ai.google.dev/gemini-api/docs/live

### Exotel
- **Dashboard**: https://my.exotel.com
- **Support**: hello@exotel.com

### Database
- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **asyncpg**: https://magicstack.github.io/asyncpg/

---

**Current Deployment:**
- Service URL: `https://kots-voice-assistant-152937800809.asia-south1.run.app`
- WebSocket: `wss://kots-voice-assistant-152937800809.asia-south1.run.app/exotel/stream`
- Project: `kots-476110`
- Region: `asia-south1` (Mumbai)
- Database: PostgreSQL 17.4 (AWS RDS)

Built with ❤️ for Kots Gated Apartments

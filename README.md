# Microsoft Graph Email Processing Application

A production-grade email automation system that intelligently processes incoming emails using Microsoft Graph API and LLM technology to classify, summarize conversations, and generate draft replies.

## Overview

This application automates email handling by:
1. Subscribing to Microsoft Graph API for real-time email notifications
2. Processing incoming emails with HTML content cleanup
3. Using LLM to classify emails as actionable or non-actionable
4. Fetching previous conversation history for actionable emails
5. Generating contextual draft replies based on conversation history
6. Proofreading and redrafting responses if needed
7. Saving approved drafts to Outlook

## Features

- **Real-time Email Processing**: Webhook-based email notifications via Microsoft Graph API
- **Intelligent Classification**: LLM-powered email classification (RESPOND/SKIP)
- **Conversation Context**: Automatic retrieval and summarization of email threads
- **Draft Generation**: AI-generated contextual email responses
- **Quality Control**: Automated proofreading and redrafting mechanism
- **Multi-Auth Support**: Both delegated (personal) and corporate authentication
- **Production Logging**: Comprehensive logging for monitoring and debugging

## Requirements

### Core Dependencies
- Python 3.8+
- ngrok (for webhook tunneling)
- Microsoft Azure App Registration

### Python Packages
```
aiofiles
fastapi
uvicorn
python-dotenv
requests
aiohttp
msal
beautifulsoup4
langchain-google-genai
pydantic
```

### External Services
- **Microsoft Graph API**: Email access and management
- **Google AI Studio**: LLM for email classification and draft generation
- **ngrok**: Secure tunneling for webhook endpoints

## Setup and Configuration

### 1. Azure App Registration

#### For Delegated Authentication (Personal Accounts)
- Register an app in Azure Portal
- Configure redirect URI: `http://localhost:8080/auth/callback`
- Required permissions: `User.Read`, `Mail.ReadWrite`, `Mail.Send`, `MailboxSettings.ReadWrite`

#### For Corporate Authentication
- Register an app with corporate tenant
- Configure application permissions as needed
- Obtain tenant ID, client ID, and client secret

### 2. Environment Variables

Create a `.env` file with the following variables:

```env
# Authentication Type
GRAPH_SERVICE_TYPE=DELEGATED  # or CORPORATE

# For Delegated Authentication
AZURE_APP_ID=your_azure_app_id
AZURE_APP_SECRET=your_azure_app_secret
MAILBOX_NAME=your_email@example.com

# For Corporate Authentication
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
TENANT_ID=your_tenant_id
USER_EMAIL=user@company.com

# LLM Configuration
GOOGLE_AI_STUDIO_API_KEY=your_google_ai_api_key
```

### 3. Installation

```bash
# Clone the repository
git clone <repository-url>
cd email_helpers

# Install dependencies
pip install -r requirements.txt
```

## Running the Application

### Step 1: Start ngrok
```bash
# Start ngrok tunnel on port 8080
ngrok http 8080
```
Note the public HTTPS URL provided by ngrok (e.g., `https://abc123.ngrok.io`)

### Step 2: Run the Application
```bash
python email_app.py
```
The application will start on `http://localhost:8080`

### Step 3: Create Email Subscription

Due to ngrok latency constraints, subscription creation must be done manually via API call:

```bash
# Create subscription using your ngrok URL
curl -X POST "https://graph.microsoft.com/v1.0/subscriptions" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "changeType": "created",
    "notificationUrl": "https://YOUR_NGROK_URL.ngrok.io/api/graph-notifications",
    "resource": "me/mailfolders('inbox')/messages",
    "expirationDateTime": "2024-12-31T23:59:59Z"
  }'
```

### Step 4: Automatic Processing

Once configured, the application automatically:
- Receives webhook notifications for new emails
- Processes emails in the background
- Creates draft replies for actionable emails
- Logs all activities for monitoring

## API Endpoints

- `GET /api/health` - Health check endpoint
- `POST /api/graph-notifications` - Webhook endpoint for email notifications
- `GET /api/list-subscriptions` - List active Graph API subscriptions
- `DELETE /api/delete-subscription` - Remove existing subscriptions

## Authentication Support

### Delegated Authentication
- Suitable for personal Microsoft accounts
- Uses OAuth2 authorization code flow
- Requires user consent for permissions

### Corporate Authentication
- For enterprise/organizational accounts
- Uses application-only authentication
- Requires admin consent for tenant-wide permissions

## Architecture

```
Email Notification → FastAPI Webhook → Background Processing
    ↓
Email Classification (LLM) → Actionable Email Detection
    ↓
Conversation History Retrieval → Context Summarization
    ↓
Draft Generation (LLM) → Proofreading → Draft Saving
```

## Future Improvements

### Message Queue Integration
- **SQS/Redis/RabbitMQ**: Replace background tasks with proper message broker services for better scalability and reliability
- **Celery Workers**: Implement distributed task processing for handling high email volumes

### Database Integration
- **Conversation History Storage**: Persist email threads and conversation summaries in database
- **Automatic Context Prefetching**: Pre-load conversation context for faster response generation
- **Analytics and Reporting**: Track email processing metrics and response rates

### Enhanced Authentication
- **Pipedream OAuth**: Implement more robust OAuth flow management
- **Token Refresh Automation**: Automated token lifecycle management
- **Multi-tenant Support**: Support multiple user accounts simultaneously

### Monitoring and Observability
- **Application Performance Monitoring**: Integration with APM tools
- **Email Processing Metrics**: Track classification accuracy and response quality
- **Alert Systems**: Notification for processing failures or quota limits

## Security Considerations

- All sensitive credentials are environment-based
- HTTPS-only webhook endpoints via ngrok
- Token-based authentication with Microsoft Graph
- Input validation and sanitization for all email content

## Monitoring and Logs

Application logs are stored in `logs/app.log` and include:
- Email processing status
- LLM classification results
- Draft generation success/failure
- API request/response details
- Error tracking and debugging information

## Production Deployment

For production environments:
- Replace ngrok with proper reverse proxy (nginx, load balancer)
- Implement proper certificate management
- Use environment-specific configuration
- Set up monitoring and alerting systems
- Consider implementing rate limiting and throttling

## Troubleshooting

### Common Issues
1. **Subscription Creation Fails**: Check ngrok URL accessibility and token validity
2. **LLM Classification Errors**: Verify Google AI Studio API key and quota
3. **Email Fetching Issues**: Confirm Graph API permissions and authentication
4. **Background Task Failures**: Check application logs for detailed error messages

### Debug Mode
Enable debug logging by setting log level to `DEBUG` in `utils.py`

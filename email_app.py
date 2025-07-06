import os
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from utils import logging, SubscriptionRequest, SubscriptionDeleteRequest
from services.ms_graph_services import MSGraphAuthDelegated, MSGraphAuthCorporate, MSGraphClient
from services.email_listener import process_email_notification

load_dotenv(override=True)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Only for Dev
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)

# Environment variables
GRAPH_SERVICE_TYPE = os.environ.get("GRAPH_SERVICE_TYPE", "DELEGATED").strip().upper()

# Initialize services based on service type
if GRAPH_SERVICE_TYPE == "DELEGATED":
    APPLICATION_ID = os.environ.get("AZURE_APP_ID")
    CLIENT_SECRET = os.environ.get("AZURE_APP_SECRET")
    SCOPES = ['User.Read', 'Mail.ReadWrite', 'Mail.Send', 'MailboxSettings.ReadWrite']
    USER_EMAIL = os.environ.get("MAILBOX_NAME")
    USER_ID = "me"
    
    if not APPLICATION_ID or not CLIENT_SECRET:
        logger.error("Missing Azure app credentials for delegated flow")
        raise ValueError("Azure app credentials required")
    
    auth = MSGraphAuthDelegated(
        application_id=APPLICATION_ID, 
        client_secret=CLIENT_SECRET, 
        scopes=SCOPES
    )
else:
    CLIENT_ID = os.environ.get("CLIENT_ID")
    CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
    TENANT_ID = os.environ.get("TENANT_ID") 
    USER_EMAIL = os.environ.get("USER_EMAIL")
    USER_ID = f"users/{USER_EMAIL}"
    
    if not all([CLIENT_ID, CLIENT_SECRET, TENANT_ID, USER_EMAIL]):
        logger.error("Missing corporate account credentials")
        raise ValueError("Corporate account credentials required")
    
    auth = MSGraphAuthCorporate(
        client_id=CLIENT_ID, 
        client_secret=CLIENT_SECRET, 
        tenant_id=TENANT_ID
    )

graph_client = MSGraphClient(auth)

@app.get("/api/health")
async def health() -> dict:
    """Health check endpoint"""
    return {"status": "success", "time": datetime.now().isoformat()}

@app.post("/api/graph-notifications")
async def process_graph_notifications(request: Request, background_tasks: BackgroundTasks) -> Response:
    """
    Handle Graph API notifications for new emails
    """
    try:
        logger.info("Processing Graph API notifications")
        validation_token = request.query_params.get("validationToken")
        
        if validation_token:
            logger.info("Subscription validation token received")
            return Response(
                content=validation_token,
                media_type="text/plain",
                headers={"Cache-Control": "no-store", "Pragma": "no-cache"}
            )
        
        try:
            payload = await request.json()
            logger.info("Received notification payload")
        except Exception as e:
            logger.error(f"Failed to parse JSON payload: {str(e)}")
            return Response(status_code=400, content="Invalid JSON payload")
    
        # TODO: this cn cause issue if somethibg breaks or one requests takes huge time. Better approach is to use SQS, Celery or similar
        background_tasks.add_task(process_email_notification, payload, graph_client, USER_ID)
        return Response(status_code=202, content="Notification received")
        
    except Exception as e:
        logger.error(f"Error in notifications endpoint: {str(e)}")
        return Response(status_code=500, content=f"Server error: {str(e)}")

@app.get("/api/list-subscriptions")
async def list_subscriptions() -> dict:
    """
    List all Graph API subscriptions
    """
    try:
        subscriptions = await graph_client.list_all_subscriptions()
        return {"subscriptions": subscriptions}
    except Exception as e:
        logger.error(f"Error listing subscriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing subscriptions: {str(e)}")


# ------------------ NOTE: Due to the redirect ngrok tunnel, we're facing latency issue for this endpoint and subscription fails. We need to do it manually || Keeping this endpoint in comments for reference----------
# @app.post("/api/create-subscription", status_code=201)
# async def create_subscription(request: SubscriptionRequest):
#     """
#     Create MS Graph subscription for email notifications
#     """
#     try:
#         result = graph_client.subscribe_to_notifications(
#             notification_accep_url=request.notification_url,
#             user_id=USER_ID,
#             folder=request.folder
#         )

@app.delete("/api/delete-subscription")
async def delete_subscription(request: SubscriptionDeleteRequest) -> dict:
    """
    Delete an existing MS Graph subscription
    """
    try:
        result = await graph_client.delete_subscription(
            subscription_id=request.subscription_id
        )
        
        return {
           "response":result
        }
    except Exception as e:
        logger.error(f"Error deleting subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting subscription: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("email_app:app", host="0.0.0.0", port=8080, reload=True) # 8080 we have ngrok running

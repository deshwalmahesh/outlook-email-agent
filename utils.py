import sys, os, logging
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import re
from bs4 import BeautifulSoup
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv(override=True)

# Setup centralized logging - only configure once
def setup_logging():
    """Setup centralized logging configuration"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Only configure if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f"{log_dir}/app.log"),
                logging.StreamHandler()
            ]
        )

# Initialize logging once
setup_logging()

def get_llm():
    """
    Initialize and return LLM instance
    
    Returns:
        ChatGoogleGenerativeAI: Initialized LLM instance
        
    Raises:
        Exception: If LLM initialization fails
    """
    logger = logging.getLogger(__name__)
    
    try:
        model_name = os.environ.get("GEMINI_MODEL_NAME")
        api_key = os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
        
        if not api_key:
            raise ValueError("GOOGLE_AI_STUDIO_API_KEY key missing")
        if not model_name:
            raise ValueError("GEMINI_MODEL_NAME key missing")
        
        llm = ChatGoogleGenerativeAI(model=model_name, api_key=api_key)
        return llm
        
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {str(e)}")
        raise


def clean_html(html_content: str) -> str:
    """
    Strip all HTML tags from email content using BeautifulSoup
    
    Args:
        html_content: HTML content to clean
        
    Returns:
        str: Cleaned text content
    """
    if not html_content:
        return ""
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error cleaning HTML content: {str(e)}")
        return html_content

# --------------Schemas ---------------

# Email data models
class EmailData(BaseModel):
    subject: str = ""
    body: str = ""
    sender: Optional[str] = ""
    recipients: Optional[List[str]] = []
    thread_id: Optional[str] = None
    internetMessageId: Optional[str] = None


class ClassificationEmail(BaseModel):
    """
    Whether Email should be responded to or not
    """
    classification: Literal["RESPOND", "SKIP"] = Field(
        description="Whether the incoming should be responded to or not. It must output 'SKIP` if it is Spam, Promotional, newsletter, marketing, product sales etc."
    )

class ClassificationResponse(BaseModel):
    """
    Whether Email draft is sendable to user as a response or not
    """
    classification: Literal["SENDABLE", "SKIP"] = Field(
        description="Whether email draft we created is SENDABLE to user or should be skipped. Email is SENDABLE if it is according to the user criteria, tone and answers the incoming email"
    )

class FirstRunRequest(BaseModel):
    email_data: EmailData


class FeedbackRequest(BaseModel):
    feedback_type: str
    draft_text: str
    thread_id: str
    email_data: Optional[Dict[str, Any]] = None


class EmailPayload(BaseModel):
    message_id: str


class SearchRequest(BaseModel):
    internet_message_id: str


class SubscriptionRequest(BaseModel):
    notification_url: str
    folder: Optional[str] = "Inbox"


class SubscriptionRenewRequest(BaseModel):
    subscription_id: str
    extension_days: Optional[float] = 6.99


class SubscriptionDeleteRequest(BaseModel):
    subscription_id: str


class UpdateTagsRequest(BaseModel):
    internet_message_id: str
    tags: List[str]

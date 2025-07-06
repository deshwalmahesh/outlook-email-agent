"""
Add your system prompts for classification, proofreading and draft creation. For example which emails should be replied to criteri for proofreading and evaluation of draft replies and how to create a draft reply [salutation, namedesignation, company etc ]
Add as much details as possible in each of the system prompts ake the LLM about the usecase and conditions
"""
from typing import Optional
from utils import get_llm, logging, ClassificationEmail, ClassificationResponse

logger = logging.getLogger(__name__)

try:
    llm = get_llm()
except Exception as e:
    logger.error(f"Failed to initialize LLM: {str(e)}")
    raise


def can_respond_to_email(subject: str, body: str) -> bool:
    """
    Classify email using LLM to determine if it is RESPOND or SKIP.
    
    Args:
        subject: Email subject (already cleaned of HTML)
        body: Email body (already cleaned of HTML)
        
    Returns:
        bool: True if the email requires a response, False if it should be skipped
        
    Raises:
        Exception: If LLM classification fails
    """
    if not subject and not body:
        logger.warning("Empty subject and body provided for classification")
        return False
        
    try:
        system_prompt = """You are an intelligent email classifier. Your task is to analyze incoming emails and determine if they require a response (RESPOND) or should be skipped (SKIP).
        
        RESPOND to:
        - Business-related communications
        - Personal messages requiring attention
        - Questions or requests for information
        - Follow-ups on ongoing conversations or projects
        - Important notifications that need acknowledgment
        
        SKIP:
        - Promotional and marketing emails
        - Newsletters and subscriptions
        - Spam or suspicious content
        - Automated notifications that don't require action
        - Sales pitches and advertisements
        - Mass emails not specifically addressed to the recipient
        
        Analyze both the subject line and body content to make your determination."""
        
        user_prompt = f"Subject: {subject}\n\nBody: {body}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        result = llm.with_structured_output(ClassificationEmail).invoke(messages).classification
        return result == "RESPOND"
        
    except Exception as e:
        logger.error(f"Error in email classification: {str(e)}")
        return False

def can_send_reply(email_subject: str, email_body: str, draft_response: str) -> bool:
    """
    Proofread draft using LLM to ensure it is worth saving to draft.
    
    Args:
        email_subject: Subject of the original email
        email_body: Body of the original email
        draft_response: Draft response to be validated
        
    Returns:
        bool: True if the draft is appropriate to send, False otherwise
        
    Raises:
        Exception: If LLM validation fails
    """
    if not all([email_subject, email_body, draft_response]):
        logger.warning("Missing required parameters for reply validation")
        return False
        
    try:
        system_prompt = """You are an expert email proofreader. Your task is to evaluate if a draft email response is appropriate to send (SENDABLE) or should be skipped (SKIP).
        
        A SENDABLE response must:
        - Directly address the content and questions from the original email
        - Be professional, courteous, and maintain appropriate tone
        - Contain relevant information that responds to the sender's needs
        - Be free of major grammatical or spelling errors
        - Be logically structured and easy to understand
        
        A response should be marked SKIP if it:
        - Is off-topic or unrelated to the original email
        - Contains inappropriate language or tone
        - Fails to address the main points of the original email
        - Is confusing, incomplete, or incoherent
        - Contains factually incorrect information
        
        Carefully compare the draft response against the original email to ensure it properly addresses the sender's concerns."""
        
        user_prompt = f"Given the initial incoming email #Subject:{email_subject}\n#Body:\n{email_body}\n\nProofread the following response:\n{draft_response}\n\nIs this response SENDABLE or should it be SKIPPED?"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        result = llm.with_structured_output(ClassificationResponse).invoke(messages).classification
        return result == "SENDABLE"
        
    except Exception as e:
        logger.error(f"Error in reply validation: {str(e)}")
        return False


async def create_email_draft_reply(subject: str, body: str, sender: str) -> Optional[str]:
    """
    Create a draft reply for an email using LLM.
    
    Args:
        subject: Email subject (already cleaned of HTML)
        body: Email body (already cleaned of HTML)  
        sender: Email sender address
        
    Returns:
        Optional[str]: Draft reply content or None if creation fails
        
    Raises:
        Exception: If LLM draft creation fails
    """
    if not all([subject, body, sender]):
        logger.warning("Missing required parameters for draft creation")
        return None
        
    try:
        system_prompt = """You are an intelligent email assistant tasked with drafting professional email responses. 
        
        Guidelines for your response:
        - Maintain a professional, courteous, and helpful tone throughout
        - Address all key points and questions from the original email
        - Be concise and to the point while being thorough
        - Use clear language and logical structure
        - Match the level of formality in the original email
        - Do not include email headers, greetings like 'Dear' or signatures
        - Start directly with the body text of the reply
        - Provide specific information when possible rather than vague statements
        - If you cannot answer a specific question, acknowledge it and suggest a follow-up
        - Avoid unnecessary pleasantries or filler content
        
        Your goal is to create a response that effectively addresses the sender's needs while being professional and efficient."""
        
        user_prompt = f"""
        Original Email:
        From: {sender}
        Subject: {subject}
        
        Body:
        {body}
        
        Please generate a professional reply to this email.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = llm.invoke(messages)
        
        if hasattr(response, 'content'):
            draft_content = response.content
        else:
            draft_content = str(response)
            
        if not draft_content or not draft_content.strip():
            logger.warning(f"Empty draft content generated for email from {sender}")
            return None
            
        logger.info(f"Generated draft reply for email from {sender}")
        return draft_content.strip()
        
    except Exception as e:
        logger.error(f"Error creating email draft: {str(e)}")
        raise


async def process_email_classification_payload(payload: dict, graph_client) -> bool:
    """
    Process email classification payload
    
    Args:
        payload: Dictionary containing message_id and other data
        graph_client: MS Graph client instance
        
    Returns:
        bool: True if processing succeeds, False otherwise
    """
    if not payload or not graph_client:
        logger.error("Missing required parameters for email classification")
        return False
        
    message_id = payload.get("message_id")
    if not message_id:
        logger.error("No message_id found in payload")
        return False
    
    try:
        logger.info(f"Processing email classification for message_id: {message_id}")
        # TODO: Implement actual classification logic
        return True
        
    except Exception as e:
        logger.error(f"Error processing email classification: {str(e)}")
        raise

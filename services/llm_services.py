"""
Add your system prompts for classification, proofreading and draft creation. For example which emails should be replied to criteri for proofreading and evaluation of draft replies and how to create a draft reply [salutation, namedesignation, company etc ]
Add as much details as possible in each of the system prompts ake the LLM about the usecase and conditions
"""
from typing import Optional, List
from utils import get_llm, logging, ClassificationEmail, ClassificationResponse, clean_html

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

def can_send_reply(email_subject: str, email_body: str, draft_response: str, prev_summary: Optional[str] = None) -> bool:
    """
    Proofread draft using LLM to ensure it is worth saving to draft.
    
    Args:
        email_subject: Subject of the original email
        email_body: Body of the original email
        draft_response: Draft response to be validated
        prev_summary: Optional summary of previous conversation context
        
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
        - If previous conversation context exists, appropriately acknowledge and build upon it
        
        A response should be marked SKIP if it:
        - Is off-topic or unrelated to the original email
        - Contains inappropriate language or tone
        - Fails to address the main points of the original email
        - Is confusing, incomplete, or incoherent
        - Contains factually incorrect information
        - Ignores important conversation context when it should be acknowledged
        
        Carefully compare the draft response against the original email and any conversation context to ensure it properly addresses the sender's concerns."""
        
        # Build user prompt with conversation context if available
        user_prompt = f"""Given the initial incoming email #Subject:{email_subject}\n#Body:\n{email_body}"""
        
        # Add previous conversation context if available
        if prev_summary:
            user_prompt += f"""\n\n#Previous Conversation Context:\n{prev_summary}"""
            
        user_prompt += f"""\n\nProofread the following response:\n{draft_response}\n\nIs this response SENDABLE or should it be SKIPPED?"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        result = llm.with_structured_output(ClassificationResponse).invoke(messages).classification
        return result == "SENDABLE"
        
    except Exception as e:
        logger.error(f"Error in reply validation: {str(e)}")
        return False


async def create_email_draft_reply(subject: str, body: str, sender: str, prev_summary: Optional[str] = None) -> Optional[str]:
    """
    Create a draft reply for an email using LLM.
    
    Args:
        subject: Email subject (already cleaned of HTML)
        body: Email body (already cleaned of HTML)  
        sender: Email sender address
        prev_summary: Optional summary of previous conversation context
        
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
        - If previous conversation context is provided, use it to create more informed and contextually appropriate responses
        
        Your goal is to create a response that effectively addresses the sender's needs while being professional and efficient."""
        
        # Build user prompt with conversation context if available
        user_prompt = f"""
        # Original Email:
        
        From: {sender}
        ##Subject:
        {subject}
        
        ## Body:
        {body}
        """
        
        # Add previous conversation context if available
        if prev_summary:
            user_prompt += f"""
        
        # Previous Conversation Context:
        {prev_summary}
        """
            
        user_prompt += "\n\nPlease generate a professional reply to this email, taking into account any previous conversation context provided."
        
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


def create_conversation_summary(conversation_messages: List[dict]) -> Optional[str]:
    """
    Create a summary of the email conversation using LLM.
    
    Args:
        conversation_messages: List of messages in the conversation, 
                             first message is current email (excluded from summary)
        
    Returns:
        Optional[str]: Summary of the previous conversation or None if creation fails
        
    Raises:
        Exception: If LLM summary creation fails
    """
    if not conversation_messages or len(conversation_messages) <= 1:
        logger.info("No previous conversation to summarize")
        return None
        
    try:
        # Skip first message (current email) and process previous messages
        previous_messages = conversation_messages[1:]
        
        # Build conversation string from previous emails
        conversation_text = "# Previous Conversations\n\n"
        
        for i, message in enumerate(previous_messages, 1):
            subject = message.get('subject', 'No Subject')
            body_content = message.get('body', {}) # "body" in graph response is a dict 
            
            # Extract and clean body content
            if isinstance(body_content, dict):
                raw_body = body_content.get('content', '')
            else:
                raw_body = str(body_content)
                
            clean_body = clean_html(raw_body)
            
            # Add email to conversation text
            conversation_text += f"## Email {i}:\n"
            conversation_text += f"### Subject: {subject}\n"
            conversation_text += f"### Body: {clean_body}\n\n"
        
        system_prompt = """You are an expert email assistant tasked with creating concise summaries of email conversations.
        
        Your task is to:
        - Read through the previous emails in the conversation thread
        - Create a brief, coherent summary that captures the key points and context
        - Focus on important decisions, questions asked, and answers provided
        - Maintain chronological order when relevant
        - Keep the summary concise but informative (3-7 sentences typically)
        - Identify any unresolved issues or pending requests
        
        Guidelines:
        - Use clear, professional language
        - Avoid repeating redundant information
        - Focus on actionable items and important context
        - Don't include email headers or formatting artifacts
        - If the conversation contains mostly pleasantries, indicate that briefly
        """
        
        user_prompt = f"Please create a summary of the following email conversation:\n\n{conversation_text}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = llm.invoke(messages)
        
        if hasattr(response, 'content'):
            summary = response.content
        else:
            summary = str(response)
            
        if not summary or not summary.strip():
            logger.warning("Empty summary generated for conversation")
            return None
            
        logger.info(f"Generated conversation summary for {len(previous_messages)} previous emails")
        return summary.strip()
        
    except Exception as e:
        logger.error(f"Error creating conversation summary: {str(e)}")
        return None

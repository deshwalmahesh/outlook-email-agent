from typing import Optional
from services.llm_services import can_respond_to_email, can_send_reply, create_email_draft_reply, create_conversation_summary, MAX_REDRAFT_TRIES
from utils import clean_html, logging

logger = logging.getLogger(__name__)



async def fetch_email_details(message_id: str, graph_client, USER_ID: str) -> Optional[dict]:
    """
    Fetch email details from Graph API and clean HTML content.
    
    Args:
        message_id: ID of the email message
        graph_client: MS Graph client instance
        USER_ID: User ID for API calls
        
    Returns:
        Optional[dict]: Email details or None if fetch fails
        
    Raises:
        Exception: If API request fails or data processing fails
    """
    if not message_id or not graph_client or not USER_ID:
        logger.error("Missing required parameters for fetch_email_details")
        return None
        
    try:
        endpoint = (
            f"/{USER_ID}/messages/{message_id}"
            "?$select=id,subject,body,conversationId,internetMessageId,"
            "receivedDateTime,sender,toRecipients,parentFolderId"
        )
        email = graph_client._make_request("GET", endpoint)
        
        if not email:
            logger.error(f"No email data received for message {message_id}")
            return None
            
        raw_subject = email.get('subject', '')
        raw_body = email.get('body', {}).get('content', '')
        sender = email.get('sender', {}).get('emailAddress', {}).get('address', '')
        
        if not sender:
            logger.warning(f"No sender found for message {message_id}")
            
        clean_subject = clean_html(raw_subject)
        clean_body = clean_html(raw_body)
        
        return {
            'id': email.get('id', ''),
            'subject': raw_subject,
            'body': raw_body,
            'clean_subject': clean_subject,
            'clean_body': clean_body,
            'conversation_id': email.get('conversationId', ''),
            'internet_message_id': email.get('internetMessageId', ''),
            'parent_folder_id': email.get('parentFolderId', ''),
            'received_date': email.get('receivedDateTime', ''),
            'sender': sender,
            'recipients': [r.get('emailAddress', {}).get('address', '') for r in email.get('toRecipients', [])]
        }
        
    except Exception as e:
        logger.error(f"Error fetching email {message_id}: {str(e)}")
        raise


async def save_draft_to_outlook(message_id: str, draft_content: str, original_email: dict, graph_client, USER_ID: str) -> bool:
    """
    Save draft reply to Outlook using Graph API.
    
    Args:
        message_id: ID of the original email message
        draft_content: Content of the draft reply
        original_email: Original email data
        graph_client: MS Graph client instance
        USER_ID: User ID for API calls
        
    Returns:
        bool: True if draft was saved successfully, False otherwise
    """
    if not all([message_id, draft_content, original_email, graph_client, USER_ID]):
        logger.error("Missing required parameters for save_draft_to_outlook")
        return False
        
    try:
        logger.info("Starting save_draft_to_outlook")
        
        draft_response = graph_client.create_draft_reply(
            message_id=message_id,
            user_id=USER_ID,
            reply_content=draft_content
        )
        
        if draft_response and draft_response.get('id'):
            logger.info(f"Draft created with ID: {draft_response.get('id')}")
            return True
        else:
            logger.error("create_draft_reply failed")
            return False
            
    except Exception as e:
        logger.error(f"Exception in save_draft_to_outlook: {str(e)}")
        raise

async def process_email_notification(payload: dict, graph_client, USER_ID: str) -> None:
    """
    Main email processing workflow.
    
    Args:
        payload: Notification payload from Graph API
        graph_client: MS Graph client instance
        USER_ID: User ID for API calls
    """
    if not payload or not graph_client or not USER_ID:
        logger.error("Missing required parameters")
        return
        
    try:
        logger.info("Starting email notification processing")
        
        notification = payload.get("value", [])
        if not notification:
            logger.error("Empty notification payload")
            return
            
        note = notification[0]
        
        if note.get("changeType") != "created":
            logger.info(f"Ignoring change type: {note.get('changeType')}")
            return
            
        resource = note.get("resource", "")
        if "Messages/" not in resource:
            logger.info("Not a message resource")
            return
            
        message_id = resource.split("Messages/")[-1]
        logger.info(f"Processing new email with ID: {message_id}")
        
        email_data = await fetch_email_details(message_id, graph_client, USER_ID)
        if not email_data:
            logger.error(f"Failed to fetch email details for {message_id}")
            return
            
        clean_subject = email_data.get('clean_subject')
        clean_body = email_data.get('clean_body')
        sender = email_data.get('sender')
        
        logger.info(f"Email from {sender} processed")
        
        classification = can_respond_to_email(clean_subject, clean_body)
        logger.info(f"Email classified as: {'RESPOND' if classification else 'SKIP'}")
        
        if not classification:
            logger.info(f"Skipping email {message_id}")
            return
            
        # Fetch conversation messages for context
        conversation_messages = []
        conversation_summary = None
        try:
            conversation_id = email_data.get('conversation_id')
            if conversation_id:
                logger.info(f"Fetching conversation messages for conversation {conversation_id}")
                conversation_messages = graph_client.get_conversation_messages(
                    identifier=conversation_id,
                    identifier_type="conversation_id", 
                    user_id=USER_ID
                )
                
                if conversation_messages and len(conversation_messages) > 1:
                    logger.info(f"Found {len(conversation_messages)} messages in conversation")
                    conversation_summary = create_conversation_summary(conversation_messages)
                    if conversation_summary:
                        logger.info("Generated conversation summary")
                    else:
                        logger.info("No conversation summary generated")
                else:
                    logger.info("No previous conversation messages found")
                    
        except Exception as e:
            logger.error(f"Error fetching conversation context: {str(e)}")
            # Continue without conversation context
        
        # Draft creation and validation loop with redrafting capability
        draft_content = None
        previous_draft = None
        previous_draft_rejection_reason = None
        
        for attempt in range(MAX_REDRAFT_TRIES + 1):  # +1 because we want original + redrafts
            logger.info(f"Draft attempt {attempt + 1} of {MAX_REDRAFT_TRIES + 1} for email {message_id}")
            
            # Create draft (original or redraft)
            try:
                if attempt == 0:
                    # First attempt - original draft
                    draft_content = await create_email_draft_reply(clean_subject, clean_body, sender, conversation_summary)
                else:
                    # Redraft attempt
                    draft_content = await create_email_draft_reply(
                        clean_subject, clean_body, sender, conversation_summary,
                        previous_draft, previous_draft_rejection_reason
                    )
            except Exception as e:
                logger.error(f"Error creating draft on attempt {attempt + 1}: {str(e)}")
                draft_content = None
            
            if not draft_content:
                logger.error(f"Failed to create draft for email {message_id} on attempt {attempt + 1}")
                return
                
            logger.info(f"Draft content created on attempt {attempt + 1}")
                
            # Validate the draft
            try:
                validation_result = can_send_reply(clean_subject, clean_body, draft_content, conversation_summary)
                if isinstance(validation_result, tuple):
                    is_sendable, reason = validation_result
                else:
                    # Fallback if function doesn't return tuple
                    is_sendable = validation_result
                    reason = "No reason provided"
            except Exception as e:
                logger.error(f"Error validating draft on attempt {attempt + 1}: {str(e)}")
                is_sendable = False
                reason = f"Validation error: {str(e)}"
            
            logger.info(f"Draft quality check attempt {attempt + 1}: {'SENDABLE' if is_sendable else 'SKIP'}")
            if not is_sendable:
                logger.info(f"Rejection reason: {reason}")
            
            if is_sendable:
                # Draft is acceptable, break out of the loop
                logger.info(f"Draft accepted on attempt {attempt + 1} for email {message_id}")
                break
            else:
                # Draft rejected
                logger.info(f"Draft rejected on attempt {attempt + 1} for email {message_id}. Reason: {reason}")
                
                # Check if we have more attempts left
                if attempt < MAX_REDRAFT_TRIES:
                    # Store the rejected draft and reason for next attempt
                    previous_draft = draft_content
                    previous_draft_rejection_reason = reason
                    logger.info(f"Will attempt redraft {attempt + 2} for email {message_id}")
                else:
                    # No more attempts left
                    logger.info(f"Maximum redraft attempts ({MAX_REDRAFT_TRIES + 1}) reached for email {message_id}, giving up")
                    return
        
        # If we reach here, we have a sendable draft
        if not is_sendable:
            logger.error(f"Unexpected state: exited loop without sendable draft for email {message_id}")
            return
            
        success = await save_draft_to_outlook(message_id, draft_content, email_data, graph_client, USER_ID)
        if success:
            total_attempts = attempt + 1
            logger.info(f"Workflow completed for email {message_id} after {total_attempts} attempt(s)")
        else:
            logger.error(f"Failed to save draft for email {message_id}")
            
    except Exception as e:
        logger.error(f"Exception in process_email_notification: {str(e)}")
        raise
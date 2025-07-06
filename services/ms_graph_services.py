import requests
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Literal, Optional, Dict
from urllib.parse import quote_plus
from dotenv import load_dotenv
import os
import webbrowser
import json
import base64
import msal
from utils import logging

load_dotenv(override=True)
logger = logging.getLogger(__name__)

MS_GRAPH_BASE_URL = 'https://graph.microsoft.com/v1.0'

class MSGraphAuthDelegated:
    """
    Handle Microsoft Graph API authentication for personal accounts using delegated permissions.
    
    This class manages the OAuth2 authorization code flow for personal Microsoft accounts,
    including token acquisition, refresh, and storage.
    """
    def __init__(self, application_id: str, client_secret: str, scopes: list, authority: str = 'https://login.microsoftonline.com/consumers/'):
        """
        Initialize the MSGraphAuth class.
        
        Args:
            application_id: The application ID from Azure AD
            client_secret: The client secret from Azure AD
            scopes: List of scopes required for the application
            authority: The authority URL for authentication
        """
        self.application_id = application_id
        self.client_secret = client_secret
        self.scopes = scopes
        self.authority = authority
        self.client = msal.ConfidentialClientApplication(
            client_id=application_id,
            client_credential=client_secret,
            authority=authority
        )
        self.access_token = None
    
    def get_access_token(self) -> str:
        """
        Get an access token for Microsoft Graph API.
        
        Returns:
            str: The access token
            
        Raises:
            Exception: If token acquisition fails
        """
        refresh_token = None
        
        if os.path.exists('refresh_token.secret'):
            with open('refresh_token.secret', 'r') as file:
                refresh_token = file.read().strip()

        try:
            if refresh_token:
                token_response = self.client.acquire_token_by_refresh_token(refresh_token, scopes=self.scopes)
            else:
                auth_request_url = self.client.get_authorization_request_url(self.scopes)
                webbrowser.open(auth_request_url)
                authorization_code = input('Enter the authorization code: ')

                if not authorization_code:
                    raise ValueError("Authorization code is empty")

                token_response = self.client.acquire_token_by_authorization_code(
                    code=authorization_code,
                    scopes=self.scopes
                )

            if 'access_token' in token_response:
                if 'refresh_token' in token_response:
                    with open('refresh_token.secret', 'w') as file:
                        file.write(token_response['refresh_token'])

                self.access_token = token_response['access_token']
                return self.access_token
            else:
                raise Exception('Failed to acquire access token: ' + str(token_response))
                
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            raise

class MSGraphAuthCorporate:
    """
    Class to handle Microsoft Graph API authentication for corporate accounts using client credentials flow.
    It requires client ID, client secret, and tenant ID to authenticate and obtain an access token.
    It uses user@corporate.doamin.com endpoints instead of /me
    """
    def __init__(self, client_id: str, client_secret: str, tenant_id: str, 
                 scope: str = 'https://graph.microsoft.com/.default'):
        """
        Initialize the CorporateMSGraphAuth class.
        
        Args:
            client_id: The client ID from Azure AD application registration
            client_secret: The client secret from Azure AD application registration
            tenant_id: The tenant ID for the organization
            scope: The scope for the token request
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.scope = scope
        self.token_url = f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token'
    
    def get_access_token(self) -> str:
        """
        Get an access token for Microsoft Graph API using client credentials flow.
        
        Returns:
            str: The access token
            
        Raises:
            Exception: If token acquisition fails
        """  
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials',
            'scope': self.scope
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        try:
            response = requests.post(self.token_url, data=payload, headers=headers)
            response.raise_for_status()
            token_data = response.json()
            return token_data.get('access_token')
        except Exception as e:
            logger.error(f"Failed to acquire corporate access token: {str(e)}")
            raise

class MSGraphClient:
    """
    Class to interact with Microsoft Graph API.
    """
    def __init__(self, auth):
        """
        Initialize the MSGraphClient class.
        
        Args:
            auth: An instance of MSGraphAuthDelegated or MSGraphAuthCorporate for authentication
        """
        self.subscription_id = None
        self.auth = auth
        self.base_url = 'https://graph.microsoft.com/v1.0'
        self.headers = {
            'Authorization': f'Bearer {self.auth.get_access_token()}',
            'Content-Type': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
        """
        Make a request to the Microsoft Graph API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            data: Request body data
            
        Returns:
            dict: Response from the API
        """
        if not endpoint:
            raise ValueError("Endpoint cannot be empty")
            
        self.headers = {
            'Authorization': f'Bearer {self.auth.get_access_token()}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.info(f"Making {method} request to {url}")
            
            if method == 'GET':
                response = requests.get(url, headers=self.headers, params=params)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, params=params, json=data)
            elif method == 'PATCH':
                response = requests.patch(url, headers=self.headers, params=params, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=self.headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            logger.info(f"Response status code: {response.status_code}")
            response.raise_for_status()
            
            if response.status_code == 204 or response.status_code == 202:
                logger.info(f"Request succeeded with status code: {response.status_code}")
                return {"status_code": response.status_code}
                
            return response.json()
        
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Request failed with status code: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            logger.error(f"Request exception: {str(e)}")
            raise
    
    def get_user_details(self, user_id: str) -> dict:
        """
        Get user details from Microsoft Graph API.
        
        Args:
            user_id: User ID or 'me' for the current user
            
        Returns:
            dict: User details
            
        Raises:
            ValueError: If user_id is empty
            Exception: If API request fails
        """
        if not user_id:
            raise ValueError("User ID cannot be empty")
            
        endpoint = f"/{user_id}"
        return self._make_request('GET', endpoint)
    
    def get_message(self, identifier: str, identifier_type: Literal["message_id", "internet_message_id"], 
                  user_id: str, select: Optional[str] = None) -> Optional[dict]:
        """
        Retrieve a single message by either Graph ID or RFC-2822 Message-ID.
        
        Args:
            identifier (str): The ID value to look up.
            identifier_type (Literal["message_id", "internet_message_id"]): Type of ID to use.
            user_id (str): User ID or 'me' for the current user.
            select (Optional[str]): Comma-separated fields to include in the response.
            
        Returns:
            Optional[dict]: Message details or None if not found.
        """
        if not identifier or not user_id:
            raise ValueError("Identifier and user_id are required")
            
        try:
            if identifier_type == "message_id":
                endpoint = f"/{user_id}/messages/{quote_plus(identifier.strip())}"
                return self._make_request("GET", endpoint)

            if identifier_type == "internet_message_id":
                filt = f"internetMessageId eq '{identifier.strip()}'"
                params = {"$filter": filt, "$top": 1}
                if select:
                    params["$select"] = select
                resp = self._make_request("GET", f"/{user_id}/messages", params=params)
                return (resp.get("value") or [None])[0]

            raise ValueError("identifier_type must be 'message_id' or 'internet_message_id'")
            
        except Exception as e:
            logger.error(f"Error getting message {identifier}: {str(e)}")
            raise

    
    def get_conversation_messages(self, identifier: str, identifier_type: Literal["conversation_id", "message_id", "internet_message_id"],
                                 user_id: str, select: Optional[str] = None, 
                                order: str = None, top: Optional[int] = None) -> List[dict]:
        """
        Retrieve the full thread for a given message.
        
        Args:
            identifier (str): ID value of any message in the thread.
            identifier_type (Literal): Type of ID to use.
            user_id (str): User ID or 'me' for the current user.
            select (Optional[str]): Comma-separated fields to include in the response.
            order (str): OrderBy expression for sorting results.
            top (Optional[int]): Maximum number of messages to return.
            
        Returns:
            List[dict]: List of messages in the conversation thread.
        """
        if not identifier or not user_id:
            raise ValueError("Identifier and user_id are required")
            
        try:
            if identifier_type != "conversation_id":
                seed = self.get_message(identifier, identifier_type, user_id, select="conversationId")
                if not seed:
                    return []
                identifier = seed["conversationId"]

            params = {
                "$filter": f"conversationId eq '{identifier}'",
                "$orderby": order,
            }
            if select:
                params["$select"] = select
            if top:
                params["$top"] = top

            result = self._make_request("GET", f"/{user_id}/messages", params=params)
            return result.get("value", [])
            
        except Exception as e:
            logger.error(f"Error getting conversation messages: {str(e)}")
            raise


    def create_draft_reply(self, message_id: str, user_id: str, reply_content: str) -> Optional[dict]:
        """
        Create a draft reply to an existing message using Graph API.
        
        Args:
            message_id: ID of the original message to reply to
            user_id: User ID or 'me' for the current user
            reply_content: Content of the reply message
            
        Returns:
            Optional[dict]: Draft reply details or None if creation fails
            
        Raises:
            ValueError: If required parameters are missing
            Exception: If API request fails
        """
        if not all([message_id, user_id, reply_content]):
            raise ValueError("All parameters are required")
            
        try:
            logger.info("Starting create_draft_reply")
            
            endpoint = f"/{user_id}/messages/{message_id}/createReply"
            logger.info(f"Creating empty draft reply at endpoint: {endpoint}")
            
            draft_response = self._make_request("POST", endpoint)
            
            if not draft_response or not draft_response.get('id'):
                logger.error(f"Failed to create draft reply for message {message_id}")
                return None
                
            draft_id = draft_response['id']
            logger.info(f"Created empty draft with ID: {draft_id}")
            
            update_endpoint = f"/{user_id}/messages/{draft_id}"
            update_body = {
                "body": {
                    "contentType": "Text",
                    "content": reply_content
                }
            }
            
            logger.info("Updating draft with content")
            updated_draft = self._make_request("PATCH", update_endpoint, data=update_body)
            
            if updated_draft:
                logger.info(f"Successfully created and updated draft reply with ID: {draft_id}")
                return updated_draft
            else:
                logger.error(f"Failed to update draft {draft_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error in create_draft_reply: {str(e)}")
            raise

    def create_email(self, subject: str, body: str, to_recipients: list, cc_recipients: list = None, bcc_recipients: list = None, 
                    attachments: list = None) -> dict:
        """
        Create an email message.
        
        Args:
            subject: Email subject
            body: Email body content
            to_recipients: List of recipient email addresses
            cc_recipients: List of CC recipient email addresses
            bcc_recipients: List of BCC recipient email addresses
            attachments: List of attachments
            
        Returns:
            dict: Created email message
        """
        if not subject or not body or not to_recipients:
            raise ValueError("Subject, body, and to_recipients are required")
            
        try:
            to_recipients_formatted = [{'emailAddress': {'address': email}} for email in to_recipients]
            
            message_data = {
                'subject': subject,
                'body': {
                    'contentType': 'HTML',
                    'content': body
                },
                'toRecipients': to_recipients_formatted
            }
            
            if cc_recipients:
                message_data['ccRecipients'] = [{'emailAddress': {'address': email}} for email in cc_recipients]
            
            if bcc_recipients:
                message_data['bccRecipients'] = [{'emailAddress': {'address': email}} for email in bcc_recipients]
            
            endpoint = '/me/messages'
            response = self._make_request('POST', endpoint, data=message_data)
            
            if attachments and response.get('id'):
                self._add_attachments_to_message(response['id'], attachments)
            
            return response
            
        except Exception as e:
            logger.error(f"Error creating email: {str(e)}")
            raise
    
    def _add_attachments_to_message(self, message_id: str, attachments: list) -> bool:
        """
        Add attachments to a message.
        
        Args:
            message_id: ID of the message
            attachments: List of attachment file paths
            
        Returns:
            bool: True if successful
        """
        if not message_id or not attachments:
            logger.warning("Missing message_id or attachments")
            return False
            
        try:
            for file_path in attachments:
                if not os.path.exists(file_path):
                    logger.warning(f"File not found: {file_path}")
                    continue
                    
                file_name = os.path.basename(file_path)
                with open(file_path, 'rb') as file:
                    file_content = file.read()
                    
                content_bytes = base64.b64encode(file_content).decode('utf-8')
                    
                attachment_data = {
                    '@odata.type': '#microsoft.graph.fileAttachment',
                    'name': file_name,
                    'contentBytes': content_bytes
                }
                
                endpoint = f"/me/messages/{message_id}/attachments"
                self._make_request('POST', endpoint, data=attachment_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding attachments: {str(e)}")
            raise
    
    def save_draft(self, subject: str, body: str, to_recipients: list, cc_recipients: list = None, bcc_recipients: list = None, attachments: list = None) -> dict:
        """
        Save an email as a draft.
        
        Args:
            subject: Email subject
            body: Email body content
            to_recipients: List of recipient email addresses
            cc_recipients: List of CC recipient email addresses
            bcc_recipients: List of BCC recipient email addresses
            attachments: List of attachments
            
        Returns:
            dict: Created draft message
        """
        return self.create_email(subject, body, to_recipients, cc_recipients, bcc_recipients, attachments)
    
    def send_email(self, subject: str, body: str, to_recipients: list, cc_recipients: list = None, bcc_recipients: list = None, attachments: list = None) -> dict:
        """
        Create and send an email directly.
        
        Args:
            subject: Email subject
            body: Email body content
            to_recipients: List of recipient email addresses
            cc_recipients: List of CC recipient email addresses
            bcc_recipients: List of BCC recipient email addresses
            attachments: List of attachments
            
        Returns:
            dict: Response from the API
        """
        if not subject or not body or not to_recipients:
            raise ValueError("Subject, body, and to_recipients are required")
            
        try:
            to_recipients_formatted = [{'emailAddress': {'address': email}} for email in to_recipients]
            
            message = {
                'subject': subject,
                'body': {
                    'contentType': 'HTML',
                    'content': body
                },
                'toRecipients': to_recipients_formatted
            }
            
            if cc_recipients:
                message['ccRecipients'] = [{'emailAddress': {'address': email}} for email in cc_recipients]
            
            if bcc_recipients:
                message['bccRecipients'] = [{'emailAddress': {'address': email}} for email in bcc_recipients]
            
            request_body = {
                'message': message,
                'saveToSentItems': True
            }
            
            if attachments:
                draft = self.create_email(subject, body, to_recipients, cc_recipients, bcc_recipients, attachments)
                endpoint = f"/me/messages/{draft['id']}/send"
                return self._make_request('POST', endpoint)
            else:
                endpoint = '/me/sendMail'
                return self._make_request('POST', endpoint, data=request_body)
                
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            raise
    
    def send_draft(self, message_id: str) -> dict:
        """
        Send an existing draft email.
        
        Args:
            message_id: ID of the draft message
            
        Returns:
            dict: Response from the API
        """
        if not message_id:
            raise ValueError("Message ID is required")
            
        endpoint = f"/me/messages/{message_id}/send"
        return self._make_request('POST', endpoint)
    
    def update_message_read_status(self, message_id: str, is_read: bool) -> dict:
        """
        Mark a message as read or unread.
        
        Args:
            message_id: ID of the message
            is_read: True to mark as read, False to mark as unread
            
        Returns:
            dict: Response from the API
        """
        if not message_id:
            raise ValueError("Message ID is required")
            
        endpoint = f"/me/messages/{message_id}"
        data = {"isRead": is_read}
        return self._make_request('PATCH', endpoint, data=data)
    
    def get_email_from_webhook_resource(self, notification_resource: str, user_id: str) -> dict | None:
        """
        Process the webhook notification from Microsoft Graph API to extract email details
        
        Args:
            notification_resource: The resource URL from the webhook notification
            user_id: User ID or 'me' for the current user
            
        Returns:
            dict | None: Email details or None if processing fails
        """
        if not notification_resource or not user_id:
            logger.error("Missing notification_resource or user_id")
            return None
            
        try:
            if 'Messages/' in notification_resource:
                logger.info(f"Processing notification resource: {notification_resource}")
                message_id = notification_resource.split('Messages/')[-1]
                endpoint = f"/{user_id}/messages/{message_id}?$select=id,subject,body,conversationId,internetMessageId,receivedDateTime,sender,parentFolderId"
                
                email_data = self._make_request('GET', endpoint)
                logger.info(f"Successfully retrieved email with ID: {message_id}")
                return email_data
            else:
                logger.warning(f"Resource doesn't contain 'Messages/': {notification_resource}")
                return None

        except Exception as e:
            logger.error(f"Error processing webhook notification: {str(e)}")
            raise
        
    def subscribe_to_notifications(self, notification_accep_url: str, user_id: str, folder: str = "Inbox") -> dict:
        """
        Subscribe to notifications for a specific resource.
        
        Args:
            notification_accep_url: Publicly accessible URL to receive notifications
            user_id: User ID or 'me' for the current user
            folder: Folder to subscribe to
            
        Returns:
            dict: Subscription response
        """
        if not notification_accep_url or not user_id:
            raise ValueError("notification_accep_url and user_id are required")
            
        try:
            logger.info("Creating a new subscription")
            body = {
                "changeType": "created",
                "notificationUrl": notification_accep_url,
                "resource": f"/{user_id}/mailFolders('{folder}')/messages",
                "expirationDateTime": (datetime.now(timezone.utc) + timedelta(days=6.99)).isoformat(),
                "clientState": "SecretClientState"
            }
            resp_json = self._make_request('POST', '/subscriptions', data=body)
            
            if "id" in resp_json:
                self.subscription_id = resp_json["id"]
                logger.info(f"Subscription created with ID: {self.subscription_id}")
            else:
                logger.error(f"Failed to create subscription: {resp_json}")
                
            return resp_json
            
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            raise

    def renew_subscription(self, subscription_id: str, extension_days: float = 6.99) -> dict:
        """
        Renew an existing subscription by extending its expiration date.
        
        Args:
            subscription_id: The ID of the subscription to renew
            extension_days: Number of days to extend the subscription
            
        Returns:
            dict: Response from the API
        """
        if not subscription_id:
            raise ValueError("Subscription ID is required")
            
        new_expiry = (datetime.now(timezone.utc) + timedelta(days=extension_days)).isoformat()
        body = {"expirationDateTime": new_expiry}
        return self._make_request("PATCH", f"/subscriptions/{subscription_id}", data=body)

    def delete_subscription(self, subscription_id: str) -> dict:
        """
        Delete an existing subscription.
        
        Args:
            subscription_id: The ID of the subscription to delete
            
        Returns:
            dict: Response from the API
        """
        if not subscription_id:
            raise ValueError("Subscription ID is required")
            
        response = self._make_request('DELETE', f"/subscriptions/{subscription_id}")
        logger.info("Delete subscription status: success")
        return response
    
    def list_all_subscriptions(self) -> list:
        """
        List all existing subscriptions.
        
        Returns:
            list: List of subscription objects
        """
        logger.info("Listing all existing subscriptions")
        response = self._make_request('GET', '/subscriptions')
        subscriptions = response.get('value', [])
        logger.info(f"Found {len(subscriptions)} existing subscriptions")
        return subscriptions
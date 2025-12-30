# openai_service.py
import os
import json
import logging
from openai import AsyncOpenAI
from prompts import (
    DOCUMENT_ROUTING_AND_TOPIC_PROMPT,
    TOPIC_AWARE_DOCUMENT_ANALYSIS_PROMPT
    # CONSOLIDATED_CHANNEL_ANALYSIS_PROMPT - DISABLED (not needed for simplified 2-prompt system)
)

# Load OpenAI credentials
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_RETRIES = 3

async def classify_document(text: str) -> dict:
    """
    Classify and route a document using Prompt 1 (Routing + Topic Creation).
    Returns routing decision and topic information.
    """
    logging.info("Classifying and routing document...")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"Attempt {attempt}: Sending routing request to OpenAI...")
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": DOCUMENT_ROUTING_AND_TOPIC_PROMPT},
                    {"role": "user", "content": text}
                ],
                temperature=0.2  # Low temperature for consistent routing decisions
            )
            content = response.choices[0].message.content.strip()
            logging.debug(f"OpenAI routing response: {content}")
            result = json.loads(content)

            # Validate required fields
            if isinstance(result, dict) and "channel" in result and "routing" in result:
                logging.info(f"Document routed to: {result.get('routing')} - Channel: {result.get('channel')}")
                if result.get('routing') == 'INBOX':
                    logging.info(f"Topic created: {result.get('topic_title')} (Type: {result.get('topic_type')})")
                return result
            else:
                logging.warning("Unexpected routing format. Defaulting to ARCHIVE.")
                return {
                    "channel": "ARCHIVE",
                    "topic_type": None,
                    "topic_title": None,
                    "routing": "ARCHIVE",
                    "urgency": "LOW",
                    "deadline": None,
                    "authority": None,
                    "reasoning": "Classification failed - routing to archive"
                }

        except Exception as e:
            logging.warning(f"Routing attempt {attempt} failed: {e}")
    
    logging.error("All routing attempts failed. Defaulting to ARCHIVE.")
    return {
        "channel": "ARCHIVE",
        "topic_type": None,
        "topic_title": None,
        "routing": "ARCHIVE",
        "urgency": "LOW",
        "deadline": None,
        "authority": None,
        "reasoning": "All classification attempts failed - routing to archive"
    }


async def analyze_document(text: str, channel: str = None, topic_type: str = None, topic_title: str = None) -> dict:
    """
    Analyze a document using Prompt 2 (Topic-Aware Analysis).
    Used only for INBOX documents after routing.
    """
    logging.info(f"Analyzing inbox topic: {topic_title} (Channel: {channel}, Type: {topic_type})")
    
    # Build context-aware analysis prompt
    analysis_prompt = f"""
Channel: {channel}
Topic Type: {topic_type}
Topic Title: {topic_title}

Document text to analyze:
{text}

Provide a detailed analysis with specific actionable items for this topic.
"""
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"Attempt {attempt}: Sending topic analysis request to OpenAI...")
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": TOPIC_AWARE_DOCUMENT_ANALYSIS_PROMPT},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.2
            )
            content = response.choices[0].message.content.strip()
            logging.debug(f"OpenAI topic analysis response: {content}")
            result = json.loads(content)

            if isinstance(result, dict) and "summary" in result:
                logging.info(f"Successfully analyzed topic with {len(result.get('actionable_items', []))} actionable items")
                return result
            else:
                logging.warning("Unexpected analysis format.")
                return {
                    "summary": "Analysis completed but format was unexpected",
                    "key_data": {},
                    "actionable_items": [
                        {
                            "type": "ai_chat",
                            "action": "ask_general_ai",
                            "label": "Ask AI for Guidance",
                            "priority": 1
                        }
                    ],
                    "risk_if_ignored": "Please review this document manually",
                    "status": "OPEN"
                }

        except Exception as e:
            logging.warning(f"Topic analysis attempt {attempt} failed: {e}")
    
    logging.error("All topic analysis attempts failed.")
    return {
        "summary": "Failed to analyze this topic",
        "key_data": {},
        "actionable_items": [
            {
                "type": "ai_chat",
                "action": "ask_general_ai",
                "label": "Ask AI for Guidance",
                "priority": 1
            }
        ],
        "risk_if_ignored": "Unable to determine - please review manually",
        "status": "OPEN"
    }

async def analyze_multiple_documents_consolidated(combined_text: str, file_info: list, channel: str, topics: list = None) -> dict:
    """
    Analyze multiple documents in a channel using consolidated channel analysis.
    Uses Prompt 3 (Consolidated Channel Analysis).
    """
    logging.info(f"Performing consolidated channel analysis for {channel}")
    logging.info(f"Analyzing {len(file_info)} documents")
    logging.info(f"Total combined text length: {len(combined_text)} characters")

    # Smart text sampling for better analysis
    if len(combined_text) > 50000:
        # For very large text, use smart sampling to get representative content
        # Take first 25,000 chars (beginning of documents) and last 25,000 chars (end of documents)
        first_part = combined_text[:25000]
        last_part = combined_text[-25000:]
        text_sample = first_part + "\n\n[... MIDDLE CONTENT TRUNCATED ...]\n\n" + last_part
        logging.info(f"Using smart sampling: {len(text_sample)} characters (first 25k + last 25k of {len(combined_text)} total)")
    else:
        # For smaller text, use all content
        text_sample = combined_text
        logging.info(f"Using all {len(text_sample)} characters for analysis")
    
    # Build consolidated analysis prompt
    topics_info = ""
    if topics:
        topics_info = f"""
Topics in this channel:
{json.dumps(topics, indent=2)}
"""
    
    consolidated_prompt = f"""
Channel: {channel}
Number of documents: {len(file_info)}

{topics_info}

Document Information:
{json.dumps(file_info, indent=2)}

Analyze the following combined text from all documents in this channel:
{text_sample}

Provide a comprehensive consolidated analysis focusing on channel-specific insights and actionable items.
"""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"Attempt {attempt}: Sending consolidated channel analysis request to OpenAI...")
            logging.info(f"Prompt length: {len(consolidated_prompt)} characters")
            logging.info(f"Text sample length: {len(text_sample)} characters")
            
            # This function is disabled - consolidated analysis not needed for MVP
            # Keeping code for reference only
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "Consolidated analysis prompt (disabled)"},
                    {"role": "user", "content": consolidated_prompt}
                ],
                temperature=0.3,
                max_tokens=3000
            )
            content = response.choices[0].message.content.strip()
            logging.debug(f"OpenAI consolidated channel analysis response: {content}")
            result = json.loads(content)

            if isinstance(result, dict) and "comprehensive_summary" in result:
                logging.info(f"Successfully analyzed {len(file_info)} documents in {channel} channel")
                return result
            else:
                logging.warning("Unexpected consolidated analysis format.")
                return {
                    "comprehensive_summary": "Analysis completed but format was unexpected",
                    "key_findings": [],
                    "aggregated_data": {},
                    "actionable_items": [
                        {
                            "type": "ai_chat",
                            "action": "ask_general_ai",
                            "label": "Ask AI for Guidance",
                            "priority": 1,
                            "applies_to": "All documents"
                        }
                    ],
                    "priority_actions": ["Please review document format"],
                    "risk_assessment": "Unable to determine"
                }

        except Exception as e:
            logging.error(f"Attempt {attempt} failed with error: {str(e)}")
            logging.error(f"Error type: {type(e).__name__}")
            if hasattr(e, '__traceback__'):
                import traceback
                logging.error(f"Full traceback: {traceback.format_exc()}")
    
    logging.error("All consolidated channel analysis attempts failed.")
    return {
        "comprehensive_summary": "Failed to analyze documents",
        "key_findings": [],
        "aggregated_data": {},
        "actionable_items": [
            {
                "type": "ai_chat",
                "action": "ask_general_ai",
                "label": "Ask AI for Guidance",
                "priority": 1,
                "applies_to": "All documents"
            }
        ],
        "priority_actions": ["Please try again or check document format"],
        "risk_assessment": "Unable to determine"
    }

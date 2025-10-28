"""
KOTS Voice Assistant - Cloud Run + Exotel Integration
Handles phone calls via Exotel WebSocket and Gemini Live API
"""

import os
import json
import base64
import asyncio
import logging
import time
import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import Response, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import websockets
from google import genai
from google.genai.types import (
    LiveConnectConfig, PrebuiltVoiceConfig, VoiceConfig, SpeechConfig,
    Blob, GenerationConfig, FunctionDeclaration, Tool, Content, Part,
    StartSensitivity, EndSensitivity
)
import numpy as np
from pydub import AudioSegment
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import system prompts
from prompts import (
    create_tenant_prompt,
    create_lead_prompt,
    create_new_caller_prompt,
    create_generalized_prompt
)

# Import database module
from database import (
    init_db_pool, close_db_pool, identify_caller, test_database_connection,
    save_ticket, save_lead_information
)

# Import ticket category matching
from ticket_categories import TicketCategoryMatcher

# Configure detailed logging to both file and console
# Use Indian Standard Time (IST)
IST = ZoneInfo("Asia/Kolkata")
os.makedirs("logs", exist_ok=True)
log_file = f"logs/voice_assistant_{datetime.now(IST).strftime('%Y%m%d')}.log"

# Create formatters with IST timezone
class ISTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=IST)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()

detailed_formatter = ISTFormatter(
    '%(asctime)s - %(name)s - [%(levelname)s] - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S IST'
)

# File handler - detailed logs
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(detailed_formatter)

# Console handler - less verbose with IST
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = ISTFormatter('%(asctime)s IST - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(console_formatter)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger(__name__)
logger.info(f"=" * 80)
logger.info(f"KOTS Voice Assistant Starting - Logs: {log_file}")
logger.info(f"=" * 80)

# Initialize FastAPI
app = FastAPI(title="KOTS Voice Assistant")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    logger.info("🚀 Application startup - Initializing database connection...")
    db_initialized = await init_db_pool()
    if db_initialized:
        # Test the connection
        await test_database_connection()
        logger.info("✅ Database initialization complete")
    else:
        logger.warning("⚠️ Database initialization failed - continuing without database")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown"""
    logger.info("🛑 Application shutdown - Closing database connection...")
    await close_db_pool()
    logger.info("✅ Database connection closed")

# Environment variables
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CLOUD_RUN_URL = os.getenv("CLOUD_RUN_URL", "")

# Validate API key
if not GOOGLE_API_KEY:
    logger.error("GOOGLE_API_KEY not set!")
    raise ValueError("GOOGLE_API_KEY environment variable required")

# Audio configuration
EXOTEL_SAMPLE_RATE = 8000  # Exotel provides 8kHz
GEMINI_INPUT_RATE = 16000  # Gemini expects 16kHz
GEMINI_OUTPUT_RATE = 24000  # Gemini outputs 24kHz
CHUNK_SIZE = 3200  # 100ms at 16kHz

# Call management
MAX_CALL_DURATION = 1800  # 30 minutes max per call
AUDIO_TIMEOUT = 90  # 90 seconds without audio = disconnect
active_sessions: Dict[str, 'ExotelGeminiSession'] = {}

# Connection metrics
connection_metrics = {
    'total_calls': 0,
    'successful_calls': 0,
    'failed_calls': 0,
    'timeout_calls': 0,
    'active_calls': 0,
    'total_duration': 0,
    'longest_call': 0,
}

# Gemini client
client = genai.Client(api_key=GOOGLE_API_KEY, http_options={"api_version": "v1alpha"})

# API Base URL
KOTS_API_BASE = "https://kots-website-staging.quantaops.com/api"

# Define function declarations for Gemini to call
def _get_function_declarations():
    """Define all available functions for Gemini to call during conversation"""

    get_properties_function = FunctionDeclaration(
        name="get_properties_by_area",
        description="""Fetches all available properties and flats in a specific area of Bangalore.
        Use this when the user asks about:
        - Properties available in a location (e.g., "properties in Whitefield", "flats in Koramangala")
        - Availability in an area
        - What properties you have in a location
        Returns real-time property data including names, locations, and available flat counts.""",
        parameters={
            "type": "object",
            "properties": {
                "area": {
                    "type": "string",
                    "description": """The area name in Bangalore. Examples: 'bangalore' (for all), 'whitefield', 'koramangala', 'marathahalli', 'bellandur', 'hennur', 'sarjapur', 'hsr', 'mahadevpura'.
                    Use 'bangalore' to get all properties across Bangalore."""
                }
            },
            "required": ["area"]
        }
    )

    get_flat_details_function = FunctionDeclaration(
        name="get_flat_details",
        description="""Fetches detailed information about a specific property or flat.
        Use this when the user asks about:
        - Details of a specific property (e.g., "tell me about KOTS RUE", "what's available in KOTS SEREIN")
        - Specific flat information (e.g., "details of flat K05A205")
        - Amenities, pricing, or features of a property
        - City is always 'bangalore'
        Returns detailed property/flat information including amenities, pricing, availability, images, etc.""",
        parameters={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name. ALWAYS set this to 'bangalore'. Never use any other value.",
                    "enum": ["bangalore"]
                },
                "area": {
                    "type": "string",
                    "description": "Area name in lowercase (e.g., 'whitefield', 'marathahalli', 'bellandur', 'koramangala', 'hennur', 'sarjapur', 'hsr', 'mahadevpura')"
                },
                "slug": {
                    "type": "string",
                    "description": "Property slug in lowercase (e.g., 'kots-rue', 'kots-serein', 'kots-bien', 'kots-neuf'). Convert property names to slugs by using lowercase and hyphens."
                },
                "flat": {
                    "type": "string",
                    "description": "Optional: Specific flat code (e.g., 'k05a205', 'k16a101'). Only provide if user asks about a specific flat. Leave empty otherwise."
                }
            },
            "required": ["city", "area", "slug"]
        }
    )

    create_ticket_function = FunctionDeclaration(
        name="create_maintenance_ticket",
        description="""Creates a maintenance or service ticket for TENANTS ONLY.
        Use this when a TENANT reports:
        - Plumbing issues (leaks, taps, toilets, drainage)
        - Electrical issues (lights, fans, power, switches)
        - Appliance issues (AC, fridge, washing machine, geyser)
        - Carpenter issues (doors, cabinets, furniture)
        - WiFi issues (speed, connection, login)
        - Common area issues (cleanliness, security, parking, garbage)
        - Any other maintenance request

        IMPORTANT: Only call this for TENANTS. Do NOT call for leads or new callers.
        After calling this function, you will receive a ticket ID to confirm to the tenant.""",
        parameters={
            "type": "object",
            "properties": {
                "issue_type": {
                    "type": "string",
                    "description": """The type of issue being reported. Must be one of:
                    plumbing, electrical, carpenter, appliance, furniture, pest, wifi_speed, wifi_disconnection,
                    wifi_login, cleanliness, security, garbage, parking_issues, check_in, check_out,
                    rental_invoices, payment_link, one_time_housekeeping, car_parking, duplicate_keys,
                    water_can, callback, or other_flat_issues"""
                },
                "issue_description": {
                    "type": "string",
                    "description": "Detailed description of the issue in 1-2 sentences. Include location if mentioned (e.g., 'kitchen tap leaking', 'bedroom AC not cooling')."
                }
            },
            "required": ["issue_type", "issue_description"]
        }
    )

    collect_lead_info_function = FunctionDeclaration(
        name="collect_lead_information",
        description="""Collects and saves lead information for LEADS and NEW CALLERS ONLY when they enquire about properties.
        Use this when a LEAD or NEW CALLER:
        - Asks about available properties
        - Shows interest in viewing flats
        - Requests property details
        - Enquires about pricing or amenities

        IMPORTANT: Only call this for LEADS or NEW CALLERS. Do NOT call for tenants.
        Call this AFTER showing them property information to capture their interest.""",
        parameters={
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Name of the lead. If they haven't provided their name, use 'Not provided'. Never leave this empty."
                }
            },
            "required": ["customer_name"]
        }
    )

    return [get_properties_function, get_flat_details_function, create_ticket_function, collect_lead_info_function]


async def execute_function_call(function_name: str, function_args: Dict[str, Any], session: Optional['ExotelGeminiSession'] = None) -> Dict[str, Any]:
    """
    Execute the actual API calls when Gemini requests function execution

    Args:
        function_name: Name of the function to call
        function_args: Arguments provided by Gemini
        session: Optional session context for tenant-specific functions

    Returns:
        API response data
    """
    try:
        logger.info(f"📞 Executing function: {function_name} with args: {function_args}")

        async with httpx.AsyncClient(timeout=10.0) as http_client:
            if function_name == "get_properties_by_area":
                area = function_args.get("area", "bangalore")
                url = f"{KOTS_API_BASE}/getPropertiesAndFlats?area={area}"

                logger.info(f"🌐 Calling API: GET {url}")
                response = await http_client.get(url)
                response.raise_for_status()

                data = response.json()
                properties = data.get('properties', [])
                logger.info(f"✅ API returned {len(properties)} properties")

                # DEBUG: Log first 3 properties to see actual data structure
                for i, prop in enumerate(properties[:3]):
                    logger.info(f"🔍 Property {i+1}: name={prop.get('displayLocation')}, availableFlats={prop.get('availableFlats')}")

                # Filter by area first (API doesn't filter correctly, so we do it client-side)
                if area.lower() != "bangalore":
                    # Only include properties where displayLocation contains the requested area
                    properties = [
                        p for p in properties
                        if area.lower() in p.get("displayLocation", "").lower()
                    ]
                    logger.info(f"📍 After area filtering: {len(properties)} properties in {area}")

                # Then filter by availability (API uses camelCase!)
                available_properties = [p for p in properties if p.get("availableFlats", 0) > 0]
                logger.info(f"📊 Final result: {len(available_properties)} available properties in {area}")

                if not available_properties:
                    return f"I found {len(properties)} properties in {area}, but currently all flats are occupied. Would you like me to notify you when flats become available?"

                # Get top 2 properties with highest availability
                top_2 = sorted(available_properties, key=lambda x: x.get("availableFlats", 0), reverse=True)[:2]

                # Create a simple, conversational response
                property_list = []
                for prop in top_2:
                    name = prop.get("displayLocation", "Unknown")
                    available = prop.get("availableFlats", 0)
                    property_list.append(f"{name} with {available} flats available")

                # Return a concise response with only top 2
                if len(available_properties) > 2:
                    response_text = f"I found {len(available_properties)} properties with availability in {area}. Top 2 are: " + " and ".join(property_list) + ". Would you like details on any of these?"
                else:
                    response_text = f"I found {len(available_properties)} properties with availability in {area}: " + " and ".join(property_list) + ". Would you like more details?"

                return response_text

            elif function_name == "get_flat_details":
                city = function_args.get("city", "bangalore")
                area = function_args.get("area")
                slug = function_args.get("slug")
                flat = function_args.get("flat")

                url = f"{KOTS_API_BASE}/getFriendlyUrls"
                payload = {
                    "slug": {
                        "city": city,
                        "area": area,
                        "slug": slug
                    }
                }

                # Add flat code if provided
                if flat:
                    payload["slug"]["flat"] = flat

                logger.info(f"🌐 Calling API: POST {url} with payload: {payload}")
                response = await http_client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()
                logger.info(f"✅ API returned flat details for {slug}")

                # Extract key details and create conversational response
                property_name = data.get('property', {}).get('name', slug)
                flat_info = data.get('flat', {})
                bhk = flat_info.get('bhk_type', 'N/A')
                price = flat_info.get('price', 'Contact us')

                response_text = f"I found details for {property_name}. "
                if flat:
                    response_text += f"The flat {flat} is a {bhk} priced at {price}."
                else:
                    response_text += f"This property has various flats available. Would you like details on a specific flat?"

                return response_text

            elif function_name == "create_maintenance_ticket":
                # Validate tenant status
                if not session or session.caller_type != "tenant":
                    logger.warning(f"⚠️ Ticket creation attempted by non-tenant (type: {session.caller_type if session else 'unknown'})")
                    return "I apologize, but I can only create maintenance tickets for registered tenants. How else can I help you?"

                if not session.caller_data:
                    logger.error("❌ Ticket creation failed: No tenant data available")
                    return "I'm having trouble accessing your tenant information. Please try again."

                # Extract arguments
                issue_type = function_args.get("issue_type", "other_flat_issues")
                issue_description = function_args.get("issue_description", "Tenant reported an issue via voice assistant")

                logger.info(f"🎫 Creating ticket for tenant: {session.caller_data.get('name')} (Flat: {session.caller_data.get('flat')})")
                logger.info(f"   Issue Type: {issue_type}")
                logger.info(f"   Description: {issue_description}")

                # Get category info from ticket matcher
                category_info = session.ticket_matcher.get_category_info(issue_type)
                if not category_info:
                    logger.warning(f"⚠️ Unknown issue type: {issue_type}, using fallback")
                    category_info = session.ticket_matcher.get_category_info("other_flat_issues")

                # Create ticket in database
                ticket_id = await save_ticket(
                    tenant_data=session.caller_data,
                    category_info=category_info,
                    issue_description=issue_description
                )

                if ticket_id:
                    session.ticket_created = True
                    session.ticket_id = ticket_id
                    logger.info(f"✅ Ticket #{ticket_id} created successfully!")
                    return f"I've created maintenance ticket number {ticket_id} for your {category_info['issue_type']}. Our team will reach out to you shortly."
                else:
                    logger.error("❌ Failed to create ticket in database")
                    return "I apologize, but I'm having trouble creating the ticket right now. I'll notify our team about your issue through another channel."

            elif function_name == "collect_lead_information":
                # Validate lead/new_caller status
                if not session or session.caller_type == "tenant":
                    logger.warning(f"⚠️ Lead data collection attempted by tenant")
                    return "Thank you for your interest! Is there anything else I can help you with?"

                # Extract customer name
                customer_name = function_args.get("customer_name", "Not provided")

                # Determine lead status
                if session.caller_type == "lead":
                    lead_status = "existing"
                    logger.info(f"📋 Collecting data for EXISTING LEAD")
                else:  # new_caller
                    lead_status = "new"
                    logger.info(f"📋 Collecting data for NEW LEAD")

                logger.info(f"   Name: {customer_name}")
                logger.info(f"   Phone: {session.caller_number}")
                logger.info(f"   Status: {lead_status}")

                # Save lead information to database
                lead_id = await save_lead_information(
                    caller_number=session.caller_number,
                    call_sid=session.call_sid,
                    customer_name=customer_name if customer_name != "Not provided" else None,
                    lead_status=lead_status,
                    call_duration=None  # Will be updated at call end
                )

                if lead_id:
                    logger.info(f"✅ Lead #{lead_id} saved successfully!")
                    return "Thank you for your interest! Our team will reach out to you shortly with more details about our properties. Is there anything else you'd like to know?"
                else:
                    logger.error("❌ Failed to save lead information")
                    return "Thank you for your interest! Our team will contact you soon. Is there anything else I can help you with?"

            else:
                logger.error(f"❌ Unknown function: {function_name}")
                return f"I encountered an error: unknown function {function_name}. Please try again."

    except httpx.HTTPError as e:
        logger.error(f"❌ HTTP error calling API: {e}")
        return f"I'm having trouble connecting to our property database right now. Please try again in a moment."
    except Exception as e:
        logger.error(f"❌ Error executing function {function_name}: {e}", exc_info=True)
        return f"I encountered an error while fetching the information. Please try again."


class AudioResampler:
    """Handle audio resampling between different sample rates"""

    @staticmethod
    def resample_audio(audio_data: bytes, from_rate: int, to_rate: int, channels: int = 1) -> bytes:
        """Resample audio from one rate to another"""
        try:
            # Check if data length is valid (must be multiple of sample_width * channels)
            sample_width = 2  # 16-bit = 2 bytes
            frame_size = sample_width * channels

            # Pad audio data if necessary
            remainder = len(audio_data) % frame_size
            if remainder != 0:
                padding_needed = frame_size - remainder
                audio_data = audio_data + (b'\x00' * padding_needed)
                logger.debug(f"Padded audio data by {padding_needed} bytes")

            # Convert bytes to AudioSegment
            audio = AudioSegment(
                data=audio_data,
                sample_width=sample_width,
                frame_rate=from_rate,
                channels=channels
            )

            # Resample
            resampled = audio.set_frame_rate(to_rate)

            # Convert back to bytes
            return resampled.raw_data
        except Exception as e:
            logger.error(f"Error resampling audio: {e}")
            return audio_data


class ExotelGeminiSession:
    """Manages a single call session between Exotel and Gemini"""

    def __init__(self, call_sid: str, exotel_ws: WebSocket):
        self.call_sid = call_sid
        self.exotel_ws = exotel_ws
        self.gemini_session = None
        self.audio_queue = asyncio.Queue()
        self.is_active = True
        self.resampler = AudioResampler()
        self.start_time = time.time()
        self.last_audio_time = None
        self.audio_received = False
        self.caller_number = None
        self.caller_type = None  # Will be set to 'tenant', 'lead', or 'new_caller'
        self.caller_data = None  # Will contain caller details from database

        # Ticket management (Step 3) - Using function calling
        self.ticket_matcher = TicketCategoryMatcher()
        self.ticket_created = False
        self.ticket_id = None

    async def start(self):
        """Start the Gemini Live session"""
        try:
            logger.info(f"Starting Gemini session for call {self.call_sid}")

            # Get dynamic system prompt based on caller type
            if self.caller_type == "tenant" and self.caller_data:
                system_prompt = create_tenant_prompt(self.caller_data)
                logger.info(f"[{self.call_sid}] Using TENANT prompt for {self.caller_data.get('name')}")
            elif self.caller_type == "lead" and self.caller_data:
                system_prompt = create_lead_prompt(self.caller_data)
                logger.info(f"[{self.call_sid}] Using LEAD prompt for {self.caller_data.get('name')}")
            elif self.caller_type == "new_caller":
                system_prompt = create_new_caller_prompt()
                logger.info(f"[{self.call_sid}] Using NEW CALLER prompt")
            else:
                # Fallback to generalized prompt if caller type is unknown
                system_prompt = create_generalized_prompt()
                logger.warning(f"[{self.call_sid}] Using GENERALIZED FALLBACK prompt (caller_type={self.caller_type})")

            # Get function declarations
            function_declarations = _get_function_declarations()
            logger.info(f"[{self.call_sid}] Configured {len(function_declarations)} functions: {[f.name for f in function_declarations]}")

            # Create Tool with all function declarations
            tools = [Tool(function_declarations=function_declarations)]

            # Create config with system instruction and tools
            # Temperature 0.3 for strict adherence with slight natural variation
            config = LiveConnectConfig(
                response_modalities=["AUDIO"],
                system_instruction=system_prompt,  # System prompt
                tools=tools,  # Enable function calling
                generation_config={
                    "temperature": 0.3,  # Low for strict guardrails with natural responses
                    "top_p": 0.8,
                    "top_k": 40
                },
                # Configure for INSTANT responses - no waiting for silence
                realtime_input_config={
                    "automatic_activity_detection": {
                        "disabled": False,
                        "start_of_speech_sensitivity": StartSensitivity.START_SENSITIVITY_HIGH,  # Detect speech instantly
                        "end_of_speech_sensitivity": EndSensitivity.END_SENSITIVITY_HIGH,  # Detect end instantly
                        "prefix_padding_ms": 0,  # Zero padding - immediate start
                        "silence_duration_ms": 50,  # Absolute minimum - respond almost instantly (50ms)
                    }
                },
                # Enable transcription for both input and output audio
                output_audio_transcription={},  # Transcribe Gemini's responses
                input_audio_transcription={}    # Transcribe user's speech
            )

            logger.info(f"[{self.call_sid}] LiveConnectConfig created with INSTANT response mode (50ms silence, zero padding)")

            # Configure speech settings
            config.speech_config = SpeechConfig(
                voice_config=VoiceConfig(
                    prebuilt_voice_config=PrebuiltVoiceConfig(
                        voice_name="Charon"  # Clear voice that works well with Indian accent
                    )
                ),
                language_code="en-IN"  # Indian English for better accent recognition
            )

    

            logger.info(f"[{self.call_sid}] Connecting to Gemini Live API...")

            # Connect to Gemini with the Live model
            async with client.aio.live.connect(
                model="gemini-2.0-flash-live-001",
                config=config
            ) as session:
                self.gemini_session = session
                logger.info(f"✅ Gemini session connected for call {self.call_sid}")
                logger.info(f"[{self.call_sid}] System prompt configured in session")

                # Wait for user to speak first - do NOT send greeting
                logger.info(f"[{self.call_sid}] ⏳ Ready - waiting for user to speak")

                # Run bidirectional audio streaming
                # Do NOT send system prompt separately - it's in the config!
                await asyncio.gather(
                    self._send_audio_to_gemini(),
                    self._receive_audio_from_gemini(),
                    return_exceptions=True
                )

        except Exception as e:
            logger.error(f"Error in Gemini session: {e}", exc_info=True)
        finally:
            self.is_active = False
            logger.info(f"Gemini session ended for call {self.call_sid}")

    async def _send_audio_to_gemini(self):
        """Send audio from Exotel to Gemini (8kHz → 16kHz)"""
        audio_chunks_sent = 0
        try:
            logger.debug(f"[{self.call_sid}] Starting audio send loop to Gemini")

            while self.is_active:
                # Get audio from queue
                exotel_audio = await asyncio.wait_for(
                    self.audio_queue.get(),
                    timeout=30.0
                )

                if exotel_audio is None:
                    logger.debug(f"[{self.call_sid}] Received stop signal in audio send loop")
                    break

                # Log audio chunk details
                logger.debug(f"[{self.call_sid}] 🎤 Received audio chunk: {len(exotel_audio)} bytes at 8kHz")

                # Resample 8kHz → 16kHz for Gemini
                gemini_audio = self.resampler.resample_audio(
                    exotel_audio,
                    from_rate=EXOTEL_SAMPLE_RATE,
                    to_rate=GEMINI_INPUT_RATE
                )

                logger.debug(f"[{self.call_sid}] 🔄 Resampled to 16kHz: {len(gemini_audio)} bytes")

                # Create audio blob
                audio_blob = Blob(
                    mime_type="audio/pcm",
                    data=gemini_audio
                )

                # Send to Gemini using send_realtime_input (the correct method for multi-turn)
                await self.gemini_session.send_realtime_input(audio=audio_blob)
                audio_chunks_sent += 1

                if audio_chunks_sent % 100 == 0:  # Log every 100 chunks (reduced verbosity)
                    logger.info(f"[{self.call_sid}] ✅ Sent {audio_chunks_sent} audio chunks to Gemini")

            logger.info(f"[{self.call_sid}] Audio send loop ended. Total chunks sent: {audio_chunks_sent}")

        except asyncio.TimeoutError:
            logger.warning(f"[{self.call_sid}] ⏱️ No audio received for 30s, closing session")
        except Exception as e:
            logger.error(f"[{self.call_sid}] ❌ Error sending audio to Gemini: {e}", exc_info=True)

    async def _receive_audio_from_gemini(self):
        """Receive audio from Gemini and send to Exotel (24kHz → 8kHz)"""
        audio_chunks_received = 0
        text_responses = []
        turn_count = 0

        try:
            logger.debug(f"[{self.call_sid}] Starting audio receive loop from Gemini")

            # Keep receiving while session is active
            # The outer loop handles iterator restarts (Gemini's receive() can complete after responses)
            while self.is_active and self.gemini_session:
                try:
                    async for response in self.gemini_session.receive():
                        if not self.is_active:
                            logger.info(f"[{self.call_sid}] Session marked inactive, stopping receive loop")
                            break

                        logger.debug(f"[{self.call_sid}] 📨 Received response from Gemini")

                        # FIRST: Check for function/tool calls at response level (CRITICAL!)
                        if hasattr(response, 'tool_call') and response.tool_call:
                            logger.info(f"[{self.call_sid}] 🎯 TOOL CALL DETECTED at response level!")

                            # Extract function_calls list from tool_call
                            tool_call = response.tool_call
                            function_calls_list = []

                            # Handle different possible structures
                            if hasattr(tool_call, 'function_calls'):
                                function_calls_list = tool_call.function_calls
                            elif isinstance(tool_call, list):
                                function_calls_list = tool_call
                            else:
                                function_calls_list = [tool_call]

                            # Process each function call
                            for func_call in function_calls_list:
                                function_name = func_call.name
                                function_args = dict(func_call.args)
                                function_id = func_call.id  # CRITICAL: Extract the ID

                                logger.info(f"[{self.call_sid}] 🔧 Function call requested: {function_name}")
                                logger.info(f"[{self.call_sid}] 📋 Arguments: {function_args}")
                                logger.info(f"[{self.call_sid}] 🆔 Function ID: {function_id}")

                                # Execute the function (pass session for ticket creation)
                                function_result = await execute_function_call(function_name, function_args, session=self)

                                # Log the result (now a string)
                                result_preview = function_result[:100] + "..." if len(function_result) > 100 else function_result
                                logger.info(f"[{self.call_sid}] ✅ Function executed successfully")
                                logger.info(f"[{self.call_sid}] 📝 Response preview: {result_preview}")

                                # Send result back with ID (CRITICAL!)
                                try:
                                    await self.gemini_session.send_tool_response(
                                        function_responses=[{
                                            "id": function_id,  # MUST include ID from tool_call
                                            "name": function_name,
                                            "response": {"result": function_result}  # Must wrap string in dict!
                                        }]
                                    )
                                    logger.info(f"[{self.call_sid}] 📤 Function response sent back to Gemini")
                                except Exception as e:
                                    logger.error(f"[{self.call_sid}] ❌ Error sending tool response: {e}", exc_info=True)

                        # THEN: Check for audio and text in server_content.model_turn.parts
                        if hasattr(response, 'server_content') and response.server_content:
                            if hasattr(response.server_content, 'model_turn') and response.server_content.model_turn:
                                model_turn = response.server_content.model_turn
                                if hasattr(model_turn, 'parts') and model_turn.parts:
                                    for part in model_turn.parts:
                                        # Handle audio data in inline_data
                                        if hasattr(part, 'inline_data') and part.inline_data:
                                            logger.debug(f"[{self.call_sid}] 🔊 Audio data found in inline_data")

                                            # Get audio bytes from inline_data
                                            gemini_audio = part.inline_data.data
                                            logger.debug(f"[{self.call_sid}] Received audio: {len(gemini_audio)} bytes at 24kHz")

                                            # Resample 24kHz → 8kHz for Exotel
                                            exotel_audio = self.resampler.resample_audio(
                                                gemini_audio,
                                                from_rate=GEMINI_OUTPUT_RATE,
                                                to_rate=EXOTEL_SAMPLE_RATE
                                            )

                                            logger.debug(f"[{self.call_sid}] 🔄 Resampled to 8kHz: {len(exotel_audio)} bytes")

                                            # Send to Exotel via WebSocket
                                            await self.exotel_ws.send_json({
                                                "event": "media",
                                                "media": {
                                                    "payload": base64.b64encode(exotel_audio).decode('utf-8')
                                                }
                                            })

                                            audio_chunks_received += 1
                                            if audio_chunks_received % 100 == 0:  # Log every 100 chunks (reduced verbosity)
                                                logger.info(f"[{self.call_sid}] ✅ Sent {audio_chunks_received} audio chunks to Exotel")

                                        # Handle text transcriptions
                                        if hasattr(part, 'text') and part.text:
                                            logger.info(f"[{self.call_sid}] 🤖 Assistant said: {part.text}")
                                            text_responses.append(part.text)

                                # Handle audio transcriptions
                                if hasattr(response.server_content, 'output_transcription') and response.server_content.output_transcription:
                                    if hasattr(response.server_content.output_transcription, 'text') and response.server_content.output_transcription.text:
                                        transcript_text = response.server_content.output_transcription.text
                                        logger.info(f"[{self.call_sid}] 📝 ASSISTANT TRANSCRIPT: {transcript_text}")
                                        text_responses.append(transcript_text)

                                if hasattr(response.server_content, 'input_transcription') and response.server_content.input_transcription:
                                    if hasattr(response.server_content.input_transcription, 'text') and response.server_content.input_transcription.text:
                                        user_transcript = response.server_content.input_transcription.text
                                        logger.info(f"[{self.call_sid}] 👤 USER TRANSCRIPT: {user_transcript}")

                                # Handle turn completion
                                if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                                    turn_count += 1
                                    logger.info(f"[{self.call_sid}] 🔄 Turn #{turn_count} complete - Gemini finished speaking")
                                    logger.info(f"[{self.call_sid}] Turn #{turn_count} audio chunks sent this turn: {audio_chunks_received}")

                except StopAsyncIteration:
                    # Iterator completed, will restart if session still active
                    if self.is_active:
                        logger.debug(f"[{self.call_sid}] Iterator completed, restarting receive loop...")
                        await asyncio.sleep(0.01)
                        continue
                    else:
                        break

            logger.info(f"[{self.call_sid}] Audio receive loop ended")
            logger.info(f"[{self.call_sid}] Total turns: {turn_count}, Total audio chunks: {audio_chunks_received}")

        except Exception as e:
            logger.error(f"[{self.call_sid}] ❌ Error receiving audio from Gemini: {e}", exc_info=True)

    async def add_audio(self, audio_data: bytes):
        """Add incoming audio from Exotel to processing queue"""
        if not self.audio_received:
            self.audio_received = True
            duration = time.time() - self.start_time
            logger.info(f"[{self.call_sid}] ✅ First audio received after {duration:.1f}s")

        self.last_audio_time = time.time()
        await self.audio_queue.put(audio_data)

    async def stop(self):
        """Stop the session and update metrics"""
        self.is_active = False
        await self.audio_queue.put(None)

        # Calculate call duration
        duration = time.time() - self.start_time
        connection_metrics['total_duration'] += duration

        if duration > connection_metrics['longest_call']:
            connection_metrics['longest_call'] = duration

        if self.audio_received:
            connection_metrics['successful_calls'] += 1

        logger.info(f"[{self.call_sid}] Call ended - Duration: {duration:.1f}s, Audio: {self.audio_received}")


@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "KOTS Voice Assistant",
        "timestamp": datetime.now(IST).isoformat(),
        "gemini_configured": bool(GOOGLE_API_KEY),
        "active_calls": len(active_sessions),
        "total_calls_handled": connection_metrics['total_calls'],
        "success_rate": round(
            (connection_metrics['successful_calls'] / connection_metrics['total_calls'] * 100)
            if connection_metrics['total_calls'] > 0 else 0,
            2
        )
    }


@app.post("/exotel/answer")
async def exotel_answer_webhook(request: Request):
    """
    Exotel calls this endpoint when a call is received
    Returns XML to configure call flow
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    from_number = form_data.get("From", "unknown")
    to_number = form_data.get("To", "unknown")

    logger.info(f"📞 Incoming call: {call_sid} from {from_number} to {to_number}")

    # Construct WebSocket URL for streaming
    ws_url = f"{CLOUD_RUN_URL.replace('https://', 'wss://')}/exotel/stream"

    # Return Exotel XML with Voicebot applet
    # The <Say> message helps fill the ~7 second initialization gap
    xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Thank you for calling KOTS. Please wait while we connect you to our AI assistant.</Say>
    <VoiceBot>
        <WebSocketUrl>{ws_url}</WebSocketUrl>
    </VoiceBot>
</Response>"""

    return Response(content=xml_response, media_type="application/xml")


@app.get("/exotel/stream-url")
async def get_stream_url():
    """Returns dynamic WebSocket URL for Exotel configuration"""
    ws_url = f"{CLOUD_RUN_URL.replace('https://', 'wss://')}/exotel/stream"
    return {"websocket_url": ws_url}


@app.websocket("/exotel/stream")
async def exotel_stream_handler(websocket: WebSocket):
    """
    WebSocket endpoint for Exotel voice streaming
    Handles bidirectional audio between Exotel and Gemini
    """
    call_sid = None
    session = None

    try:
        # Accept WebSocket connection
        await websocket.accept()
        logger.info("📡 WebSocket connection established with Exotel")

        # Update metrics
        connection_metrics['total_calls'] += 1
        connection_metrics['active_calls'] = len(active_sessions) + 1

        # Wait for connected or start event from Exotel
        first_message = None
        try:
            first_message = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=10.0
            )
            logger.info(f"📨 First message from Exotel: {first_message.get('event')}")
        except asyncio.TimeoutError:
            logger.error("⏱️ Timeout waiting for initial event from Exotel")
            connection_metrics['failed_calls'] += 1
            await websocket.close(code=1008, reason="No initial event received")
            return

        # Handle 'connected' event - wait for 'start' event next
        if first_message.get("event") == "connected":
            logger.info("✅ Received 'connected' event, waiting for 'start' event...")
            try:
                start_message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=10.0
                )
                logger.info(f"📨 Second message from Exotel: {start_message.get('event')}")
            except asyncio.TimeoutError:
                logger.error("⏱️ Timeout waiting for start event after connected")
                connection_metrics['failed_calls'] += 1
                await websocket.close(code=1008, reason="No start event after connected")
                return
        else:
            start_message = first_message

        if start_message.get("event") == "start":
            # Extract call information
            start_data = start_message.get("start", {})
            call_sid = start_data.get("callSid", f"call_{int(time.time())}")
            caller_number = start_data.get("from", "unknown")

            logger.info(f"🎙️ Call started: {call_sid}")
            logger.info(f"📞 Caller: {caller_number}")

            # Identify caller type (tenant/lead/new_caller)
            caller_info = await identify_caller(caller_number)
            caller_type = caller_info.get("type")
            caller_data = caller_info.get("data")

            # Log caller identification
            if caller_type == "tenant":
                logger.info(f"👤 TENANT identified: {caller_data['name']} (ID: {caller_data['tenant_id']}, Flat: {caller_data['flat']})")
            elif caller_type == "lead":
                logger.info(f"👤 LEAD identified: {caller_data['name']} (ID: {caller_data['lead_id']})")
            else:
                logger.info(f"👤 NEW CALLER identified: {caller_number}")

            # Create and start Gemini session
            session = ExotelGeminiSession(call_sid, websocket)
            session.caller_number = caller_number
            session.caller_type = caller_type
            session.caller_data = caller_data
            active_sessions[call_sid] = session

            # Start Gemini task
            gemini_task = asyncio.create_task(session.start())

            # Process incoming messages from Exotel
            while session.is_active:
                try:
                    # Check timeouts
                    current_time = time.time()

                    # Max call duration check
                    if (current_time - session.start_time) > MAX_CALL_DURATION:
                        logger.warning(f"[{call_sid}] ⏱️ Max call duration reached ({MAX_CALL_DURATION}s)")
                        await websocket.close(code=1000, reason="Max duration reached")
                        break

                    # Audio timeout check
                    if session.audio_received and session.last_audio_time:
                        silence_duration = current_time - session.last_audio_time
                        if silence_duration > AUDIO_TIMEOUT:
                            logger.warning(f"[{call_sid}] ⏱️ Audio timeout - no audio for {silence_duration:.1f}s")
                            connection_metrics['timeout_calls'] += 1
                            await websocket.close(code=1008, reason="Audio timeout")
                            break

                    # Receive message with timeout
                    message = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=5.0
                    )

                    event = message.get("event")

                    if event == "media":
                        # Extract and process audio payload
                        payload = message.get("media", {}).get("payload")
                        if payload:
                            try:
                                audio_data = base64.b64decode(payload)
                                logger.debug(f"[{call_sid}] 📥 Received media event: {len(payload)} chars base64, {len(audio_data)} bytes raw")
                                await session.add_audio(audio_data)
                            except Exception as audio_err:
                                logger.error(f"[{call_sid}] ❌ Audio processing error: {audio_err}", exc_info=True)

                    elif event == "stop":
                        logger.info(f"[{call_sid}] 📴 Stop event received")
                        break

                    elif event == "mark":
                        mark_name = message.get("mark", {}).get("name", "unknown")
                        logger.debug(f"[{call_sid}] Mark: {mark_name}")

                except asyncio.TimeoutError:
                    # Timeout on receive - check if session is still active
                    if not session.is_active:
                        break
                    continue

                except Exception as msg_err:
                    logger.error(f"[{call_sid}] Error processing message: {msg_err}")
                    break

            # Stop session
            if session:
                await session.stop()

            # Wait for Gemini task to complete (with timeout)
            try:
                await asyncio.wait_for(gemini_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning(f"[{call_sid}] Timeout waiting for Gemini task to finish")
                gemini_task.cancel()

        else:
            logger.error(f"Expected 'start' event, got: {start_message.get('event')}")
            connection_metrics['failed_calls'] += 1
            await websocket.close(code=1002, reason="Invalid start event")

    except WebSocketDisconnect:
        logger.info(f"[{call_sid}] WebSocket disconnected")
        if not session or not session.audio_received:
            connection_metrics['failed_calls'] += 1

    except Exception as e:
        logger.error(f"[{call_sid}] WebSocket error: {e}", exc_info=True)
        connection_metrics['failed_calls'] += 1

    finally:
        # Cleanup
        if session:
            await session.stop()

        if call_sid and call_sid in active_sessions:
            del active_sessions[call_sid]

        connection_metrics['active_calls'] = len(active_sessions)
        logger.info(f"[{call_sid}] Session cleaned up. Active calls: {len(active_sessions)}")


@app.post("/exotel/passthru")
async def exotel_passthru(request: Request):
    """
    Exotel calls this after the Voicebot applet completes
    Used for logging and analytics
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    status = form_data.get("Status", "unknown")
    duration = form_data.get("Duration", "0")

    logger.info(f"📊 Call completed: {call_sid}, Status: {status}, Duration: {duration}s")

    return PlainTextResponse("OK")


@app.get("/logs")
async def get_recent_logs(lines: int = 100):
    """Get recent log lines from the log file"""
    try:
        if not os.path.exists(log_file):
            return {"error": "Log file not found", "path": log_file}

        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return {
            "log_file": log_file,
            "total_lines": len(all_lines),
            "showing_lines": len(recent_lines),
            "logs": [line.strip() for line in recent_lines]
        }
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        return {"error": str(e)}


@app.get("/logs/download")
async def download_logs():
    """Download the full log file"""
    try:
        if not os.path.exists(log_file):
            return {"error": "Log file not found"}

        from fastapi.responses import FileResponse
        return FileResponse(
            path=log_file,
            filename=f"voice_assistant_{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}.log",
            media_type='text/plain'
        )
    except Exception as e:
        return {"error": str(e)}


@app.get("/stats")
async def get_stats():
    """Detailed stats endpoint with call metrics"""
    return {
        "service": "KOTS Voice Assistant",
        "status": "operational",
        "timestamp": datetime.now(IST).isoformat(),
        "metrics": {
            "total_calls": connection_metrics['total_calls'],
            "successful_calls": connection_metrics['successful_calls'],
            "failed_calls": connection_metrics['failed_calls'],
            "timeout_calls": connection_metrics['timeout_calls'],
            "active_calls": connection_metrics['active_calls'],
            "total_duration_seconds": round(connection_metrics['total_duration'], 2),
            "longest_call_seconds": round(connection_metrics['longest_call'], 2),
            "average_duration_seconds": round(
                connection_metrics['total_duration'] / connection_metrics['successful_calls']
                if connection_metrics['successful_calls'] > 0 else 0,
                2
            ),
        },
        "active_sessions": [
            {
                "call_sid": sid,
                "caller": session.caller_number,
                "caller_type": session.caller_type,
                "caller_name": session.caller_data.get('name') if session.caller_data else None,
                "duration": round(time.time() - session.start_time, 2),
                "audio_received": session.audio_received,
            }
            for sid, session in active_sessions.items()
        ],
        "config": {
            "max_call_duration": MAX_CALL_DURATION,
            "audio_timeout": AUDIO_TIMEOUT,
            "gemini_model": "gemini-2.0-flash-live-001",
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

"""
Database module for KOTS Voice Assistant
Handles PostgreSQL connections and caller identification
"""

import os
import logging
import asyncpg
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Database connection pool
db_pool = None


def normalize_phone_number(phone: str) -> list:
    """
    Normalize phone number to handle different formats

    Database formats: +918943864188, 918943864188
    Exotel format: 08943864188

    Returns list of possible phone number variations for matching
    """
    if not phone:
        return []

    # Remove all spaces, hyphens, parentheses
    cleaned = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    variations = []

    # If starts with 0, convert to +91 and 91 formats
    if cleaned.startswith("0"):
        without_zero = cleaned[1:]  # Remove leading 0
        variations.append(f"+91{without_zero}")  # +918943864188
        variations.append(f"91{without_zero}")   # 918943864188
        variations.append(without_zero)          # 8943864188

    # If starts with +91
    elif cleaned.startswith("+91"):
        variations.append(cleaned)                    # +918943864188
        variations.append(cleaned[1:])                # 918943864188
        variations.append(cleaned[3:])                # 8943864188
        variations.append(f"0{cleaned[3:]}")          # 08943864188

    # If starts with 91
    elif cleaned.startswith("91") and len(cleaned) > 10:
        variations.append(f"+{cleaned}")              # +918943864188
        variations.append(cleaned)                    # 918943864188
        variations.append(cleaned[2:])                # 8943864188
        variations.append(f"0{cleaned[2:]}")          # 08943864188

    # If just 10 digit number
    elif len(cleaned) == 10:
        variations.append(f"+91{cleaned}")            # +918943864188
        variations.append(f"91{cleaned}")             # 918943864188
        variations.append(cleaned)                    # 8943864188
        variations.append(f"0{cleaned}")              # 08943864188

    # Add original as fallback
    variations.append(cleaned)

    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for v in variations:
        if v not in seen:
            seen.add(v)
            unique_variations.append(v)

    logger.debug(f"Phone number variations for '{phone}': {unique_variations}")
    return unique_variations


async def init_db_pool():
    """Initialize database connection pool"""
    global db_pool

    try:
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")

        if not all([db_host, db_name, db_user, db_password]):
            logger.error("Missing database configuration in environment variables")
            return False

        logger.info(f"Connecting to database: {db_name} at {db_host}:{db_port}")

        db_pool = await asyncpg.create_pool(
            host=db_host,
            port=int(db_port),
            database=db_name,
            user=db_user,
            password=db_password,
            min_size=2,
            max_size=10,
            command_timeout=60
        )

        logger.info("✅ Database connection pool created successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to initialize database pool: {e}", exc_info=True)
        return False


async def close_db_pool():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed")


async def identify_caller(phone_number: str) -> Dict[str, Any]:
    """
    Identify caller type by checking phone number in database

    Returns:
        {
            "type": "tenant" | "lead" | "new_caller",
            "data": {...caller details...} or None
        }
    """
    if not db_pool:
        logger.error("Database pool not initialized")
        return {"type": "new_caller", "data": None}

    # Normalize phone number to handle format differences
    phone_variations = normalize_phone_number(phone_number)

    if not phone_variations:
        logger.warning(f"Could not normalize phone number: {phone_number}")
        return {"type": "new_caller", "data": None}

    logger.info(f"🔍 Identifying caller: {phone_number}")
    logger.debug(f"Checking variations: {phone_variations}")

    try:
        async with db_pool.acquire() as conn:
            # First, check if it's a TENANT
            logger.debug("Checking services_tenants table...")
            tenant_query = """
                SELECT bookingid, account_name, phone_number, email, flat
                FROM services_tenants
                WHERE phone_number = ANY($1::text[])
                LIMIT 1
            """

            tenant_row = await conn.fetchrow(tenant_query, phone_variations)

            if tenant_row:
                tenant_data = {
                    "tenant_id": tenant_row['bookingid'],
                    "name": tenant_row['account_name'],
                    "phone": tenant_row['phone_number'],
                    "email": tenant_row['email'],
                    "flat": tenant_row['flat']
                }
                logger.info(f"✅ TENANT identified: {tenant_data['name']} (ID: {tenant_data['tenant_id']})")
                return {
                    "type": "tenant",
                    "data": tenant_data
                }

            # Not a tenant, check if it's a LEAD
            logger.debug("Checking leads table...")
            lead_query = """
                SELECT id, customer_name, caller_number
                FROM leads
                WHERE caller_number = ANY($1::text[])
                LIMIT 1
            """

            lead_row = await conn.fetchrow(lead_query, phone_variations)

            if lead_row:
                lead_data = {
                    "lead_id": lead_row['id'],
                    "name": lead_row['customer_name'],
                    "phone": lead_row['caller_number']
                }
                logger.info(f"✅ LEAD identified: {lead_data['name']} (ID: {lead_data['lead_id']})")
                return {
                    "type": "lead",
                    "data": lead_data
                }

            # Not found in either table
            logger.info(f"📞 NEW CALLER identified: {phone_number}")
            return {
                "type": "new_caller",
                "data": None
            }

    except Exception as e:
        logger.error(f"❌ Error identifying caller: {e}", exc_info=True)
        # Fallback to new_caller on error
        return {
            "type": "new_caller",
            "data": None
        }


async def save_to_sales_webhook(
    name: str,
    phone: str,
    location: str,
    flat_type: str,
    channel: str = "Voice Call",
    campaign_id: str = ""
) -> Optional[int]:
    """
    Save sales lead information to sales_webhook table

    Args:
        name: Customer name
        phone: Phone number
        location: Preferred location (e.g., "HSR Layout", "Whitefield")
        flat_type: Flat type (e.g., "1BHK", "2BHK", "Studio")
        channel: Channel source (default: "Voice Call")
        campaign_id: Campaign ID (default: empty string)

    Returns:
        record_id (int) if successful, None if failed
    """
    if not db_pool:
        logger.error("Database pool not initialized")
        return None

    try:
        async with db_pool.acquire() as conn:
            insert_query = """
                INSERT INTO sales_webhook (
                    timestamp,
                    name,
                    phone,
                    channel,
                    campaign_id,
                    location,
                    flat_type
                ) VALUES (
                    CURRENT_TIMESTAMP,
                    $1, $2, $3, $4, $5, $6
                )
                RETURNING id
            """

            record_id = await conn.fetchval(
                insert_query,
                name,
                phone,
                channel,
                campaign_id,
                location,
                flat_type
            )

            logger.info(f"✅ Sales lead saved to sales_webhook! ID: {record_id}")
            logger.info(f"   Name: {name}")
            logger.info(f"   Phone: {phone}")
            logger.info(f"   Location: {location}")
            logger.info(f"   Flat Type: {flat_type}")

            return record_id

    except Exception as e:
        logger.error(f"❌ Error saving to sales_webhook: {e}", exc_info=True)
        return None


async def save_to_landlord_webhook(
    name: str,
    phone: str,
    channel: str = "Voice Call",
    campaign_id: str = ""
) -> Optional[int]:
    """
    Save landlord information to landlord_webhook table

    Args:
        name: Landlord name
        phone: Phone number
        channel: Channel source (default: "Voice Call")
        campaign_id: Campaign ID (default: empty string)

    Returns:
        record_id (int) if successful, None if failed
    """
    if not db_pool:
        logger.error("Database pool not initialized")
        return None

    try:
        async with db_pool.acquire() as conn:
            insert_query = """
                INSERT INTO landlord_webhook (
                    timestamp,
                    name,
                    phone,
                    channel,
                    campaign_id
                ) VALUES (
                    CURRENT_TIMESTAMP,
                    $1, $2, $3, $4
                )
                RETURNING id
            """

            record_id = await conn.fetchval(
                insert_query,
                name,
                phone,
                channel,
                campaign_id
            )

            logger.info(f"✅ Landlord saved to landlord_webhook! ID: {record_id}")
            logger.info(f"   Name: {name}")
            logger.info(f"   Phone: {phone}")

            return record_id

    except Exception as e:
        logger.error(f"❌ Error saving to landlord_webhook: {e}", exc_info=True)
        return None


async def save_to_service_webhook(
    name: str,
    phone: str,
    booking_id: str,
    ticket_category: str,
    ticket_description: str,
    channel: str = "Voice Call"
) -> Optional[int]:
    """
    Save tenant service request to service_webhook table

    Args:
        name: Tenant name
        phone: Phone number
        booking_id: Booking ID from services_tenants
        ticket_category: Category (e.g., "Maintenance", "Plumbing")
        ticket_description: Description of the issue
        channel: Channel source (default: "Voice Call")

    Returns:
        record_id (int) if successful, None if failed
    """
    if not db_pool:
        logger.error("Database pool not initialized")
        return None

    try:
        async with db_pool.acquire() as conn:
            insert_query = """
                INSERT INTO service_webhook (
                    timestamp,
                    name,
                    phone,
                    channel,
                    booking_id,
                    ticket_category,
                    ticket_description
                ) VALUES (
                    CURRENT_TIMESTAMP,
                    $1, $2, $3, $4, $5, $6
                )
                RETURNING id
            """

            record_id = await conn.fetchval(
                insert_query,
                name,
                phone,
                channel,
                booking_id,
                ticket_category,
                ticket_description
            )

            logger.info(f"✅ Service request saved to service_webhook! ID: {record_id}")
            logger.info(f"   Name: {name}")
            logger.info(f"   Booking ID: {booking_id}")
            logger.info(f"   Category: {ticket_category}")

            return record_id

    except Exception as e:
        logger.error(f"❌ Error saving to service_webhook: {e}", exc_info=True)
        return None


async def save_to_contact_logs(
    name: str,
    phone: str,
    channel: str = "Voice Call",
    campaign_id: str = ""
) -> Optional[int]:
    """
    Save all contact logs to capture_contact_logs table
    Called for EVERY call to track analytics

    Args:
        name: Caller name (if available)
        phone: Phone number
        channel: Channel source (default: "Voice Call")
        campaign_id: Campaign ID (default: empty string)

    Returns:
        record_id (int) if successful, None if failed
    """
    if not db_pool:
        logger.error("Database pool not initialized")
        return None

    try:
        async with db_pool.acquire() as conn:
            insert_query = """
                INSERT INTO capture_contact_logs (
                    timestamp,
                    name,
                    phone,
                    channel,
                    campaign_id
                ) VALUES (
                    CURRENT_TIMESTAMP,
                    $1, $2, $3, $4
                )
                RETURNING id
            """

            record_id = await conn.fetchval(
                insert_query,
                name,
                phone,
                channel,
                campaign_id
            )

            logger.info(f"✅ Contact logged to capture_contact_logs! ID: {record_id}")

            return record_id

    except Exception as e:
        logger.error(f"❌ Error saving to capture_contact_logs: {e}", exc_info=True)
        return None


async def save_to_need_call_back_webhook(
    name: str,
    phone: str,
    callback_type: str,  # "Sales" or "Service"
    channel: str = "Voice Call",
    # Sales-specific fields
    location: str = None,
    flat_type: str = None,
    # Service-specific fields
    booking_id: str = "",
    ticket_category: str = None,
    ticket_description: str = None,
    call_transcript: str = None
) -> Optional[int]:
    """
    Save callback request to need_call_back_webhook table
    This is for users who explicitly request to speak with a human

    Args:
        name: Customer name
        phone: Phone number
        callback_type: "Sales" or "Service"
        channel: Channel source (default: "Voice Call")
        location: For Sales - preferred location
        flat_type: For Sales - flat type preference
        booking_id: For Service - tenant booking ID
        ticket_category: For Service - issue category
        ticket_description: For Service - issue description
        call_transcript: Optional call transcript

    Returns:
        record_id (int) if successful, None if failed
    """
    if not db_pool:
        logger.error("Database pool not initialized")
        return None

    try:
        async with db_pool.acquire() as conn:
            insert_query = """
                INSERT INTO need_call_back_webhook (
                    name,
                    phone,
                    channel,
                    call_type,
                    location,
                    flat_type,
                    booking_id,
                    ticket_category,
                    ticket_description,
                    call_transcript
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
                )
                RETURNING id
            """

            record_id = await conn.fetchval(
                insert_query,
                name,
                phone,
                channel,
                callback_type,
                location,
                flat_type,
                booking_id,
                ticket_category,
                ticket_description,
                call_transcript
            )

            logger.info(f"✅ Callback request saved to need_call_back_webhook! ID: {record_id}")
            logger.info(f"   Name: {name}")
            logger.info(f"   Phone: {phone}")
            logger.info(f"   Type: {callback_type}")
            if callback_type == "Sales":
                logger.info(f"   Location: {location}")
                logger.info(f"   Flat Type: {flat_type}")
            else:
                logger.info(f"   Booking ID: {booking_id}")
                logger.info(f"   Ticket Category: {ticket_category}")
                logger.info(f"   Ticket Description: {ticket_description}")

            return record_id

    except Exception as e:
        logger.error(f"❌ Error saving to need_call_back_webhook: {e}", exc_info=True)
        return None


async def test_database_connection():
    """Test database connection and queries"""
    try:
        if not db_pool:
            logger.error("Database pool not initialized")
            return False

        async with db_pool.acquire() as conn:
            # Test connection
            version = await conn.fetchval('SELECT version()')
            logger.info(f"✅ Database connection test successful")
            logger.debug(f"PostgreSQL version: {version}")

            # Test tenants table
            tenant_count = await conn.fetchval('SELECT COUNT(*) FROM services_tenants')
            logger.info(f"📊 services_tenants table: {tenant_count} records")

            # Test leads table
            lead_count = await conn.fetchval('SELECT COUNT(*) FROM leads')
            logger.info(f"📊 leads table: {lead_count} records")

            return True

    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}", exc_info=True)
        return False

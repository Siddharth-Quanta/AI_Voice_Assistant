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


async def save_ticket(
    tenant_data: Dict[str, Any],
    category_info: Dict[str, Any],
    issue_description: str
) -> Optional[int]:
    """
    Save ticket to tenant_tickets table

    Args:
        tenant_data: Tenant information from identify_caller
        category_info: Category details from TicketCategoryMatcher
        issue_description: Detailed description of the issue from conversation

    Returns:
        ticket_id (int) if successful, None if failed
    """
    if not db_pool:
        logger.error("Database pool not initialized")
        return None

    try:
        async with db_pool.acquire() as conn:
            # Extract tenant info
            tenant_name = tenant_data.get('name', '')
            # Split name into first and last name
            name_parts = tenant_name.split(' ', 1)
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            # Insert ticket
            insert_query = """
                INSERT INTO tenant_tickets (
                    subject,
                    description,
                    department,
                    department_id,
                    channel,
                    status,
                    priority,
                    email,
                    phone,
                    layout,
                    layout_id,
                    team_id,
                    classification,
                    sub_category,
                    issue_type,
                    module,
                    assigned_to,
                    cf_booking_id,
                    cf_flat_unique_id,
                    cf_last_name,
                    cf_issue_description,
                    created_at,
                    updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                    $21, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                RETURNING id
            """

            ticket_id = await conn.fetchval(
                insert_query,
                category_info.get('subject', ''),                    # subject
                issue_description,                                   # description
                category_info.get('department', ''),                # department
                category_info.get('department_id', ''),             # department_id
                'AI Voice Assistant',                                # channel
                'Open',                                              # status
                'Medium',                                            # priority
                tenant_data.get('email', ''),                       # email
                tenant_data.get('phone', ''),                       # phone
                category_info.get('layout', ''),                    # layout
                category_info.get('layout_id', ''),                 # layout_id
                category_info.get('team_id', ''),                   # team_id
                category_info.get('classification', ''),            # classification
                category_info.get('sub_category', ''),              # sub_category
                category_info.get('issue_type', ''),                # issue_type
                category_info.get('module', ''),                    # module
                category_info.get('assigned_to', ''),               # assigned_to
                tenant_data.get('tenant_id', ''),                   # cf_booking_id
                tenant_data.get('flat', ''),                        # cf_flat_unique_id
                last_name,                                           # cf_last_name
                issue_description                                    # cf_issue_description
            )

            logger.info(f"✅ Ticket #{ticket_id} created successfully")
            logger.info(f"   Type: {category_info.get('issue_type')}")
            logger.info(f"   Tenant: {tenant_name} ({tenant_data.get('flat')})")
            logger.info(f"   Department: {category_info.get('assigned_to')}")

            return ticket_id

    except Exception as e:
        logger.error(f"❌ Error saving ticket: {e}", exc_info=True)
        return None


async def save_lead_information(
    caller_number: str,
    call_sid: str,
    customer_name: Optional[str] = None,
    lead_status: str = "new",
    call_duration: Optional[int] = None
) -> Optional[int]:
    """
    Save lead information to new_lead table when lead/new caller enquires about properties

    Args:
        caller_number: Phone number of the caller
        call_sid: Call session ID
        customer_name: Name of the lead (optional, can be None for anonymous)
        lead_status: "new" for new callers, "existing" for existing leads
        call_duration: Duration of call in seconds (optional)

    Returns:
        lead_id (int) if successful, None if failed
    """
    if not db_pool:
        logger.error("Database pool not initialized")
        return None

    try:
        async with db_pool.acquire() as conn:
            # Insert lead data
            insert_query = """
                INSERT INTO new_lead (
                    timestamp,
                    customer_name,
                    lead_status,
                    caller_number,
                    call_sid,
                    call_duration,
                    created_at,
                    updated_at
                ) VALUES (
                    CURRENT_TIMESTAMP,
                    $1,
                    $2,
                    $3,
                    $4,
                    $5,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                RETURNING id
            """

            lead_id = await conn.fetchval(
                insert_query,
                customer_name,           # customer_name (can be NULL)
                lead_status,             # lead_status ("new" or "existing")
                caller_number,           # caller_number
                call_sid,                # call_sid
                call_duration            # call_duration (can be NULL)
            )

            logger.info(f"✅ Lead data saved successfully! Lead ID: {lead_id}")
            logger.info(f"   Name: {customer_name or 'Not provided'}")
            logger.info(f"   Phone: {caller_number}")
            logger.info(f"   Status: {lead_status}")
            logger.info(f"   Call SID: {call_sid}")

            return lead_id

    except Exception as e:
        logger.error(f"❌ Error saving lead information: {e}", exc_info=True)
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

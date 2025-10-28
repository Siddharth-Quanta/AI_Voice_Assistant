"""
Ticket Category Matcher - Keyword-based ticket categorization
Maps conversation issues to tenant_tickets database table
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class TicketCategoryMatcher:
    """Simple keyword-based ticket category detection for 50 ticket types"""
    
    def __init__(self):
        # 50 Ticket Categories with Database Mappings
        self.categories = {
            # 1-7: Flat Repairs and Maintenance
            "plumbing": {
                "issue_type": "Plumbing Issue",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Flat Repairs and Maintenance",
                "sub_category": "Plumbing Issue",
                "subject": "AO-Flat Repairs and Maintenance",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["plumbing", "pipe", "water leak", "leaking", "toilet", "sink", "drainage", 
                           "faucet", "tap", "basin", "shower", "water flow", "water issue", "tap broken", 
                           "tap not working", "tap is broken", "tap problem", "water problem", 
                           "bathroom tap", "kitchen tap", "washbasin", "flush", "commode"]
            },
            "electrical": {
                "issue_type": "Electrical Issue",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Flat Repairs and Maintenance",
                "sub_category": "Electrical Issue",
                "subject": "AO-Flat Repairs and Maintenance",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["electrical", "power", "electricity", "light", "fan", "outlet", "socket", 
                           "switch", "circuit", "bulb", "wiring", "electric", "light not working", 
                           "fan not working", "power issue", "no electricity", "electrical problem"]
            },
            "carpenter": {
                "issue_type": "Carpenter Issue",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Flat Repairs and Maintenance",
                "sub_category": "Carpenter Issue",
                "subject": "AO-Flat Repairs and Maintenance",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["carpenter", "wood", "door", "hinge", "cabinet", "wardrobe", "drawer", 
                           "woodwork", "wooden", "shelf", "door broken", "door not closing", 
                           "cupboard broken", "wooden repair"]
            },
            "appliance": {
                "issue_type": "Appliance Issues",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Flat Repairs and Maintenance",
                "sub_category": "Appliance Issues",
                "subject": "AO-Flat Repairs and Maintenance",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["appliance", "refrigerator", "fridge", "washing machine", "ac", 
                           "air conditioner", "microwave", "stove", "oven", "geyser", "water heater", 
                           "tv", "television", "fridge not working", "ac not cooling", 
                           "washing machine broken", "geyser not working"]
            },
            "furniture": {
                "issue_type": "Furniture and Fittings",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Flat Repairs and Maintenance",
                "sub_category": "Furniture and Fittings",
                "subject": "AO-Flat Repairs and Maintenance",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["furniture", "chair", "table", "sofa", "bed", "mattress", "desk", "shelf", 
                           "couch", "furnishing", "cupboard", "chair broken", "bed broken", "furniture repair"]
            },
            "pest": {
                "issue_type": "Pests Ants and Rats",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Flat Repairs and Maintenance",
                "sub_category": "Pests Ants and Rats",
                "subject": "AO-Flat Repairs and Maintenance",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["pest", "insect", "rat", "mouse", "cockroach", "bug", "ant", "mosquito", 
                           "termite", "rodent", "fly", "pest control", "insects in flat"]
            },
            "other_flat_issues": {
                "issue_type": "Other Flat Issues",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Flat Repairs and Maintenance",
                "sub_category": "Other Flat Issues",
                "subject": "AO-Flat Repairs and Maintenance",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["flat issue", "apartment issue", "flat problem", "apartment problem", 
                           "flat maintenance", "repair needed", "fix required", "maintenance issue"]
            },
            
            # 8-10: Flat Customization and Installations
            "new_installation": {
                "issue_type": "New Installation",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Flat Customization and Installations",
                "sub_category": "New Installation",
                "subject": "AO-Flat Customization and Installations",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["new installation", "install new", "setup new", "add new", 
                           "want to install", "need to install"]
            },
            "change_setup": {
                "issue_type": "Change of Setup",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Flat Customization and Installations",
                "sub_category": "Change of Setup",
                "subject": "AO-Flat Customization and Installations",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["change setup", "rearrange", "reconfigure", "change layout", 
                           "move furniture", "relocate", "reposition"]
            },
            "other_customizations": {
                "issue_type": "Other Customizations",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Flat Customization and Installations",
                "sub_category": "Other Customizations",
                "subject": "AO-Flat Customization and Installations",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["customization", "custom", "personalize", "modify", "adapt", "adjust"]
            },
            
            # 11-19: Common Area Issues
            "common_area_repairs": {
                "issue_type": "Common area Repairs",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Common Area Issues",
                "sub_category": "Common area Repairs",
                "subject": "AO-Common Area Issues",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["common area repair", "hallway", "corridor", "lobby", "staircase", 
                           "entrance", "common space", "shared space"]
            },
            "cleanliness": {
                "issue_type": "Common area Cleanliness",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Common Area Issues",
                "sub_category": "Common area Cleanliness",
                "subject": "AO-Common Area Issues",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["cleanliness", "cleaning", "dirty", "mess", "sweep", "mop", "dusty", 
                           "hygiene", "sanitation", "untidy"]
            },
            "security": {
                "issue_type": "Security and CCTV",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Common Area Issues",
                "sub_category": "Security and CCTV",
                "subject": "AO-Common Area Issues",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["security", "cctv", "camera", "guard", "theft", "stolen", "unauthorized", 
                           "access", "break in", "safety"]
            },
            "staff": {
                "issue_type": "Building Staff",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Common Area Issues",
                "sub_category": "Building Staff Issue",
                "subject": "AO-Common Area Issues",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["staff", "caretaker", "security guard", "manager", "attendant", "janitor", 
                           "housekeeping staff", "building staff"]
            },
            "neighbor": {
                "issue_type": "Neighbour Tenant Issues",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Common Area Issues",
                "sub_category": "Neighbour Tenant Issues",
                "subject": "AO-Common Area Issues",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["neighbor", "neighbour", "noise", "loud", "disturb", "nuisance", 
                           "complaint", "next door", "adjacent flat", "noise complaint"]
            },
            "garbage": {
                "issue_type": "Garbage",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Common Area Issues",
                "sub_category": "Garbage",
                "subject": "AO-Common Area Issues",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["garbage", "trash", "waste", "bin", "disposal", "collection", 
                           "segregation", "dump", "rubbish"]
            },
            "parking_issues": {
                "issue_type": "Parking Issues",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Common Area Issues",
                "sub_category": "Parking Issues",
                "subject": "AO-Common Area Issues",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["parking", "car park", "vehicle", "bike", "slot", "space", 
                           "two-wheeler", "four-wheeler", "parking space"]
            },
            "outside_property": {
                "issue_type": "Outside Property issues",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Common Area Issues",
                "sub_category": "Outside Property issues",
                "subject": "AO-Common Area Issues",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["outside property", "outside building", "surroundings", "surrounding area", 
                           "locality", "neighborhood"]
            },
            "other_common_area": {
                "issue_type": "Other Common Area Issues",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "AO-Common Area Issues",
                "sub_category": "Other Common Area Issues",
                "subject": "AO-Common Area Issues",
                "assigned_to": "AREA Operations",
                "team_id": "101504000026580561",
                "keywords": ["common area issue", "common issue", "shared space issue", 
                           "community area", "shared facility"]
            },
            
            # 20-24: Wifi Issues
            "wifi_speed": {
                "issue_type": "Wifi Speed Issue",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Wifi Issues",
                "sub_category": "Wifi Speed Issue",
                "subject": "CO-Wifi Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["wifi speed", "slow internet", "internet speed", "buffering", "slow wifi", 
                           "lagging", "speed test"]
            },
            "wifi_limit": {
                "issue_type": "Wifi Limit Exhausted",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Wifi Issues",
                "sub_category": "Wifi Limit Exhausted",
                "subject": "CO-Wifi Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["wifi limit", "data exhausted", "data limit", "bandwidth limit", 
                           "data cap", "usage limit", "exceeded data"]
            },
            "wifi_disconnection": {
                "issue_type": "Wifi Disconnection",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Wifi Issues",
                "sub_category": "Wifi Disconnection",
                "subject": "CO-Wifi Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["wifi disconnection", "internet disconnection", "wifi keeps disconnecting", 
                           "connection drops", "no connection", "disconnects"]
            },
            "wifi_login": {
                "issue_type": "Wifi Login issue",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Wifi Issues",
                "sub_category": "Wifi Login issue",
                "subject": "CO-Wifi Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["wifi login", "wifi password", "internet login", "cannot connect", 
                           "wifi access", "network password"]
            },
            "other_wifi": {
                "issue_type": "Other Wifi Issue",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Wifi Issues",
                "sub_category": "Other Wifi Issue",
                "subject": "CO-Wifi Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["wifi issue", "internet issue", "network issue", "connectivity", 
                           "router", "modem", "wifi signal"]
            },
            
            # 25-26: General Issues
            "apartment_rules": {
                "issue_type": "Apartment Rules",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Apartment Rules",
                "sub_category": "Apartment Rules Decorum",
                "subject": "CO-Apartment Rules",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["apartment rules", "building rules", "society rules", "regulations", 
                           "guidelines", "policy", "bylaws", "community rules"]
            },
            "other_apartment": {
                "issue_type": "Other Apartment Issues",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-General Queries - Others",
                "sub_category": "Others",
                "subject": "CO-General Queries - Others",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["apartment issue", "apartment problem", "building issue", 
                           "complex issue", "residential issue"]
            },
            
            # 27-31: Check-in/Check-out Process
            "check_in": {
                "issue_type": "Check In Process",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Checkin - Checkout Process",
                "sub_category": "Check In Process",
                "subject": "CO-Checkin - Checkout Process",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["check in", "move in", "moving in", "shifting", "arrival", "onboarding", 
                           "new tenant", "begin lease"]
            },
            "change_move_in": {
                "issue_type": "Change Move In Date",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Checkin - Checkout Process",
                "sub_category": "Change Move In Date",
                "subject": "CO-Checkin - Checkout Process",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["change move in", "reschedule move in", "postpone move in", 
                           "move in date change", "arrival date", "check in date"]
            },
            "check_out": {
                "issue_type": "Check Out Process",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Checkin - Checkout Process",
                "sub_category": "Check Out Process",
                "subject": "CO-Checkin - Checkout Process",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["check out", "move out", "moving out", "leaving", "exit", "departure", 
                           "end tenancy", "vacate"]
            },
            "change_move_out": {
                "issue_type": "Change Move Out Date",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Checkin - Checkout Process",
                "sub_category": "Change Move Out Date",
                "subject": "CO-Checkin - Checkout Process",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["change move out", "reschedule move out", "postpone move out", 
                           "delay move out", "extend stay", "change departure"]
            },
            "notice_termination": {
                "issue_type": "Notice and Termination",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Checkin - Checkout Process",
                "sub_category": "Notice and Termination",
                "subject": "Queries on Notice and Termination",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["notice", "terminate", "termination", "end contract", "exit", 
                           "moving out", "vacate", "lease termination", "contract end"]
            },
            
            # 32-35: Rental Contract Queries
            "lock_in_period": {
                "issue_type": "Lock In Period",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Billing, Payment & Contract",
                "layout_id": "101504000026558328",
                "classification": "Rental Contract Queries",
                "sub_category": "",
                "subject": "Rental Contract & Utilities Related Queries",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["lock in period", "minimum stay", "contract duration", "lease period", 
                           "lock in", "duration commitment"]
            },
            "contract_renewal": {
                "issue_type": "Contract Renewal",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Billing, Payment & Contract",
                "layout_id": "101504000026558328",
                "classification": "Rental Contract Queries",
                "sub_category": "",
                "subject": "Rental Contract & Utilities Related Queries",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["contract renewal", "lease renewal", "extend contract", "renew agreement", 
                           "renew lease", "continue tenancy"]
            },
            "contract_terms": {
                "issue_type": "Contract Terms",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Billing, Payment & Contract",
                "layout_id": "101504000026558328",
                "classification": "Rental Contract Queries",
                "sub_category": "",
                "subject": "Rental Contract & Utilities Related Queries",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["contract terms", "lease terms", "agreement terms", "rental terms", 
                           "tenancy terms", "tenancy conditions"]
            },
            "other_contract": {
                "issue_type": "Other Contract Issue",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Billing, Payment & Contract",
                "layout_id": "101504000026558328",
                "classification": "Rental Contract Queries",
                "sub_category": "",
                "subject": "Rental Contract & Utilities Related Queries",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["contract issue", "lease issue", "agreement problem", "rental agreement", 
                           "lease document", "rent document"]
            },
            
            # 36-41: Payment-related
            "rental_invoices": {
                "issue_type": "Rental Invoices",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Billing, Payment & Contract",
                "layout_id": "101504000026558328",
                "classification": "Payment Receipt and Invoice",
                "sub_category": "",
                "subject": "Payment Link, Receipt & Invoice Related",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["rent invoice", "rental invoice", "rent bill", "monthly invoice", 
                           "rent receipt", "rental receipt"]
            },
            "rental_arrears": {
                "issue_type": "Rental Arrears",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Billing, Payment & Contract",
                "layout_id": "101504000026558328",
                "classification": "Arrears - Rental Queries",
                "sub_category": "",
                "subject": "Arrears - Rental & Addtional Services Queries",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["rent arrears", "rent due", "overdue payment", "pending rent", 
                           "late payment", "unpaid rent"]
            },
            "utility_queries": {
                "issue_type": "Utility Queries",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Billing, Payment & Contract",
                "layout_id": "101504000026558328",
                "classification": "Utility Related Queries",
                "sub_category": "",
                "subject": "Rental Contract & Utilities Related Queries",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["utility", "electricity bill", "water bill", "gas bill", "power bill", 
                           "utility payment", "meter reading"]
            },
            "additional_services": {
                "issue_type": "Additional Services",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Billing, Payment & Contract",
                "layout_id": "101504000026558328",
                "classification": "Additonal Services Queries",
                "sub_category": "",
                "subject": "Additonal Services & Services Refund Queries",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["additional service", "extra service", "premium service", "added service", 
                           "service upgrade", "special service"]
            },
            "payment_receipts": {
                "issue_type": "Payment Receipts",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Billing, Payment & Contract",
                "layout_id": "101504000026558328",
                "classification": "Payment Receipt and Invoice",
                "sub_category": "",
                "subject": "Payment Link, Receipt & Invoice Related",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["payment receipt", "transaction receipt", "payment proof", "money receipt", 
                           "fee receipt", "receipt"]
            },
            "payment_link": {
                "issue_type": "Payment Link",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Billing, Payment & Contract",
                "layout_id": "101504000026558328",
                "classification": "Payment Link Generation",
                "sub_category": "",
                "subject": "Payment Link, Receipt & Invoice Related",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["payment link", "pay online", "online payment", "payment portal", 
                           "payment url", "payment gateway", "payment method"]
            },
            
            # 42-49: Additional Services Issues
            "one_time_housekeeping": {
                "issue_type": "One time Housekeeping",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Additional Services Issues",
                "sub_category": "One time Housekeeping",
                "subject": "CO-Additional Services Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["one time cleaning", "single cleaning", "one-off cleaning", 
                           "cleaning service", "housekeeping service", "one time maid"]
            },
            "housekeeping_subscription": {
                "issue_type": "Housekeeping Subscription",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Additional Services Issues",
                "sub_category": "Housekeeping Subscription",
                "subject": "CO-Additional Services Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["regular cleaning", "cleaning subscription", "monthly cleaning", 
                           "weekly cleaning", "recurrent housekeeping"]
            },
            "car_parking": {
                "issue_type": "Car Parking",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Additional Services Issues",
                "sub_category": "Car Parking",
                "subject": "CO-Additional Services Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["car parking", "vehicle parking", "parking slot", "reserved parking", 
                           "parking space", "car park"]
            },
            "duplicate_keys": {
                "issue_type": "Duplicate Keys",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Additional Services Issues",
                "sub_category": "Duplicate Keys",
                "subject": "CO-Additional Services Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["duplicate key", "spare key", "extra key", "replacement key", 
                           "new key", "key copy", "lost key"]
            },
            "vehicle_wash": {
                "issue_type": "Vehicle Wash",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Additional Services Issues",
                "sub_category": "Vehicle Wash",
                "subject": "CO-Additional Services Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["car wash", "vehicle wash", "bike wash", "car cleaning", 
                           "vehicle cleaning", "washing service"]
            },
            "water_can": {
                "issue_type": "Water Can Service",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Additional Services Issues",
                "sub_category": "Water Can Service",
                "subject": "CO-Additional Services Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["water can", "drinking water", "water jar", "water bottle", 
                           "mineral water", "water delivery", "water dispenser"]
            },
            "food_service": {
                "issue_type": "Food Service",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Additional Services Issues",
                "sub_category": "Food Service",
                "subject": "CO-Additional Services Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["food service", "meal service", "food delivery", "meal delivery", 
                           "catering", "tiffin", "lunch", "dinner"]
            },
            "other_additional_services": {
                "issue_type": "Other Issues Additional Services",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "CO-Additional Services Issues",
                "sub_category": "Other Issues Additional Services",
                "subject": "CO-Additional Services Issues",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["extra service", "special request", "additional facility", 
                           "premium service", "concierge", "personalized service"]
            },
            
            # 50: Call Back Request
            "callback": {
                "issue_type": "Need CAll Back (CRA Call Back)",
                "module": "Services",
                "department": "ALL OPERATIONS",
                "department_id": "101504000015928849",
                "layout": "Tenant SRs",
                "layout_id": "101504000015966282",
                "classification": "Call Back Request",
                "sub_category": "CRA Call Back",
                "subject": "Call Back Request",
                "assigned_to": "Customer Operations",
                "team_id": "101504000026409126",
                "keywords": ["call back", "callback", "call me", "speak to someone", "talk to someone", 
                           "talk to human", "need to speak", "want to talk", "connect me with", 
                           "representative", "manager", "supervisor", "talk to agent", 
                           "connect to agent", "human", "person", "speak with agent", 
                           "contact by phone"]
            }
        }
    
    def detect_issue_from_conversation(self, conversation_text: str) -> Optional[Dict[str, Any]]:
        """
        Detect issue category from conversation using keyword matching.
        
        Args:
            conversation_text: The full conversation text to analyze
            
        Returns:
            Dict with category info or None if no match
            {
                'category_key': 'plumbing',
                'category_info': {...all fields...},
                'matched_keywords': ['tap', 'water leak'],
                'match_count': 2
            }
        """
        text_lower = conversation_text.lower()
        
        # First check for callback request (highest priority)
        for keyword in self.categories["callback"]["keywords"]:
            if keyword in text_lower:
                logger.info(f"🎯 Detected CALLBACK request - keyword: '{keyword}'")
                return {
                    'category_key': 'callback',
                    'category_info': self.categories['callback'],
                    'matched_keywords': [keyword],
                    'match_count': 1
                }
        
        # Check all other categories and count matches
        category_matches = {}
        
        for category_key, category_data in self.categories.items():
            if category_key == "callback":
                continue  # Already checked
            
            matched_keywords = []
            for keyword in category_data["keywords"]:
                if keyword in text_lower:
                    matched_keywords.append(keyword)
            
            if matched_keywords:
                category_matches[category_key] = {
                    'category_info': category_data,
                    'matched_keywords': matched_keywords,
                    'match_count': len(matched_keywords)
                }
        
        # Return the category with most keyword matches
        if category_matches:
            best_match_key = max(category_matches.items(), key=lambda x: x[1]['match_count'])[0]
            best_match = category_matches[best_match_key]
            
            logger.info(f"🎯 Detected issue category: {best_match_key}")
            logger.info(f"   Issue Type: {best_match['category_info']['issue_type']}")
            logger.info(f"   Matched Keywords: {', '.join(best_match['matched_keywords'][:5])}")
            logger.info(f"   Match Count: {best_match['match_count']}")
            
            return {
                'category_key': best_match_key,
                'category_info': best_match['category_info'],
                'matched_keywords': best_match['matched_keywords'],
                'match_count': best_match['match_count']
            }
        
        logger.info("❌ No issue category detected in conversation")
        return None
    
    def get_category_info(self, category_key: str) -> Optional[Dict[str, Any]]:
        """Get full category information by key"""
        return self.categories.get(category_key)
    
    def get_all_categories(self) -> List[str]:
        """Get list of all category keys"""
        return list(self.categories.keys())

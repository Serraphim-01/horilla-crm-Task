"""Service for generating demo CRM data from existing users."""

import random
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from horilla.apps import apps
from horilla_core.models import Company, CustomerRole, Role, TeamRole

User = get_user_model()

FIRST_NAMES = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
COMPANIES = ["NovaTech Solutions", "Quantum Dynamics", "Pinnacle Group", "Vertex Systems", "Apex Innovations", "Crestwood Industries", "Fairview Technologies", "Silverstone Partners", "Brookfield Corp", "Eastwood Enterprises"]
CITIES = ["New York", "London", "San Francisco", "Berlin", "Tokyo", "Toronto", "Sydney", "Paris", "Singapore", "Dubai"]
INDUSTRIES = ["finance", "healthcare", "manufacturing", "technology", "banking", "education", "insurance", "construction"]

ACCOUNT_NAMES = [
    "Acme Corp", "Globex Inc", "Initech", "Hooli", "Sterling Cooper",
    "Wayne Enterprises", "Stark Industries", "Oscorp", "Massive Dynamic",
    "Cyberdyne Systems", "Wonka Industries", "Dunder Mifflin", "Pied Piper",
    "Rannoch Pharma", "Omni Consumer Products", "Tyrell Corp", "Weyland-Yutani",
    "Solyent Corp", "Blue Harvest", "Oceanic Airlines",
]

OPPORTUNITY_NAMES = [
    "Enterprise License Renewal", "Cloud Migration Project", "SaaS Implementation",
    "Infrastructure Upgrade", "Security Audit Package", "Data Analytics Platform",
    "CRM Integration Suite", "Mobile App Development", "IT Consulting Retainer",
    "Managed Services Contract", "Hardware Refresh Program", "Staff Augmentation",
    "Compliance Review", "Disaster Recovery Setup", "Network Redesign",
]


def _get_or_create_default_roles(company):
    team_roles = {}
    for name in ["Sales Rep", "Sales Engineer", "Account Manager", "Solution Architect"]:
        role, _ = TeamRole.objects.get_or_create(
            team_role_name=name,
            company=company,
            defaults={"description": f"Default {name} role"},
        )
        team_roles[name] = role

    customer_roles = {}
    for name in ["Decision Maker", "Champion", "Technical Evaluator", "End User", "Procurement"]:
        role, _ = CustomerRole.objects.get_or_create(
            customer_role_name=name,
            company=company,
            defaults={"description": f"Default {name} role"},
        )
        customer_roles[name] = role

    return team_roles, customer_roles


def _get_or_create_lead_statuses(company):
    LeadStatus = apps.get_model("horilla_crm", "LeadStatus")
    statuses = {}
    defaults = [
        ("New", 1, 10, False),
        ("Contacted", 2, 20, False),
        ("Qualified", 3, 50, False),
        ("Converted", 4, 100, True),
        ("Disqualified", 5, 0, True),
    ]
    for name, order, prob, is_final in defaults:
        status, _ = LeadStatus.objects.get_or_create(
            name=name,
            company=company,
            defaults={"order": order, "probability": prob, "is_final": is_final},
        )
        statuses[name] = status
    return statuses


def _get_or_create_opportunity_stages(company):
    OpportunityStage = apps.get_model("horilla_crm", "OpportunityStage")
    stages = {}
    defaults = [
        ("Qualification", 1, 10, "open", False),
        ("Discovery", 2, 25, "open", False),
        ("Proposal", 3, 50, "open", False),
        ("Negotiation", 4, 75, "open", False),
        ("Closed Won", 5, 100, "won", True),
        ("Closed Lost", 6, 0, "lost", True),
    ]
    for name, order, prob, stage_type, is_final in defaults:
        stage, _ = OpportunityStage.objects.get_or_create(
            name=name,
            company=company,
            defaults={"order": order, "probability": prob, "stage_type": stage_type, "is_final": is_final},
        )
        stages[name] = stage
    return stages


def _get_or_create_forecast_type(company):
    ForecastType = apps.get_model("horilla_crm", "ForecastType")
    ft, _ = ForecastType.objects.get_or_create(
        name="Deal Revenue",
        company=company,
        defaults={
            "forecast_type": "deal_revenue_amount",
            "include_pipeline": True,
            "include_best_case": True,
            "include_commit": True,
            "include_closed": True,
        },
    )
    return ft


def _get_current_fiscal_periods(company):
    FiscalYearInstance = apps.get_model("horilla_core", "FiscalYearInstance")
    Quarter = apps.get_model("horilla_core", "Quarter")
    Period = apps.get_model("horilla_core", "Period")
    now = timezone.now()

    current_fy = FiscalYearInstance.objects.filter(
        company=company, start_date__lte=now, end_date__gte=now
    ).first()
    if not current_fy:
        current_fy = FiscalYearInstance.objects.filter(company=company).first()
    if not current_fy:
        return None, None, None

    current_quarter = Quarter.objects.filter(
        fiscal_year=current_fy, start_date__lte=now, end_date__gte=now
    ).first()
    current_period = Period.objects.filter(
        quarter=current_quarter, start_date__lte=now, end_date__gte=now
    ).first() if current_quarter else None

    return current_fy, current_quarter, current_period


def generate_demo_data(company):
    """Generate demo CRM data using existing users tied to the given company."""
    Account = apps.get_model("horilla_crm", "Account")
    Contact = apps.get_model("horilla_crm", "Contact")
    ContactAccountRelationship = apps.get_model("horilla_crm", "ContactAccountRelationship")
    Lead = apps.get_model("horilla_crm", "Lead")
    Opportunity = apps.get_model("horilla_crm", "Opportunity")
    Campaign = apps.get_model("horilla_crm", "Campaign")
    Forecast = apps.get_model("horilla_crm", "Forecast")

    users = list(User.objects.filter(company=company, is_active=True))
    if not users:
        raise ValueError(_("No active users found for company {}").format(company.name))

    team_roles, customer_roles = _get_or_create_default_roles(company)
    lead_statuses = _get_or_create_lead_statuses(company)
    opp_stages = _get_or_create_opportunity_stages(company)
    forecast_type = _get_or_create_forecast_type(company)
    current_fy, current_quarter, current_period = _get_current_fiscal_periods(company)

    random.seed(42)

    with transaction.atomic():
        campaigns = []
        campaign_configs = [
            ("Google Ads Q2 2026", "advertisement", "in_progress", 5000, 4200, 10000, 3.0),
            ("Summer Webinar Series", "webinar", "planned", 2000, 0, 5000, 15.0),
            ("Partner Referral Program", "referral", "in_progress", 500, 300, 0, 0),
            ("Email Campaign - Q2", "email", "in_progress", 3000, 2500, 20000, 5.0),
            ("Tech Conference 2026", "event", "planned", 10000, 0, 0, 0),
        ]
        for name, ctype, status, budget, actual, sent, response_rate in campaign_configs:
            owner = random.choice(users)
            campaign, _ = Campaign.objects.get_or_create(
                campaign_name=name,
                company=company,
                defaults={
                    "campaign_owner": owner,
                    "campaign_type": ctype,
                    "status": status,
                    "budget_cost": budget,
                    "actual_cost": actual,
                    "number_sent": sent,
                    "expected_response": response_rate,
                },
            )
            campaigns.append(campaign)

        accounts = []
        sample_accounts = random.sample(ACCOUNT_NAMES, min(len(ACCOUNT_NAMES), max(6, len(users) * 2)))
        for i, acct_name in enumerate(sample_accounts):
            owner = random.choice(users)
            industry = random.choice(INDUSTRIES)
            account, _ = Account.objects.get_or_create(
                name=acct_name,
                company=company,
                defaults={
                    "account_owner": owner,
                    "account_type": random.choice(["prospect", "customer_direct", "customer_channel"]),
                    "industry": industry,
                    "annual_revenue": random.randint(500000, 50000000),
                    "number_of_employees": random.randint(10, 5000),
                    "billing_city": random.choice(CITIES),
                    "rating": random.choice(["Hot", "Warm", "Cold"]),
                    "website": f"https://{acct_name.lower().replace(' ', '')}.com",
                    "phone": f"+1-555-{random.randint(1000,9999)}",
                },
            )
            accounts.append(account)

        contacts = []
        for account in accounts:
            for _ in range(random.randint(1, 3)):
                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                owner = account.account_owner
                contact, _ = Contact.objects.get_or_create(
                    first_name=first,
                    last_name=last,
                    email=f"{first.lower()}.{last.lower()}@{account.name.lower().replace(' ', '')}.com",
                    company=company,
                    defaults={
                        "contact_owner": owner,
                        "phone": f"+1-555-{random.randint(1000,9999)}",
                        "address_city": account.billing_city or random.choice(CITIES),
                        "is_primary": False,
                    },
                )
                contacts.append(contact)
                ContactAccountRelationship.objects.get_or_create(
                    contact=contact,
                    account=account,
                    company=company,
                    defaults={"role": random.choice(list(customer_roles.values()))},
                )

        leads = []
        lead_status_values = list(lead_statuses.values())
        for _ in range(max(5, len(users) * 3)):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            owner = random.choice(users)
            status = random.choice(lead_status_values)
            company_name = random.choice(COMPANIES)
            lead, _ = Lead.objects.get_or_create(
                first_name=first,
                last_name=last,
                email=f"{first.lower()}.{last.lower()}_{random.randint(1,999)}@{company_name.lower().replace(' ', '')}.com",
                company=company,
                defaults={
                    "lead_owner": owner,
                    "lead_status": status,
                    "lead_source": random.choice(["website", "referral", "campaign", "email", "phone", "event"]),
                    "lead_company": company_name,
                    "industry": random.choice(INDUSTRIES),
                    "annual_revenue": random.randint(100000, 20000000),
                    "requirements": random.choice([
                        "Looking for enterprise-grade solution",
                        "Need scalable platform for growing team",
                        "Evaluating vendor options for Q3",
                        "Interested in demo and pricing",
                        "Need custom integration support",
                    ]),
                    "city": random.choice(CITIES),
                },
            )
            leads.append(lead)

        opportunities = []
        for _ in range(max(5, len(users) * 3)):
            owner = random.choice(users)
            stage = random.choice(list(opp_stages.values()))
            amount = random.choice([5000, 10000, 15000, 25000, 50000, 75000, 100000, 150000, 250000])
            account = random.choice(accounts) if random.random() > 0.3 else None
            campaign = random.choice(campaigns) if random.random() > 0.5 else None
            opp_name = f"{account.name + ' - ' if account else ''}{random.choice(OPPORTUNITY_NAMES)}"

            days_to_close = random.randint(5, 90)
            close_date = timezone.now().date() + timedelta(days=days_to_close)

            opportunity, _ = Opportunity.objects.get_or_create(
                name=opp_name,
                company=company,
                owner=owner,
                stage=stage,
                defaults={
                    "amount": amount,
                    "close_date": close_date,
                    "account": account,
                    "primary_campaign_source": campaign,
                    "opportunity_type": random.choice(["new_customer", "existing_customer_upgrade"]),
                    "lead_source": random.choice(["website", "referral", "campaign", "email", "phone"]),
                    "description": f"Demo opportunity for {opp_name}",
                },
            )
            opportunities.append(opportunity)

        total_pipeline = sum(o.amount for o in opportunities if o.forecast_category == "pipeline" and o.amount)
        total_best_case = sum(o.amount for o in opportunities if o.forecast_category == "best_case" and o.amount)
        total_commit = sum(o.amount for o in opportunities if o.forecast_category == "commit" and o.amount)
        total_closed = sum(o.amount for o in opportunities if o.forecast_category == "closed" and o.amount)

        if current_fy and forecast_type:
            forecast_name = f"{current_fy.name} Revenue Forecast"
            forecast, _ = Forecast.objects.get_or_create(
                name=forecast_name,
                company=company,
                forecast_type=forecast_type,
                fiscal_year=current_fy,
                defaults={
                    "period": current_period,
                    "quarter": current_quarter,
                    "owner": users[0],
                    "target_amount": sum(o.amount for o in opportunities if o.amount) if opportunities else 500000,
                    "pipeline_amount": total_pipeline,
                    "best_case_amount": total_best_case,
                    "commit_amount": total_commit,
                    "closed_amount": total_closed,
                    "status": "draft",
                },
            )

        campaign_updates = {}
        for opp in opportunities:
            if opp.primary_campaign_source and opp.forecast_category == "closed" and opp.stage and opp.stage.is_won:
                camp = opp.primary_campaign_source
                if camp.pk not in campaign_updates:
                    campaign_updates[camp.pk] = {"won": 0, "value": 0}
                campaign_updates[camp.pk]["won"] += 1
                campaign_updates[camp.pk]["value"] += opp.amount or 0

        for camp_pk, updates in campaign_updates.items():
            Campaign.objects.filter(pk=camp_pk).update(
                won_opportunities_in_campaign=models.F("won_opportunities_in_campaign") + updates["won"],
                value_won_opportunities=models.F("value_won_opportunities") + updates["value"],
                opportunities_in_campaign=models.F("opportunities_in_campaign") + len([o for o in opportunities if o.primary_campaign_source and o.primary_campaign_source.pk == camp_pk]),
            )

    return {
        "accounts": len(accounts),
        "contacts": len(contacts),
        "leads": len(leads),
        "opportunities": len(opportunities),
        "campaigns": len(campaigns),
    }

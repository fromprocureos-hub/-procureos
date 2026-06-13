"""
ProcureOS — Company Intelligence Context Builder
Feeds past RFQ data, vendor history, and company info into AI prompts.
"""
from models import db, Company, Procurement, ProcurementVendor, Vendor

def build_company_context(company_id):
    """Build a compact context string about the company for AI prompts."""
    try:
        company = Company.query.get(company_id)
        if not company:
            return ""

        lines = []

        # Company basics
        lines.append(f"COMPANY: {company.name}")
        if company.industry:
            lines.append(f"INDUSTRY: {company.industry.name}")

        # Last 5 completed procurements
        past = (
            Procurement.query
            .filter_by(company_id=company_id)
            .filter(Procurement.status.in_(['completed', 'approved']))
            .order_by(Procurement.created_at.desc())
            .limit(5)
            .all()
        )

        if past:
            lines.append("PAST ORDERS:")
            for p in past:
                winner = p.selected_vendor.company_name if p.selected_vendor else "unknown"
                price = f"Rs.{p.total_value}" if p.total_value else "no price"
                lines.append(f"- {p.item_name} x{p.quantity} {p.unit} → {winner} ({price})")

        # Top vendors by win count
        wins = (
            db.session.query(
                Vendor.company_name,
                Vendor.categories,
                Vendor.reliability_score,
                db.func.count(Procurement.selected_vendor_id).label('wins')
            )
            .join(Procurement, Procurement.selected_vendor_id == Vendor.id)
            .filter(Vendor.company_id == company_id)
            .group_by(Vendor.id)
            .order_by(db.text('wins DESC'))
            .limit(5)
            .all()
        )

        if wins:
            lines.append("TOP VENDORS:")
            for v in wins:
                lines.append(f"- {v.company_name} ({v.categories or 'general'}) — {v.wins} orders, {v.reliability_score}% reliability")

        # Common categories
        cats = (
            db.session.query(Procurement.category_tag, db.func.count().label('n'))
            .filter_by(company_id=company_id)
            .filter(Procurement.category_tag != None)
            .group_by(Procurement.category_tag)
            .order_by(db.text('n DESC'))
            .limit(5)
            .all()
        )
        if cats:
            lines.append("COMMON CATEGORIES: " + ", ".join([c.category_tag for c in cats]))

        return "\n".join(lines)

    except Exception as e:
        print(f'[CONTEXT] Error building context: {e}')
        return ""


def get_item_history(company_id, item_name):
    """Get past orders of a similar item for smart quantity/spec suggestions."""
    try:
        similar = (
            Procurement.query
            .filter_by(company_id=company_id)
            .filter(Procurement.item_name.ilike(f'%{item_name.split()[0]}%'))
            .order_by(Procurement.created_at.desc())
            .limit(3)
            .all()
        )
        if not similar:
            return ""
        lines = ["SIMILAR PAST ORDERS FOR THIS ITEM:"]
        for p in similar:
            lines.append(f"- {p.item_name} x{p.quantity} {p.unit}, notes: {p.notes or 'none'}")
        return "\n".join(lines)
    except Exception as e:
        print(f'[CONTEXT] Error getting item history: {e}')
        return ""
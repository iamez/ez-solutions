"""
Management command: seed_plans

Usage:
    python manage.py seed_plans            # create or update default plans
    python manage.py seed_plans --clear    # wipe existing plans first
"""

from django.core.management.base import BaseCommand

from services.models import PlanFeature, ServicePlan


class Command(BaseCommand):
    help = "Seed the database with default service plans"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing plans before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count, _ = ServicePlan.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {count} existing plans"))

        plans = [
            {
                "name": "Starter",
                "slug": "starter",
                "tagline": "Perfect for individuals and small projects",
                "price_monthly": "9.00",
                "price_annual": "86.00",
                "tier_key": "starter",
                "is_active": True,
                "is_featured": False,
                "sort_order": 10,
                "features": [
                    ("1 Website", True),
                    ("10 GB NVMe SSD Storage", True),
                    ("Free SSL Certificate", True),
                    ("Daily Backups", True),
                    ("5 Email Accounts", True),
                    ("10 GB Bandwidth", True),
                    ("Priority Support", False),
                    ("Dedicated Account Manager", False),
                ],
            },
            {
                "name": "Professional",
                "slug": "professional",
                "tagline": "Everything your growing business needs",
                "price_monthly": "29.00",
                "price_annual": "278.00",
                "tier_key": "professional",
                "is_active": True,
                "is_featured": True,
                "sort_order": 20,
                "features": [
                    ("10 Websites", True),
                    ("50 GB NVMe SSD Storage", True),
                    ("Free SSL Certificate", True),
                    ("Daily Backups (7-day retention)", True),
                    ("Unlimited Email Accounts", True),
                    ("Unlimited Bandwidth", True),
                    ("Priority Support (< 2 hr response)", True),
                    ("Dedicated Account Manager", False),
                ],
            },
            {
                "name": "Enterprise",
                "slug": "enterprise",
                "tagline": "Custom solutions for large organisations",
                "price_monthly": "99.00",
                "price_annual": "950.00",
                "tier_key": "enterprise",
                "is_active": True,
                "is_featured": False,
                "sort_order": 30,
                "features": [
                    ("Unlimited Websites", True),
                    ("500 GB NVMe SSD Storage", True),
                    ("Free SSL Certificate", True),
                    ("Daily Backups (30-day retention)", True),
                    ("Unlimited Email Accounts", True),
                    ("Unlimited Bandwidth", True),
                    ("Priority Support (< 30 min response)", True),
                    ("Dedicated Account Manager", True),
                ],
            },
        ]

        created_count = 0
        updated_count = 0

        for plan_data in plans:
            features_data = plan_data.pop("features")
            plan, created = ServicePlan.objects.update_or_create(
                slug=plan_data["slug"],
                defaults=plan_data,
            )
            action = "Created" if created else "Updated"
            if created:
                created_count += 1
            else:
                updated_count += 1

            # Rebuild features
            plan.features.all().delete()
            for order, (text, is_included) in enumerate(features_data, start=1):
                PlanFeature.objects.create(
                    plan=plan,
                    text=text,
                    is_included=is_included,
                    sort_order=order,
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  {action}: {plan.name} (${plan.price_monthly}/mo, "
                    f"{len(features_data)} features)"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone — {created_count} created, {updated_count} updated."
            )
        )

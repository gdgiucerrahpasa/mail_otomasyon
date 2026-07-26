"""
One-time migration: import templates from old config.json into the new Draft DB.

Usage:
  python migrate_from_config.py path/to/config.json

Imports exactly 2 drafts per segment:
  template_1 → slug="{event}", is_reminder=False  (reach-out mail)
  reminder   → slug="{event}", is_reminder=True   (reminder mail)

template_2, template_3, template_4 are ignored — the new engine sends one
reach-out then up to 3 reminders, all using the same two draft templates.

You'll be prompted for the event slug (e.g. "casestudy").
"""

import json
import sys
from app.database import init_db, SessionLocal
from app.models import Draft


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "../mail_otomasyon_final/config.json"
    try:
        with open(config_path) as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {config_path}")
        sys.exit(1)

    templates = config.get("email", {}).get("templates", {})
    subject   = config.get("email", {}).get("subject", "Konu")
    cc        = ", ".join(config.get("email", {}).get("cc",  []))
    bcc       = ", ".join(config.get("email", {}).get("bcc", []))
    attachments = ", ".join(config.get("email", {}).get("attachments", []))

    if not templates:
        print("No templates found in config.json")
        sys.exit(1)

    print("Templates found:", list(templates.keys()))
    slug = input("Enter the segment slug for these templates (e.g. 'casestudy'): ").strip().lower()
    if not slug:
        print("Slug required.")
        sys.exit(1)

    init_db()
    db = SessionLocal()

    template_map = {
        "template_1": ("İlk Ulaşım", False),
        "reminder":   ("Hatırlatma", True),
    }

    count = 0
    for key, body in templates.items():
        if not body or not body.strip():
            continue
        label, is_reminder = template_map.get(key, (key, False))
        draft = Draft(
            name        = f"{slug} — {label}",
            slug        = slug,
            is_reminder = is_reminder,
            subject     = subject,
            body_html   = body,
            cc          = cc,
            bcc         = bcc,
            attachments = attachments if not is_reminder else "",
        )
        db.add(draft)
        count += 1
        print(f"  + {draft.name} (is_reminder={is_reminder})")

    db.commit()
    db.close()
    print(f"\nDone. Imported {count} drafts for slug '{slug}'.")
    print("Now update your Google Sheet: rename 'Şablon No' column to 'Segment'")
    print(f"and fill the new column with '{slug}' for all rows in this event.")


if __name__ == "__main__":
    main()

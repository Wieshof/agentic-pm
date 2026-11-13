"""Friendly message texts the agent sends to people (EN/DE, German with "Du").

Kept in one place so tone stays consistent: warm, short, never pushy.
Other languages fall back to English (see briefs.morning.base_language).
"""

from __future__ import annotations

from typing import Any

from agentic_pm.adapters.base import Task, TaskPatch
from agentic_pm.config.team import TeamConfig

LANGUAGE_NAMES = {
    "en": {"en": "English", "de": "German"},
    "de": {"en": "Englisch", "de": "Deutsch"},
}

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "approval_subject": "🙋 Your OK needed: {change_short} on #{id} {title}",
        "approval_body": (
            "Hi {name},\n\n{actor} would like to {change} on #{id} {title}.\n"
            "Why: {reason}\n\nThis needs your OK because {why_tier}.\n\n"
            "Have a look and decide here: {url}\n\n"
            "The link works until {expires}. If the task changes before then, I'll simply "
            "ask again. Thanks! 💬"
        ),
        "why_high": "it affects a client deadline or who owns the task",
        "why_medium": "it changes the plan for your task",
        "pending_comment": "⏳ Proposed: {change}. Waiting for {names} to confirm.",
        "approved_comment": "✅ Approved by {name}.",
        "declined_comment": "🙅 {name} decided not to {change}. Nothing was changed.",
        "howto_subject": "🎉 #{id} is done. How did you solve it?",
        "howto_body": (
            "Hi {name},\n\nnice work closing #{id} {title}!\n\n"
            "Could you reply with one or two sentences on how you solved it? For example: "
            "what was the cause, and what fixed it.\n\n"
            "I'll turn it into a short how-to on the ticket (in {ticket_language}) so the next "
            "person finds it. No formatting needed, a quick note is perfect.\n\nThanks! 🙏"
        ),
        "howto_asked_comment": "📝 Asked {names} for a short how-to.",
        "ack_howto": "Thanks, {name}! I've added it to #{id} as a how-to: {url}",
        "ack_note": "Thanks, {name}! I've added your note to #{id}: {url}",
        "ack_scope": (
            "Thanks, {name}! This sounds like a new request, so I've passed it to {leads} "
            "to decide before anyone starts on it. I'll let you know."
        ),
        "ack_unknown_task": (
            "Hi {name}, thanks for your message! I couldn't tell which task it's about. "
            "Could you reply to one of my task emails, or mention the task number like #142?"
        ),
        "scope_lead_subject": "💡 Possible new scope from {requester}",
        "scope_lead_body": (
            "Hi {name},\n\n{requester} wrote about #{id} {title}:\n\n> {quote}\n\n"
            "This looks like new scope, so I haven't created any work for it. "
            "Formal change requests with impact estimates are coming soon (#50). "
            "Until then, could you decide how to handle it?\n\nThanks! 💬"
        ),
        "onboarding_subject": "👋 Hi {name}, I'm your team's project assistant",
        "onboarding_body": (
            "Hi {name},\n\n"
            "I'm agent-pm, the project assistant your team set up for {project}. "
            "I help with the small stuff: briefs, reminders, and turning \"here's how I fixed "
            'it" into a how-to on the ticket.\n\n'
            "What I use about you:\n"
            "  • your name, {channels} and language ({language}) from the team file\n"
            "  • the tasks assigned to you in {tracker}\n"
            "  • the messages you send me, so I can add them to the right task\n\n"
            "What I don't do:\n"
            "  • no scores, rankings or productivity numbers about you\n"
            "  • no history about you; I look at the tasks as they are right now\n"
            "  • no guessing your mood from messages\n"
            "  • messages are processed by a model running on our own servers ({llm})\n\n"
            "Your brief: {brief}.\n"
            "Want something changed or switched off? Just reply, or ask {leads}.\n"
            "Details: {doc}\n\nNice to meet you! 🙌"
        ),
        "onboarding_no_brief": "none for now",
        "reply_subject": "Re: #{id} {title}",
        "status_due": "move the due date from {old} to {new}",
        "status_due_short": "new due date",
        "assign": "hand it over from {old} to {new}",
        "assign_short": "new owner",
        "status": "set the status to {new}",
        "status_short": "status change",
        "estimate": "change the estimate to {new}",
        "estimate_short": "new estimate",
        "labels": "update the labels",
        "nobody": "nobody",
    },
    "de": {
        "approval_subject": "🙋 Dein OK gebraucht: {change_short} bei #{id} {title}",
        "approval_body": (
            "Hallo {name},\n\n{actor} möchte bei #{id} {title} {change}.\n"
            "Grund: {reason}\n\nDafür brauche ich Dein OK, weil {why_tier}.\n\n"
            "Hier kannst Du es Dir ansehen und entscheiden: {url}\n\n"
            "Der Link gilt bis {expires}. Ändert sich die Aufgabe vorher, frage ich einfach "
            "neu. Danke! 💬"
        ),
        "why_high": "es einen Kundentermin betrifft oder wer die Aufgabe verantwortet",
        "why_medium": "es den Plan für Deine Aufgabe ändert",
        "pending_comment": "⏳ Vorschlag: {change}. Wartet auf die Bestätigung von {names}.",
        "approved_comment": "✅ Freigegeben von {name}.",
        "declined_comment": (
            "🙅 {name} hat sich dagegen entschieden: {change}. Nichts wurde geändert."
        ),
        "howto_subject": "🎉 #{id} ist erledigt. Wie hast Du es gelöst?",
        "howto_body": (
            "Hallo {name},\n\nstark, dass #{id} {title} erledigt ist!\n\n"
            "Magst Du mit ein, zwei Sätzen antworten, wie Du es gelöst hast? Zum Beispiel: "
            "Was war die Ursache, und was hat geholfen?\n\n"
            "Ich mache daraus ein kurzes How-to im Ticket (auf {ticket_language}), damit die "
            "Nächsten es finden. Formatierung brauchst Du nicht, eine kurze Notiz reicht "
            "völlig.\n\nDanke! 🙏"
        ),
        "howto_asked_comment": "📝 {names} um ein kurzes How-to gebeten.",
        "ack_howto": "Danke, {name}! Ich habe es als How-to zu #{id} hinzugefügt: {url}",
        "ack_note": "Danke, {name}! Ich habe Deine Notiz zu #{id} hinzugefügt: {url}",
        "ack_scope": (
            "Danke, {name}! Das klingt nach einer neuen Anforderung, deshalb habe ich es an "
            "{leads} weitergegeben, damit vor dem Start entschieden wird. Ich melde mich."
        ),
        "ack_unknown_task": (
            "Hallo {name}, danke für Deine Nachricht! Ich konnte nicht erkennen, um welche "
            "Aufgabe es geht. Magst Du auf eine meiner Aufgaben-Mails antworten oder die "
            "Nummer nennen, z. B. #142?"
        ),
        "scope_lead_subject": "💡 Möglicher neuer Umfang von {requester}",
        "scope_lead_body": (
            "Hallo {name},\n\n{requester} hat zu #{id} {title} geschrieben:\n\n> {quote}\n\n"
            "Das sieht nach neuem Umfang aus, deshalb habe ich dafür noch keine Arbeit "
            "angelegt. Formale Änderungsanträge mit Auswirkungsschätzung kommen bald (#50). "
            "Magst Du bis dahin entscheiden, wie es weitergeht?\n\nDanke! 💬"
        ),
        "onboarding_subject": "👋 Hallo {name}, ich bin der Projekt-Assistent Deines Teams",
        "onboarding_body": (
            "Hallo {name},\n\n"
            "ich bin agent-pm, der Projekt-Assistent, den Dein Team für {project} eingerichtet "
            'hat. Ich helfe beim Kleinkram: Briefings, Erinnerungen, und aus "so habe ich es '
            'gelöst" ein How-to im Ticket machen.\n\n'
            "Was ich über Dich verwende:\n"
            "  • Deinen Namen, {channels} und Deine Sprache ({language}) aus der Team-Datei\n"
            "  • die Aufgaben, die Dir in {tracker} zugewiesen sind\n"
            "  • die Nachrichten, die Du mir schickst, damit ich sie der richtigen Aufgabe "
            "zuordnen kann\n\n"
            "Was ich nicht tue:\n"
            "  • keine Bewertungen, Ranglisten oder Produktivitätszahlen über Dich\n"
            "  • keine Historie über Dich; ich schaue nur auf die Aufgaben, wie sie gerade sind\n"
            "  • kein Erraten Deiner Stimmung aus Nachrichten\n"
            "  • Nachrichten verarbeitet ein Modell auf unseren eigenen Servern ({llm})\n\n"
            "Dein Briefing: {brief}.\n"
            "Möchtest Du etwas ändern oder abschalten? Antworte einfach oder frag {leads}.\n"
            "Details: {doc}\n\nSchön, Dich kennenzulernen! 🙌"
        ),
        "onboarding_no_brief": "vorerst keins",
        "reply_subject": "Re: #{id} {title}",
        "status_due": "den Termin von {old} auf {new} verschieben",
        "status_due_short": "neuer Termin",
        "assign": "die Aufgabe von {old} an {new} übergeben",
        "assign_short": "neue Verantwortung",
        "status": "den Status auf {new} setzen",
        "status_short": "Statuswechsel",
        "estimate": "die Schätzung auf {new} ändern",
        "estimate_short": "neue Schätzung",
        "labels": "die Labels anpassen",
        "nobody": "niemand",
    },
}


def texts(lang: str) -> dict[str, str]:
    code = lang.split("-")[0]
    return TEXTS[code] if code in TEXTS else TEXTS["en"]


def language_name(code: str, in_lang: str) -> str:
    names = LANGUAGE_NAMES.get(in_lang.split("-")[0], LANGUAGE_NAMES["en"])
    return names.get(code.split("-")[0], code)


def describe_patch(task: Task, patch: TaskPatch, lang: str) -> tuple[str, str]:
    """(long description, short label) of a patch, e.g. ('move the due date …', 'new due date')."""
    t = texts(lang)
    from agentic_pm.adapters._text import format_hours

    parts: list[tuple[str, str]] = []
    if patch.due is not None and patch.due != task.due:
        parts.append(
            (t["status_due"].format(old=task.due or "-", new=patch.due), t["status_due_short"])
        )
    if patch.assignees is not None and sorted(patch.assignees) != sorted(task.assignees):
        parts.append(
            (
                t["assign"].format(
                    old=", ".join(task.assignees) or t["nobody"],
                    new=", ".join(patch.assignees) or t["nobody"],
                ),
                t["assign_short"],
            )
        )
    if patch.status is not None and patch.status != task.status:
        parts.append((t["status"].format(new=patch.status.value), t["status_short"]))
    if patch.estimate_hours is not None and patch.estimate_hours != task.estimate_hours:
        parts.append(
            (t["estimate"].format(new=format_hours(patch.estimate_hours)), t["estimate_short"])
        )
    if not parts:
        parts.append((t["labels"], t["labels"]))
    return "; ".join(p[0] for p in parts), parts[0][1]


def render(lang: str, key: str, **kw: Any) -> str:
    return texts(lang)[key].format(**kw)


CHANNEL_LABELS = {
    "en": {"email": "email", "phone": "phone number", "whatsapp": "WhatsApp", "chat": "chat"},
    "de": {"email": "E-Mail", "phone": "Telefonnummer", "whatsapp": "WhatsApp", "chat": "Chat"},
}


def tracker_name(key: str) -> str:
    from agentic_pm.adapters.catalog import load_catalog

    entry = load_catalog().get(key)
    return entry.name if entry else key


DOC_URL = "https://github.com/Wieshof/agentic-pm/blob/main/docs/{path}people-data.md"


def onboarding(cfg: TeamConfig, handle: str) -> tuple[str, str]:
    """(subject, text) of the friendly first message to a person (ADR-0004 transparency)."""
    person = cfg.people[handle]
    lang = person.language
    t = texts(lang)
    labels = CHANNEL_LABELS.get(lang.split("-")[0], CHANNEL_LABELS["en"])
    channels = ", ".join(labels[k] for k, v in person.channels.model_dump().items() if v)
    brief = t["onboarding_no_brief"]
    if person.brief:
        when = person.brief.when or cfg.cadence.morning_triage or "-"
        brief = f"{person.brief.format.value} ({when}, {cfg.project.timezone})"
    llm = cfg.llm.model
    names = ", ".join(cfg.display_name(h) for h in cfg.project.leads)
    de = lang.split("-")[0] == "de"
    return (
        t["onboarding_subject"].format(name=cfg.display_name(handle)),
        t["onboarding_body"].format(
            name=cfg.display_name(handle),
            project=cfg.project.repo,
            channels=channels,
            language=language_name(lang, lang),
            tracker=tracker_name(cfg.project.tracker),
            llm=llm,
            brief=brief,
            leads=names,
            doc=DOC_URL.format(path="de/" if de else ""),
        ),
    )

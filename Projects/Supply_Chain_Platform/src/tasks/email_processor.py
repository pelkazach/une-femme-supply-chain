"""Celery tasks for email processing and classification.

This module provides tasks for:
- Fetching new emails from Gmail
- Classifying emails using Ollama LLM
- Storing classification results in the database
- Queuing attachments for OCR processing
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.celery_app import celery_app
from src.config import settings
from src.database import get_async_database_url
from src.models.email_classification import EmailClassification
from src.services.email_classifier import (
    ClassificationError,
    ClassificationResult,
    OllamaError,
    classify_email_with_fallback,
)
from src.services.gmail import (
    EmailMessage,
    GmailAPIError,
    GmailAuthError,
    GmailClient,
)

logger = logging.getLogger(__name__)

# Processing latency target (15 seconds per email)
MAX_PROCESSING_TIME_MS = 15000


async def get_processed_message_ids(
    session: AsyncSession,
    message_ids: list[str],
) -> set[str]:
    """Get set of message IDs that have already been processed.

    Args:
        session: Database session
        message_ids: List of message IDs to check

    Returns:
        Set of message IDs that exist in the database
    """
    if not message_ids:
        return set()

    result = await session.execute(
        select(EmailClassification.message_id).where(
            EmailClassification.message_id.in_(message_ids)
        )
    )
    return {row[0] for row in result}


async def store_classification(
    session: AsyncSession,
    email: EmailMessage,
    classification: ClassificationResult,
    processing_time_ms: int,
    ollama_used: bool,
) -> EmailClassification:
    """Store email classification result in the database.

    Args:
        session: Database session
        email: The email message that was classified
        classification: The classification result
        processing_time_ms: Time taken to classify in milliseconds
        ollama_used: Whether Ollama was used (vs rule-based fallback)

    Returns:
        The created EmailClassification record
    """
    # Serialize attachment names to JSON
    attachment_names = json.dumps([att.filename for att in email.attachments])

    record = EmailClassification(
        message_id=email.message_id,
        thread_id=email.thread_id,
        subject=email.subject[:1000] if email.subject else "",
        sender=email.sender[:500] if email.sender else "",
        recipient=email.to[:500] if email.to else "",
        received_at=email.date,
        category=classification.category.value,
        confidence=classification.confidence,
        reasoning=classification.reasoning,
        needs_review=classification.needs_review,
        has_attachments=len(email.attachments) > 0,
        attachment_names=attachment_names,
        processing_time_ms=processing_time_ms,
        ollama_used=ollama_used,
    )
    session.add(record)
    return record


async def process_single_email(
    email: EmailMessage,
) -> tuple[ClassificationResult, int, bool]:
    """Process and classify a single email.

    Args:
        email: The email message to classify

    Returns:
        Tuple of (classification_result, processing_time_ms, ollama_used)
    """
    start_time = time.monotonic()

    # Get attachment filenames for classification
    attachment_filenames = [att.filename for att in email.attachments]

    # Classify the email using Ollama with fallback
    try:
        result = await classify_email_with_fallback(
            subject=email.subject,
            body_preview=email.body_preview,
            sender=email.sender,
            attachments=attachment_filenames,
        )
        ollama_used = True

        # Check if it fell back to rule-based
        if "Rule-based" in result.reasoning:
            ollama_used = False

    except (OllamaError, ClassificationError) as e:
        logger.error("Classification failed for email %s: %s", email.message_id, e)
        raise

    processing_time_ms = int((time.monotonic() - start_time) * 1000)

    # Log if processing took too long
    if processing_time_ms > MAX_PROCESSING_TIME_MS:
        logger.warning(
            "Email %s took %dms to classify (target: %dms)",
            email.message_id,
            processing_time_ms,
            MAX_PROCESSING_TIME_MS,
        )

    return result, processing_time_ms, ollama_used


async def _async_process_emails(
    max_emails: int = 100,
    label_ids: list[str] | None = None,
    query: str = "",
) -> dict[str, Any]:
    """Async implementation of email processing.

    Args:
        max_emails: Maximum number of emails to process per run
        label_ids: Gmail label IDs to filter (default: INBOX)
        query: Gmail search query (default: unread emails)

    Returns:
        Dictionary with processing results
    """
    start_time = datetime.now(UTC)

    # Default to INBOX and UNREAD if not specified
    if label_ids is None:
        label_ids = ["INBOX"]
    if not query:
        query = "is:unread"

    results: dict[str, Any] = {
        "status": "success",
        "started_at": start_time.isoformat(),
        "completed_at": None,
        "emails_fetched": 0,
        "emails_processed": 0,
        "emails_skipped": 0,
        "emails_failed": 0,
        "classifications": {
            "PO": 0,
            "BOL": 0,
            "INVOICE": 0,
            "GENERAL": 0,
        },
        "needs_review_count": 0,
        "avg_processing_time_ms": 0,
        "errors": [],
    }

    # Create database connection
    engine = create_async_engine(
        get_async_database_url(settings.database_url),
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    gmail_client = GmailClient()

    try:
        # Load Gmail token
        if not gmail_client.load_token():
            results["status"] = "error"
            results["errors"].append(
                "Gmail token not found. Run OAuth setup first."
            )
            logger.error("Gmail token not found - OAuth setup required")
            return results

        # Fetch message list
        message_list = gmail_client.list_messages(
            query=query,
            max_results=max_emails,
            label_ids=label_ids,
        )
        results["emails_fetched"] = len(message_list)
        logger.info("Fetched %d emails from Gmail", len(message_list))

        if not message_list:
            logger.info("No new emails to process")
            return results

        async with async_session() as session:
            # Get IDs of already processed messages
            message_ids = [msg["id"] for msg in message_list]
            processed_ids = await get_processed_message_ids(session, message_ids)
            logger.info(
                "%d of %d emails already processed",
                len(processed_ids),
                len(message_ids),
            )

            processing_times: list[int] = []

            for msg_meta in message_list:
                message_id = msg_meta["id"]

                # Skip already processed emails
                if message_id in processed_ids:
                    results["emails_skipped"] += 1
                    continue

                try:
                    # Fetch full message
                    email = gmail_client.get_message(message_id)

                    # Process and classify
                    classification, processing_time_ms, ollama_used = (
                        await process_single_email(email)
                    )

                    # Store in database
                    await store_classification(
                        session,
                        email,
                        classification,
                        processing_time_ms,
                        ollama_used,
                    )

                    # Update stats
                    results["emails_processed"] += 1
                    results["classifications"][classification.category.value] += 1
                    processing_times.append(processing_time_ms)

                    if classification.needs_review:
                        results["needs_review_count"] += 1

                    logger.info(
                        "Processed email %s: %s (confidence: %.2f, %dms)",
                        message_id,
                        classification.category.value,
                        classification.confidence,
                        processing_time_ms,
                    )

                except (GmailAPIError, OllamaError, ClassificationError) as e:
                    results["emails_failed"] += 1
                    results["errors"].append(f"Email {message_id}: {e}")
                    logger.error("Failed to process email %s: %s", message_id, e)

                except Exception as e:
                    results["emails_failed"] += 1
                    results["errors"].append(f"Email {message_id}: {e}")
                    logger.exception("Unexpected error processing email %s", message_id)

            # Commit all changes
            await session.commit()

            # Calculate average processing time
            if processing_times:
                results["avg_processing_time_ms"] = sum(processing_times) // len(
                    processing_times
                )

    except GmailAuthError as e:
        results["status"] = "error"
        results["errors"].append(f"Gmail authentication failed: {e}")
        logger.error("Gmail authentication failed: %s", e)

    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"Unexpected error: {e}")
        logger.exception("Unexpected error during email processing")

    finally:
        await engine.dispose()

    results["completed_at"] = datetime.now(UTC).isoformat()

    # Update overall status
    if results["emails_failed"] > 0 and results["emails_processed"] > 0:
        results["status"] = "partial"
    elif (
        results["emails_failed"] > 0
        and results["emails_processed"] == 0
        and results["emails_fetched"] > 0
    ):
        results["status"] = "error"

    return results


@celery_app.task(
    bind=True,
    name="src.tasks.email_processor.process_emails",
    max_retries=3,
    default_retry_delay=60,  # 1 minute
    autoretry_for=(GmailAPIError, OllamaError),
)
def process_emails(
    self: Any,
    max_emails: int = 100,
    label_ids: list[str] | None = None,
    query: str = "",
) -> dict[str, Any]:
    """Celery task to process and classify emails from Gmail.

    This task:
    1. Fetches unread emails from Gmail
    2. Skips already-processed emails
    3. Classifies each email using Ollama LLM (with rule-based fallback)
    4. Stores classification results in the database
    5. Flags low-confidence classifications for human review

    Args:
        max_emails: Maximum number of emails to process per run (default: 100)
        label_ids: Gmail label IDs to filter (default: ["INBOX"])
        query: Gmail search query (default: "is:unread")

    Returns:
        Dictionary with processing results including counts and any errors
    """
    logger.info("Starting email processing task")
    try:
        result = asyncio.run(
            _async_process_emails(
                max_emails=max_emails,
                label_ids=label_ids,
                query=query,
            )
        )
        logger.info(
            "Email processing completed: %d fetched, %d processed, "
            "%d skipped, %d failed, %d need review",
            result["emails_fetched"],
            result["emails_processed"],
            result["emails_skipped"],
            result["emails_failed"],
            result["needs_review_count"],
        )
        return result
    except Exception as e:
        logger.exception("Email processing task failed")
        raise self.retry(exc=e) from e


@celery_app.task(
    bind=True,
    name="src.tasks.email_processor.process_single_email_task",
    max_retries=3,
    default_retry_delay=30,  # 30 seconds
)
def process_single_email_task(
    self: Any,
    message_id: str,
) -> dict[str, Any]:
    """Celery task to process a single email by message ID.

    Use this for on-demand processing of specific emails.

    Args:
        message_id: Gmail message ID to process

    Returns:
        Dictionary with processing result
    """
    logger.info("Processing single email: %s", message_id)

    async def _process() -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "success",
            "message_id": message_id,
            "category": None,
            "confidence": None,
            "needs_review": None,
            "processing_time_ms": None,
            "error": None,
        }

        engine = create_async_engine(
            get_async_database_url(settings.database_url),
            pool_pre_ping=True,
        )
        async_session = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        gmail_client = GmailClient()

        try:
            if not gmail_client.load_token():
                result["status"] = "error"
                result["error"] = "Gmail token not found"
                return result

            # Check if already processed
            async with async_session() as session:
                processed_ids = await get_processed_message_ids(session, [message_id])
                if message_id in processed_ids:
                    result["status"] = "skipped"
                    result["error"] = "Already processed"
                    return result

                # Fetch and process email
                email = gmail_client.get_message(message_id)
                classification, processing_time_ms, ollama_used = (
                    await process_single_email(email)
                )

                # Store result
                await store_classification(
                    session,
                    email,
                    classification,
                    processing_time_ms,
                    ollama_used,
                )
                await session.commit()

                result["category"] = classification.category.value
                result["confidence"] = classification.confidence
                result["needs_review"] = classification.needs_review
                result["processing_time_ms"] = processing_time_ms

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.exception("Failed to process email %s", message_id)

        finally:
            await engine.dispose()

        return result

    try:
        return asyncio.run(_process())
    except Exception as e:
        logger.exception("Single email processing task failed")
        raise self.retry(exc=e) from e


async def _async_get_pending_review_count() -> int:
    """Get count of emails pending human review."""
    engine = create_async_engine(
        get_async_database_url(settings.database_url),
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with async_session() as session:
            from sqlalchemy import func

            result = await session.execute(
                select(func.count(EmailClassification.id)).where(
                    EmailClassification.needs_review == True,  # noqa: E712
                    EmailClassification.reviewed == False,  # noqa: E712
                )
            )
            return result.scalar() or 0
    finally:
        await engine.dispose()


def get_pending_review_count() -> int:
    """Get count of emails pending human review.

    Returns:
        Number of emails awaiting review
    """
    return asyncio.run(_async_get_pending_review_count())

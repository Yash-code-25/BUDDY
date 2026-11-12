import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response as ApiResponse
from rest_framework.views import APIView

from notifications import emails

from .matching import run_match_for_joiner
from .models import AuditLog, Buddy, Joiner, QuestionSet, Response, Settings

logger = logging.getLogger(__name__)


class LinkExpired(APIException):
    status_code = 410
    default_detail = "This link has expired. Please contact the COMPASS team."
    default_code = "expired"


def load_subject(kind, token):
    """Return (person, assessment code, first name) for a quiz link."""
    if kind == "joiner":
        joiner = get_object_or_404(Joiner, token=token)
        today = timezone.localdate()
        if today > joiner.date_of_joining:
            raise LinkExpired()
        # After submitting, the same link shows their buddy card, so only the quiz itself runs out.
        submitted = joiner.responses.filter(submitted_at__isnull=False).exists()
        if not submitted and joiner.quiz_link_expired(today):
            raise LinkExpired("The questions are closed. Please ask the COMPASS team to reopen them.")
        return joiner, Response.Code.JOINER, emails.first_name(joiner.name)
    if kind == "buddy":
        buddy = get_object_or_404(Buddy, token=token)
        return buddy, Response.Code.BUDDY, emails.first_name(buddy.name)
    raise ValidationError("Unknown assessment type.")


def subject_key(code):
    return "buddy" if code == Response.Code.BUDDY else "joiner"


def current_response(subject, code, question_set):
    return Response.objects.filter(
        **{subject_key(code): subject}, assessment_code=code, question_set=question_set
    ).first()


def status_of(resp):
    if resp and resp.submitted_at:
        return "submitted"
    if resp and any(a is not None for a in resp.answers()):
        return "in_progress"
    return "not_started"


class AssessmentView(APIView):
    """GET: the questions (labels only) and any saved progress."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, kind, token):
        subject, code, first_name = load_subject(kind, token)
        qs = QuestionSet.active()
        resp = current_response(subject, code, qs)
        status = status_of(resp)
        s = Settings.load()
        data = {
            "first_name": first_name,
            "status": status,
            "intro": s.joiner_intro if kind == "joiner" else s.buddy_intro,
        }
        if status == "submitted":
            return ApiResponse(data)
        data["question_set_version"] = qs.version
        data["answers"] = (
            {str(i + 1): a for i, a in enumerate(resp.answers()) if a is not None} if resp else {}
        )
        data["questions"] = [q.payload() for q in qs.questions.all()]
        return ApiResponse(data)


class AnswerView(APIView):
    """POST {question: 1-5, value: 1-5}: autosave one answer."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, kind, token):
        subject, code, _ = load_subject(kind, token)
        qs = QuestionSet.active()
        number, value = request.data.get("question"), request.data.get("value")
        valid = all(
            isinstance(x, int) and not isinstance(x, bool) and 1 <= x <= 5 for x in (number, value)
        )
        if not valid:
            raise ValidationError("question and value must be whole numbers from 1 to 5.")
        with transaction.atomic():
            resp, _ = Response.objects.get_or_create(
                **{subject_key(code): subject}, assessment_code=code, question_set=qs
            )
            if resp.submitted_at:
                raise ValidationError("This assessment has already been submitted.")
            setattr(resp, f"q{number}", value)
            resp.save(update_fields=[f"q{number}"])
            if not qs.is_locked:  # a question set is locked once anyone answers it
                QuestionSet.objects.filter(pk=qs.pk).update(is_locked=True)
        return ApiResponse({"saved": True})


class SubmitView(APIView):
    """POST: finish the assessment. Answers can no longer be edited."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, kind, token):
        subject, code, _ = load_subject(kind, token)
        qs = QuestionSet.active()
        with transaction.atomic():
            resp = current_response(subject, code, qs)
            if resp is None or any(a is None for a in resp.answers()):
                raise ValidationError("Please answer all five questions.")
            if resp.submitted_at:
                raise ValidationError("This assessment has already been submitted.")
            resp.submitted_at = timezone.now()
            resp.save(update_fields=["submitted_at"])

            needs_match = code == Response.Code.JOINER and subject.compass_status in (
                Joiner.Status.AWAITING_ASSESSMENT, Joiner.Status.MANUAL,
            )
            if needs_match:
                subject.compass_status = Joiner.Status.AWAITING_PAIRING
                subject.save(update_fields=["compass_status"])
            elif code == Response.Code.BUDDY and subject.pool_status == Buddy.PoolStatus.PAUSED:
                subject.pool_status = Buddy.PoolStatus.ACTIVE
                subject.save(update_fields=["pool_status"])

            AuditLog.record("assessment_submitted", subject, object_type=code,
                            after={"question_set_version": qs.version})

        # The joiner's submission is already saved. If matching fails, the admin can re-run it.
        if needs_match:
            try:
                run_match_for_joiner(subject)
            except Exception:
                logger.exception("Match run failed for joiner %s", subject.pk)
        return ApiResponse({"submitted": True})
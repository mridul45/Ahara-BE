import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.http import StreamingHttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from google import genai

from utilities.response import api_response
from .models import ChatMessage, ChatSession
from .serializers import (
    AskGeminiSerializer,
    ChatSessionDetailSerializer,
    ChatSessionListSerializer,
)
from .logic.ved_vyas import VedVyas
from .logic.memory import MemoryManager

logger = logging.getLogger("intelligence.views")

# ── Configuration ────────────────────────────────────────────────────
RESUMED_SESSION_CONTEXT_PAIRS = 10  # Max message pairs sent to LLM on resume


class IntelligenceViewSet(viewsets.GenericViewSet):
    """
    Intelligence ViewSet for AI-related operations.

    Endpoints:
        POST   /api/intelligence/ask/                    – Stream AI response
        POST   /api/intelligence/end-session/            – Flush working memory
        GET    /api/intelligence/sessions/               – List chat sessions
        GET    /api/intelligence/sessions/<uuid>/        – Get session detail
        DELETE /api/intelligence/sessions/<uuid>/        – Archive a session
    """

    serializer_class = AskGeminiSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = []
    throttle_classes = []

    serializer_action_classes = {
        "ask_gemini": AskGeminiSerializer,
    }
    permission_action_classes = {
        "ask_gemini": [IsAuthenticated],
        "end_session": [IsAuthenticated],
        "list_sessions": [IsAuthenticated],
        "get_session": [IsAuthenticated],
        "delete_session": [IsAuthenticated],
    }
    authentication_action_classes = {
        "ask_gemini": [JWTAuthentication],
        "end_session": [JWTAuthentication],
        "list_sessions": [JWTAuthentication],
        "get_session": [JWTAuthentication],
        "delete_session": [JWTAuthentication],
    }
    throttle_action_classes = {
        "ask_gemini": [],
        "end_session": [],
        "list_sessions": [],
        "get_session": [],
        "delete_session": [],
    }

    def initialize_request(self, request, *args, **kwargs):
        if not hasattr(self, "action"):
            action_map = getattr(self, "action_map", None)
            if action_map:
                self.action = action_map.get(request.method.lower())
        return super().initialize_request(request, *args, **kwargs)

    def get_serializer_class(self):
        return self.serializer_action_classes.get(self.action, self.serializer_class)

    def get_permissions(self):
        classes = self.permission_action_classes.get(self.action, self.permission_classes)
        return [cls() for cls in classes]

    def get_authenticators(self):
        classes = self.authentication_action_classes.get(self.action, self.authentication_classes)
        return [cls() for cls in classes]

    def get_throttles(self):
        classes = self.throttle_action_classes.get(self.action, self.throttle_classes)
        return [cls() for cls in classes]

    def get_queryset(self):
        return None

    # ═══════════════════════════════════════════════════════════════════
    # ASK — Stream AI response (existing, enhanced with session support)
    # ═══════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["post"], url_path="ask", url_name="ask_gemini")
    def ask_gemini(self, request, *args, **kwargs):
        """
        POST /api/intelligence/ask/

        Body:
        {
            "prompt": "your question",
            "think": true | false,
            "session_id": "uuid" | null      ← NEW (optional)
        }

        If ``session_id`` is provided, the session's recent messages are
        injected into the LLM context so the AI has conversation history.
        If omitted, a new ChatSession is created automatically.

        The response includes an ``X-Session-Id`` header with the session
        UUID so the client can track which session this belongs to.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prompt = serializer.validated_data["prompt"]
        think = serializer.validated_data.get("think", False)
        session_id = serializer.validated_data.get("session_id")
        api_key = settings.GEMINI_API_KEY

        if not api_key:
            return api_response(
                request,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                errors={"detail": "Gemini API key is not configured."},
            )

        # ── Resolve or create the ChatSession ────────────────────────
        session = self._resolve_session(request.user, session_id, prompt)

        # ── Build conversation history for resumed sessions ──────────
        history_context = self._build_history_context(session)

        # ── Memory context injection (3-tier system, unchanged) ──────
        system_context = MemoryManager.build_prompt_context(request.user)

        full_prompt = system_context
        if history_context:
            full_prompt += f"\n\n## Conversation History (this session)\n{history_context}"
        full_prompt += f"\n\nUser Query: {prompt}"

        try:
            client = genai.Client(api_key=api_key)
            model_name = "models/gemini-2.5-flash"

            # Pre-persist the user message so it's available immediately
            ChatMessage.objects.create(
                session=session,
                role=ChatMessage.Role.USER,
                content=prompt,
            )

            def stream_generator():
                accumulated_response = ""
                try:
                    iterations_to_run = 3 if think else 1
                    reasoner = VedVyas(
                        client=client,
                        model_name=model_name,
                        iterations=iterations_to_run,
                    )
                    stream = reasoner.generate_stream(full_prompt)

                    for chunk in stream:
                        if hasattr(chunk, "text") and chunk.text:
                            text_chunk = chunk.text
                            accumulated_response += text_chunk
                            yield text_chunk

                    # ── POST-STREAM: Persist assistant message ────────
                    if accumulated_response:
                        ChatMessage.objects.create(
                            session=session,
                            role=ChatMessage.Role.ASSISTANT,
                            content=accumulated_response,
                        )
                        # Touch session timestamp
                        session.save(update_fields=["updated_at"])

                    # ── POST-STREAM: Record in 3-tier memory (unchanged) ──
                    MemoryManager.record_interaction(
                        request.user, prompt, accumulated_response,
                    )

                except Exception as e:
                    logger.exception(
                        "intelligence.ask user=%s session=%s error=%s",
                        request.user.id, session.id, str(e),
                    )
                    yield f"\n[Streaming error] {str(e)}"

            response = StreamingHttpResponse(
                streaming_content=stream_generator(),
                content_type="text/plain; charset=utf-8",
            )
            # Tell the client which session this belongs to
            response["X-Session-Id"] = str(session.id)

            origin = request.headers.get("Origin")
            if origin:
                response["Access-Control-Allow-Origin"] = origin
                response["Access-Control-Allow-Credentials"] = "true"
                response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
                response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
                response["Access-Control-Expose-Headers"] = "X-Session-Id"

            return response

        except Exception as e:
            return api_response(
                request,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                errors={"detail": f"Failed to contact Gemini API: {str(e)}"},
            )

    # ═══════════════════════════════════════════════════════════════════
    # END SESSION — Flush working memory (existing, unchanged)
    # ═══════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["post"], url_path="end-session", url_name="end_session")
    def end_session(self, request, *args, **kwargs):
        """
        POST /api/intelligence/end-session/

        Called by the mobile app in onPause()/onDestroy() to flush
        remaining working memory and distill it into persistent storage
        before the user exits.

        No request body required.

        Response:
        {
            "flushed": true,
            "turns": 5,
            "facts_count": 3
        }
        """
        result = MemoryManager.end_session(request.user)

        return api_response(
            request,
            status_code=status.HTTP_200_OK,
            data=result,
        )

    # ═══════════════════════════════════════════════════════════════════
    # SESSIONS — CRUD for chat history
    # ═══════════════════════════════════════════════════════════════════

    @action(detail=False, methods=["get"], url_path="sessions", url_name="list_sessions")
    def list_sessions(self, request, *args, **kwargs):
        """
        GET /api/intelligence/sessions/

        Returns a paginated list of the user's active (non-archived)
        chat sessions, ordered by most recently updated.

        Query params:
            ?page=1  (default, 20 per page)
        """
        sessions = ChatSession.objects.filter(
            user=request.user,
            is_archived=False,
        ).order_by("-updated_at")

        # Simple offset pagination
        page = int(request.query_params.get("page", 1))
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size

        page_sessions = sessions[start:end]
        total = sessions.count()

        serializer = ChatSessionListSerializer(page_sessions, many=True)

        return api_response(
            request,
            status_code=status.HTTP_200_OK,
            data=serializer.data,
            meta={
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_next": end < total,
            },
        )

    @action(
        detail=False,
        methods=["get"],
        url_path=r"sessions/(?P<session_id>[0-9a-f-]+)",
        url_name="get_session",
    )
    def get_session(self, request, session_id=None, *args, **kwargs):
        """
        GET /api/intelligence/sessions/<uuid>/

        Returns the full session with all messages, for restoring a
        conversation in the client UI.
        """
        try:
            session_uuid = uuid.UUID(session_id)
        except (ValueError, AttributeError):
            return api_response(
                request,
                status_code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": "Invalid session ID format."},
            )

        try:
            session = ChatSession.objects.get(
                id=session_uuid,
                user=request.user,
                is_archived=False,
            )
        except ChatSession.DoesNotExist:
            return api_response(
                request,
                status_code=status.HTTP_404_NOT_FOUND,
                errors={"detail": "Session not found."},
            )

        serializer = ChatSessionDetailSerializer(session)

        return api_response(
            request,
            status_code=status.HTTP_200_OK,
            data=serializer.data,
        )

    @action(
        detail=False,
        methods=["delete"],
        url_path=r"sessions/(?P<session_id>[0-9a-f-]+)/delete",
        url_name="delete_session",
    )
    def delete_session(self, request, session_id=None, *args, **kwargs):
        """
        DELETE /api/intelligence/sessions/<uuid>/delete/

        Soft-deletes (archives) a session.  The data is retained in the
        database but hidden from the user's session list.
        """
        try:
            session_uuid = uuid.UUID(session_id)
        except (ValueError, AttributeError):
            return api_response(
                request,
                status_code=status.HTTP_400_BAD_REQUEST,
                errors={"detail": "Invalid session ID format."},
            )

        updated = ChatSession.objects.filter(
            id=session_uuid,
            user=request.user,
            is_archived=False,
        ).update(is_archived=True)

        if not updated:
            return api_response(
                request,
                status_code=status.HTTP_404_NOT_FOUND,
                errors={"detail": "Session not found."},
            )

        return api_response(
            request,
            status_code=status.HTTP_200_OK,
            data={"archived": True},
            message="Session archived successfully.",
        )

    # ═══════════════════════════════════════════════════════════════════
    # Private helpers
    # ═══════════════════════════════════════════════════════════════════

    def _resolve_session(self, user, session_id, prompt: str) -> ChatSession:
        """
        Resolve an existing session or create a new one.

        If ``session_id`` is provided, validates ownership and returns it.
        Otherwise creates a fresh session with an auto-generated title.
        """
        if session_id:
            try:
                return ChatSession.objects.get(
                    id=session_id,
                    user=user,
                    is_archived=False,
                )
            except ChatSession.DoesNotExist:
                logger.warning(
                    "intelligence.ask user=%s session=%s not_found, creating new",
                    user.id, session_id,
                )

        # Create new session
        session = ChatSession(user=user)
        session.generate_title_from_message(prompt)
        session.save()

        # Enforce retention limit (archive oldest beyond 50)
        ChatSession.enforce_retention(user.id)

        return session

    @staticmethod
    def _build_history_context(session: ChatSession) -> str:
        """
        Build a conversation history string from the session's recent
        messages for injection into the LLM prompt.

        Returns an empty string for new sessions (no prior messages).
        """
        messages = (
            session.messages
            .order_by("-created_at")[:RESUMED_SESSION_CONTEXT_PAIRS * 2]
        )
        # Reverse to chronological order
        messages = list(messages)[::-1]

        if not messages:
            return ""

        lines: list[str] = []
        for msg in messages:
            role_label = "User" if msg.role == ChatMessage.Role.USER else "Assistant"
            lines.append(f"{role_label}: {msg.content}")

        return "\n".join(lines)
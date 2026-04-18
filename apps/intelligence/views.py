from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from utilities.response import api_response
from .serializers import AskGeminiSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from google import genai
from .logic.ved_vyas import VedVyas
from .logic.memory import MemoryManager


class IntelligenceViewSet(viewsets.GenericViewSet):
    """
    Intelligence ViewSet for AI-related operations.
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
    }
    authentication_action_classes = {
        "ask_gemini": [JWTAuthentication],
        "end_session": [JWTAuthentication],
    }
    throttle_action_classes = {
        "ask_gemini": [],
        "end_session": [],
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

    # ---------------------------------------------------------

    @action(detail=False, methods=["post"], url_path="ask", url_name="ask_gemini")
    def ask_gemini(self, request, *args, **kwargs):
        """
        POST /api/intelligence/ask/

        Body:
        {
            "prompt": "your question",
            "think": true | false
        }
        """

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prompt = serializer.validated_data["prompt"]
        think = serializer.validated_data.get("think", False)
        api_key = settings.GEMINI_API_KEY

        if not api_key:
            return api_response(
                request,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                errors={"detail": "Gemini API key is not configured."},
            )

        # ------------------------------------------------------------------
        # MEMORY CONTEXT INJECTION (3-tier system)
        # ------------------------------------------------------------------
        system_context = MemoryManager.build_prompt_context(request.user)
        full_prompt = f"{system_context}\n\nUser Query: {prompt}"
        # ------------------------------------------------------------------

        try:
            client = genai.Client(api_key=api_key)

            model_name = (
                "models/gemini-2.5-flash"
            )

            def stream_generator():
                accumulated_response = ""
                try:
                    # Determine iterations based on the 'think' flag
                    iterations_to_run = 3 if think else 1
                    
                    # Instantiate the RecursiveReasoner
                    reasoner = VedVyas(
                        client=client, 
                        model_name=model_name, 
                        iterations=iterations_to_run
                    )
                    
                    # Generate the stream using the reasoning class
                    stream = reasoner.generate_stream(full_prompt)

                    for chunk in stream:
                        if hasattr(chunk, "text") and chunk.text:
                            text_chunk = chunk.text
                            accumulated_response += text_chunk
                            yield text_chunk

                    # ----------------------------------------------------------
                    # POST-STREAM: Record interaction in 3-tier memory
                    # (runs after user has received the full response)
                    # ----------------------------------------------------------
                    MemoryManager.record_interaction(
                        request.user, prompt, accumulated_response,
                    )

                except Exception as e:
                    yield f"\n[Streaming error] {str(e)}"

            response = StreamingHttpResponse(
                streaming_content=stream_generator(),
                content_type="text/plain; charset=utf-8"
            )

            origin = request.headers.get("Origin")
            if origin:
                response["Access-Control-Allow-Origin"] = origin
                response["Access-Control-Allow-Credentials"] = "true"
                response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
                response["Access-Control-Allow-Methods"] = "POST, OPTIONS"

            return response

        except Exception as e:
            return api_response(
                request,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                errors={"detail": f"Failed to contact Gemini API: {str(e)}"},
            )

    # ---------------------------------------------------------

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
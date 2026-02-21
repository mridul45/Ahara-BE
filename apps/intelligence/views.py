from django.conf import settings
from django.core.cache import cache
from django.http import StreamingHttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from utilities.response import api_response
from .serializers import AskGeminiSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from google import genai
from .models import Memory
import json
from .logic.ved_vyas import VedVyas


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
        "ask_gemini": [IsAuthenticated]
    }
    authentication_action_classes = {
        "ask_gemini": [JWTAuthentication],
    }
    throttle_action_classes = {
        "ask_gemini": [],
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
        # MEMORY CONTEXT INJECTION
        # ------------------------------------------------------------------
        system_context = ""
        cache_key = None

        if request.user.is_authenticated:
            cache_key = f"user_memory_data_{request.user.id}"
            memory_data = cache.get(cache_key)

            if memory_data is None:
                # Not in cache, fetch from DB
                memory_obj = Memory.objects.filter(user=request.user).first()
                if not memory_obj:
                    memory_obj = Memory.objects.create(user=request.user)
                
                memory_data = memory_obj.data
                cache.set(cache_key, memory_data, timeout=3600)

            user_snapshot = memory_data.get("user_snapshot", {})
            chat_context = memory_data.get("chat", {})

            context_lines = ["User Profile Context:"]
            for key, value in user_snapshot.items():
                if value:
                    context_lines.append(f"- {key}: {value}")

            context_lines.append("\nPrevious Chat/Memory Context:")
            if chat_context:
                 context_lines.append(json.dumps(chat_context, indent=2))
            else:
                 context_lines.append("(No previous chat memory)")

            system_context = "\n".join(context_lines)
        else:
            system_context = "User is anonymous (No memory context)."

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

                    # --------------------------------------------------------------
                    # UPDATE MEMORY (Redis + DB)
                    # --------------------------------------------------------------
                    if request.user.is_authenticated and cache_key:
                        current_mem_data = cache.get(cache_key)
                        if current_mem_data is None:
                            mem_obj = Memory.objects.filter(user=request.user).first()
                            current_mem_data = mem_obj.data if mem_obj else {}

                        chat_history = current_mem_data.get("chat", [])
                        if isinstance(chat_history, dict):
                            chat_history = []

                        chat_history.append({"role": "user", "content": prompt})
                        chat_history.append({"role": "model", "content": accumulated_response})

                        current_mem_data["chat"] = chat_history

                        cache.set(cache_key, current_mem_data, timeout=3600)
                        Memory.objects.filter(user=request.user).update(data=current_mem_data)

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
from rest_framework import serializers

from .models import ChatMessage, ChatSession


# ═════════════════════════════════════════════════════════════════════════
# Ask / Streaming
# ═════════════════════════════════════════════════════════════════════════

class AskGeminiSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=True, allow_blank=False)
    think = serializers.BooleanField(required=False, default=False)
    session_id = serializers.UUIDField(required=False, allow_null=True, default=None)


# ═════════════════════════════════════════════════════════════════════════
# Chat History — Sessions
# ═════════════════════════════════════════════════════════════════════════

class ChatSessionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the session sidebar.

    Returns just enough data to render a list item: title, preview of the
    last message, message count, and timestamps.
    """

    preview = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "title",
            "preview",
            "message_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_preview(self, obj: ChatSession) -> str:
        """Return a truncated preview of the last message in this session."""
        last_msg = obj.messages.order_by("-created_at").values_list("content", flat=True).first()
        if not last_msg:
            return ""
        return last_msg[:80].replace("\n", " ")

    def get_message_count(self, obj: ChatSession) -> int:
        return obj.messages.count()


class ChatSessionDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for loading a specific session with all its messages.
    Used when the user taps a session in the sidebar to resume it.
    """

    messages = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "title",
            "messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_messages(self, obj: ChatSession) -> list[dict]:
        msgs = obj.messages.order_by("created_at")
        return ChatMessageSerializer(msgs, many=True).data


# ═════════════════════════════════════════════════════════════════════════
# Chat History — Messages
# ═════════════════════════════════════════════════════════════════════════

class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for individual chat messages."""

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "role",
            "content",
            "created_at",
        ]
        read_only_fields = fields


# ═════════════════════════════════════════════════════════════════════════
# Model Memory — User-facing memory inspection & editing
# ═════════════════════════════════════════════════════════════════════════

class MemoryUpdateSerializer(serializers.Serializer):
    """
    Validates PATCH /api/intelligence/memory/ requests.

    Supported actions:
        update   — Edit a fact.  Requires category, index, fact.
        delete   — Remove a fact.  Requires category, index.
        clear_all — Wipe the entire long-term memory profile.
    """

    ACTION_CHOICES = ("update", "delete", "clear_all")
    VALID_CATEGORIES = ("health", "diet", "goals", "lifestyle", "preferences")

    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    category = serializers.ChoiceField(choices=VALID_CATEGORIES, required=False)
    index = serializers.IntegerField(min_value=0, required=False)
    fact = serializers.CharField(max_length=500, required=False)

    def validate(self, attrs):
        action = attrs.get("action")

        if action == "update":
            if "category" not in attrs or "index" not in attrs or "fact" not in attrs:
                raise serializers.ValidationError(
                    "action='update' requires 'category', 'index', and 'fact'."
                )

        elif action == "delete":
            if "category" not in attrs or "index" not in attrs:
                raise serializers.ValidationError(
                    "action='delete' requires 'category' and 'index'."
                )

        # clear_all needs no extra fields
        return attrs
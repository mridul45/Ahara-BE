from rest_framework import serializers

class AskGeminiSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=True, allow_blank=False)
    think = serializers.BooleanField(required=False, default=False)
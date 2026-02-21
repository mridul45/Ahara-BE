from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.test import TestCase

class IntelligenceViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Router is likely registered as 'intelligence' basename.
        # Action url_name is 'ask_gemini'.
        # app_name is 'intelligence'.
        # So likely 'intelligence:intelligence-ask_gemini'
        self.url = reverse('intelligence:intelligence-ask_gemini')

    @patch('apps.intelligence.views.genai.Client')
    def test_ask_gemini_streaming(self, mock_client_class):
        # We need to mock settings, but we can't easily patch settings using decorator if it's imported in views.
        # But in views.py it uses `settings.GEMINI_API_KEY`.
        # We can use @override_settings
        from django.test import override_settings
        
        with override_settings(GEMINI_API_KEY='fake_key'):
            # Mock the client instance
            mock_client = mock_client_class.return_value
            
            # Mock the streaming response
            mock_chunk1 = MagicMock()
            mock_chunk1.text = "Hello "
            mock_chunk2 = MagicMock()
            mock_chunk2.text = "World"
            
            # generate_content_stream returns an iterator
            mock_client.models.generate_content_stream.return_value = iter([mock_chunk1, mock_chunk2])

            data = {"prompt": "Hi"}
            response = self.client.post(self.url, data, format='json')

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if it is a streaming response
            self.assertTrue(response.streaming)
            
            # Consuming the stream to verify content
            content = b"".join(response.streaming_content).decode('utf-8')
            self.assertEqual(content, "Hello World")
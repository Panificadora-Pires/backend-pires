import requests
from django.contrib.auth import get_user_model
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class CustomGoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        access_token = request.data.get('access_token')
        if not access_token:
            return Response({'error': 'Access token is required'}, status=400)

        google_user_info_url = 'https://www.googleapis.com/oauth2/v3/userinfo'
        headers = {'Authorization': f'Bearer {access_token}'}
        google_response = requests.get(google_user_info_url, headers=headers)

        if google_response.status_code != 200:  # ruff:ignore[magic-value-comparison]
            return Response({'error': 'Invalid Google token'}, status=400)

        user_info = google_response.json()
        email = user_info.get('email')
        name = user_info.get('name', '')

        if not email:
            return Response({'error': 'Email not provided by Google'}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user = User.objects.create_user(email=email, name=name)

        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.pk,
                'email': user.email,
                'name': user.name,
                'is_staff': user.is_staff
            }
        })
